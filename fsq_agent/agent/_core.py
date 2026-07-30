# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import time
import os
import inspect
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from fsq_agent.config import Settings, load_settings
from fsq_agent.knowledge import PrivateKnowledgeLoader
from fsq_agent.models import KnowledgeBundle, PlanningError, RunEvent, RunEventSink, Task, TaskResult
from fsq_agent.observation import ExecutionLogger
from fsq_agent.providers import refresh_model_provider_session
from fsq_agent.report import ReportGenerator
from fsq_agent.skills import SkillLoader
from fsq_agent.tools import AgentToolAdapter, AgentToolRegistry, DefaultAgentToolProvider, FileOps

from fsq_agent.agent._openai_runtime import OpenAIAgentsRuntime
from fsq_agent.agent._events import RunEventEmitter
from fsq_agent.agent._verifier import Verifier


class FsqAgent:
    def __init__(
        self,
        settings: Settings,
        verifier: Verifier,
        reporter: ReportGenerator,
        knowledge_loader: PrivateKnowledgeLoader,
        skill_loader: SkillLoader,
        runtime: OpenAIAgentsRuntime,
        event_logger: ExecutionLogger | None = None,
    ) -> None:
        self.settings = settings
        self.verifier = verifier
        self.reporter = reporter
        self.knowledge_loader = knowledge_loader
        self.skill_loader = skill_loader
        self.runtime = runtime
        self.event_logger = event_logger

    @classmethod
    def from_config(cls, path: str | Path | None = None, workspace: str | Path | None = None) -> "FsqAgent":
        return cls.from_settings(load_settings(path, workspace))

    @classmethod
    def from_settings(cls, settings: Settings, harness_factory: Callable[[str], Any] | None = None) -> "FsqAgent":
        output_root = settings.output.root_dir
        knowledge = settings.agent_context.knowledge
        knowledge_root = knowledge.root_dir
        skills_dir = knowledge.skills.dir
        pre_plan_knowledge_dir = knowledge.pre_plan.dir or knowledge_root
        file_ops = FileOps(
            read_roots=[settings.cases.dir, knowledge_root, skills_dir, pre_plan_knowledge_dir, output_root],
            write_root=output_root / "artifacts",
        )
        agent_tool_provider = DefaultAgentToolProvider(
            file_ops,
            runtime_secret_settings=settings.runtime_secrets,
            local_tool_output_settings=settings.openai_agents.local_tool_output,
            runs_dir=settings.output.runs_dir,
        )
        agent_tool_adapter = AgentToolAdapter(
            AgentToolRegistry.from_providers([agent_tool_provider]),
            local_tool_output_settings=settings.openai_agents.local_tool_output,
        )
        knowledge_loader = PrivateKnowledgeLoader(knowledge_root)
        skill_loader = SkillLoader(skills_dir)
        reporter = ReportGenerator(settings.output.runs_dir, secret_values=cls._runtime_secret_values(settings))
        event_logger = ExecutionLogger(settings.output.runs_dir)
        return cls(
            settings,
            Verifier(),
            reporter,
            knowledge_loader,
            skill_loader,
            OpenAIAgentsRuntime(settings, agent_tool_adapter, harness_factory=harness_factory),
            event_logger,
        )

    @staticmethod
    def _runtime_secret_values(settings: Settings) -> tuple[str, ...]:
        values = [os.getenv(name) for name in settings.runtime_secrets.allowed_env_names]
        return tuple(sorted({value for value in values if value}, key=len, reverse=True))

    async def run(self, task: Task, event_sink: RunEventSink | None = None) -> TaskResult:
        started = time.perf_counter()
        run_id = f"{task.id}-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        emitter = RunEventEmitter(self.event_logger, event_sink)
        await emitter.emit(
            RunEvent(run_id=run_id, task_id=task.id, type="run_started", title="Run started", message=task.name)
        )
        try:
            knowledge = self.knowledge_loader.load_for_task(task)
            skills = self.skill_loader.load(self.settings.skills)
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="agent_started",
                    title="Agent context loaded",
                    message=f"Loaded {len(skills)} skills and {len(knowledge.items)} knowledge items.",
                    payload={"skill_count": len(skills), "knowledge_item_count": len(knowledge.items)},
                )
            )
            provider_refresh_session = refresh_model_provider_session(self.settings)
            provider_refresh_session.close_sync()
            task = await self._augment_goal_only_task_with_pre_plan(task, skills, run_id, emitter)
            results = await self.runtime.run_task(task, knowledge, skills, run_id, emitter.emit)
            events_path = self.event_logger.log_root / run_id / "events.jsonl" if self.event_logger else None
            run_verification_task = getattr(self.runtime, "_run_verification_task", None)
            if callable(run_verification_task):
                results.extend(await run_verification_task(task, results, run_id, events_path, emitter.emit))
            verification = await self.verifier.verify(task, results, events_path=events_path)
            report = self.reporter.generate(run_id, task, results, verification)
            duration_ms = int((time.perf_counter() - started) * 1000)
            result = TaskResult(
                task_id=task.id,
                status=verification.status,
                steps=results,
                verification=verification,
                report=report,
                duration_ms=duration_ms,
            )
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="run_completed",
                    title="Run completed",
                    message=verification.summary,
                    duration_ms=duration_ms,
                    payload={"status": verification.status, "report_path": str(report.path)},
                )
            )
            return result
        except BaseException as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            message = str(exc) or exc.__class__.__name__
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="run_failed",
                    title="Run failed",
                    message=message,
                    duration_ms=duration_ms,
                    payload={"exception_type": exc.__class__.__name__},
                )
            )
            raise

    def _load_pre_plan_knowledge(self) -> KnowledgeBundle:
        items: dict[str, str] = {}
        knowledge = self.settings.agent_context.knowledge
        project_path = knowledge.root_dir / "project.md"
        if project_path.exists():
            items["project.md"] = project_path.read_text(encoding="utf-8")

        pre_plan_dir = knowledge.pre_plan.dir or knowledge.root_dir
        index_path = pre_plan_dir / "index.md"
        if index_path.exists():
            items["index.md"] = index_path.read_text(encoding="utf-8")
        return KnowledgeBundle(items=items)

    async def _augment_goal_only_task_with_pre_plan(
        self,
        task: Task,
        skills: list[object],
        run_id: str,
        emitter: RunEventEmitter,
    ) -> Task:
        if task.key_actions and self._usable_text(task.verification_goal):
            return task

        reference_type, reference_text = self._planning_reference_for_task(task)
        pre_plan = await self._run_pre_plan(reference_type, reference_text, skills, run_id, emitter)
        generated_key_actions = [
            f"Key action {index}: {action.action.strip()}"
            for index, action in enumerate(pre_plan.key_actions, start=1)
            if action.action.strip()
        ]
        key_actions = list(task.key_actions) or generated_key_actions
        verification_goal = pre_plan.verification_goal.strip()
        payload = {
            "key_action_count": len(key_actions),
            "verification_goal_present": bool(verification_goal),
            "relevant_page_ids": pre_plan.relevant_page_ids,
            "warnings": pre_plan.warnings,
        }
        if not key_actions:
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="planning_update",
                    title="Goal pre-plan produced no key actions",
                    message="Pre-plan did not produce a useful key-action chain.",
                    payload=payload,
                )
            )
            raise PlanningError("Goal pre-plan did not produce useful key actions.", context=payload)
        if not verification_goal:
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="planning_update",
                    title="Goal pre-plan produced no verification goal",
                    message="Pre-plan did not produce a usable final verification goal.",
                    payload=payload,
                )
            )
            raise PlanningError("Goal pre-plan did not produce a usable verification goal.", context=payload)

        await emitter.emit(
            RunEvent(
                run_id=run_id,
                task_id=task.id,
                type="planning_update",
                title="Goal pre-plan injected",
                message=pre_plan.summary or f"Generated {len(key_actions)} key actions and one verification goal.",
                payload=payload,
            )
        )
        return task.model_copy(update={"key_actions": key_actions, "verification_goal": verification_goal})

    async def _run_pre_plan(
        self,
        reference_type: str,
        reference_text: str,
        skills: list[object],
        run_id: str,
        emitter: RunEventEmitter,
    ):
        knowledge = self._load_pre_plan_knowledge()
        signature = inspect.signature(self.runtime.run_pre_plan)
        accepts_reference_type = "reference_type" in signature.parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
        )
        if accepts_reference_type:
            return await self.runtime.run_pre_plan(
                reference_text,
                knowledge,
                skills,
                run_id,
                emitter.emit,
                reference_type=reference_type,
            )
        return await self.runtime.run_pre_plan(reference_text, knowledge, skills, run_id, emitter.emit)

    def _planning_reference_for_task(self, task: Task) -> tuple[str, str]:
        if task.planning_reference_text and task.planning_reference_text.strip():
            return task.planning_reference_kind or "unknown", task.planning_reference_text.strip()
        return "unknown", self._goal_text_for_task(task)

    def _goal_text_for_task(self, task: Task) -> str:
        if task.verification_goal and task.verification_goal.startswith("Goal completed: "):
            return task.verification_goal.removeprefix("Goal completed: ").strip()
        return task.name if task.name and task.name != "Task" else task.description

    def _usable_text(self, value: str | None) -> bool:
        return bool(value and value.strip())
