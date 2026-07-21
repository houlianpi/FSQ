import asyncio
import re
from pathlib import Path
from typing import Any

import pytest

from fsq_agent import FsqAgent, Task
from fsq_agent.agent import Verifier
from fsq_agent.agent._openai_runtime import OpenAIAgentsRuntime, _RecentToolOutputInputFilter
from fsq_agent.config import Settings
from fsq_agent.models import ConfigurationError, GoalPrePlan, KnowledgeBundle, ReportArtifact, RunEvent, StepResult
from fsq_agent.observation import ExecutionLogger


@pytest.mark.asyncio
async def test_agent_run_requires_configured_model_provider_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AZURE_OPENAI_BASE_URL", "https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/")
    monkeypatch.setenv("AZURE_OPENAI_MODEL", "gpt-5.4")
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
output:
  root_dir: output
workspace:
  root_dir: workspace
cases:
  dir: cases
agent_context:
    knowledge:
        root_dir: knowledge
openai_agents:
    provider: azure_openai
""",
        encoding="utf-8",
    )
    task = Task(
        id="smoke",
        name="Smoke",
        description="Record a smoke test task.",
        acceptance_criteria=["A report exists."],
    )

    with pytest.raises(ConfigurationError, match="API key"):
        await FsqAgent.from_config(config_path).run(task)


class _KnowledgeLoader:
    def load_for_task(self, task: Task) -> KnowledgeBundle:
        return KnowledgeBundle()


class _SkillLoader:
    def load(self, skills: list[object]) -> list[object]:
        return []


def _settings_with_knowledge(knowledge_dir: Path, pre_plan_dir: Path | None = None) -> Settings:
    knowledge: dict[str, object] = {"root_dir": knowledge_dir}
    if pre_plan_dir is not None:
        knowledge["pre_plan"] = {"dir": pre_plan_dir}
    return Settings(agent_context={"knowledge": knowledge})


class _Runtime:
    def __init__(self) -> None:
        self.last_task: Task | None = None

    async def run_task(
        self,
        task: Task,
        knowledge: KnowledgeBundle,
        skills: list[object],
        run_id: str,
        event_sink: object | None = None,
    ) -> list[StepResult]:
        self.last_task = task
        return [
            StepResult(
                step_id=1,
                status="success",
                actual_outcome='{"status":"success","summary":"Done","pre_plan":[],"plan_updates":[],"satisfied_criteria":["A report exists."],"unmet_criteria":[],"evidence":["Report generated"],"errors":[]}',
                tool_name="openai_agents.runner",
            )
        ]


class _GoalRunRuntime(_Runtime):
    def __init__(self) -> None:
        super().__init__()
        self.pre_plan_goal: str | None = None
        self.pre_plan_reference_type: str | None = None

    async def run_pre_plan(
        self,
        reference_text: str,
        knowledge: KnowledgeBundle,
        skills: list[object],
        run_id: str,
        event_sink: object | None = None,
        reference_type: str = "goal",
    ) -> GoalPrePlan:
        self.pre_plan_goal = reference_text
        self.pre_plan_reference_type = reference_type
        return GoalPrePlan(
            goal=reference_text,
            verification_goal=f"Verify planned outcome for {reference_type}: {reference_text.splitlines()[0]}",
            summary="Generated execution actions.",
            relevant_page_ids=["edge_android_new_tab_page"],
            key_actions=[
                {"step_id": 1, "action": "Open the overflow menu."},
                {"step_id": 2, "action": "Tap Downloads."},
            ],
        )

    async def run_task(
        self,
        task: Task,
        knowledge: KnowledgeBundle,
        skills: list[object],
        run_id: str,
        event_sink: object | None = None,
    ) -> list[StepResult]:
        self.last_task = task
        satisfied = task.verification_goal or "Verification goal missing."
        return [
            StepResult(
                step_id=1,
                status="success",
                actual_outcome=(
                    '{"status":"success","summary":"Goal done","pre_plan":[],"plan_updates":[],'
                    f'"satisfied_criteria":["{satisfied}"],"unmet_criteria":[],"evidence":["Goal observed"],"errors":[]}}'
                ),
                tool_name="openai_agents.runner",
            )
        ]


class _CancelledRuntime:
    async def run_task(
        self,
        task: Task,
        knowledge: KnowledgeBundle,
        skills: list[object],
        run_id: str,
        event_sink: object | None = None,
    ) -> list[StepResult]:
        raise asyncio.CancelledError()


class _FakeArtifactStore:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str, dict[str, Any]]] = []

    def write(self, tool_name: str, output_text: str, metadata: dict[str, Any]) -> Path:
        self.writes.append((tool_name, output_text, metadata))
        return Path("artifact.json")


class _Reporter:
    def __init__(self) -> None:
        self.run_ids: list[str] = []

    def generate(self, run_id: str, task: Task, steps: list[StepResult], verification: object) -> ReportArtifact:
        self.run_ids.append(run_id)
        return ReportArtifact(run_id=run_id, path=Path("report.md"))


class _RefreshSession:
    def close_sync(self) -> None:
        pass


def _stub_provider_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fsq_agent.agent._core.refresh_model_provider_session", lambda settings: _RefreshSession())


@pytest.mark.asyncio
async def test_agent_run_id_uses_friendly_timestamp_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_provider_refresh(monkeypatch)
    reporter = _Reporter()
    agent = FsqAgent(
        Settings(),
        verifier=Verifier(),
        reporter=reporter,  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=_Runtime(),  # type: ignore[arg-type]
    )
    task = Task(
        id="smoke",
        name="Smoke",
        description="Record a smoke test task.",
        acceptance_criteria=["A report exists."],
        key_actions=["Key action 1: Record report existence."],
        verification_goal="A report exists.",
    )

    result = await agent.run(task)

    assert result.report.run_id == reporter.run_ids[0]
    assert re.fullmatch(r"smoke-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", result.report.run_id)


def test_recent_tool_output_filter_does_not_artifact_sensitive_outputs() -> None:
    artifact_store = _FakeArtifactStore()
    input_filter = _RecentToolOutputInputFilter(
        sdk_filter=None,
        recent_tool_outputs=0,
        max_output_chars=1,
        preview_chars=1,
        trimmable_tools=None,
        artifact_store=artifact_store,  # type: ignore[arg-type]
    )

    path = input_filter._artifact_path_for(
        {"call_id": "call-1"},
        {"get_runtime_secret"},
        '{"type":"runtime_secret","name":"TEST_ACCOUNT_PASSWORD","value":"secret","sensitive":true}',
    )

    assert path is None
    assert artifact_store.writes == []


def test_recent_tool_output_filter_omits_wrapped_sensitive_history_preview() -> None:
    from agents.run_config import ModelInputData

    artifact_store = _FakeArtifactStore()
    input_filter = _RecentToolOutputInputFilter(
        sdk_filter=None,
        recent_tool_outputs=0,
        max_output_chars=1,
        preview_chars=20,
        trimmable_tools=None,
        artifact_store=artifact_store,  # type: ignore[arg-type]
    )
    output = (
        '{"tool_name":"get_runtime_secret","model_output":"full","result":'
        '{"tool_name":"get_runtime_secret","status":"success","output":'
        '{"type":"runtime_secret","name":"TEST_ACCOUNT_PASSWORD","value":"secret-password","sensitive":true},'
        '"sensitive":true}}'
    )
    data = type(
        "Data",
        (),
        {
            "model_data": ModelInputData(
                input=[
                    {"type": "function_call", "call_id": "call-1", "name": "get_runtime_secret"},
                    {"type": "function_call_output", "call_id": "call-1", "output": output},
                ],
                instructions="instructions",
            )
        },
    )()

    filtered = input_filter(data)

    assert artifact_store.writes == []
    assert "secret-password" not in filtered.input[1]["output"]
    assert filtered.input[1]["output"] == "[Sensitive historical get_runtime_secret output omitted.]"


def test_recent_tool_output_filter_omits_small_wrapped_sensitive_history() -> None:
    from agents.run_config import ModelInputData

    artifact_store = _FakeArtifactStore()
    input_filter = _RecentToolOutputInputFilter(
        sdk_filter=None,
        recent_tool_outputs=0,
        max_output_chars=100000,
        preview_chars=20,
        trimmable_tools=None,
        artifact_store=artifact_store,  # type: ignore[arg-type]
    )
    output = (
        '{"tool_name":"get_runtime_secret","model_output":"full","result":'
        '{"tool_name":"get_runtime_secret","status":"success","output":'
        '{"type":"runtime_secret","name":"TEST_ACCOUNT_PASSWORD","value":"secret-password","sensitive":true},'
        '"sensitive":true}}'
    )
    data = type(
        "Data",
        (),
        {
            "model_data": ModelInputData(
                input=[
                    {"type": "function_call", "call_id": "call-1", "name": "get_runtime_secret"},
                    {"type": "function_call_output", "call_id": "call-1", "output": output},
                ],
                instructions="instructions",
            )
        },
    )()

    filtered = input_filter(data)

    assert artifact_store.writes == []
    assert "secret-password" not in filtered.input[1]["output"]
    assert filtered.input[1]["output"] == "[Sensitive historical get_runtime_secret output omitted.]"


@pytest.mark.asyncio
async def test_agent_run_emits_and_persists_live_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_provider_refresh(monkeypatch)
    reporter = _Reporter()
    events: list[RunEvent] = []
    agent = FsqAgent(
        Settings(),
        verifier=Verifier(),
        reporter=reporter,  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=_Runtime(),  # type: ignore[arg-type]
        event_logger=ExecutionLogger(tmp_path),
    )
    task = Task(
        id="smoke",
        name="Smoke",
        description="Record a smoke test task.",
        acceptance_criteria=["A report exists."],
        key_actions=["Key action 1: Record report existence."],
        verification_goal="A report exists.",
    )

    result = await agent.run(task, event_sink=events.append)

    assert [event.type for event in events] == ["run_started", "agent_started", "run_completed"]
    assert [event.sequence for event in events] == [1, 2, 3]
    timeline_path = tmp_path / result.report.run_id / "events.jsonl"
    assert timeline_path.exists()
    assert "run_completed" in timeline_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_agent_run_persists_run_failed_for_cancellation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_provider_refresh(monkeypatch)
    events: list[RunEvent] = []
    agent = FsqAgent(
        Settings(),
        verifier=Verifier(),
        reporter=_Reporter(),  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=_CancelledRuntime(),  # type: ignore[arg-type]
        event_logger=ExecutionLogger(tmp_path),
    )
    task = Task(
        id="smoke",
        name="Smoke",
        description="Record a smoke test task.",
        key_actions=["Key action 1: Start smoke task."],
        verification_goal="Start smoke task.",
    )

    with pytest.raises(asyncio.CancelledError):
        await agent.run(task, event_sink=events.append)

    assert [event.type for event in events] == ["run_started", "agent_started", "run_failed"]
    assert events[-1].message == "CancelledError"
    assert events[-1].payload["exception_type"] == "CancelledError"
    timeline_paths = list(tmp_path.glob("smoke-*/events.jsonl"))
    assert len(timeline_paths) == 1
    timeline = timeline_paths[0].read_text(encoding="utf-8")
    assert "run_failed" in timeline
    assert "CancelledError" in timeline


@pytest.mark.asyncio
async def test_agent_run_preplans_goal_only_task_before_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_provider_refresh(monkeypatch)
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "index.md").write_text("# Page Knowledge", encoding="utf-8")
    runtime = _GoalRunRuntime()
    events: list[RunEvent] = []
    agent = FsqAgent(
        _settings_with_knowledge(knowledge_dir),
        verifier=Verifier(),
        reporter=_Reporter(),  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=runtime,  # type: ignore[arg-type]
    )
    task = Task(
        id="downloads",
        name="Access Downloads",
        description="Access Downloads through the overflow menu.",
        verification_goal="Goal completed: Access Downloads",
        acceptance_criteria=["Goal completed: Access Downloads"],
    )

    result = await agent.run(task, event_sink=events.append)

    assert result.status == "success"
    assert runtime.pre_plan_goal == "Access Downloads"
    assert runtime.pre_plan_reference_type == "unknown"
    assert runtime.last_task is not None
    assert runtime.last_task.key_actions == [
        "Key action 1: Open the overflow menu.",
        "Key action 2: Tap Downloads.",
    ]
    assert runtime.last_task.verification_goal == "Verify planned outcome for unknown: Access Downloads"
    assert any(event.title == "Goal pre-plan injected" for event in events)


@pytest.mark.asyncio
async def test_agent_run_refreshes_provider_before_pre_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "index.md").write_text("# Page Knowledge", encoding="utf-8")
    runtime = _GoalRunRuntime()
    calls: list[str] = []

    def fake_refresh_model_provider_session(settings: Settings) -> _RefreshSession:
        calls.append("refresh")
        session = _RefreshSession()
        session.close_sync = lambda: calls.append("refresh_closed")  # type: ignore[method-assign]
        return session

    original_run_pre_plan = runtime.run_pre_plan

    async def recording_run_pre_plan(*args, **kwargs):
        calls.append("pre_plan")
        return await original_run_pre_plan(*args, **kwargs)

    runtime.run_pre_plan = recording_run_pre_plan  # type: ignore[method-assign]
    monkeypatch.setattr("fsq_agent.agent._core.refresh_model_provider_session", fake_refresh_model_provider_session)
    agent = FsqAgent(
        _settings_with_knowledge(knowledge_dir),
        verifier=Verifier(),
        reporter=_Reporter(),  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=runtime,  # type: ignore[arg-type]
    )
    task = Task(
        id="downloads",
        name="Access Downloads",
        description="Access Downloads through the overflow menu.",
        verification_goal="Goal completed: Access Downloads",
        acceptance_criteria=["Goal completed: Access Downloads"],
    )

    result = await agent.run(task)

    assert result.status == "success"
    assert calls[:3] == ["refresh", "refresh_closed", "pre_plan"]
    assert calls.count("refresh") == 1


@pytest.mark.asyncio
async def test_agent_pre_plan_uses_explicit_raw_case_planning_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_provider_refresh(monkeypatch)
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "index.md").write_text("# Page Knowledge", encoding="utf-8")
    runtime = _GoalRunRuntime()
    agent = FsqAgent(
        _settings_with_knowledge(knowledge_dir),
        verifier=Verifier(),
        reporter=_Reporter(),  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=runtime,  # type: ignore[arg-type]
    )
    raw_reference = """Source path: cases/settings.codex.yaml

Raw case content:
```yaml
- tapOn: Privacy and security
- tapOn: Microsoft services
```
"""
    task = Task(
        id="settings",
        name="Case reference: settings.codex.yaml",
        description="Run raw case content.",
        planning_reference_kind="raw_case",
        planning_reference_text=raw_reference,
        verification_goal="Goal completed: Execute the referenced case content from settings.codex.yaml.",
        acceptance_criteria=["Goal completed: Execute the referenced case content from settings.codex.yaml."],
    )

    result = await agent.run(task)

    assert result.status == "success"
    assert runtime.pre_plan_reference_type == "raw_case"
    assert runtime.pre_plan_goal == raw_reference.strip()
    assert runtime.pre_plan_goal is not None
    assert "Microsoft services" in runtime.pre_plan_goal
    assert "Execute the referenced case content" not in runtime.pre_plan_goal
    assert runtime.last_task is not None
    assert runtime.last_task.verification_goal.startswith("Verify planned outcome for raw_case:")


@pytest.mark.asyncio
async def test_pre_plan_runtime_reads_page_by_index_page_id(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    pages_dir = knowledge_dir / "pages"
    pages_dir.mkdir(parents=True)
    (knowledge_dir / "index.md").write_text(
    """
# Knowledge Index

```json
{
    "schema_version": "page_knowledge_index_v1",
    "product": "Microsoft Edge",
    "platform": "Android",
    "pages": [
        {
            "page_id": "edge_android_new_tab_page",
            "file": "pages/edge_android_new_tab_page.md",
            "name": "New Tab Page",
            "intents": ["new tab"]
        }
    ]
}
```
""",
        encoding="utf-8",
    )
    (pages_dir / "edge_android_new_tab_page.md").write_text("# New Tab Page", encoding="utf-8")
    runtime = OpenAIAgentsRuntime(_settings_with_knowledge(knowledge_dir), object())  # type: ignore[arg-type]

    output = await runtime._read_knowledge_page_tool(None, '{"page_id":"edge_android_new_tab_page"}')

    assert '"ok": true' in output
    assert "# New Tab Page" in output
    assert "pages/edge_android_new_tab_page.md" in output


@pytest.mark.asyncio
async def test_pre_plan_runtime_reads_from_pre_plan_knowledge_dir(tmp_path: Path) -> None:
    private_knowledge_dir = tmp_path / "knowledge"
    page_knowledge_dir = tmp_path / "knowledge" / "project_android_v1"
    private_knowledge_dir.mkdir(parents=True)
    pages_dir = page_knowledge_dir / "pages"
    pages_dir.mkdir(parents=True)
    (page_knowledge_dir / "index.md").write_text("# Page Graph Index", encoding="utf-8")
    (pages_dir / "edge_android_new_tab_page.md").write_text("# New Tab Page", encoding="utf-8")
    runtime = OpenAIAgentsRuntime(
        _settings_with_knowledge(private_knowledge_dir, page_knowledge_dir),
        object(),
    )  # type: ignore[arg-type]

    index_output = await runtime._read_knowledge_index_tool(None, "{}")
    page_output = await runtime._read_knowledge_page_tool(None, '{"file":"pages/edge_android_new_tab_page.md"}')

    assert "# Page Graph Index" in index_output
    assert "# New Tab Page" in page_output
