from typing import Any

import pytest

from fsq_agent.core import ArtifactStore, HarnessInterface
from fsq_agent.core.harness._ai_assertion_tool import AIAssertionBackendToolMixin
from fsq_agent.core.harness._driver_tools import _windows_driver_tool
from fsq_agent.core.harness._windows import WindowsHarness
from fsq_agent.models import (
    AIAssertionRequest,
    AIAssertionResult,
    ExecutableStep,
    HarnessContext,
    WindowsAssertWithAIParams,
    WindowsAssertVisibleParams,
    WindowsClickOnParams,
    WindowsDoubleClickOnParams,
    WindowsKillAppParams,
    WindowsLaunchAppParams,
    WindowsPressKeyParams,
    WindowsRightClickOnParams,
    WindowsTypeTextParams,
    WindowsUiSnapshotParams,
)


class FakeWindowsDriver(AIAssertionBackendToolMixin):
    backend = "fake-pywinauto"

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def context(self) -> dict[str, object]:
        self.calls.append(("context", None))
        return {
            "session_id": "pywinauto:uia",
            "current_url": None,
            "screen_size": (1920, 1080),
            "metadata": {"backend_kind": "uia", "app_path_configured": True},
        }

    def _record(self, method_name: str, params: object) -> dict[str, object]:
        if hasattr(params, "model_dump"):
            recorded = params.model_dump(mode="json", exclude_none=True)
        else:
            recorded = params
        self.calls.append((method_name, recorded))
        return {method_name: True}

    @_windows_driver_tool(
        "launchApp",
        description="Launch the configured Windows desktop application.",
        capture_evidence=True,
        metadata={"evidence_capture_before": False, "evidence_capture_on_failure": False},
    )
    def launch_app(self, params: WindowsLaunchAppParams) -> dict[str, object]:
        return self._record("launch_app", params)

    @_windows_driver_tool("killApp", description="Stop the launched Windows desktop application.")
    def kill_app(self, params: WindowsKillAppParams) -> dict[str, object]:
        return self._record("kill_app", params)

    @_windows_driver_tool("clickOn", description="Click a Windows control resolved from the UI snapshot.", capture_evidence=True)
    def click_on(self, params: WindowsClickOnParams) -> dict[str, object]:
        return self._record("click_on", params)

    @_windows_driver_tool("doubleClickOn", description="Double-click a Windows control.", capture_evidence=True)
    def double_click_on(self, params: WindowsDoubleClickOnParams) -> dict[str, object]:
        return self._record("double_click_on", params)

    @_windows_driver_tool("rightClickOn", description="Right-click a Windows control.", capture_evidence=True)
    def right_click_on(self, params: WindowsRightClickOnParams) -> dict[str, object]:
        return self._record("right_click_on", params)

    @_windows_driver_tool("typeText", description="Type text into a Windows control.", capture_evidence=True)
    def type_text(self, params: WindowsTypeTextParams) -> dict[str, object]:
        return self._record("type_text", params)

    @_windows_driver_tool("pressKey", description="Send a keyboard key sequence to the active Windows window.", capture_evidence=True)
    def press_key(self, params: WindowsPressKeyParams) -> dict[str, object]:
        return self._record("press_key", params)

    @_windows_driver_tool("assertVisible", description="Assert that a Windows control is visible.")
    def assert_visible(self, params: WindowsAssertVisibleParams) -> dict[str, object]:
        return self._record("assert_visible", params)

    @_windows_driver_tool("assertWithAI", description="Evaluate an explicit Windows visual assertion with AI.")
    def assert_with_ai(self, params: WindowsAssertWithAIParams) -> dict[str, object]:
        return self._run_ai_assertion_tool(params)

    @_windows_driver_tool("uiSnapshot", description="Return the current Windows window control tree snapshot.")
    def ui_snapshot(self, params: WindowsUiSnapshotParams) -> dict[str, object]:
        if hasattr(params, "model_dump"):
            recorded = params.model_dump(mode="json", exclude_none=True)
        else:
            recorded = params
        self.calls.append(("ui_snapshot", recorded))
        return {"title": "Notepad", "snapshot_type": "control_tree"}

    def screenshot(self, params: object | None = None) -> bytes:
        self.calls.append(("screenshot", None))
        return b"fake-png"


def _step(action_name: str, params: dict[str, Any] | None = None) -> ExecutableStep:
    return ExecutableStep(step_id="step-1", kind="action", action_name=action_name, params=params or {})


def test_windows_harness_dispatches_fsq_action_names_to_driver() -> None:
    driver = FakeWindowsDriver()
    harness = WindowsHarness(driver=driver)

    context = harness.get_context()

    cases = [
        ("launchApp", {"app_path": "notepad.exe"}, "launch_app"),
        ("clickOn", {"target": "File"}, "click_on"),
        ("doubleClickOn", {"locator": {"title": "Document", "control_type": "Edit"}}, "double_click_on"),
        ("rightClickOn", {"target": "File"}, "right_click_on"),
        ("typeText", {"target": "Document", "text": "hello"}, "type_text"),
        ("pressKey", {"key": "^s"}, "press_key"),
        ("assertVisible", {"target": "Save"}, "assert_visible"),
        ("uiSnapshot", {}, "ui_snapshot"),
        ("killApp", {}, "kill_app"),
    ]

    for action_name, params, _method_name in cases:
        result = harness.invoke_action(_step(action_name, params), context)
        assert result.status == "passed"
        assert result.action_name == action_name

    assert isinstance(harness, HarnessInterface)
    assert context == HarnessContext(
        platform="windows",
        session_id="pywinauto:uia",
        current_url=None,
        screen_size=(1920, 1080),
        metadata={"backend_kind": "uia", "app_path_configured": True},
    )
    assert driver.calls == [("context", None)] + [(method_name, params) for _action_name, params, method_name in cases]


def test_windows_harness_action_space_returns_catalog_backed_schemas() -> None:
    harness = WindowsHarness(driver=FakeWindowsDriver())

    schemas = {schema.name: schema for schema in harness.action_space()}

    assert "click_on" in schemas
    assert "ui_snapshot" in schemas
    assert "assert_with_ai" not in schemas
    assert schemas["click_on"].driver_method == "click_on"
    assert schemas["click_on"].fsq_action_name == "clickOn"
    assert schemas["click_on"].platform == "windows"
    assert schemas["click_on"].capture_evidence is True
    assert schemas["click_on"].metadata["driver_class"] == "FakeWindowsDriver"
    assert schemas["click_on"].metadata["backend"] == "fake-pywinauto"
    assert schemas["click_on"].metadata["replay"] == {"kind": "fsq_command", "alias": "clickOn"}
    assert "target" in schemas["click_on"].params_json_schema["properties"]
    assert schemas["ui_snapshot"].driver_method == "ui_snapshot"
    assert schemas["ui_snapshot"].fsq_action_name == "uiSnapshot"
    assert schemas["ui_snapshot"].capture_evidence is False


def test_windows_harness_validation_failure_does_not_call_driver_method() -> None:
    driver = FakeWindowsDriver()
    harness = WindowsHarness(driver=driver)

    result = harness.invoke_action(_step("clickOn", {"locator": {"unknown": "Login"}}), harness.get_context())

    assert result.status == "failed"
    assert result.failure_category == "configuration_error"
    assert result.error_message == "Invalid Windows parameters for clickOn."
    assert result.metadata["validation_errors"]
    assert driver.calls == [("context", None)]


def test_windows_harness_captures_screenshot_and_ui_snapshot_with_artifact_store(tmp_path) -> None:
    driver = FakeWindowsDriver()
    harness = WindowsHarness(driver=driver, artifact_store=ArtifactStore(run_dir=tmp_path))
    context = harness.get_context()

    screenshot_ref = harness.capture_artifact(
        kind="screenshot",
        reason="after click",
        context=context,
        step_id="step-1",
        phase="invoke",
    )
    snapshot_ref = harness.capture_artifact(
        kind="ui_snapshot",
        reason="after click",
        context=context,
        step_id="step-1",
        phase="finalize",
    )

    assert (tmp_path / screenshot_ref.path).read_bytes() == b"fake-png"
    assert "Notepad" in (tmp_path / snapshot_ref.path).read_text(encoding="utf-8")
    assert driver.calls == [("context", None), ("screenshot", None), ("ui_snapshot", {})]


def test_windows_harness_assert_with_ai_uses_injected_evaluator(tmp_path) -> None:
    class FakeEvaluator:
        def __init__(self) -> None:
            self.requests: list[AIAssertionRequest] = []

        def evaluate(self, request: AIAssertionRequest) -> AIAssertionResult:
            self.requests.append(request)
            return AIAssertionResult(
                status="passed",
                passed=True,
                explanation="The expected window is visible.",
                provider="fake",
                model="fake-model",
                artifact_refs=[request.screenshot_artifact_ref] if request.screenshot_artifact_ref else [],
            )

    evaluator = FakeEvaluator()
    harness = WindowsHarness(
        driver=FakeWindowsDriver(),
        artifact_store=ArtifactStore(run_dir=tmp_path),
        ai_assertion_evaluator=evaluator,
    )

    result = harness.invoke_action(_step("assertWithAI", {"prompt": "The Save dialog is visible."}), harness.get_context())

    assert result.status == "passed"
    assert result.action_name == "assertWithAI"
    assert len(evaluator.requests) == 1
    assert evaluator.requests[0].platform == "windows"
    assert evaluator.requests[0].prompt == "The Save dialog is visible."


def test_windows_harness_assert_with_ai_requires_evaluator() -> None:
    harness = WindowsHarness(driver=FakeWindowsDriver())

    result = harness.invoke_action(_step("assertWithAI", {"prompt": "anything"}), harness.get_context())

    assert result.status == "failed"
    assert result.failure_category == "configuration_error"


def test_windows_harness_rejects_unknown_action() -> None:
    harness = WindowsHarness(driver=FakeWindowsDriver())

    result = harness.invoke_action(_step("unsupportedAction", {}), harness.get_context())

    assert result.status == "failed"
    assert result.failure_category == "configuration_error"
    assert "Unsupported Windows action" in (result.error_message or "")


def test_pywinauto_driver_launch_app_uses_launch_args_and_window_title_re() -> None:
    from fsq_agent.core.harness._pywinauto_driver import PywinautoWindowsDriver
    from fsq_agent.models import WindowsLaunchAppParams

    class FakeWindow:
        def __init__(self) -> None:
            self.waited: list[str] = []

        def wait(self, state: str, timeout: float | None = None) -> "FakeWindow":
            self.waited.append(state)
            return self

    class FakeApp:
        def __init__(self, backend: str) -> None:
            self.backend = backend
            self.started_cmd: str | None = None
            self.connected_title_re: str | None = None
            self.window_title_re: str | None = None
            self.window_control_type: str | None = None
            self.window_obj = FakeWindow()

        def start(self, cmd: str) -> "FakeApp":
            self.started_cmd = cmd
            return self

        def connect(self, title_re: str) -> "FakeApp":
            self.connected_title_re = title_re
            return self

        def window(self, title_re: str, control_type: str | None = None) -> FakeWindow:
            self.window_title_re = title_re
            self.window_control_type = control_type
            return self.window_obj

        def top_window(self) -> FakeWindow:
            return self.window_obj

    fake_app = FakeApp(backend="uia")

    driver = PywinautoWindowsDriver(
        app_path="msedge.exe",
        window_title_re=".*Microsoft.*Edge Beta",
        launch_args=["--no-first-run", "--window-size=1280,920"],
        window=object(),
    )
    driver._application_cls = lambda: (lambda backend: fake_app)  # type: ignore[attr-defined]

    result = driver.launch_app(WindowsLaunchAppParams(extra_args=["--incognito"]))

    assert result["status"] == "passed"
    assert fake_app.started_cmd == "msedge.exe --no-first-run --window-size=1280,920 --incognito"
    assert fake_app.connected_title_re == ".*Microsoft.*Edge Beta"
    assert fake_app.window_title_re == ".*Microsoft.*Edge Beta"
    assert fake_app.window_control_type == "Window"
    assert fake_app.window_obj.waited == ["exists visible enabled"]
    assert driver._window is fake_app.window_obj
