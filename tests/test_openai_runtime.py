import asyncio
import json
from pathlib import Path
import time
from types import SimpleNamespace
from typing import Any

import pytest

from fsq_agent.agent import OpenAIAgentsRuntime
from fsq_agent.agent._harness_tools import HarnessToolAdapter
from fsq_agent.agent._prompt import PromptModelBuilder, PromptRenderer
from fsq_agent.agent._pre_plan import build_pre_plan_input
from fsq_agent.agent._verification_task import VerificationEvidenceBuilder
from fsq_agent.config import Settings
from fsq_agent.models import (
    AgentFinalOutput,
    GoalPrePlan,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    HarnessFunctionSchema,
    KnowledgeBundle,
    LocalToolOutputSettings,
    OpenAIAgentsSettings,
    OutputSettings,
    RunnerStepResult,
    RuntimeSecretSettings,
    SkillBundle,
    StepPhase,
    StepPhaseReport,
    StepResult,
    Task,
)
from fsq_agent.providers import build_model_provider_session


class _EmptyToolFactory:
    def build_tools(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return []


class _CapturingToolFactory:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    def build_tools(self, *_args: Any, **kwargs: Any) -> list[Any]:
        self.kwargs = kwargs
        return []


class _FakeFunctionTool:
    def __init__(self, **kwargs: Any) -> None:
        self.name = kwargs["name"]
        self.description = kwargs["description"]
        self.params_json_schema = kwargs["params_json_schema"]
        self.strict_json_schema = kwargs.get("strict_json_schema", True)
        self.on_invoke_tool = kwargs["on_invoke_tool"]


class _FakeHarness:
    def __init__(
        self,
        *,
        tool_name: str = "tap_on",
        driver_method: str = "tap_on",
        fsq_action_name: str = "tapOn",
        screen_size: tuple[int, int] | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.driver_method = driver_method
        self.fsq_action_name = fsq_action_name
        self.screen_size = screen_size
        self.steps: list[Any] = []
        self.calls: list[str] = []

    def action_space(self) -> list[HarnessFunctionSchema]:
        return [
            HarnessFunctionSchema(
                name=self.tool_name,
                description=f"Run {self.fsq_action_name}.",
                params_json_schema={"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]},
                platform="android",
                driver_method=self.driver_method,
                fsq_action_name=self.fsq_action_name,
            )
        ]

    def get_context(self) -> HarnessContext:
        self.calls.append("get_context")
        return HarnessContext(platform="android", session_id="session-1", screen_size=self.screen_size)

    def before_action(self, step: Any, context: HarnessContext) -> None:
        self.calls.append(f"before:{step.action_name}:{context.session_id}")

    def invoke_action(self, step: Any, context: HarnessContext) -> HarnessActionResult:
        self.calls.append(f"invoke:{step.action_name}:{context.session_id}")
        self.steps.append(step)
        return HarnessActionResult(
            status="passed",
            action_name=step.action_name,
            output={"context_session_id": context.session_id, "params": step.params},
            metadata={"harness": "fake"},
        )

    def after_action(
        self,
        step: Any,
        context: HarnessContext,
        action_result: HarnessActionResult | None,
    ) -> None:
        status = action_result.status if action_result else "none"
        self.calls.append(f"after:{step.action_name}:{status}")

    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        self.calls.append(f"capture:{kind}:{reason}:{step_id}:{phase}:{context.session_id}")
        return HarnessArtifactRef(
            artifact_id=f"{step_id}-{phase}-{reason}-{kind}",
            kind=kind,
            path=Path(f"artifacts/{kind}/{step_id}-{phase}-{reason}.{kind}"),
        )

    def classify_error(self, _error: BaseException, _phase: StepPhase, _step: Any) -> str:
        return "unknown"


class _FailingHarness(_FakeHarness):
    def action_space(self) -> list[HarnessFunctionSchema]:
        raise RuntimeError("Harness action-space failed")


class _FailingCaptureHarness(_FakeHarness):
    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        self.calls.append(f"capture:{kind}:{reason}:{step_id}:{phase}:{context.session_id}")
        raise RuntimeError("capture failed")


class _DirectInvokeForbiddenHarness(_FakeHarness):
    def invoke_action(self, step: Any, context: HarnessContext) -> HarnessActionResult:
        raise AssertionError("adapter must not directly invoke the harness")


class _FakeWebHarness(_FakeHarness):
    def __init__(self) -> None:
        super().__init__(tool_name="click_on", driver_method="click_on", fsq_action_name="clickOn")

    def action_space(self) -> list[HarnessFunctionSchema]:
        schemas = super().action_space()
        return [schemas[0].model_copy(update={"platform": "web"})]

    def get_context(self) -> HarnessContext:
        self.calls.append("get_context")
        return HarnessContext(platform="web", session_id="session-1")


def _fake_harness_factory(_run_id: str) -> _FakeHarness:
    return _FakeHarness()


class _FakeProviderSession:
    def create_agents_provider(self, **_kwargs: Any) -> str:
        return "provider"

    async def close(self) -> None:
        return None


class _FakeAgent:
    instances: list["_FakeAgent"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.instances.append(self)


class _FakeRunConfig:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeToolOutputTrimmer:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeRunResult:
    def __init__(self, final_output: Any | None = None) -> None:
        self.final_output = final_output or AgentFinalOutput(status="success", summary="Done.")

    async def stream_events(self) -> Any:
        if False:
            yield None


class _FakeRunner:
    @staticmethod
    def run_streamed(agent: _FakeAgent, *_args: Any, **_kwargs: Any) -> _FakeRunResult:
        if agent.kwargs.get("output_type") is GoalPrePlan:
            return _FakeRunResult(GoalPrePlan(goal="Open the app.", verification_goal="The app is open."))
        return _FakeRunResult()


def _patch_runtime_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    import agents
    import agents.extensions
    import fsq_agent.agent._openai_runtime as runtime_module

    _FakeAgent.instances = []
    monkeypatch.setattr(runtime_module, "build_model_provider_session", lambda _settings: _FakeProviderSession())
    monkeypatch.setattr(agents, "Agent", _FakeAgent)
    monkeypatch.setattr(agents, "FunctionTool", _FakeFunctionTool)
    monkeypatch.setattr(agents, "RunConfig", _FakeRunConfig)
    monkeypatch.setattr(agents, "Runner", _FakeRunner)
    monkeypatch.setattr(agents, "set_tracing_disabled", lambda _disabled: None)
    monkeypatch.setattr(agents.extensions, "ToolOutputTrimmer", _FakeToolOutputTrimmer)


@pytest.mark.asyncio
async def test_runtime_failure_returns_failed_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    openai_settings = OpenAIAgentsSettings(provider="azure_openai")
    openai_settings.base_url = "https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/"
    openai_settings.model = "gpt-5.4"
    settings = Settings(openai_agents=openai_settings)
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), lambda _run_id: _FailingHarness())
    task = Task(
        id="runtime-failure",
        name="Runtime Failure",
        description="Trigger harness failure.",
        acceptance_criteria=["A failed step is returned."],
    )

    results = await runtime.run_task(task, KnowledgeBundle(), [], "runtime-failure-2026-05-09_00-00-00")

    assert results[0].status == "failed"
    assert results[0].tool_name == "openai_agents.runner"
    assert "Harness action-space discovery failed" in str(results[0].error)


@pytest.mark.asyncio
async def test_runtime_emits_startup_events_before_main_planning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    _patch_runtime_sdk(monkeypatch)
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory(), _fake_harness_factory)
    task = Task(id="startup", name="Startup", description="Run startup.")
    events: list[Any] = []

    results = await runtime.run_task(task, KnowledgeBundle(), [], "startup-run", event_sink=events.append)

    assert results[-1].status == "success"
    titles = [event.title for event in events]
    expected_titles = [
        "Runtime startup started",
        "Provider setup started",
        "Provider setup completed",
        "Harness setup started",
        "Harness setup completed",
        "Tool setup started",
        "Tool setup completed",
        "SDK agent ready",
        "Planning started",
    ]
    for title in expected_titles:
        assert title in titles
    assert [titles.index(title) for title in expected_titles] == sorted(titles.index(title) for title in expected_titles)
    harness_started = events[titles.index("Harness setup started")]
    assert harness_started.payload["timeout_seconds"] == 60
    assert harness_started.payload["app_id_configured"] is False
    harness_completed = events[titles.index("Harness setup completed")]
    assert harness_completed.payload["harness_class"] == "_FakeHarness"
    assert "driver_class" not in harness_completed.payload


@pytest.mark.asyncio
async def test_runtime_constructs_sdk_agents_with_explicit_medium_model_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from agents.model_settings import ModelSettings

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    _patch_runtime_sdk(monkeypatch)
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory(), _fake_harness_factory)
    task = Task(id="explicit-model-settings", name="Model Settings", description="Run with stable SDK settings.")

    await runtime.run_pre_plan("Open the app.", KnowledgeBundle(), [], "explicit-model-settings-run")
    await runtime.run_task(task, KnowledgeBundle(), [], "explicit-model-settings-run")
    await runtime._run_verification_task(task, [], "explicit-model-settings-run")

    assert [agent.kwargs["name"] for agent in _FakeAgent.instances] == [
        "fsq-agent pre-planner",
        "fsq-agent",
        "fsq-agent verifier",
    ]
    for agent in _FakeAgent.instances:
        model_settings = agent.kwargs["model_settings"]
        assert isinstance(model_settings, ModelSettings)
        assert model_settings.reasoning is not None
        assert model_settings.reasoning.effort == "medium"
        assert model_settings.verbosity == "medium"


@pytest.mark.asyncio
async def test_runtime_harness_construction_failure_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    _patch_runtime_sdk(monkeypatch)

    def fail_harness(_run_id: str) -> _FakeHarness:
        raise RuntimeError("device connect failed")

    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory(), fail_harness)
    events: list[Any] = []

    results = await runtime.run_task(Task(id="failure", description="Fail startup."), KnowledgeBundle(), [], "failure-run", events.append)

    assert results[0].status == "failed"
    assert "device connect failed" in str(results[0].error)
    titles = [event.title for event in events]
    assert "Harness setup started" in titles
    assert "Harness setup completed" not in titles
    assert titles[-1] == "SDK run failed"


@pytest.mark.asyncio
async def test_runtime_harness_construction_timeout_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    _patch_runtime_sdk(monkeypatch)

    def slow_harness(_run_id: str) -> _FakeHarness:
        time.sleep(2)
        return _FakeHarness()

    settings = Settings(agent={"step_timeout_seconds": 1}, openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), slow_harness)
    events: list[Any] = []

    results = await runtime.run_task(Task(id="timeout", description="Timeout startup."), KnowledgeBundle(), [], "timeout-run", events.append)

    assert results[0].status == "failed"
    assert "Harness setup timed out after 1 seconds" in str(results[0].error)
    titles = [event.title for event in events]
    assert "Harness setup started" in titles
    assert "Harness setup completed" not in titles
    assert titles[-1] == "SDK run failed"


def test_runtime_harness_timeout_does_not_wait_for_worker_shutdown() -> None:
    def slow_harness(_run_id: str) -> _FakeHarness:
        time.sleep(3)
        return _FakeHarness()

    settings = Settings(agent={"step_timeout_seconds": 1}, openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), slow_harness)

    async def run_timeout() -> None:
        with pytest.raises(TimeoutError, match="Harness setup timed out after 1 seconds"):
            await runtime._build_harness_with_timeout("shutdown-run")

    started = time.perf_counter()
    asyncio.run(run_timeout())

    assert time.perf_counter() - started < 1.8


@pytest.mark.asyncio
async def test_runtime_classifies_sdk_content_filter_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    import agents

    class _ContentFilterRunResult:
        async def stream_events(self) -> Any:
            raise RuntimeError(
                "Responses stream ended with terminal event `response.incomplete`. "
                "status=incomplete; incomplete_details=IncompleteDetails(reason='content_filter')."
            )
            yield None

    class _ContentFilterRunner:
        @staticmethod
        def run_streamed(_agent: _FakeAgent, *_args: Any, **_kwargs: Any) -> _ContentFilterRunResult:
            return _ContentFilterRunResult()

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    _patch_runtime_sdk(monkeypatch)
    monkeypatch.setattr(agents, "Runner", _ContentFilterRunner)
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory(), _fake_harness_factory)
    events: list[Any] = []

    results = await runtime.run_task(Task(id="content-filter", description="Trigger content filter."), KnowledgeBundle(), [], "content-filter-run", events.append)

    assert results[0].status == "failed"
    assert results[0].actual_outcome == "OpenAI Agents SDK run ended with an incomplete provider response due to content filtering."
    assert results[0].tool_output["failure_category"] == "provider_content_filter"
    assert events[-1].type == "run_failed"
    assert events[-1].payload["failure_category"] == "provider_content_filter"
    assert events[-1].payload["failure_reason"] == "content_filter"


def test_runtime_builds_configured_web_harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: dict[str, Any] = {}

    class _FakeWebDriver:
        def __init__(self, **kwargs: Any) -> None:
            calls["driver"] = kwargs

    import fsq_agent.agent._openai_runtime as runtime_module

    monkeypatch.setattr("fsq_agent.core.harness._factory.PlaywrightWebDriver", _FakeWebDriver)
    monkeypatch.setattr(runtime_module, "build_ai_assertion_evaluator", lambda _settings: "ai-evaluator")
    chrome_path = tmp_path / "chrome.exe"
    chrome_path.write_text("", encoding="utf-8")
    settings = Settings(
        harness={
            "platform": "web",
            "web": {
                "backend": "playwright",
                "channel": "chrome",
                "headless": False,
                "base_url": "https://example.test",
                "viewport_width": 390,
                "viewport_height": 844,
            },
        },
        output={"root_dir": tmp_path / "output"},
        openai_agents=OpenAIAgentsSettings(),
    )
    settings.harness.web.browser_executable_path = chrome_path
    settings.output.runs_dir = tmp_path / "runs"
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())

    payload = runtime._harness_setup_payload()
    harness = runtime._build_harness("web-run")
    completed_payload = runtime._harness_setup_payload(harness)

    assert calls["driver"] == {
        "channel": "chrome",
        "executable_path": chrome_path,
        "headless": False,
        "base_url": "https://example.test",
        "viewport": (390, 844),
    }
    assert payload == {
        "platform": "web",
        "timeout_seconds": 60,
        "backend": "playwright",
        "channel": "chrome",
        "browser_executable_configured": True,
        "headless": False,
        "base_url_configured": True,
        "viewport_configured": True,
    }
    assert completed_payload["harness_class"] == "WebHarness"
    assert completed_payload["driver_class"] == "_FakeWebDriver"


def test_runtime_builds_configured_macos_harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: dict[str, Any] = {}

    class _FakeMacOSDriver:
        def __init__(self, **kwargs: Any) -> None:
            calls["driver"] = kwargs

    import fsq_agent.agent._openai_runtime as runtime_module

    monkeypatch.setattr("fsq_agent.core.harness._factory.AppiumMac2Driver", _FakeMacOSDriver)
    monkeypatch.setattr(runtime_module, "build_ai_assertion_evaluator", lambda _settings: "ai-evaluator")
    settings = Settings(
        harness={
            "platform": "macos",
            "macos": {
                "backend": "appium_mac2",
                "page_source_max_depth": 7,
                "action_timeout_seconds": 11,
            },
        },
        output={"root_dir": tmp_path / "output"},
        openai_agents=OpenAIAgentsSettings(),
    )
    settings.harness.macos.appium_server_url = "http://127.0.0.1:4723"
    settings.harness.macos.bundle_id = "com.example.MacApp"
    settings.output.runs_dir = tmp_path / "runs"
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())

    payload = runtime._harness_setup_payload()
    harness = runtime._build_harness("mac-run")
    completed_payload = runtime._harness_setup_payload(harness)

    assert calls["driver"] == {
        "server_url": "http://127.0.0.1:4723",
        "bundle_id": "com.example.MacApp",
        "app_path": None,
        "page_source_max_depth": 7,
        "action_timeout_seconds": 11,
    }
    assert payload == {
        "platform": "macos",
        "timeout_seconds": 60,
        "backend": "appium_mac2",
        "appium_server_configured": True,
        "bundle_id_configured": True,
        "app_path_configured": False,
        "action_timeout_seconds": 11,
        "configured_skill_names": [],
    }
    assert completed_payload["harness_class"] == "MacOSHarness"
    assert completed_payload["driver_class"] == "_FakeMacOSDriver"


def test_runtime_builds_step_results_from_structured_pre_plan() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    final_output = """
{
    "status": "failed",
    "summary": "Could not finish.",
    "pre_plan": [
        {
            "step_id": 1,
            "action": "Open browser",
            "success_criteria": ["Browser is open"],
            "status": "success"
        },
        {
            "step_id": 2,
            "action": "Add page to favorites",
            "success_criteria": ["Page is favorited"],
            "status": "adjusted"
        }
    ],
    "plan_updates": ["Used keyboard shortcut after toolbar button was unavailable."],
    "satisfied_criteria": ["Browser is open"],
    "unmet_criteria": ["Page is favorited"],
    "evidence": [],
    "errors": []
}
"""

    steps = runtime._build_pre_plan_step_results(final_output, duration_ms=123)

    assert [step.step_id for step in steps] == [1, 2]
    assert [step.status for step in steps] == ["success", "adjusted"]
    assert steps[0].tool_name == "pre_plan"
    assert "Browser is open" in steps[0].actual_outcome
    assert "Used keyboard shortcut" in steps[1].actual_outcome


def test_runtime_task_input_uses_goal_only_verification_contract() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    task = Task(id="derive", name="Derive", description="Open the page and verify it loads.")

    task_input = runtime._build_task_input(task)

    assert "Structured task input:" in task_input
    assert '"schema_version": "task_input_v1"' in task_input
    assert "Final verification goal: none provided" in task_input
    assert "verification_goal" in task_input


def test_pre_plan_input_includes_available_platform_tools() -> None:
    payload = json.loads(
        build_pre_plan_input(
            "Open downloads.",
            KnowledgeBundle(),
            [],
            available_platform_tools=[
                {
                    "name": "tap_on",
                    "alias": "tapOn",
                    "aliases": [],
                    "executor_kind": "driver",
                    "step_kind": "action",
                    "platform": "android",
                }
            ],
        )
    )

    assert payload["available_platform_tools"] == [
        {
            "name": "tap_on",
            "alias": "tapOn",
            "aliases": [],
            "executor_kind": "driver",
            "step_kind": "action",
            "platform": "android",
        }
    ]


def test_runtime_pre_plan_tool_summary_uses_active_platform_registry() -> None:
    settings = Settings(harness={"platform": "android"}, openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())

    tools = runtime._pre_plan_tool_summary()

    by_name = {tool["name"]: tool for tool in tools}
    assert by_name["tap_on"]["alias"] == "tapOn"
    assert by_name["tap_at"]["alias"] == "tapAt"
    assert by_name["ui_snapshot"]["alias"] == "uiTree"
    assert by_name["assert_visible"]["step_kind"] == "assertion"
    assert by_name["get_runtime_secret"]["executor_kind"] == "common"
    assert by_name["get_runtime_secret"]["platform"] is None


def test_runtime_instructions_exclude_loader_diagnostics() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    knowledge = KnowledgeBundle(items={"project.md": "Use Edge account guidance."}, warnings=["missing optional knowledge"])
    skills = [SkillBundle(name="automation-basics", kind="markdown", instructions="Use semantic actions.")]

    instructions = runtime._build_instructions(knowledge, skills)

    assert "Custom operator instructions:" not in instructions
    assert "Knowledge warnings:" not in instructions
    assert "Skill warnings:" not in instructions
    assert "missing optional knowledge" not in instructions
    assert "Use Edge account guidance." in instructions
    assert "Use semantic actions." in instructions
    assert "Final output JSON Schema:" not in instructions
    assert "AgentFinalOutput structured output required by the SDK" in instructions


def test_runtime_instructions_use_configured_prompt_templates(tmp_path: Path) -> None:
    agent_template = tmp_path / "agent.j2"
    task_template = tmp_path / "task.j2"
    agent_template.write_text(
        "Configured base instruction.\n"
        "Configured knowledge:\n"
        "{% for item in private_knowledge %}- {{ item.key }}={{ item.value }}\n{% endfor %}",
        encoding="utf-8",
    )
    task_template.write_text(
        "Task {{ task.id }}: {{ task.description }}\n"
        "{% if task.acceptance_criteria %}{{ task.acceptance_criteria | join(', ') }}{% else %}Configured no criteria text.{% endif %}\n",
        encoding="utf-8",
    )
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(
            prompt={
                "agent_template_path": agent_template,
                "task_template_path": task_template,
            },
        )
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    knowledge = KnowledgeBundle(items={"k": "v"})

    instructions = runtime._build_instructions(knowledge, [])
    task_input = runtime._build_task_input(Task(id="t1", description="Do it."))

    assert instructions.startswith("Configured base instruction.")
    assert "Configured knowledge:" in instructions
    assert task_input == "Task t1: Do it.\nConfigured no criteria text."


def test_runtime_instructions_include_knowledge_index_content() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    knowledge = KnowledgeBundle(items={"project.md": "Use Other ways to sign in, then choose password sign-in."})

    instructions = runtime._build_instructions(knowledge, [])

    assert "Private knowledge:" in instructions
    assert "project.md" in instructions
    assert "choose password sign-in" in instructions


def test_prompt_model_builder_and_renderer_use_templates() -> None:
    settings = OpenAIAgentsSettings().prompt
    builder = PromptModelBuilder(settings)
    renderer = PromptRenderer(settings)

    agent_model = builder.build_agent_prompt(KnowledgeBundle(), [])
    task_model = builder.build_task_prompt(Task(id="task-1", description="Do it.", verification_goal="Done."))

    assert "Custom operator instructions:" not in renderer.render_agent_prompt(agent_model)
    assert "Preserve ordered key-action semantic fidelity." in renderer.render_agent_prompt(agent_model)
    assert "launch_app harness tool" not in renderer.render_agent_prompt(agent_model)
    assert "kill_app harness tool" not in renderer.render_agent_prompt(agent_model)
    assert "tool usage error" in renderer.render_agent_prompt(agent_model)
    rendered_task = renderer.render_task_prompt(task_model)
    assert "Structured task input:" in rendered_task
    assert '"id": "task-1"' in rendered_task
    assert "Verification goal:" in rendered_task
    assert "Done." in rendered_task


def test_openai_agents_settings_rejects_obsolete_custom_instruction_fields(tmp_path: Path) -> None:
    custom_instructions = tmp_path / "custom-instructions.md"

    with pytest.raises(ValueError):
        OpenAIAgentsSettings(prompt={"custom_instructions": ["Custom."]})

    with pytest.raises(ValueError):
        OpenAIAgentsSettings(prompt={"custom_instructions_path": custom_instructions})


def test_prompt_renderer_injects_model_into_configured_jinja_templates(tmp_path: Path) -> None:
    agent_template = tmp_path / "agent.j2"
    task_template = tmp_path / "task.j2"
    agent_template.write_text("{{ variables.prefix }}{% for skill in skills %} {{ skill.name }}={{ skill.instructions }}{% endfor %}", encoding="utf-8")
    task_template.write_text("Task {{ task.id }} {{ task.variables.prefix }}", encoding="utf-8")
    settings = OpenAIAgentsSettings(
        prompt={
            "agent_template_path": agent_template,
            "task_template_path": task_template,
            "variables": {"prefix": "Base."},
        },
    ).prompt
    builder = PromptModelBuilder(settings)
    renderer = PromptRenderer(settings)

    agent_model = builder.build_agent_prompt(KnowledgeBundle(), [SkillBundle(name="s", kind="markdown", instructions="Skill.")])
    task_model = builder.build_task_prompt(Task(id="task-1", description="Do it.", acceptance_criteria=["Done."]))

    assert renderer.render_agent_prompt(agent_model) == "Base. s=Skill."
    assert renderer.render_task_prompt(task_model) == "Task task-1 Base."


@pytest.mark.asyncio
async def test_harness_tool_adapter_delegates_to_step_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    import fsq_agent.agent._harness_tools as harness_tools_module

    runner_calls: list[tuple[Any, str, Any]] = []

    class _FakeStepRunner:
        def __init__(self, harness: Any, **_: Any) -> None:
            self.harness = harness

        def run_step(self, run_id: str, step: Any) -> RunnerStepResult:
            runner_calls.append((self.harness, run_id, step))
            return RunnerStepResult(
                step_id=step.step_id,
                status="passed",
                duration_ms=7,
                phase_reports=[
                    StepPhaseReport(
                        step_id=step.step_id,
                        phase="invoke",
                        status="passed",
                        metadata={
                            "harness_output": {"params": step.params},
                            "harness_metadata": {"runner": "fake"},
                        },
                    )
                ],
            )

    monkeypatch.setattr(harness_tools_module, "StepRunner", _FakeStepRunner)
    harness = _DirectInvokeForbiddenHarness()
    adapter = HarnessToolAdapter(harness, run_id="run-1")

    tools = adapter.build_tools(_FakeFunctionTool)
    output = await tools[0].on_invoke_tool(None, json.dumps({"target": "Downloads"}))

    payload = json.loads(output)
    assert payload["status"] == "passed"
    assert payload["duration_ms"] == 7
    assert payload["runner_step_id"] == "agent-tap_on-1"
    assert payload["runner_result"]["status"] == "passed"
    assert payload["result"]["output"] == {"params": {"target": "Downloads"}}
    assert runner_calls[0][0] is harness
    assert runner_calls[0][1] == "run-1"
    assert runner_calls[0][2].action_name == "tap_on"
    assert runner_calls[0][2].metadata["authored_action_name"] == "tapOn"
    assert runner_calls[0][2].evidence_policy.capture_before is False
    assert runner_calls[0][2].evidence_policy.artifact_kinds == []
    assert harness.steps == []


@pytest.mark.asyncio
async def test_harness_tool_adapter_applies_evidence_policy_to_mutating_action() -> None:
    harness = _FakeHarness()
    adapter = HarnessToolAdapter(harness, run_id="run-1")

    tools = adapter.build_tools(_FakeFunctionTool)
    output = await tools[0].on_invoke_tool(None, json.dumps({"target": "Downloads"}))

    payload = json.loads(output)
    assert tools[0].name == "tap_on"
    assert payload["tool_origin"] == "platform"
    assert payload["status"] == "passed"
    assert payload["driver_method"] == "tap_on"
    assert payload["fsq_action_name"] == "tapOn"
    assert payload["result"]["output"]["params"] == {"target": "Downloads"}
    assert [ref["kind"] for ref in payload["artifact_refs"]] == ["screenshot", "ui_snapshot", "screenshot", "ui_snapshot"]
    assert payload["result"]["artifact_refs"] == payload["artifact_refs"]
    assert payload["runner_result"]["phase_reports"][0]["phase"] == "prepare"
    assert payload["runner_result"]["phase_reports"][2]["phase"] == "finalize"
    assert harness.steps[0].action_name == "tap_on"
    assert harness.steps[0].metadata["authored_action_name"] == "tapOn"
    assert harness.steps[0].kind == "action"
    assert harness.steps[0].evidence_policy.capture_before is True
    assert harness.steps[0].evidence_policy.capture_after is True
    assert harness.steps[0].evidence_policy.capture_on_failure is False
    assert harness.steps[0].evidence_policy.artifact_kinds == ["screenshot", "ui_snapshot"]
    assert [call for call in harness.calls if call.startswith("capture:")] == [
        "capture:screenshot:before-action:agent-tap_on-1:prepare:session-1",
        "capture:ui_snapshot:before-action:agent-tap_on-1:prepare:session-1",
        "capture:screenshot:after-action:agent-tap_on-1:finalize:session-1",
        "capture:ui_snapshot:after-action:agent-tap_on-1:finalize:session-1",
    ]


@pytest.mark.asyncio
async def test_harness_tool_adapter_outputs_tap_at_safe_replay_params() -> None:
    harness = _FakeHarness(tool_name="tap_at", driver_method="tap_at", fsq_action_name="tapAt", screen_size=(1080, 2400))
    adapter = HarnessToolAdapter(harness, run_id="run-1")

    tools = adapter.build_tools(_FakeFunctionTool)
    output = await tools[0].on_invoke_tool(None, json.dumps({"point": {"x": 100, "y": 200}}))

    payload = json.loads(output)
    expected = {"point": {"x": 100, "y": 200}, "reference_screen_size": {"width": 1080, "height": 2400}}
    assert payload["tool_name"] == "tap_at"
    assert payload["safe_replay_params"] == expected
    assert payload["runner_result"]["phase_reports"][1]["metadata"]["safe_replay_params"] == expected


def test_harness_tool_adapter_uses_default_strict_schema_for_capability_tools() -> None:
    harness = _FakeHarness(tool_name="perform_actions", driver_method="perform_actions", fsq_action_name="performActions")
    adapter = HarnessToolAdapter(harness, run_id="run-1")

    tools = adapter.build_tools(_FakeFunctionTool)

    assert tools[0].name == "perform_actions"
    assert tools[0].strict_json_schema is True


@pytest.mark.asyncio
async def test_harness_tool_adapter_keeps_default_evidence_policy_for_assertion_actions() -> None:
    harness = _FakeHarness(
        tool_name="assert_visible",
        driver_method="assert_visible",
        fsq_action_name="assertVisible",
    )
    adapter = HarnessToolAdapter(harness, run_id="run-1")

    tools = adapter.build_tools(_FakeFunctionTool)
    output = await tools[0].on_invoke_tool(None, json.dumps({"target": "Downloads"}))

    payload = json.loads(output)
    assert payload["status"] == "passed"
    assert [ref["kind"] for ref in payload["artifact_refs"]] == ["screenshot", "ui_snapshot"]
    assert payload["result"]["artifact_refs"] == payload["artifact_refs"]
    assert harness.steps[0].action_name == "assert_visible"
    assert harness.steps[0].metadata["authored_action_name"] == "assertVisible"
    assert harness.steps[0].kind == "assertion"
    assert harness.steps[0].evidence_policy.capture_before is True
    assert harness.steps[0].evidence_policy.capture_after is False
    assert harness.steps[0].evidence_policy.artifact_kinds == ["screenshot", "ui_snapshot"]
    assert [call for call in harness.calls if call.startswith("capture:")] == [
        "capture:screenshot:before-action:agent-assert_visible-1:prepare:session-1",
        "capture:ui_snapshot:before-action:agent-assert_visible-1:prepare:session-1",
    ]


@pytest.mark.asyncio
async def test_harness_tool_adapter_uses_step_kind_for_effective_evidence_policy() -> None:
    harness = _FakeHarness()
    adapter = HarnessToolAdapter(harness, run_id="run-1")

    tools = adapter.build_tools(_FakeFunctionTool)
    output = await tools[0].on_invoke_tool(None, json.dumps({"target": "Downloads"}))

    payload = json.loads(output)
    assert payload["status"] == "passed"
    assert payload["fsq_action_name"] == "tapOn"
    assert [ref["kind"] for ref in payload["artifact_refs"]] == ["screenshot", "ui_snapshot", "screenshot", "ui_snapshot"]
    assert harness.steps[0].action_name == "tap_on"
    assert harness.steps[0].metadata["authored_action_name"] == "tapOn"
    assert harness.steps[0].evidence_policy.capture_before is True
    assert harness.steps[0].evidence_policy.artifact_kinds == ["screenshot", "ui_snapshot"]
    assert [call for call in harness.calls if call.startswith("capture:")] == [
        "capture:screenshot:before-action:agent-tap_on-1:prepare:session-1",
        "capture:ui_snapshot:before-action:agent-tap_on-1:prepare:session-1",
        "capture:screenshot:after-action:agent-tap_on-1:finalize:session-1",
        "capture:ui_snapshot:after-action:agent-tap_on-1:finalize:session-1",
    ]


@pytest.mark.asyncio
async def test_harness_tool_adapter_uses_web_platform_registry_for_evidence_policy() -> None:
    harness = _FakeWebHarness()
    adapter = HarnessToolAdapter(harness, run_id="run-1", platform="web")

    tools = adapter.build_tools(_FakeFunctionTool)
    output = await tools[0].on_invoke_tool(None, json.dumps({"target": "Search"}))

    payload = json.loads(output)
    assert payload["status"] == "passed"
    assert payload["fsq_action_name"] == "clickOn"
    assert [ref["kind"] for ref in payload["artifact_refs"]] == [
        "screenshot",
        "ui_snapshot",
        "screenshot",
        "ui_snapshot",
    ]
    assert harness.steps[0].action_name == "click_on"
    assert harness.steps[0].metadata["authored_action_name"] == "clickOn"
    assert harness.steps[0].evidence_policy.artifact_kinds == ["screenshot", "ui_snapshot"]


@pytest.mark.asyncio
async def test_harness_tool_adapter_surfaces_artifact_capture_failure() -> None:
    harness = _FailingCaptureHarness()
    adapter = HarnessToolAdapter(harness, run_id="run-1")

    tools = adapter.build_tools(_FakeFunctionTool)
    output = await tools[0].on_invoke_tool(None, json.dumps({"target": "Downloads"}))

    payload = json.loads(output)
    assert payload["status"] == "failed"
    assert payload["failure_category"] == "artifact_error"
    assert payload["result"]["failure_category"] == "artifact_error"
    assert payload["runner_result"]["status"] == "failed"
    assert payload["runner_result"]["failure_category"] == "artifact_error"
    assert "capture failed" in payload["error_message"]


def test_runtime_tool_origin_recognizes_platform_tools() -> None:
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory(), _fake_harness_factory)
    runtime._agent_tool_names = {"read_file"}
    runtime._harness_tool_names = {"tap_on"}

    assert runtime._tool_origin("tap_on") == "platform"
    assert runtime._tool_origin("read_file") == "agent_tool"
    assert runtime._tool_origin("read_knowledge_index") == "runtime"
    assert runtime._tool_origin("unexpected_tool") == "unknown"


def test_runtime_tool_output_payload_preserves_runner_evidence_fields() -> None:
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory())
    output = json.dumps(
        {
            "tool_name": "tap_on",
            "tool_origin": "harness",
            "status": "passed",
            "replay": {"kind": "fsq_command", "alias": "tapAt"},
            "safe_replay_params": {"point": {"x": 100, "y": 200}, "reference_screen_size": {"width": 1080, "height": 2400}},
            "runner_step_id": "agent-tap_on-1",
            "runner_result": {"step_id": "agent-tap_on-1", "status": "passed"},
            "artifact_refs": [{"kind": "screenshot", "path": "artifacts/screenshots/before.png"}],
            "result": {
                "artifact_refs": [{"kind": "ui_tree", "path": "artifacts/ui-trees/after.json"}],
            },
        }
    )

    payload = runtime._tool_output_payload(output)

    assert payload["runner_step_id"] == "agent-tap_on-1"
    assert payload["replay"] == {"kind": "fsq_command", "alias": "tapAt"}
    assert payload["safe_replay_params"] == {"point": {"x": 100, "y": 200}, "reference_screen_size": {"width": 1080, "height": 2400}}
    assert payload["runner_result"] == {"step_id": "agent-tap_on-1", "status": "passed"}
    assert payload["artifact_refs"] == [{"kind": "screenshot", "path": "artifacts/screenshots/before.png"}]


def test_runtime_tool_output_payload_adds_agent_tool_fields() -> None:
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory())
    runtime._agent_tool_names = {"search_artifact"}
    output = json.dumps(
        {
            "tool_name": "search_artifact",
            "model_output": "full",
            "artifact": {"path": None, "content_chars": None},
            "status": "passed",
            "result": {
                "tool_name": "search_artifact",
                "status": "success",
                "output": {"matches": []},
                "duration_ms": 12,
            },
        }
    )

    payload = runtime._tool_output_payload(output)

    assert payload["tool_name"] == "search_artifact"
    assert payload["tool_origin"] == "agent_tool"
    assert payload["executor_kind"] == "agent_tool"
    assert payload["status"] == "passed"
    assert payload["duration_ms"] == 12


@pytest.mark.asyncio
async def test_runtime_uses_sdk_stream_events_for_agent_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    _patch_runtime_sdk(monkeypatch)
    tool_factory = _CapturingToolFactory()
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), tool_factory, _fake_harness_factory)
    task = Task(id="agent-tools", name="Agent Tools", description="Run with AgentTools.")

    await runtime.run_task(task, KnowledgeBundle(), [], "agent-tools-run", event_sink=lambda _event: None)

    assert tool_factory.kwargs is not None
    assert tool_factory.kwargs["event_sink"] is None
    assert callable(tool_factory.kwargs["runner_invoker"])


def test_runtime_stream_tool_output_preserves_tool_name_from_started_event() -> None:
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory())
    started = SimpleNamespace(
        type="run_item_stream_event",
        name="tool_called",
        item=SimpleNamespace(
            raw_item=SimpleNamespace(
                name="read_knowledge_page",
                call_id="call-1",
                arguments='{"page_id":"edge_android_new_tab_page","file":null}',
            )
        ),
    )
    completed = SimpleNamespace(
        type="run_item_stream_event",
        name="tool_output",
        item=SimpleNamespace(raw_item=SimpleNamespace(call_id="call-1"), output='{"ok":true,"page_id":"edge_android_new_tab_page","duration_ms":123}'),
    )

    start_event = runtime._map_stream_event(started, "run-1", "pre-plan")
    completed_event = runtime._map_stream_event(completed, "run-1", "pre-plan")

    assert start_event is not None
    assert completed_event is not None
    assert completed_event.tool_name == "read_knowledge_page"
    assert completed_event.tool_call_id == "call-1"
    assert completed_event.duration_ms == 123


def test_runtime_stream_message_output_uses_text_not_sdk_object_repr() -> None:
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory())
    event = SimpleNamespace(
        type="run_item_stream_event",
        name="message_output_created",
        item=SimpleNamespace(
            raw_item=SimpleNamespace(content=[SimpleNamespace(text='{"schema_version":"task_run_v1","status":"success"}')])
        ),
    )

    run_event = runtime._map_stream_event(event, "run-1", "task")

    assert run_event is not None
    assert run_event.message == '{"schema_version":"task_run_v1","status":"success"}'


def test_runtime_stream_omits_empty_reasoning_summary() -> None:
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory())
    event = SimpleNamespace(
        type="run_item_stream_event",
        name="reasoning_item_created",
        item=SimpleNamespace(raw_item=SimpleNamespace(summary=[])),
    )

    assert runtime._map_stream_event(event, "run-1", "task") is None


def test_verification_evidence_builder_uses_text_only_after_runner_visual_assertion(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    screenshots_dir = output_root / "harness-screenshots"
    screenshots_dir.mkdir(parents=True)
    screenshot_path = screenshots_dir / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    task = Task(
        id="visual",
        description="Verify the page visually.",
        verification_goal="Verify the logo is visible.",
    )
    results = [
        StepResult(
            step_id=1,
            status="success",
            actual_outcome=json.dumps(
                {
                    "schema_version": "task_run_v1",
                    "status": "success",
                    "summary": "Visual assertion passed.",
                    "pre_plan": [],
                    "plan_updates": [],
                    "satisfied_criteria": ["Key action 1: assertWithAI Verify the logo is visible."],
                    "unmet_criteria": [],
                    "evidence": [f"Runner inspected submitted screenshot {screenshot_path} and verified the logo."],
                    "errors": [],
                }
            ),
            tool_name="openai_agents.runner",
        )
    ]

    model_input = VerificationEvidenceBuilder().build_model_input(task, results, image_root=output_root)

    assert isinstance(model_input, str)
    evidence = json.loads(model_input)
    assert evidence["verification_goal"] == "Verify the logo is visible."
    assert "verification_mode" not in evidence
    assert "blocking_criteria" not in evidence
    assert "visual_artifacts" not in evidence
    assert evidence["agent_claims"]["status"] == "success"
    assert "Runner inspected submitted screenshot" in evidence["agent_claims"]["evidence"][0]
    assert "input_image" not in model_input


def test_verification_evidence_builder_does_not_attach_images_from_paths(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    screenshot_path = outside_root / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    task = Task(id="visual", description="Verify the page visually.")
    results = [
        StepResult(
            step_id=1,
            status="success",
            actual_outcome=f"Screenshot outside output root: {screenshot_path}",
        )
    ]

    model_input = VerificationEvidenceBuilder().build_model_input(task, results, image_root=output_root)

    assert isinstance(model_input, str)
    assert "input_image" not in model_input
    assert "visual_artifacts" not in model_input


def test_runtime_builds_run_config_with_tool_output_trimmer(monkeypatch: pytest.MonkeyPatch) -> None:
    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())

    run_config = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider")

    assert run_config.kwargs["model_provider"] == "provider"
    assert run_config.kwargs["tracing_disabled"] is True
    input_filter = run_config.kwargs["call_model_input_filter"]
    assert input_filter.recent_tool_outputs == 3
    assert input_filter.sdk_filter.kwargs == {
        "recent_turns": 2,
        "max_output_chars": 30000,
        "preview_chars": 1000,
        "trimmable_tools": None,
    }


def test_runtime_builds_run_config_enables_sdk_tracing_with_openai_export_key(monkeypatch: pytest.MonkeyPatch) -> None:
    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

    monkeypatch.setenv("OPENAI_API_KEY", "trace-key")
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())

    run_config = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider")

    assert run_config.kwargs["tracing_disabled"] is False


def test_runtime_builds_run_config_respects_explicit_tracing_disable(monkeypatch: pytest.MonkeyPatch) -> None:
    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

    monkeypatch.setenv("OPENAI_API_KEY", "trace-key")
    settings = Settings(openai_agents=OpenAIAgentsSettings(tracing_enabled=False))
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())

    run_config = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider")

    assert run_config.kwargs["tracing_disabled"] is True


def test_provider_session_builds_azure_openai_agents_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class _AsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _OpenAIProvider:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-key")
    openai_settings = OpenAIAgentsSettings(provider="azure_openai")
    openai_settings.base_url = "https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/"
    openai_settings.model = "gpt-5.4"
    settings = Settings(openai_agents=openai_settings)

    session = build_model_provider_session(settings)
    provider = session.create_agents_provider(openai_provider_type=_OpenAIProvider, async_openai_type=_AsyncOpenAI)

    assert provider.kwargs["use_responses"] is True
    assert provider.kwargs["openai_client"].kwargs == {
        "api_key": "azure-key",
        "base_url": "https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/",
        "default_headers": None,
    }


def test_runtime_tool_count_filter_keeps_small_recent_outputs_and_trims_large_outputs() -> None:
    from types import SimpleNamespace

    from agents.run_config import ModelInputData

    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __call__(self, data: Any) -> Any:
            return data.model_data

    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider").kwargs["call_model_input_filter"]
    old_output = "old-output " * 4000
    recent_output = "recent-output " * 4000
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "1", "name": "read_file"},
                {"type": "function_call_output", "call_id": "1", "output": old_output},
                {"type": "function_call", "call_id": "2", "name": "read_file"},
                {"type": "function_call_output", "call_id": "2", "output": "recent 1"},
                {"type": "function_call", "call_id": "3", "name": "read_file"},
                {"type": "function_call_output", "call_id": "3", "output": "recent 2"},
                {"type": "function_call", "call_id": "4", "name": "read_file"},
                {"type": "function_call_output", "call_id": "4", "output": recent_output},
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert filtered.input[1]["output"].startswith("[Trimmed historical read_file output")
    assert filtered.input[3]["output"] == "recent 1"
    assert filtered.input[5]["output"] == "recent 2"
    assert filtered.input[7]["output"].startswith("[Trimmed historical read_file output")


def test_runtime_tool_count_filter_writes_artifact_for_trimmed_history(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from agents.run_config import ModelInputData

    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __call__(self, data: Any) -> Any:
            return data.model_data

    openai_settings = OpenAIAgentsSettings()
    openai_settings.local_tool_output = LocalToolOutputSettings(recent_full_output_count=0)
    output_settings = OutputSettings()
    output_settings.runs_dir = tmp_path / "runs"
    settings = Settings(openai_agents=openai_settings, output=output_settings)
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "1", "name": "harness_source"},
                {"type": "function_call_output", "call_id": "1", "output": "<node>" * 7000},
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert "Artifact path:" in filtered.input[1]["output"]
    assert list((tmp_path / "runs" / "run-1" / "artifacts" / "tools").glob("*.json"))


def test_runtime_input_filter_trims_recent_large_ui_snapshot_to_artifact(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from agents.run_config import ModelInputData

    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __call__(self, data: Any) -> Any:
            return data.model_data

    output_settings = OutputSettings()
    output_settings.runs_dir = tmp_path / "runs"
    settings = Settings(openai_agents=OpenAIAgentsSettings(), output=output_settings)
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    snapshot_output = json.dumps(
        {
            "tool_name": "ui_snapshot",
            "status": "passed",
            "result": {"output": {"xml": "<node password=\"false\">" + ("visible text " * 5000) + "</node>"}},
        }
    )
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "snapshot", "name": "ui_snapshot"},
                {"type": "function_call_output", "call_id": "snapshot", "output": snapshot_output},
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert filtered.input[1]["output"].startswith("[Trimmed historical ui_snapshot output")
    assert "Artifact path:" in filtered.input[1]["output"]
    assert len(filtered.input[1]["output"]) < len(snapshot_output)
    assert list((tmp_path / "runs" / "run-1" / "artifacts" / "tools").glob("*.json"))


def test_runtime_preview_redacts_wrapped_sensitive_tool_output() -> None:
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory())
    output = json.dumps(
        {
            "tool_name": "get_runtime_secret",
            "model_output": "full",
            "result": {
                "tool_name": "get_runtime_secret",
                "status": "success",
                "output": {
                    "type": "runtime_secret",
                    "name": "TEST_ACCOUNT_PASSWORD",
                    "value": "super-secret",
                    "sensitive": True,
                },
                "sensitive": True,
            },
        }
    )

    preview = runtime._preview(output)

    assert "super-secret" not in preview
    assert '"value": "***"' in preview


def test_runtime_redacts_configured_secret_values_from_final_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_ACCOUNT_PASSWORD", "super-secret")
    runtime = OpenAIAgentsRuntime(
        Settings(
            openai_agents=OpenAIAgentsSettings(),
            runtime_secrets=RuntimeSecretSettings(allowed_env_names=["TEST_ACCOUNT_PASSWORD"]),
        ),
        _EmptyToolFactory(),
    )
    final_output = AgentFinalOutput(
        status="success",
        summary="Logged in with super-secret.",
        evidence=["The password super-secret was entered."],
    )

    redacted = runtime._redact_runtime_secrets(final_output)

    assert isinstance(redacted, AgentFinalOutput)
    assert redacted.summary == "Logged in with ***."
    assert redacted.evidence == ["The password *** was entered."]


def test_runtime_redacts_configured_secret_values_from_tool_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_ACCOUNT_PASSWORD", "super-secret")
    runtime = OpenAIAgentsRuntime(
        Settings(
            openai_agents=OpenAIAgentsSettings(),
            runtime_secrets=RuntimeSecretSettings(allowed_env_names=["TEST_ACCOUNT_PASSWORD"]),
        ),
        _EmptyToolFactory(),
    )
    item = type("Item", (), {"raw_item": {"arguments": {"text": "super-secret", "target": "Password"}}})()

    arguments = runtime._tool_arguments(item)

    assert arguments == {"text": "***", "target": "Password"}


def test_runtime_input_filter_leaves_plain_screenshot_outputs_text_only(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from agents.run_config import ModelInputData

    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __call__(self, data: Any) -> Any:
            return data.model_data

    output_root = tmp_path / "output"
    screenshots_dir = output_root / "harness-screenshots"
    screenshots_dir.mkdir(parents=True)
    screenshot_path = screenshots_dir / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    output_settings = OutputSettings(root_dir=output_root)
    output_settings.runs_dir = output_root / "runs"
    settings = Settings(openai_agents=OpenAIAgentsSettings(), output=output_settings)
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "img", "name": "harness_screenshot"},
                {
                    "type": "function_call_output",
                    "call_id": "img",
                    "output": f"Screenshot saved successfully to: {screenshot_path}",
                },
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert filtered.input == data.model_data.input


def test_runtime_input_filter_does_not_attach_submitted_visual_assertion_image(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from agents.run_config import ModelInputData

    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __call__(self, data: Any) -> Any:
            return data.model_data

    output_root = tmp_path / "output"
    screenshots_dir = output_root / "harness-screenshots"
    screenshots_dir.mkdir(parents=True)
    screenshot_path = screenshots_dir / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    output_settings = OutputSettings(root_dir=output_root)
    output_settings.runs_dir = output_root / "runs"
    settings = Settings(openai_agents=OpenAIAgentsSettings(), output=output_settings)
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    output = json.dumps(
        {
            "type": "visual_assertion_submission",
            "assertion_id": "key-action-7",
            "prompt": "Verify the logo is visible.",
            "screenshot_path": str(screenshot_path),
        }
    )
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "visual", "name": "submit_visual_assertion"},
                {"type": "function_call_output", "call_id": "visual", "output": output},
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert filtered.input[1]["output"] == output
    assert len(filtered.input) == 2


def test_runtime_input_filter_rejects_screenshot_images_outside_output_root(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from agents.run_config import ModelInputData

    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __call__(self, data: Any) -> Any:
            return data.model_data

    output_root = tmp_path / "output"
    output_root.mkdir()
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    screenshot_path = outside_root / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    output_settings = OutputSettings(root_dir=output_root)
    output_settings.runs_dir = output_root / "runs"
    settings = Settings(openai_agents=OpenAIAgentsSettings(), output=output_settings)
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "visual", "name": "submit_visual_assertion"},
                {
                    "type": "function_call_output",
                    "call_id": "visual",
                    "output": json.dumps(
                        {
                            "type": "visual_assertion_submission",
                            "assertion_id": "key-action-7",
                            "prompt": "Verify the logo is visible.",
                            "screenshot_path": str(screenshot_path),
                        }
                    ),
                },
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert filtered.input == data.model_data.input
