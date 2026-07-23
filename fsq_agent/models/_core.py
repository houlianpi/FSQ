from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


StepPhase: TypeAlias = Literal["prepare", "invoke", "finalize"]
RunnerStatus: TypeAlias = Literal["pending", "running", "passed", "failed", "skipped", "cancelled"]
ExecutableStepKind: TypeAlias = Literal["action", "assertion", "observation", "diagnostic", "setup", "teardown"]
FailureCategory: TypeAlias = Literal[
    "configuration_error",
    "context_error",
    "target_resolution_error",
    "action_error",
    "assertion_error",
    "timeout_error",
    "observation_error",
    "artifact_error",
    "harness_error",
    "cancelled",
    "unknown",
]
RunnerEventType: TypeAlias = Literal[
    "session_start",
    "session_finish",
    "step_start",
    "phase_start",
    "harness_call_start",
    "harness_call_finish",
    "artifact_captured",
    "phase_finish",
    "step_error",
    "step_finish",
]
EvidenceArtifactKind: TypeAlias = Literal["screenshot", "ui_tree", "page_snapshot", "ui_snapshot", "tool_call", "log", "json", "text", "other"]
HarnessPlatform: TypeAlias = Literal["android", "ios", "macos", "windows", "web"]
AndroidSwipeDirection: TypeAlias = Literal["up", "down", "left", "right"]
WebMouseButton: TypeAlias = Literal["left", "right", "middle"]
WebWaitUntil: TypeAlias = Literal["commit", "domcontentloaded", "load", "networkidle"]
WebWaitForState: TypeAlias = Literal["visible", "hidden", "attached", "detached"]
WindowsMouseButton: TypeAlias = Literal["left", "right", "middle"]
MacOSOrderDirection: TypeAlias = Literal["vertical", "horizontal"]


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_id: str | None = None
    step_index: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=1, ge=1)
    delay_ms: int = Field(default=0, ge=0)
    retry_on: list[FailureCategory] = Field(default_factory=list)


class EvidencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capture_before: bool = False
    capture_after: bool = True
    capture_on_failure: bool = True
    artifact_kinds: list[EvidenceArtifactKind] = Field(default_factory=list)


class ExecutableStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    source_ref: SourceRef | None = None
    kind: ExecutableStepKind
    action_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    target_ref: str | None = None
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    evidence_policy: EvidencePolicy = Field(default_factory=EvidencePolicy)
    timeout_ms: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HarnessArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: EvidenceArtifactKind
    path: Path
    mime_type: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("path", when_used="json")
    def serialize_path(self, value: Path) -> str:
        return value.as_posix()


class HarnessContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: HarnessPlatform
    session_id: str | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    current_url: str | None = None
    current_activity: str | None = None
    screen_size: tuple[int, int] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HarnessActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RunnerStatus
    action_name: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = Field(default=0, ge=0)
    output: Any = None
    artifact_refs: list[HarnessArtifactRef] = Field(default_factory=list)
    error_message: str | None = None
    failure_category: FailureCategory | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HarnessFunctionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    params_json_schema: dict[str, Any] = Field(default_factory=dict)
    platform: HarnessPlatform
    driver_method: str
    fsq_action_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AndroidLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resourceId: str | None = None
    accessibilityId: str | None = None
    text: str | None = None
    className: str | None = None
    xpath: str | None = None

    def has_value(self) -> bool:
        return any(isinstance(value, str) and value.strip() for value in self.model_dump().values())


class RuntimeSecretRef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    env_name: str = Field(alias="runtimeSecret")

    @model_validator(mode="after")
    def _require_env_name(self) -> "RuntimeSecretRef":
        if self.env_name.strip():
            return self
        raise ValueError("requires non-empty runtimeSecret name")


class WaitMsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_ms: int = Field(ge=1, le=60000)
    reason: str | None = None


class AndroidPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int
    y: int


class AndroidScreenSize(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(ge=1)
    height: int = Field(ge=1)


class _AndroidTargetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str | None = None
    locator: AndroidLocator | None = None

    @model_validator(mode="after")
    def _require_target(self) -> "_AndroidTargetParams":
        if self._has_target_value():
            return self
        raise ValueError("requires target or non-empty locator")

    def _has_target_value(self) -> bool:
        if isinstance(self.target, str) and self.target.strip():
            return True
        return self.locator is not None and self.locator.has_value()


class AndroidLaunchAppParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str | None = None


class AndroidKillAppParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str | None = None


class AndroidTapOnParams(_AndroidTargetParams):
    pass


class AndroidTapAtParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point: AndroidPoint
    reference_screen_size: AndroidScreenSize | None = None


class AndroidLongPressOnParams(_AndroidTargetParams):
    pass


class AndroidInputTextParams(_AndroidTargetParams):
    text: str


class AndroidPressKeyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str

    @model_validator(mode="after")
    def _require_key(self) -> "AndroidPressKeyParams":
        if self.key.strip():
            return self
        raise ValueError("requires non-empty key")


class AndroidSwipeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: AndroidSwipeDirection | None = None
    start: AndroidPoint | None = None
    end: AndroidPoint | None = None
    reference_screen_size: AndroidScreenSize | None = None
    duration: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _require_direction_or_points(self) -> "AndroidSwipeParams":
        has_direction = self.direction is not None
        has_points = self.start is not None and self.end is not None
        if has_direction or has_points:
            return self
        raise ValueError("requires direction or both start and end points")


class AndroidUiTreeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AndroidPerformActionsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[dict[str, Any]]


class AndroidAssertVisibleParams(_AndroidTargetParams):
    optional: bool | None = None


class AndroidAssertNotVisibleParams(_AndroidTargetParams):
    optional: bool | None = None


class AndroidTextAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contains: str | None = None
    equals: str | None = None

    @model_validator(mode="after")
    def _require_text_assertion(self) -> "AndroidTextAssertion":
        if isinstance(self.contains, str) or isinstance(self.equals, str):
            return self
        raise ValueError("requires contains or equals")


class AndroidElementState(AndroidLocator):
    enabled: bool | None = None
    checked: bool | None = None
    selected: bool | None = None
    clickable: bool | None = None
    focused: bool | None = None

    def has_state_assertion(self) -> bool:
        return any(
            value is not None
            for value in [self.enabled, self.checked, self.selected, self.clickable, self.focused]
        )


class AndroidAssertStateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element: AndroidElementState | None = None
    text: AndroidTextAssertion | None = None
    optional: bool | None = None

    @model_validator(mode="after")
    def _require_assertion(self) -> "AndroidAssertStateParams":
        if self.text is not None:
            return self
        if self.element is not None and (self.element.has_value() or self.element.has_state_assertion()):
            return self
        raise ValueError("requires text assertion or element locator/state assertion")


class AndroidAssertWithAIParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    optional: bool | None = None

    @model_validator(mode="after")
    def _require_prompt(self) -> "AndroidAssertWithAIParams":
        if self.prompt.strip():
            return self
        raise ValueError("requires non-empty prompt")


class WebLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = None
    name: str | None = None
    text: str | None = None
    label: str | None = None
    placeholder: str | None = None
    testId: str | None = None
    css: str | None = None
    xpath: str | None = None
    altText: str | None = None
    title: str | None = None

    def has_value(self) -> bool:
        return any(isinstance(value, str) and value.strip() for value in self.model_dump().values())


class _WebTargetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str | None = None
    locator: WebLocator | None = None

    @model_validator(mode="after")
    def _require_target(self) -> "_WebTargetParams":
        if self._has_target_value():
            return self
        raise ValueError("requires target or non-empty locator")

    def _has_target_value(self) -> bool:
        if isinstance(self.target, str) and self.target.strip():
            return True
        return self.locator is not None and self.locator.has_value()


class WebStartBrowserParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WebCloseBrowserParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WebNavigateToParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    waitUntil: WebWaitUntil | None = None

    @model_validator(mode="after")
    def _require_url(self) -> "WebNavigateToParams":
        if self.url.strip():
            return self
        raise ValueError("requires non-empty url")


class WebNavigateBackParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    waitUntil: WebWaitUntil | None = None


class WebClickOnParams(_WebTargetParams):
    button: WebMouseButton | None = None
    double: bool | None = None


class WebTypeTextParams(_WebTargetParams):
    text: str
    clear: bool | None = None

    @model_validator(mode="after")
    def _require_text(self) -> "WebTypeTextParams":
        if isinstance(self.text, str):
            return self
        raise ValueError("requires text")


class WebSelectOptionParams(_WebTargetParams):
    value: str | None = None
    label: str | None = None
    index: int | None = Field(default=None, ge=0)
    values: list[str] | None = None

    @model_validator(mode="after")
    def _require_option(self) -> "WebSelectOptionParams":
        has_single = any(isinstance(value, str) and value.strip() for value in [self.value, self.label])
        has_index = self.index is not None
        has_values = self.values is not None and any(isinstance(value, str) and value.strip() for value in self.values)
        if has_single or has_index or has_values:
            return self
        raise ValueError("requires value, label, index, or values")


class WebHoverOnParams(_WebTargetParams):
    pass


class WebPressKeyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str

    @model_validator(mode="after")
    def _require_key(self) -> "WebPressKeyParams":
        if self.key.strip():
            return self
        raise ValueError("requires non-empty key")


class WebWaitForParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str | None = None
    locator: WebLocator | None = None
    text: str | None = None
    url: str | None = None
    state: WebWaitForState | None = None
    timeout_ms: int | None = Field(default=None, ge=1, le=60000)

    @model_validator(mode="after")
    def _require_wait_condition(self) -> "WebWaitForParams":
        if isinstance(self.target, str) and self.target.strip():
            return self
        if self.locator is not None and self.locator.has_value():
            return self
        if isinstance(self.text, str) and self.text.strip():
            return self
        if isinstance(self.url, str) and self.url.strip():
            return self
        if self.timeout_ms is not None:
            return self
        raise ValueError("requires target, locator, text, url, or timeout_ms")


class WebTakeScreenshotParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fullPage: bool | None = None
    omitBackground: bool | None = None


class WebPageSnapshotParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WebAssertVisibleParams(_WebTargetParams):
    optional: bool | None = None


class WebAssertNotVisibleParams(_WebTargetParams):
    optional: bool | None = None


class WebTextAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contains: str | None = None
    equals: str | None = None

    @model_validator(mode="after")
    def _require_text_assertion(self) -> "WebTextAssertion":
        if isinstance(self.contains, str) or isinstance(self.equals, str):
            return self
        raise ValueError("requires contains or equals")


class WebAssertTextParams(_WebTargetParams):
    text: WebTextAssertion
    optional: bool | None = None


class WebAssertWithAIParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    optional: bool | None = None

    @model_validator(mode="after")
    def _require_prompt(self) -> "WebAssertWithAIParams":
        if self.prompt.strip():
            return self
        raise ValueError("requires non-empty prompt")


@dataclass(frozen=True)
class AndroidActionDefinition:
    fsq_action_name: str
    driver_method: str
    params_model: type[BaseModel]
    step_kind: ExecutableStepKind
    owner: Literal["driver", "platform", "harness"] = "driver"


ANDROID_ACTION_DEFINITIONS: tuple[AndroidActionDefinition, ...] = (
    AndroidActionDefinition("launchApp", "launch_app", AndroidLaunchAppParams, "setup"),
    AndroidActionDefinition("killApp", "kill_app", AndroidKillAppParams, "teardown"),
    AndroidActionDefinition("tapOn", "tap_on", AndroidTapOnParams, "action"),
    AndroidActionDefinition("tapAt", "tap_at", AndroidTapAtParams, "action"),
    AndroidActionDefinition("assertVisible", "assert_visible", AndroidAssertVisibleParams, "assertion"),
    AndroidActionDefinition("performActions", "perform_actions", AndroidPerformActionsParams, "action"),
    AndroidActionDefinition("assert", "assert_state", AndroidAssertStateParams, "assertion"),
    AndroidActionDefinition("pressKey", "press_key", AndroidPressKeyParams, "action"),
    AndroidActionDefinition("inputText", "input_text", AndroidInputTextParams, "action"),
    AndroidActionDefinition("assertNotVisible", "assert_not_visible", AndroidAssertNotVisibleParams, "assertion"),
    AndroidActionDefinition("longPressOn", "long_press_on", AndroidLongPressOnParams, "action"),
    AndroidActionDefinition("swipe", "swipe", AndroidSwipeParams, "action"),
    AndroidActionDefinition("uiTree", "ui_snapshot", AndroidUiTreeParams, "observation"),
    AndroidActionDefinition("assertWithAI", "assert_with_ai", AndroidAssertWithAIParams, "assertion"),
)
ANDROID_ACTION_DEFINITIONS_BY_NAME: dict[str, AndroidActionDefinition] = {
    definition.fsq_action_name: definition for definition in ANDROID_ACTION_DEFINITIONS
}


@dataclass(frozen=True)
class WebActionDefinition:
    fsq_action_name: str
    driver_method: str
    params_model: type[BaseModel]
    step_kind: ExecutableStepKind
    owner: Literal["driver", "platform", "harness"] = "driver"


WEB_ACTION_DEFINITIONS: tuple[WebActionDefinition, ...] = (
    WebActionDefinition("startBrowser", "start_browser", WebStartBrowserParams, "setup"),
    WebActionDefinition("closeBrowser", "close_browser", WebCloseBrowserParams, "teardown"),
    WebActionDefinition("navigateTo", "navigate_to", WebNavigateToParams, "action"),
    WebActionDefinition("navigateBack", "navigate_back", WebNavigateBackParams, "action"),
    WebActionDefinition("clickOn", "click_on", WebClickOnParams, "action"),
    WebActionDefinition("typeText", "type_text", WebTypeTextParams, "action"),
    WebActionDefinition("selectOption", "select_option", WebSelectOptionParams, "action"),
    WebActionDefinition("hoverOn", "hover_on", WebHoverOnParams, "action"),
    WebActionDefinition("pressKey", "press_key", WebPressKeyParams, "action"),
    WebActionDefinition("waitFor", "wait_for", WebWaitForParams, "action"),
    WebActionDefinition("takeScreenshot", "take_screenshot", WebTakeScreenshotParams, "observation"),
    WebActionDefinition("pageSnapshot", "page_snapshot", WebPageSnapshotParams, "observation"),
    WebActionDefinition("assertVisible", "assert_visible", WebAssertVisibleParams, "assertion"),
    WebActionDefinition("assertNotVisible", "assert_not_visible", WebAssertNotVisibleParams, "assertion"),
    WebActionDefinition("assertText", "assert_text", WebAssertTextParams, "assertion"),
    WebActionDefinition("assertWithAI", "assert_with_ai", WebAssertWithAIParams, "assertion"),
)
WEB_ACTION_DEFINITIONS_BY_NAME: dict[str, WebActionDefinition] = {
    definition.fsq_action_name: definition for definition in WEB_ACTION_DEFINITIONS
}


class WindowsLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    control_type: str | None = None
    automation_id: str | None = None
    class_name: str | None = None
    index: int | None = Field(default=None, ge=1)
    parent_title: str | None = None
    parent_control_type: str | None = None
    parent_automation_id: str | None = None

    def has_value(self) -> bool:
        return any(
            isinstance(value, str) and value.strip()
            for value in (self.title, self.control_type, self.automation_id, self.class_name)
        )


class _WindowsTargetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    locator: WindowsLocator

    @model_validator(mode="after")
    def _require_target(self) -> "_WindowsTargetParams":
        if not self._has_target_value():
            raise ValueError("requires non-empty target")
        if not self.locator.has_value():
            raise ValueError("requires non-empty locator")
        return self

    def _has_target_value(self) -> bool:
        return bool(self.target.strip())


class WindowsPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)


class WindowsOffset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int = 0
    y: int = 0

    @model_validator(mode="after")
    def _require_non_zero_offset(self) -> "WindowsOffset":
        if self.x != 0 or self.y != 0:
            return self
        raise ValueError("requires non-zero offset")


class WindowsMouseSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locator: WindowsLocator | None = None
    point: WindowsPoint | None = None

    @model_validator(mode="after")
    def _require_exactly_one_mode(self) -> "WindowsMouseSource":
        if sum(value is not None for value in (self.locator, self.point)) != 1:
            raise ValueError("requires exactly one of locator or point")
        if self.locator is not None and not self.locator.has_value():
            raise ValueError("requires non-empty locator")
        return self


class WindowsMouseDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locator: WindowsLocator | None = None
    point: WindowsPoint | None = None
    offset: WindowsOffset | None = None

    @model_validator(mode="after")
    def _require_exactly_one_mode(self) -> "WindowsMouseDestination":
        if sum(value is not None for value in (self.locator, self.point, self.offset)) != 1:
            raise ValueError("requires exactly one of locator, point, or offset")
        if self.locator is not None and not self.locator.has_value():
            raise ValueError("requires non-empty locator")
        return self


class WindowsLaunchAppParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extra_args: list[str] | None = None


class WindowsKillAppParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WindowsClickOnParams(_WindowsTargetParams):
    button: WindowsMouseButton | None = None
    double: bool | None = None


class WindowsDoubleClickOnParams(_WindowsTargetParams):
    button: WindowsMouseButton | None = None


class WindowsRightClickOnParams(_WindowsTargetParams):
    pass


class WindowsTypeTextParams(_WindowsTargetParams):
    text: str
    clear: bool | None = None

    @model_validator(mode="after")
    def _require_text(self) -> "WindowsTypeTextParams":
        if isinstance(self.text, str):
            return self
        raise ValueError("requires text")


class WindowsPressKeyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str

    @model_validator(mode="after")
    def _require_key(self) -> "WindowsPressKeyParams":
        if self.key.strip():
            return self
        raise ValueError("requires non-empty key")


class WindowsHoverOnParams(_WindowsTargetParams):
    pass


class WindowsScrollOnParams(_WindowsTargetParams):
    wheel_dist: int

    @model_validator(mode="after")
    def _require_wheel_distance(self) -> "WindowsScrollOnParams":
        if self.wheel_dist != 0:
            return self
        raise ValueError("requires non-zero wheel_dist")


class WindowsDragToParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    source: WindowsMouseSource
    destination: WindowsMouseDestination
    mouse_button: WindowsMouseButton = "left"

    @model_validator(mode="after")
    def _require_target(self) -> "WindowsDragToParams":
        if self.target.strip():
            return self
        raise ValueError("requires non-empty target")


class WindowsAssertVisibleParams(_WindowsTargetParams):
    optional: bool | None = None


class WindowsUiSnapshotParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WindowsAssertWithAIParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    optional: bool | None = None

    @model_validator(mode="after")
    def _require_prompt(self) -> "WindowsAssertWithAIParams":
        if self.prompt.strip():
            return self
        raise ValueError("requires non-empty prompt")


class MacOSPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int
    y: int


class MacOSLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accessibilityId: str | None = None
    name: str | None = None
    label: str | None = None
    value: str | None = None
    role: str | None = None
    controlType: str | None = None
    className: str | None = None
    xpath: str | None = None
    predicate: str | None = None
    point: MacOSPoint | None = None

    def has_value(self) -> bool:
        if self.point is not None:
            return True
        return any(
            isinstance(value, str) and value.strip()
            for value in (
                self.accessibilityId,
                self.name,
                self.label,
                self.value,
                self.role,
                self.controlType,
                self.className,
                self.xpath,
                self.predicate,
            )
        )


class _MacOSTargetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str | None = None
    locator: MacOSLocator | None = None
    point: MacOSPoint | None = None

    @model_validator(mode="after")
    def _require_target(self) -> "_MacOSTargetParams":
        if self._has_target_value():
            return self
        raise ValueError("requires target, non-empty locator, or point")

    def _has_target_value(self) -> bool:
        if isinstance(self.target, str) and self.target.strip():
            return True
        if self.locator is not None and self.locator.has_value():
            return True
        return self.point is not None


class _MacOSElementRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str | None = None
    locator: MacOSLocator | None = None

    @model_validator(mode="after")
    def _require_element_ref(self) -> "_MacOSElementRef":
        if isinstance(self.target, str) and self.target.strip():
            return self
        if self.locator is not None and self.locator.has_value():
            return self
        raise ValueError("requires target or non-empty locator")


class MacOSLaunchAppParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str | None = None
    app_path: str | None = None
    arguments: list[str] | None = None
    environment: dict[str, str] | None = None


class MacOSKillAppParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str | None = None
    close_session: bool | None = None


class MacOSClickOnParams(_MacOSTargetParams):
    modifiers: list[str] | None = None


class MacOSDoubleClickOnParams(_MacOSTargetParams):
    modifiers: list[str] | None = None


class MacOSRightClickOnParams(_MacOSTargetParams):
    modifiers: list[str] | None = None


class MacOSHoverOnParams(_MacOSTargetParams):
    duration_ms: int | None = Field(default=None, ge=1)


class MacOSTypeTextParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    target: str | None = None
    locator: MacOSLocator | None = None
    point: MacOSPoint | None = None
    clear: bool | None = None

    @model_validator(mode="after")
    def _require_text(self) -> "MacOSTypeTextParams":
        if isinstance(self.text, str):
            return self
        raise ValueError("requires text")


class MacOSPressKeyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    modifiers: list[str] | None = None

    @model_validator(mode="after")
    def _require_key(self) -> "MacOSPressKeyParams":
        if self.key.strip():
            return self
        raise ValueError("requires non-empty key")


class MacOSDragEndpoint(_MacOSTargetParams):
    pass


class MacOSDragToParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: MacOSDragEndpoint
    destination: MacOSDragEndpoint
    duration_ms: int | None = Field(default=None, ge=1)


class MacOSTakeScreenshotParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_screen: bool | None = None


class MacOSUiSnapshotParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_depth: int | None = Field(default=None, ge=1)
    include_attributes: bool | None = None


class MacOSAssertVisibleParams(_MacOSTargetParams):
    optional: bool | None = None


class MacOSAssertElementsOrderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    elements: list[_MacOSElementRef] = Field(min_length=2)
    direction: MacOSOrderDirection = "vertical"
    expected_order: list[int] | None = None
    tolerance: float | None = Field(default=None, ge=0)
    require_all: bool = True

    @model_validator(mode="after")
    def _validate_expected_order(self) -> "MacOSAssertElementsOrderParams":
        if self.expected_order is None:
            return self
        expected = self.expected_order
        if len(expected) != len(self.elements):
            raise ValueError("expected_order length must match elements length")
        if sorted(expected) != list(range(len(self.elements))):
            raise ValueError("expected_order must contain each zero-based element index exactly once")
        return self


class MacOSAssertWithAIParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    optional: bool | None = None

    @model_validator(mode="after")
    def _require_prompt(self) -> "MacOSAssertWithAIParams":
        if self.prompt.strip():
            return self
        raise ValueError("requires non-empty prompt")


@dataclass(frozen=True)
class MacOSActionDefinition:
    fsq_action_name: str
    driver_method: str
    params_model: type[BaseModel]
    step_kind: ExecutableStepKind
    owner: Literal["driver", "platform", "harness"] = "driver"


MACOS_ACTION_DEFINITIONS: tuple[MacOSActionDefinition, ...] = (
    MacOSActionDefinition("launchApp", "launch_app", MacOSLaunchAppParams, "setup"),
    MacOSActionDefinition("killApp", "kill_app", MacOSKillAppParams, "teardown"),
    MacOSActionDefinition("clickOn", "click_on", MacOSClickOnParams, "action"),
    MacOSActionDefinition("doubleClickOn", "double_click_on", MacOSDoubleClickOnParams, "action"),
    MacOSActionDefinition("rightClickOn", "right_click_on", MacOSRightClickOnParams, "action"),
    MacOSActionDefinition("typeText", "type_text", MacOSTypeTextParams, "action"),
    MacOSActionDefinition("pressKey", "press_key", MacOSPressKeyParams, "action"),
    MacOSActionDefinition("hoverOn", "hover_on", MacOSHoverOnParams, "action"),
    MacOSActionDefinition("dragTo", "drag_to", MacOSDragToParams, "action"),
    MacOSActionDefinition("takeScreenshot", "take_screenshot", MacOSTakeScreenshotParams, "observation"),
    MacOSActionDefinition("uiSnapshot", "ui_snapshot", MacOSUiSnapshotParams, "observation"),
    MacOSActionDefinition("assertVisible", "assert_visible", MacOSAssertVisibleParams, "assertion"),
    MacOSActionDefinition("assertElementsOrder", "assert_elements_order", MacOSAssertElementsOrderParams, "assertion"),
    MacOSActionDefinition("assertWithAI", "assert_with_ai", MacOSAssertWithAIParams, "assertion"),
)
MACOS_ACTION_DEFINITIONS_BY_NAME: dict[str, MacOSActionDefinition] = {
    definition.fsq_action_name: definition for definition in MACOS_ACTION_DEFINITIONS
}


class StepCallInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: StepPhase
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = Field(default=0, ge=0)
    status: RunnerStatus
    return_value: Any = None
    exception_type: str | None = None
    exception_message: str | None = None
    failure_category: FailureCategory | None = None


class EvidenceArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: EvidenceArtifactKind
    path: Path
    mime_type: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    step_id: str | None = None
    phase: StepPhase | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("path", when_used="json")
    def serialize_path(self, value: Path) -> str:
        return value.as_posix()


class StepPhaseReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    phase: StepPhase
    status: RunnerStatus
    duration_ms: int = Field(default=0, ge=0)
    failure_category: FailureCategory | None = None
    error_message: str | None = None
    artifact_refs: list[EvidenceArtifactRef] = Field(default_factory=list)
    harness_call_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunnerStepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    source_ref: SourceRef | None = None
    status: RunnerStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = Field(default=0, ge=0)
    phase_reports: list[StepPhaseReport] = Field(default_factory=list)
    attempt_index: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=1, ge=1)
    failure_category: FailureCategory | None = None
    error_message: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunnerEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str | None = None
    event_type: RunnerEventType
    run_id: str
    step_id: str | None = None
    phase: StepPhase | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = "1.0"
    manifest_path: Path | None = None
    events: list[RunnerEvent] = Field(default_factory=list)
    steps: list[RunnerStepResult] = Field(default_factory=list)
    artifacts: list[EvidenceArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle: EvidenceBundle

