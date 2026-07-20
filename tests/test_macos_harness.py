from typing import Any

import pytest

from fsq_agent.core import ArtifactStore, HarnessInterface
from fsq_agent.core.harness._ai_assertion_tool import AIAssertionBackendToolMixin
from fsq_agent.core.harness._appium_mac2_driver import AppiumMac2Driver
from fsq_agent.core.harness._macos import MacOSHarness
from fsq_agent.core.harness._driver_tools import _macos_driver_tool
from fsq_agent.models import (
    AIAssertionRequest,
    AIAssertionResult,
    ConfigurationError,
    ExecutableStep,
    HarnessContext,
    MacOSAssertElementsOrderParams,
    MacOSAssertVisibleParams,
    MacOSAssertWithAIParams,
    MacOSClickOnParams,
    MacOSDoubleClickOnParams,
    MacOSDragToParams,
    MacOSHoverOnParams,
    MacOSKillAppParams,
    MacOSLaunchAppParams,
    MacOSPressKeyParams,
    MacOSRightClickOnParams,
    MacOSTakeScreenshotParams,
    MacOSTypeTextParams,
    MacOSUiSnapshotParams,
)


class FakeMacOSDriver(AIAssertionBackendToolMixin):
    backend = "fake-appium-mac2"

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def context(self) -> dict[str, object]:
        self.calls.append(("context", None))
        return {
            "session_id": "mac2:session",
            "current_url": None,
            "screen_size": (1440, 900),
            "capabilities": {"platformName": "Mac"},
            "metadata": {"backend": self.backend, "bundle_id_configured": True},
        }

    def _record(self, method_name: str, params: object) -> dict[str, object]:
        recorded = params.model_dump(mode="json", exclude_none=True) if hasattr(params, "model_dump") else params
        self.calls.append((method_name, recorded))
        return {"status": "passed", "output": {method_name: True}}

    @_macos_driver_tool(
        "launchApp",
        description="Launch a configured macOS application.",
        capture_evidence=True,
        metadata={"evidence_capture_before": False, "evidence_capture_on_failure": False},
    )
    def launch_app(self, params: MacOSLaunchAppParams) -> dict[str, object]:
        return self._record("launch_app", params)

    @_macos_driver_tool("killApp", description="Stop the active macOS application.")
    def kill_app(self, params: MacOSKillAppParams) -> dict[str, object]:
        return self._record("kill_app", params)

    @_macos_driver_tool("clickOn", description="Click a macOS element or point.", capture_evidence=True)
    def click_on(self, params: MacOSClickOnParams) -> dict[str, object]:
        return self._record("click_on", params)

    @_macos_driver_tool("doubleClickOn", description="Double-click a macOS element or point.", capture_evidence=True)
    def double_click_on(self, params: MacOSDoubleClickOnParams) -> dict[str, object]:
        return self._record("double_click_on", params)

    @_macos_driver_tool("rightClickOn", description="Right-click a macOS element or point.", capture_evidence=True)
    def right_click_on(self, params: MacOSRightClickOnParams) -> dict[str, object]:
        return self._record("right_click_on", params)

    @_macos_driver_tool("typeText", description="Type text into macOS.", capture_evidence=True)
    def type_text(self, params: MacOSTypeTextParams) -> dict[str, object]:
        return self._record("type_text", params)

    @_macos_driver_tool("pressKey", description="Press a macOS key or shortcut.", capture_evidence=True)
    def press_key(self, params: MacOSPressKeyParams) -> dict[str, object]:
        return self._record("press_key", params)

    @_macos_driver_tool("hoverOn", description="Hover over a macOS element or point.")
    def hover_on(self, params: MacOSHoverOnParams) -> dict[str, object]:
        return self._record("hover_on", params)

    @_macos_driver_tool("dragTo", description="Drag between macOS elements or points.", capture_evidence=True)
    def drag_to(self, params: MacOSDragToParams) -> dict[str, object]:
        return self._record("drag_to", params)

    @_macos_driver_tool("takeScreenshot", description="Capture a macOS screenshot.")
    def take_screenshot(self, params: MacOSTakeScreenshotParams) -> bytes:
        recorded = params.model_dump(mode="json", exclude_none=True)
        self.calls.append(("take_screenshot", recorded))
        return b"fake-png"

    @_macos_driver_tool("uiSnapshot", description="Return the macOS accessibility tree.")
    def ui_snapshot(self, params: MacOSUiSnapshotParams) -> dict[str, object]:
        recorded = params.model_dump(mode="json", exclude_none=True)
        self.calls.append(("ui_snapshot", recorded))
        return {"title": "Finder", "snapshot_type": "macos_accessibility_tree"}

    @_macos_driver_tool("assertVisible", description="Assert a macOS element is visible.")
    def assert_visible(self, params: MacOSAssertVisibleParams) -> dict[str, object]:
        return self._record("assert_visible", params)

    @_macos_driver_tool("assertElementsOrder", description="Assert macOS elements appear in order.")
    def assert_elements_order(self, params: MacOSAssertElementsOrderParams) -> dict[str, object]:
        return self._record("assert_elements_order", params)

    @_macos_driver_tool("assertWithAI", description="Evaluate a macOS visual assertion with AI.")
    def assert_with_ai(self, params: MacOSAssertWithAIParams) -> dict[str, object]:
        return self._run_ai_assertion_tool(params)

    def screenshot(self, params: object | None = None) -> bytes:
        recorded = params.model_dump(mode="json", exclude_none=True) if hasattr(params, "model_dump") else None
        self.calls.append(("screenshot", recorded))
        return b"fake-png"


def _step(action_name: str, params: dict[str, Any] | None = None) -> ExecutableStep:
    return ExecutableStep(step_id="step-1", kind="action", action_name=action_name, params=params or {})


def test_macos_harness_dispatches_fsq_action_names_to_driver() -> None:
    driver = FakeMacOSDriver()
    harness = MacOSHarness(driver=driver)

    context = harness.get_context()

    cases = [
        ("launchApp", {"bundle_id": "com.example.MacApp"}, "launch_app"),
        ("clickOn", {"target": "File"}, "click_on"),
        ("doubleClickOn", {"locator": {"accessibilityId": "Open"}}, "double_click_on"),
        ("rightClickOn", {"point": {"x": 10, "y": 20}}, "right_click_on"),
        ("typeText", {"target": "Search", "text": "hello"}, "type_text"),
        ("pressKey", {"key": "Enter"}, "press_key"),
        ("hoverOn", {"target": "Menu"}, "hover_on"),
        ("dragTo", {"source": {"point": {"x": 1, "y": 2}}, "destination": {"target": "Trash"}}, "drag_to"),
        ("takeScreenshot", {}, "take_screenshot"),
        ("uiSnapshot", {}, "ui_snapshot"),
        ("assertVisible", {"target": "Save"}, "assert_visible"),
        ("assertElementsOrder", {"elements": [{"target": "File"}, {"target": "Edit"}]}, "assert_elements_order"),
        ("killApp", {}, "kill_app"),
    ]

    for action_name, params, _method_name in cases:
        result = harness.invoke_action(_step(action_name, params), context)
        assert result.status == "passed"
        assert result.action_name == action_name

    assert isinstance(harness, HarnessInterface)
    assert context == HarnessContext(
        platform="macos",
        session_id="mac2:session",
        current_url=None,
        screen_size=(1440, 900),
        capabilities={"platformName": "Mac"},
        metadata={"backend": "fake-appium-mac2", "bundle_id_configured": True},
    )
    assert [method_name for method_name, _params in driver.calls] == ["context"] + [method_name for _action, _params, method_name in cases]


def test_macos_harness_action_space_returns_catalog_backed_schemas() -> None:
    harness = MacOSHarness(driver=FakeMacOSDriver())

    schemas = {schema.name: schema for schema in harness.action_space()}

    assert "click_on" in schemas
    assert "ui_snapshot" in schemas
    assert "assert_elements_order" in schemas
    assert "assert_with_ai" not in schemas
    assert schemas["click_on"].driver_method == "click_on"
    assert schemas["click_on"].fsq_action_name == "clickOn"
    assert schemas["click_on"].platform == "macos"
    assert schemas["click_on"].capture_evidence is True
    assert schemas["click_on"].metadata["driver_class"] == "FakeMacOSDriver"
    assert schemas["click_on"].metadata["backend"] == "fake-appium-mac2"
    assert schemas["click_on"].metadata["replay"] == {"kind": "fsq_command", "alias": "clickOn"}
    assert "target" in schemas["click_on"].params_json_schema["properties"]
    assert schemas["ui_snapshot"].driver_method == "ui_snapshot"
    assert schemas["ui_snapshot"].fsq_action_name == "uiSnapshot"
    assert schemas["ui_snapshot"].capture_evidence is False
    assert schemas["assert_elements_order"].fsq_action_name == "assertElementsOrder"


def test_macos_harness_validation_failure_does_not_call_driver_method() -> None:
    driver = FakeMacOSDriver()
    harness = MacOSHarness(driver=driver)

    result = harness.invoke_action(_step("clickOn", {"locator": {"unknown": "Login"}}), harness.get_context())

    assert result.status == "failed"
    assert result.failure_category == "configuration_error"
    assert result.error_message == "Invalid macOS parameters for clickOn."
    assert result.metadata["validation_errors"]
    assert driver.calls == [("context", None)]


def test_macos_harness_captures_screenshot_and_ui_snapshot_with_artifact_store(tmp_path) -> None:
    driver = FakeMacOSDriver()
    harness = MacOSHarness(driver=driver, artifact_store=ArtifactStore(run_dir=tmp_path))
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
    assert "Finder" in (tmp_path / snapshot_ref.path).read_text(encoding="utf-8")
    assert driver.calls[0] == ("context", None)
    assert ("screenshot", {}) in driver.calls
    assert ("ui_snapshot", {}) in driver.calls


def test_macos_harness_reports_unlaunched_session_without_implicit_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    driver = AppiumMac2Driver(bundle_id="com.example.MacApp")
    called = False

    def fake_ensure_session(params=None):
        nonlocal called
        called = True
        return FakeMacSession({})

    monkeypatch.setattr(driver, "_ensure_session", fake_ensure_session)
    harness = MacOSHarness(driver=driver)

    result = harness.invoke_action(_step("uiSnapshot", {}), harness.get_context())

    assert result.status == "failed"
    assert result.failure_category == "configuration_error"
    assert result.error_message == "Appium Mac2 session is not available. Call launchApp before macOS Appium actions."
    assert called is False


def test_macos_harness_records_unavailable_artifact_before_launch(tmp_path) -> None:
    harness = MacOSHarness(driver=AppiumMac2Driver(bundle_id="com.example.MacApp"), artifact_store=ArtifactStore(run_dir=tmp_path))

    artifact_ref = harness.capture_artifact(
        kind="ui_snapshot",
        reason="before click",
        context=harness.get_context(),
        step_id="step-1",
        phase="prepare",
    )

    payload = (tmp_path / artifact_ref.path).read_text(encoding="utf-8")
    assert artifact_ref.kind == "json"
    assert "macos_session_not_started" in payload


def test_macos_harness_assert_with_ai_uses_injected_evaluator(tmp_path) -> None:
    class FakeEvaluator:
        def __init__(self) -> None:
            self.requests: list[AIAssertionRequest] = []

        def evaluate(self, request: AIAssertionRequest) -> AIAssertionResult:
            self.requests.append(request)
            return AIAssertionResult(
                status="passed",
                passed=True,
                explanation="The expected macOS window is visible.",
                provider="fake",
                model="fake-model",
                artifact_refs=[request.screenshot_artifact_ref] if request.screenshot_artifact_ref else [],
            )

    evaluator = FakeEvaluator()
    harness = MacOSHarness(
        driver=FakeMacOSDriver(),
        artifact_store=ArtifactStore(run_dir=tmp_path),
        ai_assertion_evaluator=evaluator,
    )

    result = harness.invoke_action(_step("assertWithAI", {"prompt": "The Save dialog is visible."}), harness.get_context())

    assert result.status == "passed"
    assert result.action_name == "assertWithAI"
    assert len(evaluator.requests) == 1
    assert evaluator.requests[0].platform == "macos"
    assert evaluator.requests[0].prompt == "The Save dialog is visible."


def test_macos_harness_assert_with_ai_requires_evaluator() -> None:
    harness = MacOSHarness(driver=FakeMacOSDriver())

    result = harness.invoke_action(_step("assertWithAI", {"prompt": "anything"}), harness.get_context())

    assert result.status == "failed"
    assert result.failure_category == "configuration_error"


def test_macos_harness_rejects_unknown_action() -> None:
    harness = MacOSHarness(driver=FakeMacOSDriver())

    result = harness.invoke_action(_step("unsupportedAction", {}), harness.get_context())

    assert result.status == "failed"
    assert result.failure_category == "configuration_error"
    assert "Unsupported macOS action" in (result.error_message or "")


class FakeMacElement:
    def __init__(self, *, x: int, y: int, width: int = 10, height: int = 10) -> None:
        self.rect = {"x": x, "y": y, "width": width, "height": height}


class FakeMacSession:
    def __init__(self, elements: dict[str, FakeMacElement], *, page_source: str = "", session_id: str = "mac2:session") -> None:
        self.elements = elements
        self.page_source = page_source
        self.session_id = session_id

    def find_element(self, strategy: str, locator: str) -> FakeMacElement:
        if strategy == "accessibility id" and locator in self.elements:
            return self.elements[locator]
        raise RuntimeError("not found")


def test_appium_mac2_driver_assert_elements_order_returns_structured_pass_output() -> None:
    driver = AppiumMac2Driver(
        session=FakeMacSession(
            {
                "First": FakeMacElement(x=10, y=10),
                "Second": FakeMacElement(x=10, y=40),
            }
        )
    )

    result = driver.assert_elements_order(
        MacOSAssertElementsOrderParams.model_validate({"elements": [{"target": "First"}, {"target": "Second"}]})
    )

    assert result["status"] == "passed"
    assert result["output"] == {
        "direction": "vertical",
        "elements_found": 2,
        "elements_total": 2,
        "actual_order": [0, 1],
        "expected_order": [0, 1],
        "positions": [
            {"index": 0, "coordinate": 15.0, "rect": {"x": 10.0, "y": 10.0, "width": 10.0, "height": 10.0}},
            {"index": 1, "coordinate": 45.0, "rect": {"x": 10.0, "y": 40.0, "width": 10.0, "height": 10.0}},
        ],
    }


def test_appium_mac2_driver_assert_elements_order_fails_on_wrong_order() -> None:
    driver = AppiumMac2Driver(
        session=FakeMacSession(
            {
                "First": FakeMacElement(x=10, y=10),
                "Second": FakeMacElement(x=40, y=10),
            }
        )
    )

    result = driver.assert_elements_order(
        MacOSAssertElementsOrderParams.model_validate(
            {"elements": [{"target": "First"}, {"target": "Second"}], "direction": "horizontal", "expected_order": [1, 0]}
        )
    )

    assert result["status"] == "failed"
    assert result["failure_category"] == "assertion_error"
    assert result["output"]["direction"] == "horizontal"
    assert result["output"]["actual_order"] == [0, 1]
    assert result["output"]["expected_order"] == [1, 0]


def test_appium_mac2_driver_assert_elements_order_reports_missing_required_elements() -> None:
    driver = AppiumMac2Driver(session=FakeMacSession({"First": FakeMacElement(x=10, y=10)}))

    result = driver.assert_elements_order(
        MacOSAssertElementsOrderParams.model_validate({"elements": [{"target": "First"}, {"target": "Missing"}]})
    )

    assert result["status"] == "failed"
    assert result["failure_category"] == "target_resolution_error"
    assert result["metadata"] == {"missing_indexes": [1]}
    assert result["output"]["elements_found"] == 1
    assert result["output"]["elements_total"] == 2


def test_appium_mac2_driver_ui_snapshot_simplifies_page_source_to_max_depth() -> None:
    driver = AppiumMac2Driver(
        session=FakeMacSession(
            {},
            page_source=(
                '<AppiumAUT name="Root">'
                '<Window name="Main"><Group name="Toolbar"><Button name="Save" custom="hidden" /></Group></Window>'
                '<Window name="Other" />'
                '</AppiumAUT>'
            ),
        ),
        page_source_max_depth=2,
    )

    snapshot = driver.ui_snapshot(MacOSUiSnapshotParams())

    assert "source" not in snapshot
    assert snapshot["snapshot_type"] == "macos_accessibility_tree"
    assert snapshot["max_depth"] == 2
    page_source = snapshot["page_source"]
    assert page_source["format"] == "xml"
    assert page_source["node_count"] == 5
    assert page_source["root"] == {
        "type": "AppiumAUT",
        "attributes": {"name": "Root"},
        "children": [
            {"type": "Window", "attributes": {"name": "Main"}, "children_truncated": 1},
            {"type": "Window", "attributes": {"name": "Other"}},
        ],
    }


def test_appium_mac2_driver_requires_explicit_launch_before_session_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    driver = AppiumMac2Driver(bundle_id="com.example.MacApp")
    called = False

    def fake_ensure_session(params=None):
        nonlocal called
        called = True
        return FakeMacSession({})

    monkeypatch.setattr(driver, "_ensure_session", fake_ensure_session)

    with pytest.raises(ConfigurationError, match="Call launchApp before macOS Appium actions"):
        driver.ui_snapshot(MacOSUiSnapshotParams())

    assert called is False