# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import inspect
import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fsq_agent._capability_bootstrap import build_capability_registry
from fsq_agent.agent._harness_tools import HarnessToolAdapter
from fsq_agent.agent._pre_plan import (
    PRE_PLAN_AGENT_INSTRUCTIONS,
    ReadKnowledgeIndexArgs,
    ReadKnowledgePageArgs,
    build_pre_plan_input,
    page_file_from_index,
    safe_page_relative_path,
)
from fsq_agent.agent._prompt import PromptModelBuilder, PromptRenderer
from fsq_agent.agent._structured_output import coerce_agent_final_output, coerce_string_list, serialize_agent_final_output
from fsq_agent.agent._verification_task import VERIFICATION_AGENT_INSTRUCTIONS, VerificationEvidenceBuilder
from fsq_agent.config import Settings, validate_runtime_settings
from fsq_agent.core import (
    ArtifactStore,
    HarnessFactory,
    HarnessInterface,
    RuntimeSecretStore,
)
from fsq_agent.models import AgentFinalOutput, ConfigurationError, GoalPrePlan, KnowledgeBundle, PlanningError, RunEvent, RunEventSink, SkillBundle, StepResult, Task
from fsq_agent.providers import build_ai_assertion_evaluator, build_model_provider_session
from fsq_agent.tools import AgentToolAdapter, ToolArtifactStore

_RUNTIME_TOOL_NAMES = {
    "read_knowledge_index",
    "read_knowledge_page",
}


def _sdk_failure_metadata(exc: BaseException) -> dict[str, str]:
    message = str(exc)
    normalized = message.lower()
    if "response.incomplete" in normalized and "content_filter" in normalized:
        return {
            "failure_category": "provider_content_filter",
            "failure_reason": "content_filter",
            "failure_summary": "OpenAI Agents SDK run ended with an incomplete provider response due to content filtering.",
        }
    if "response.incomplete" in normalized or "status=incomplete" in normalized:
        return {
            "failure_category": "provider_response_incomplete",
            "failure_reason": "incomplete",
            "failure_summary": "OpenAI Agents SDK run ended with an incomplete provider response.",
        }
    return {
        "failure_category": "sdk_error",
        "failure_reason": "sdk_error",
        "failure_summary": "OpenAI Agents SDK run failed before producing structured verification output.",
    }


class _RecentToolOutputInputFilter:
    def __init__(
        self,
        sdk_filter: Any | None,
        recent_tool_outputs: int,
        max_output_chars: int,
        preview_chars: int,
        trimmable_tools: set[str] | None,
        artifact_store: ToolArtifactStore | None,
    ) -> None:
        self.sdk_filter = sdk_filter
        self.recent_tool_outputs = recent_tool_outputs
        self.max_output_chars = max_output_chars
        self.preview_chars = preview_chars
        self.trimmable_tools = trimmable_tools
        self.artifact_store = artifact_store
        self.artifact_paths_by_call_id: dict[str, str] = {}

    def __call__(self, data: Any) -> Any:
        from agents.run_config import ModelInputData

        model_data = self.sdk_filter(data) if self.sdk_filter else data.model_data
        items = model_data.input
        if not items or self.recent_tool_outputs < 0:
            return model_data

        call_id_to_names = self._call_id_to_names(items)
        output_indices = [index for index, item in enumerate(items) if isinstance(item, dict) and item.get("type") == "function_call_output"]
        protected = set(output_indices[-self.recent_tool_outputs :]) if self.recent_tool_outputs else set()
        new_items: list[Any] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict) or item.get("type") != "function_call_output":
                new_items.append(item)
                continue
            tool_names = call_id_to_names.get(str(item.get("call_id") or item.get("id") or ""), set())
            output = item.get("output", "")
            output_text = output if isinstance(output, str) else str(output)
            is_sensitive = self._is_sensitive_tool_output(output_text)
            artifact_path = self._artifact_path_for(item, tool_names, output_text)
            if index in protected and len(output_text) <= self.max_output_chars:
                new_items.append(item)
                continue
            if is_sensitive:
                trimmed_item = dict(item)
                display_name = next(iter(tool_names), "tool")
                trimmed_item["output"] = f"[Sensitive historical {display_name} output omitted.]"
                new_items.append(trimmed_item)
                continue
            if self.trimmable_tools and not tool_names.intersection(self.trimmable_tools):
                new_items.append(item)
                continue
            if len(output_text) <= self.max_output_chars:
                new_items.append(item)
                continue
            trimmed_item = dict(item)
            display_name = next(iter(tool_names), "tool")
            preview = output_text[: self.preview_chars]
            artifact_line = f" Artifact path: {artifact_path}." if artifact_path else ""
            trimmed_item["output"] = f"[Trimmed historical {display_name} output: {len(output_text)} chars, preview follows].{artifact_line}\n{preview}..."
            new_items.append(trimmed_item)
        return ModelInputData(input=new_items, instructions=model_data.instructions)

    def _call_id_to_names(self, items: list[Any]) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = {}
        for item in items:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            call_id = str(item.get("call_id") or item.get("id") or "")
            if not call_id:
                continue
            names = {str(value) for value in (item.get("name"), item.get("tool_name")) if value}
            mapping[call_id] = names
        return mapping

    def _artifact_path_for(self, item: dict[str, Any], tool_names: set[str], output_text: str) -> str | None:
        if self._is_sensitive_tool_output(output_text):
            return None
        if not self.artifact_store:
            return None
        call_id = str(item.get("call_id") or item.get("id") or "")
        if call_id in self.artifact_paths_by_call_id:
            return self.artifact_paths_by_call_id[call_id]
        tool_name = next(iter(tool_names), "sdk_tool")
        path = self.artifact_store.write(tool_name, output_text, {"source": "model_input_filter", "call_id": call_id})
        if not path:
            return None
        artifact_path = str(path)
        if call_id:
            self.artifact_paths_by_call_id[call_id] = artifact_path
        return artifact_path

    def _is_sensitive_tool_output(self, output_text: str) -> bool:
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError:
            return False
        return self._has_sensitive_marker(payload)

    def _has_sensitive_marker(self, value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("sensitive") is True:
                return True
            return any(self._has_sensitive_marker(item) for item in value.values())
        if isinstance(value, list):
            return any(self._has_sensitive_marker(item) for item in value)
        return False


class OpenAIAgentsRuntime:
    def __init__(
        self,
        settings: Settings,
        tool_factory: AgentToolAdapter,
        harness_factory: Callable[[str], HarnessInterface] | None = None,
    ) -> None:
        self.settings = settings
        self.tool_factory = tool_factory
        self.harness_factory = harness_factory
        self._agent_tool_names = self._discover_agent_tool_names(tool_factory)
        self._harness_tool_names: set[str] = set()
        self._harness_tool_schemas: dict[str, Any] = {}
        self._stream_tool_calls: dict[tuple[str, str, str], dict[str, Any]] = {}

    def _discover_agent_tool_names(self, tool_factory: AgentToolAdapter) -> set[str]:
        registry = getattr(tool_factory, "registry", None)
        list_tools = getattr(registry, "list_tools", None)
        if callable(list_tools):
            return {definition.name for definition in list_tools()}
        return set()

    def _agent_tool_providers(self) -> list[Any] | None:
        registry = getattr(self.tool_factory, "registry", None)
        list_providers = getattr(registry, "list_providers", None)
        if callable(list_providers):
            return list(list_providers())
        return None

    async def run_task(
        self,
        task: Task,
        knowledge: KnowledgeBundle,
        skills: list[SkillBundle],
        run_id: str,
        event_sink: RunEventSink | None = None,
    ) -> list[StepResult]:
        validate_runtime_settings(self.settings)
        started = time.perf_counter()
        try:
            from agents import Agent, FunctionTool, OpenAIProvider, RunConfig, Runner, set_tracing_disabled
            from agents.extensions import ToolOutputTrimmer
            from agents.model_settings import ModelSettings
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ConfigurationError("openai-agents and openai packages are required when SDK runtime is enabled.") from exc

        provider_session = None
        result = None
        try:
            await self._emit(
                event_sink,
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="planning_update",
                    title="Runtime startup started",
                    message="Preparing provider, harness, tools, and SDK agent for main execution.",
                    payload={"platform": self.settings.harness.platform},
                ),
            )
            set_tracing_disabled(self._sdk_tracing_disabled())
            await self._emit(
                event_sink,
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="planning_update",
                    title="Provider setup started",
                    message="Creating the configured model provider session.",
                    payload={"provider": self.settings.openai_agents.provider, "model": self.settings.openai_agents.model},
                ),
            )
            provider_session = build_model_provider_session(self.settings)
            provider = provider_session.create_agents_provider(openai_provider_type=OpenAIProvider, async_openai_type=AsyncOpenAI)
            await self._emit(
                event_sink,
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="planning_update",
                    title="Provider setup completed",
                    message="Model provider session is ready for the main execution agent.",
                    payload={"provider": self.settings.openai_agents.provider, "model": self.settings.openai_agents.model},
                ),
            )
            try:
                await self._emit(
                    event_sink,
                    RunEvent(
                        run_id=run_id,
                        task_id=task.id,
                        type="planning_update",
                        title="Harness setup started",
                        message="Constructing the platform harness for main execution.",
                        payload=self._harness_setup_payload(),
                    ),
                )
                harness = await self._build_harness_with_timeout(run_id)
                await self._emit(
                    event_sink,
                    RunEvent(
                        run_id=run_id,
                        task_id=task.id,
                        type="planning_update",
                        title="Harness setup completed",
                        message="Platform harness is ready for tool schema discovery.",
                        payload=self._harness_setup_payload(harness),
                    ),
                )
                await self._emit(
                    event_sink,
                    RunEvent(
                        run_id=run_id,
                        task_id=task.id,
                        type="planning_update",
                        title="Tool setup started",
                        message="Building AgentTools and platform tools for the SDK agent.",
                    ),
                )
                harness_adapter = HarnessToolAdapter(
                    harness,
                    run_id=run_id,
                    reserved_tool_names={*self._agent_tool_names, *_RUNTIME_TOOL_NAMES},
                    post_action_delay_seconds=self.settings.execution.post_action_delay_seconds,
                    runtime_secret_store=self._runtime_secret_store(),
                    platform=self.settings.harness.platform,
                )
                self._harness_tool_names = harness_adapter.tool_names
                self._harness_tool_schemas = harness_adapter.schemas_by_name
                agent_tools = self.tool_factory.build_tools(
                    FunctionTool,
                    run_id=run_id,
                    task_id=task.id,
                    event_sink=None,
                    runner_invoker=harness_adapter.run_step_with_capability_result,
                )
                harness_tools = harness_adapter.build_tools(FunctionTool)
                await self._emit(
                    event_sink,
                    RunEvent(
                        run_id=run_id,
                        task_id=task.id,
                        type="planning_update",
                        title="Tool setup completed",
                        message="SDK tools are ready for main execution.",
                        payload={"agent_tool_count": len(agent_tools), "platform_tool_count": len(harness_tools)},
                    ),
                )
                agent = Agent(
                    name=self.settings.agent.name,
                    model=self.settings.openai_agents.model,
                    model_settings=ModelSettings(reasoning={"effort": "medium"}, verbosity="medium"),
                    instructions=self._build_instructions(knowledge, skills),
                    tools=[*agent_tools, *harness_tools],
                    output_type=AgentFinalOutput,
                )
                await self._emit(
                    event_sink,
                    RunEvent(
                        run_id=run_id,
                        task_id=task.id,
                        type="planning_update",
                        title="SDK agent ready",
                        message="Main execution agent is ready to start streamed planning.",
                        payload={"tool_count": len(agent_tools) + len(harness_tools)},
                    ),
                )
                await self._emit(
                    event_sink,
                    RunEvent(
                        run_id=run_id,
                        task_id=task.id,
                        type="planning_started",
                        title="Planning started",
                        message="The agent is deriving success criteria and preparing the first actions.",
                    ),
                )
                result = Runner.run_streamed(
                    agent,
                    input=self._build_task_input(task),
                    max_turns=self.settings.openai_agents.max_turns,
                    run_config=self._build_run_config(RunConfig, ToolOutputTrimmer, provider, run_id),
                )
                async for event in result.stream_events():
                    run_event = self._map_stream_event(event, run_id, task.id)
                    if run_event:
                        await self._emit(event_sink, run_event)
            # SDK and provider packages raise implementation-specific exceptions that become failed steps.
            except Exception as exc:  # noqa: BLE001
                duration_ms = int((time.perf_counter() - started) * 1000)
                failure_metadata = _sdk_failure_metadata(exc)
                error_message = self._replace_secret_values(str(exc), self._runtime_secret_values())
                await self._emit(
                    event_sink,
                    RunEvent(
                        run_id=run_id,
                        task_id=task.id,
                        type="run_failed",
                        title="SDK run failed",
                        message=error_message,
                        duration_ms=duration_ms,
                        payload=failure_metadata,
                    ),
                )
                return [
                    StepResult(
                        step_id=1,
                        status="failed",
                        actual_outcome=failure_metadata["failure_summary"],
                        duration_ms=duration_ms,
                        error=error_message,
                        tool_name="openai_agents.runner",
                        tool_output=failure_metadata,
                    )
                ]
        # Runtime startup dependencies may fail with package-specific exceptions that become failed steps.
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - started) * 1000)
            failure_metadata = _sdk_failure_metadata(exc)
            error_message = self._replace_secret_values(str(exc), self._runtime_secret_values())
            await self._emit(
                event_sink,
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="run_failed",
                    title="SDK run failed",
                    message=error_message,
                    duration_ms=duration_ms,
                    payload=failure_metadata,
                ),
            )
            return [
                StepResult(
                    step_id=1,
                    status="failed",
                    actual_outcome=failure_metadata["failure_summary"],
                    duration_ms=duration_ms,
                    error=error_message,
                    tool_name="openai_agents.runner",
                    tool_output=failure_metadata,
                )
            ]
        finally:
            if provider_session is not None:
                await provider_session.close()

        duration_ms = int((time.perf_counter() - started) * 1000)
        if result is None:
            return [
                StepResult(
                    step_id=1,
                    status="failed",
                    actual_outcome="OpenAI Agents SDK run ended before producing a streamed result.",
                    duration_ms=duration_ms,
                    error="OpenAI Agents SDK run ended before producing a streamed result.",
                    tool_name="openai_agents.runner",
                )
            ]
        final_output = coerce_agent_final_output(result.final_output) or str(result.final_output)
        final_output = self._redact_runtime_secrets(final_output)
        serialized_final_output = serialize_agent_final_output(final_output)
        pre_plan_steps = self._build_pre_plan_step_results(final_output, duration_ms)
        structured_steps = pre_plan_steps
        return [
            *structured_steps,
            StepResult(
                step_id=len(structured_steps) + 1,
                status="success",
                actual_outcome=serialized_final_output,
                duration_ms=duration_ms,
                tool_name="openai_agents.runner",
                tool_output=final_output.model_dump(mode="json") if isinstance(final_output, AgentFinalOutput) else serialized_final_output,
            ),
        ]

    async def _build_harness_with_timeout(self, run_id: str) -> HarnessInterface:
        timeout_seconds = self.settings.agent.step_timeout_seconds

        loop = asyncio.get_running_loop()
        future: asyncio.Future[HarnessInterface] = loop.create_future()

        def set_result(harness: HarnessInterface) -> None:
            if not future.done():
                future.set_result(harness)

        def set_exception(exc: Exception) -> None:
            if not future.done():
                future.set_exception(exc)

        def build_harness() -> None:
            try:
                harness = self._build_harness(run_id)
            # Backend construction failures must be forwarded from the worker thread to the event loop.
            except Exception as exc:  # noqa: BLE001
                try:
                    loop.call_soon_threadsafe(set_exception, exc)
                except RuntimeError:
                    pass
            else:
                try:
                    loop.call_soon_threadsafe(set_result, harness)
                except RuntimeError:
                    pass

        threading.Thread(target=build_harness, name=f"fsq-harness-setup-{run_id}", daemon=True).start()
        try:
            return await asyncio.wait_for(future, timeout=timeout_seconds)
        except TimeoutError as exc:
            if future.done() and not future.cancelled():
                raise
            future.cancel()
            raise TimeoutError(f"Harness setup timed out after {timeout_seconds} seconds.") from exc

    def _harness_setup_payload(self, harness: HarnessInterface | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "platform": self.settings.harness.platform,
            "timeout_seconds": self.settings.agent.step_timeout_seconds,
        }
        if self.settings.harness.platform == "android":
            android = self.settings.harness.android
            payload.update(
                {
                    "backend": android.backend,
                    "app_id_configured": bool(android.app_id),
                    "serial_configured": bool(android.serial),
                }
            )
        if self.settings.harness.platform == "web":
            web = self.settings.harness.web
            payload.update(
                {
                    "backend": web.backend,
                    "channel": web.channel,
                    "browser_executable_configured": web.browser_executable_path is not None,
                    "headless": web.headless,
                    "base_url_configured": bool(web.base_url),
                    "viewport_configured": web.viewport_width is not None and web.viewport_height is not None,
                }
            )
        if self.settings.harness.platform == "windows":
            windows = self.settings.harness.windows
            payload.update(
                {
                    "backend": windows.backend,
                    "backend_kind": windows.backend_kind,
                    "app_path_configured": windows.app_path is not None,
                    "window_title_re_configured": windows.window_title_re is not None,
                }
            )
        if self.settings.harness.platform == "macos":
            macos = self.settings.harness.macos
            payload.update(
                {
                    "backend": macos.backend,
                    "appium_server_configured": macos.appium_server_url is not None,
                    "bundle_id_configured": macos.bundle_id is not None,
                    "app_path_configured": macos.app_path is not None,
                    "action_timeout_seconds": macos.action_timeout_seconds,
                    "configured_skill_names": [skill.name for skill in self.settings.skills],
                }
            )
        if harness is not None:
            payload["harness_class"] = type(harness).__name__
            driver = getattr(harness, "driver", None)
            if driver is not None:
                payload["driver_class"] = type(driver).__name__
        return payload

    async def run_pre_plan(
        self,
        reference_text: str,
        knowledge: KnowledgeBundle,
        skills: list[SkillBundle],
        run_id: str,
        event_sink: RunEventSink | None = None,
        reference_type: str = "goal",
    ) -> GoalPrePlan:
        validate_runtime_settings(self.settings)
        task_id = "pre-plan"
        started = time.perf_counter()
        try:
            from agents import Agent, FunctionTool, OpenAIProvider, RunConfig, Runner, set_tracing_disabled
            from agents.extensions import ToolOutputTrimmer
            from agents.model_settings import ModelSettings
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ConfigurationError("openai-agents and openai packages are required when SDK runtime is enabled.") from exc

        await self._emit(
            event_sink,
            RunEvent(
                run_id=run_id,
                task_id=task_id,
                type="planning_started",
                title="Pre-plan started",
                message="Generating key actions from the planning reference and page knowledge.",
            ),
        )
        set_tracing_disabled(self._sdk_tracing_disabled())
        provider_session = build_model_provider_session(self.settings)
        provider = provider_session.create_agents_provider(openai_provider_type=OpenAIProvider, async_openai_type=AsyncOpenAI)
        try:
            agent = Agent(
                name=f"{self.settings.agent.name} pre-planner",
                model=self.settings.openai_agents.model,
                model_settings=ModelSettings(reasoning={"effort": "medium"}, verbosity="medium"),
                instructions=PRE_PLAN_AGENT_INSTRUCTIONS,
                tools=self._build_pre_plan_tools(FunctionTool),
                output_type=GoalPrePlan,
            )
            result = Runner.run_streamed(
                agent,
                input=build_pre_plan_input(
                    reference_text,
                    knowledge,
                    skills,
                    reference_type=reference_type,
                    available_platform_tools=self._pre_plan_tool_summary(),
                    runtime_secret_names=list(self._runtime_secret_store().available_names()),
                    runtime_secret_warnings=list(self._runtime_secret_store().warnings()),
                ),
                max_turns=self.settings.openai_agents.max_turns,
                run_config=self._build_run_config(RunConfig, ToolOutputTrimmer, provider, run_id),
            )
            async for event in result.stream_events():
                run_event = self._map_stream_event(event, run_id, task_id)
                if run_event:
                    await self._emit(event_sink, run_event)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await self._emit(
                event_sink,
                RunEvent(
                    run_id=run_id,
                    task_id=task_id,
                    type="run_failed",
                    title="Pre-plan failed",
                    message=self._replace_secret_values(str(exc), self._runtime_secret_values()),
                    duration_ms=duration_ms,
                ),
            )
            raise PlanningError("Goal pre-plan failed before producing structured output.", context={"error": str(exc)}) from exc
        finally:
            await provider_session.close()

        pre_plan = result.final_output
        if isinstance(pre_plan, GoalPrePlan):
            return pre_plan
        try:
            if isinstance(pre_plan, str):
                return GoalPrePlan.model_validate_json(pre_plan)
            return GoalPrePlan.model_validate(pre_plan)
        except Exception as exc:
            raise PlanningError("Goal pre-plan output did not match the expected schema.") from exc

    def _build_pre_plan_tools(self, function_tool_cls: Any) -> list[Any]:
        return [
            function_tool_cls(
                name="read_knowledge_index",
                description=(
                    "Read available pre-plan knowledge entries, including project.md and the page index when present. "
                    "Use this to reload project guidance or resolve page ids before loading page details."
                ),
                params_json_schema=ReadKnowledgeIndexArgs.model_json_schema(),
                on_invoke_tool=self._read_knowledge_index_tool,
            ),
            function_tool_cls(
                name="read_knowledge_page",
                description=(
                    "Read one optional page knowledge node from the pre-plan knowledge directory by page_id or relative file path. Use this only for pages needed to continue the goal action chain."
                ),
                params_json_schema=ReadKnowledgePageArgs.model_json_schema(),
                on_invoke_tool=self._read_knowledge_page_tool,
            ),
        ]

    def _pre_plan_tool_summary(self) -> list[dict[str, Any]]:
        registry = build_capability_registry(platform=self.settings.harness.platform)
        return [
            {
                "name": capability.name,
                "alias": capability.replay.alias if capability.replay else None,
                "description": capability.description,
                "executor_kind": capability.executor_kind,
                "step_kind": capability.step_kind,
                "platform": capability.platform,
            }
            for capability in registry.snapshot().capabilities
        ]

    def _pre_plan_knowledge_dir(self) -> Path:
        knowledge = self.settings.agent_context.knowledge
        return knowledge.pre_plan.dir or knowledge.root_dir

    def _pre_plan_entry_paths(self) -> list[tuple[str, Path]]:
        knowledge = self.settings.agent_context.knowledge
        return [
            ("project.md", knowledge.root_dir / "project.md"),
            ("index.md", self._pre_plan_knowledge_dir() / "index.md"),
        ]

    async def _read_knowledge_index_tool(self, _ctx: Any, args: str) -> str:
        ReadKnowledgeIndexArgs.model_validate_json(args or "{}")
        entries: list[dict[str, str]] = []
        for entry_path, path in self._pre_plan_entry_paths():
            if not path.exists():
                continue
            try:
                entries.append({"path": entry_path, "content": path.read_text(encoding="utf-8")})
            except OSError as exc:
                return json.dumps({"ok": False, "error": str(exc), "path": entry_path}, ensure_ascii=False)
        content = "\n\n".join(f"--- {entry['path']} ---\n{entry['content']}" for entry in entries)
        path = entries[0]["path"] if entries else None
        return json.dumps({"ok": True, "path": path, "content": content, "entries": entries}, ensure_ascii=False)

    async def _read_knowledge_page_tool(self, _ctx: Any, args: str) -> str:
        parsed = ReadKnowledgePageArgs.model_validate_json(args or "{}")
        relative_path = None
        if parsed.file:
            relative_path = safe_page_relative_path(parsed.file)
        elif parsed.page_id:
            knowledge_dir = self._pre_plan_knowledge_dir()
            index_path = knowledge_dir / "index.md"
            index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
            indexed_file = page_file_from_index(index_text, parsed.page_id)
            relative_path = safe_page_relative_path(indexed_file or f"{parsed.page_id}.md")
        knowledge_dir = self._pre_plan_knowledge_dir()
        if relative_path is None:
            return json.dumps(
                {"ok": False, "error": "A safe page_id or relative page file is required.", "page_id": parsed.page_id, "file": parsed.file},
                ensure_ascii=False,
            )
        path = (knowledge_dir / relative_path).resolve()
        try:
            path.relative_to(knowledge_dir.resolve())
        except ValueError:
            return json.dumps({"ok": False, "error": "Resolved page path escaped the knowledge directory."}, ensure_ascii=False)
        if not path.exists() or not path.is_file():
            return json.dumps(
                {"ok": False, "error": "Knowledge page not found.", "page_id": parsed.page_id, "path": str(relative_path).replace("\\", "/")},
                ensure_ascii=False,
            )
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return json.dumps({"ok": False, "error": str(exc), "path": str(relative_path).replace("\\", "/")}, ensure_ascii=False)
        return json.dumps(
            {"ok": True, "page_id": parsed.page_id, "path": str(relative_path).replace("\\", "/"), "content": content},
            ensure_ascii=False,
        )

    async def _run_verification_task(
        self,
        task: Task,
        execution_results: list[StepResult],
        run_id: str,
        events_path: Any = None,
        event_sink: RunEventSink | None = None,
    ) -> list[StepResult]:
        validate_runtime_settings(self.settings)
        started = time.perf_counter()
        try:
            from agents import Agent, OpenAIProvider, RunConfig, Runner, set_tracing_disabled
            from agents.extensions import ToolOutputTrimmer
            from agents.model_settings import ModelSettings
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ConfigurationError("openai-agents and openai packages are required when SDK runtime is enabled.") from exc

        await self._emit(
            event_sink,
            RunEvent(
                run_id=run_id,
                task_id=task.id,
                type="planning_update",
                title="Verification started",
                message="Running evidence-based verifier agent over execution records and artifacts.",
            ),
        )
        evidence_input = VerificationEvidenceBuilder().build_model_input(
            task,
            execution_results,
            events_path,
        )
        evidence_input = self._replace_secret_values(evidence_input, self._runtime_secret_values())
        set_tracing_disabled(self._sdk_tracing_disabled())
        provider_session = build_model_provider_session(self.settings)
        provider = provider_session.create_agents_provider(openai_provider_type=OpenAIProvider, async_openai_type=AsyncOpenAI)
        try:
            agent = Agent(
                name=f"{self.settings.agent.name} verifier",
                model=self.settings.openai_agents.model,
                model_settings=ModelSettings(reasoning={"effort": "medium"}, verbosity="medium"),
                instructions=VERIFICATION_AGENT_INSTRUCTIONS,
                tools=[],
                output_type=AgentFinalOutput,
            )
            result = Runner.run_streamed(
                agent,
                input=evidence_input,
                max_turns=self.settings.openai_agents.max_turns,
                run_config=self._build_run_config(RunConfig, ToolOutputTrimmer, provider, run_id),
            )
            async for event in result.stream_events():
                run_event = self._map_stream_event(event, run_id, task.id)
                if run_event:
                    await self._emit(event_sink, run_event)
        # Verifier SDK/provider failures must become reportable verification step failures.
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - started) * 1000)
            return [
                StepResult(
                    step_id=len(execution_results) + 1,
                    status="failed",
                    actual_outcome="Evidence-based verifier agent failed before producing structured output.",
                    duration_ms=duration_ms,
                    error=self._replace_secret_values(str(exc), self._runtime_secret_values()),
                    tool_name="openai_agents.verifier",
                )
            ]
        finally:
            await provider_session.close()

        duration_ms = int((time.perf_counter() - started) * 1000)
        final_output = coerce_agent_final_output(result.final_output) or str(result.final_output)
        final_output = self._redact_runtime_secrets(final_output)
        serialized_final_output = serialize_agent_final_output(final_output)
        return [
            StepResult(
                step_id=len(execution_results) + 1,
                status="success",
                actual_outcome=serialized_final_output,
                duration_ms=duration_ms,
                tool_name="openai_agents.verifier",
                tool_output=final_output.model_dump(mode="json") if isinstance(final_output, AgentFinalOutput) else serialized_final_output,
            )
        ]

    async def _emit(self, event_sink: RunEventSink | None, event: RunEvent) -> None:
        if not event_sink:
            return
        result = event_sink(event)
        if inspect.isawaitable(result):
            await result

    def _sdk_tracing_disabled(self) -> bool:
        if not self.settings.openai_agents.tracing_enabled:
            return True
        export_api_key = os.getenv("OPENAI_API_KEY")
        return not bool(export_api_key and export_api_key.strip())

    def _build_run_config(self, run_config_cls: Any, tool_output_trimmer_cls: Any, provider: Any, run_id: str = "") -> Any:
        trimming = self.settings.openai_agents.context_trimming
        local_output = self.settings.openai_agents.local_tool_output
        input_filter = None
        if trimming.enabled:
            trimmable_tools = set(trimming.trimmable_tools) if trimming.trimmable_tools else None
            artifact_store = ToolArtifactStore(self.settings.output.runs_dir, run_id, local_output) if run_id and local_output.artifact_enabled else None
            sdk_filter = tool_output_trimmer_cls(
                recent_turns=trimming.recent_turns,
                max_output_chars=trimming.max_tool_output_chars,
                preview_chars=trimming.preview_chars,
                trimmable_tools=frozenset(trimmable_tools) if trimmable_tools else None,
            )
            input_filter = _RecentToolOutputInputFilter(
                sdk_filter,
                local_output.recent_full_output_count,
                trimming.max_tool_output_chars,
                trimming.preview_chars,
                trimmable_tools,
                artifact_store,
            )
        return run_config_cls(
            model_provider=provider,
            call_model_input_filter=input_filter,
            tracing_disabled=self._sdk_tracing_disabled(),
        )

    def _build_harness(self, run_id: str) -> HarnessInterface:
        if self.harness_factory is not None:
            return self.harness_factory(run_id)
        return HarnessFactory().create_harness(
            platform=self.settings.harness.platform,
            harness_settings=self.settings.harness,
            artifact_store=ArtifactStore(self.settings.output.runs_dir / run_id),
            ai_assertion_evaluator=build_ai_assertion_evaluator(self.settings),
            runtime_secret_settings=self.settings.runtime_secrets,
            app_id=self.settings.harness.android.app_id,
        )

    def _map_stream_event(self, event: Any, run_id: str, task_id: str) -> RunEvent | None:
        event_type = getattr(event, "type", "")
        if event_type == "agent_updated_stream_event":
            new_agent = getattr(event, "new_agent", None)
            agent_name = getattr(new_agent, "name", "agent")
            return RunEvent(run_id=run_id, task_id=task_id, type="agent_started", title="Agent updated", message=str(agent_name))
        if event_type != "run_item_stream_event":
            return None

        name = getattr(event, "name", "")
        item = getattr(event, "item", None)
        if name == "tool_called":
            tool_name = self._tool_name(item)
            tool_call_id = self._tool_call_id(item)
            tool_arguments = self._tool_arguments(item)
            if tool_call_id:
                self._stream_tool_calls[(run_id, task_id, tool_call_id)] = {
                    "tool_name": tool_name,
                    "tool_arguments": tool_arguments,
                }
            payload = {"tool_origin": self._tool_origin(tool_name)}
            schema = self._harness_tool_schemas.get(tool_name or "")
            if schema is not None:
                payload.update(
                    {
                        "platform": schema.platform,
                        "driver_method": schema.driver_method,
                        "fsq_action_name": schema.fsq_action_name,
                        "step_kind": schema.metadata.get("step_kind"),
                        "metadata": schema.metadata,
                    }
                )
            return RunEvent(
                run_id=run_id,
                task_id=task_id,
                type="tool_call_started",
                title="Tool call started",
                message=self._tool_call_message(item),
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                tool_arguments=tool_arguments,
                payload=payload,
            )
        if name == "tool_output":
            output = getattr(item, "output", None)
            payload = self._tool_output_payload(output)
            tool_call_id = self._tool_call_id(item)
            remembered = self._stream_tool_calls.pop((run_id, task_id, tool_call_id or ""), {})
            tool_name = payload.get("tool_name") or remembered.get("tool_name") or self._tool_name(item)
            duration_ms = payload.get("duration_ms")
            return RunEvent(
                run_id=run_id,
                task_id=task_id,
                type="tool_call_completed",
                title="Tool call completed",
                message=self._tool_output_message(item),
                tool_name=str(tool_name) if tool_name else None,
                tool_call_id=tool_call_id,
                duration_ms=duration_ms if isinstance(duration_ms, int) and duration_ms >= 0 else None,
                tool_output_preview=self._preview(output),
                payload=payload,
            )
        if name == "reasoning_item_created":
            summary = self._reasoning_summary(item)
            if not summary:
                return None
            return RunEvent(run_id=run_id, task_id=task_id, type="reasoning_summary", title="Reasoning summary", message=summary)
        if name == "message_output_created":
            message = self._message_output_text(item)
            return RunEvent(
                run_id=run_id,
                task_id=task_id,
                type="planning_update",
                title="Agent message",
                message=self._preview(message if message is not None else getattr(item, "raw_item", item)),
            )
        return None

    def _tool_name(self, item: Any) -> str | None:
        value = getattr(item, "tool_name", None)
        if value:
            return str(value)
        raw_item = getattr(item, "raw_item", None)
        if isinstance(raw_item, dict):
            return raw_item.get("name")
        return str(getattr(raw_item, "name", "")) or None

    def _tool_call_id(self, item: Any) -> str | None:
        value = getattr(item, "call_id", None)
        if value:
            return str(value)
        raw_item = getattr(item, "raw_item", None)
        if isinstance(raw_item, dict):
            return str(raw_item.get("call_id") or raw_item.get("id") or "") or None
        return str(getattr(raw_item, "call_id", None) or getattr(raw_item, "id", "")) or None

    def _tool_arguments(self, item: Any) -> dict[str, Any] | str | None:
        raw_item = getattr(item, "raw_item", None)
        if isinstance(raw_item, dict):
            return self._redact(raw_item.get("arguments") or raw_item.get("input") or raw_item)
        arguments = getattr(raw_item, "arguments", None) or getattr(raw_item, "input", None)
        return self._redact(arguments) if arguments is not None else None

    def _tool_call_message(self, item: Any) -> str:
        tool_name = self._tool_name(item) or "tool"
        return f"Calling {tool_name}."

    def _tool_output_message(self, item: Any) -> str:
        return "Tool returned output."

    def _reasoning_summary(self, item: Any) -> str | None:
        raw_item = getattr(item, "raw_item", None)
        summary = getattr(raw_item, "summary", None)
        if isinstance(summary, list) and summary:
            return self._preview(summary)
        if isinstance(summary, str) and summary:
            return self._preview(summary)
        return None

    def _message_output_text(self, item: Any) -> str | None:
        raw_item = getattr(item, "raw_item", None)
        candidates = [raw_item, item]
        for candidate in candidates:
            if isinstance(candidate, dict):
                text = candidate.get("text")
                if isinstance(text, str):
                    return text
                content = candidate.get("content")
                if isinstance(content, list):
                    text_parts = [part.get("text") for part in content if isinstance(part, dict) and isinstance(part.get("text"), str)]
                    if text_parts:
                        return "\n".join(text_parts)
                continue
            text = getattr(candidate, "text", None)
            if isinstance(text, str):
                return text
            content = getattr(candidate, "content", None)
            if isinstance(content, list):
                parts = [getattr(part, "text", None) for part in content]
                text_parts = [part for part in parts if isinstance(part, str)]
                if text_parts:
                    return "\n".join(text_parts)
        return None

    def _preview(self, value: Any, limit: int = 1000) -> str:
        text = value if isinstance(value, str) else repr(value)
        text = self._redact_sensitive_tool_output(text)
        text = self._replace_secret_values(text, self._runtime_secret_values())
        text = text.replace("\r", " ").replace("\n", " ")
        return text if len(text) <= limit else f"{text[:limit]}..."

    def _redact_sensitive_tool_output(self, text: str) -> str:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text
        redacted, changed = self._redact_sensitive_payload(payload)
        if changed:
            return json.dumps(redacted, ensure_ascii=False)
        return text

    def _redact_sensitive_payload(self, value: Any) -> tuple[Any, bool]:
        if isinstance(value, dict):
            changed = False
            redacted: dict[str, Any] = {}
            is_sensitive = value.get("sensitive") is True
            for key, item in value.items():
                if is_sensitive and key == "value":
                    redacted[key] = "***"
                    changed = changed or item != "***"
                    continue
                redacted_item, item_changed = self._redact_sensitive_payload(item)
                redacted[key] = redacted_item
                changed = changed or item_changed
            return redacted, changed
        if isinstance(value, list):
            redacted_items: list[Any] = []
            changed = False
            for item in value:
                redacted_item, item_changed = self._redact_sensitive_payload(item)
                redacted_items.append(redacted_item)
                changed = changed or item_changed
            return redacted_items, changed
        return value, False

    def _redact_runtime_secrets(self, value: Any) -> Any:
        secret_values = self._runtime_secret_values()
        if not secret_values:
            return value
        redacted = self._replace_secret_values(value, secret_values)
        if isinstance(value, AgentFinalOutput) and isinstance(redacted, dict):
            return AgentFinalOutput.model_validate(redacted)
        return redacted

    def _runtime_secret_values(self) -> tuple[str, ...]:
        values: list[str] = []
        for name in self.settings.runtime_secrets.allowed_env_names:
            raw_value = os.getenv(name)
            if raw_value:
                values.append(raw_value)
        return tuple(sorted(set(values), key=len, reverse=True))

    def _replace_secret_values(self, value: Any, secret_values: tuple[str, ...]) -> Any:
        if isinstance(value, AgentFinalOutput):
            return self._replace_secret_values(value.model_dump(mode="json"), secret_values)
        if isinstance(value, dict):
            return {key: self._replace_secret_values(item, secret_values) for key, item in value.items()}
        if isinstance(value, list):
            return [self._replace_secret_values(item, secret_values) for item in value]
        if isinstance(value, str):
            redacted = value
            for secret_value in secret_values:
                redacted = redacted.replace(secret_value, "***")
            return redacted
        return value

    def _redact(self, value: Any) -> Any:
        sensitive = ("token", "key", "secret", "password", "authorization", "cookie")
        secret_values = self._runtime_secret_values()
        if isinstance(value, dict):
            return {key: "***" if any(part in str(key).lower() for part in sensitive) else self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, str):
            return self._replace_secret_values(value, secret_values)
        return value

    def _offset_step_ids(self, steps: list[StepResult], offset: int) -> list[StepResult]:
        if offset <= 0:
            return steps
        return [step.model_copy(update={"step_id": step.step_id + offset}) for step in steps]

    def _build_pre_plan_step_results(self, final_output: AgentFinalOutput | str, duration_ms: int) -> list[StepResult]:
        payload = coerce_agent_final_output(final_output)
        if not payload:
            return []
        pre_plan = payload.pre_plan
        plan_updates = payload.plan_updates
        steps: list[StepResult] = []
        for index, item in enumerate(pre_plan, start=1):
            steps.append(self._build_pre_plan_step(index, item.model_dump(mode="json"), plan_updates, duration_ms))
        return steps

    def _build_pre_plan_step(
        self,
        fallback_step_id: int,
        item: dict[str, Any],
        plan_updates: list[str],
        duration_ms: int,
    ) -> StepResult:
        raw_step_id = item.get("step_id", fallback_step_id)
        step_id = raw_step_id if isinstance(raw_step_id, int) and raw_step_id >= 1 else fallback_step_id
        raw_status = str(item.get("status", "skipped")).lower()
        status = raw_status if raw_status in {"success", "failed", "skipped", "adjusted"} else "skipped"
        action = str(item.get("action") or "Pre-plan step")
        success_criteria = coerce_string_list(item.get("success_criteria"))
        lines = [f"Action: {action}"]
        if success_criteria:
            lines.extend(["Success criteria:", *[f"- {criterion}" for criterion in success_criteria]])
        if status == "adjusted" and plan_updates:
            lines.extend(["Plan updates:", *[f"- {update}" for update in plan_updates]])
        return StepResult(
            step_id=step_id,
            status=status,
            actual_outcome="\n".join(lines),
            duration_ms=duration_ms,
            tool_name="pre_plan",
            tool_output=item,
        )

    def _build_instructions(self, knowledge: KnowledgeBundle, skills: list[SkillBundle]) -> str:
        prompt = self.settings.openai_agents.prompt
        model = PromptModelBuilder(prompt).build_agent_prompt(knowledge, skills)
        return PromptRenderer(prompt).render_agent_prompt(model)

    def _build_task_input(self, task: Task, runtime_policy: list[str] | None = None) -> str:
        prompt = self.settings.openai_agents.prompt
        store = self._runtime_secret_store()
        model = PromptModelBuilder(prompt).build_task_prompt(
            task,
            runtime_policy,
            runtime_secret_names=list(store.available_names()),
            runtime_secret_warnings=list(store.warnings()),
        )
        return PromptRenderer(prompt).render_task_prompt(model)

    def _runtime_secret_store(self) -> RuntimeSecretStore:
        return RuntimeSecretStore.from_settings(self.settings.runtime_secrets)

    def _tool_origin(self, tool_name: str | None) -> str:
        if not tool_name:
            return "unknown"
        if tool_name in self._agent_tool_names:
            return "agent_tool"
        if tool_name in _RUNTIME_TOOL_NAMES:
            return "runtime"
        if tool_name in self._harness_tool_names:
            schema = self._harness_tool_schemas.get(tool_name)
            if schema is not None and schema.metadata.get("executor_kind") == "common":
                return "common"
            return "platform"
        return "unknown"

    def _artifact_path_from_output(self, output: Any) -> str | None:
        if isinstance(output, str):
            text = output
        else:
            text = str(output) if output is not None else ""
        if not text:
            return None
        try:
            payload = json.loads(text)
        # Arbitrary malformed SDK tool output is treated as having no artifact reference.
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        artifact = payload.get("artifact")
        if isinstance(artifact, dict) and artifact.get("path"):
            return str(artifact["path"])
        result = payload.get("result")
        if isinstance(result, dict):
            artifact_refs = result.get("artifact_refs")
            if isinstance(artifact_refs, list) and artifact_refs:
                first_ref = artifact_refs[0]
                if isinstance(first_ref, dict) and first_ref.get("path"):
                    return str(first_ref["path"])
        return None

    def _tool_output_payload(self, output: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"artifact_path": self._artifact_path_from_output(output)}
        parsed = self._json_payload(output)
        if not isinstance(parsed, dict):
            return payload
        parsed_tool_name = parsed.get("tool_name")
        if isinstance(parsed_tool_name, str) and parsed_tool_name:
            payload["tool_name"] = parsed_tool_name
            payload["tool_origin"] = self._tool_origin(parsed_tool_name)
            if payload["tool_origin"] == "agent_tool":
                payload["executor_kind"] = "agent_tool"
        safe_keys = {
            "tool_name",
            "tool_origin",
            "platform",
            "driver_method",
            "fsq_action_name",
            "status",
            "failure_category",
            "error_message",
            "duration_ms",
            "step_kind",
            "replay",
            "safe_replay_params",
            "runner_step_id",
        }
        for key in safe_keys:
            if key in parsed:
                payload[key] = parsed[key]
        runner_result = parsed.get("runner_result")
        if isinstance(runner_result, dict):
            payload["runner_result"] = runner_result
        artifact_refs = parsed.get("artifact_refs")
        if isinstance(artifact_refs, list):
            payload["artifact_refs"] = artifact_refs
        metadata = parsed.get("metadata")
        if isinstance(metadata, dict):
            payload["metadata"] = metadata
        result = parsed.get("result")
        if isinstance(result, dict):
            if "tool_name" not in payload and isinstance(result.get("tool_name"), str):
                result_tool_name = str(result["tool_name"])
                payload["tool_name"] = result_tool_name
                payload["tool_origin"] = self._tool_origin(result_tool_name)
                if payload["tool_origin"] == "agent_tool":
                    payload["executor_kind"] = "agent_tool"
            if "duration_ms" not in payload and isinstance(result.get("duration_ms"), int):
                payload["duration_ms"] = result["duration_ms"]
            if "status" not in payload and result.get("status") is not None:
                payload["status"] = result.get("status")
            if "failure_category" not in payload and result.get("failure_category") is not None:
                payload["failure_category"] = result.get("failure_category")
            if "error_message" not in payload and result.get("error_message") is not None:
                payload["error_message"] = result.get("error_message")
            result_artifact_refs = result.get("artifact_refs")
            if "artifact_refs" not in payload and isinstance(result_artifact_refs, list) and result_artifact_refs:
                payload["artifact_refs"] = result_artifact_refs
        return payload

    def _json_payload(self, output: Any) -> Any:
        if isinstance(output, str):
            text = output
        else:
            text = str(output) if output is not None else ""
        if not text:
            return None
        try:
            return json.loads(text)
        # Arbitrary malformed SDK tool output is treated as an absent JSON payload.
        except json.JSONDecodeError:
            return None
