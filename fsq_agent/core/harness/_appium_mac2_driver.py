# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from itertools import pairwise
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from pydantic import BaseModel

from fsq_agent.core.harness._ai_assertion_tool import AIAssertionBackendToolMixin
from fsq_agent.core.harness._driver_tools import _macos_driver_tool
from fsq_agent.models import (
    ConfigurationError,
    MacOSAssertElementsOrderParams,
    MacOSAssertVisibleParams,
    MacOSAssertWithAIParams,
    MacOSClickOnParams,
    MacOSDoubleClickOnParams,
    MacOSDragEndpoint,
    MacOSDragToParams,
    MacOSHoverOnParams,
    MacOSKillAppParams,
    MacOSLaunchAppParams,
    MacOSLocator,
    MacOSPoint,
    MacOSPressKeyParams,
    MacOSRightClickOnParams,
    MacOSTakeScreenshotParams,
    MacOSTypeTextParams,
    MacOSUiSnapshotParams,
)

DEFAULT_APPIUM_MAC2_SERVER_URL = "http://127.0.0.1:4723"
DEFAULT_MACOS_PAGE_SOURCE_MAX_DEPTH = 12
DEFAULT_MACOS_ACTION_TIMEOUT_SECONDS = 10
DEFAULT_MACOS_SNAPSHOT_SOURCE_PREVIEW_CHARS = 2000
DEFAULT_MACOS_SNAPSHOT_ATTRIBUTE_KEYS = frozenset(
    {
        "identifier",
        "name",
        "label",
        "value",
        "type",
        "role",
        "enabled",
        "visible",
        "x",
        "y",
        "width",
        "height",
    }
)


def _parse_xml_safely(source: str) -> ElementTree.Element:
    normalized = source.upper()
    if "<!DOCTYPE" in normalized or "<!ENTITY" in normalized:
        raise ElementTree.ParseError("DTD and entity declarations are not allowed.")
    # DTD and entity declarations are rejected above, preventing attacker-controlled entity expansion.
    return ElementTree.fromstring(source)  # noqa: S314


class AppiumMac2Driver(AIAssertionBackendToolMixin):
    backend = "appium_mac2"

    def __init__(
        self,
        *,
        server_url: str = DEFAULT_APPIUM_MAC2_SERVER_URL,
        bundle_id: str | None = None,
        app_path: str | Path | None = None,
        page_source_max_depth: int = DEFAULT_MACOS_PAGE_SOURCE_MAX_DEPTH,
        action_timeout_seconds: int = DEFAULT_MACOS_ACTION_TIMEOUT_SECONDS,
        session: object | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.bundle_id = bundle_id.strip() if isinstance(bundle_id, str) and bundle_id.strip() else None
        self.app_path = str(Path(app_path)) if app_path else None
        self.page_source_max_depth = page_source_max_depth
        self.action_timeout_seconds = action_timeout_seconds
        self._session = session

    def context(self) -> dict[str, object]:
        session_id = self._safe_attr(self._session, "session_id")
        return {
            "session_id": session_id if isinstance(session_id, str) else None,
            "current_url": None,
            "screen_size": self._window_size(),
            "capabilities": self._safe_attr(self._session, "capabilities") or {},
            "metadata": {
                "backend": self.backend,
                "server_url_configured": bool(self.server_url),
                "bundle_id_configured": self.bundle_id is not None,
                "app_path_configured": self.app_path is not None,
            },
        }

    @_macos_driver_tool(
        "launchApp",
        description="Create or reuse an Appium Mac2 session for the configured macOS application.",
    )
    def launch_app(self, params: MacOSLaunchAppParams) -> dict[str, object]:
        session = self._ensure_session(params)
        return self._passed(
            {
                "session_id": self._safe_attr(session, "session_id"),
                "bundle_id": params.bundle_id or self.bundle_id,
                "app_path": params.app_path or self.app_path,
            }
        )

    @_macos_driver_tool("killApp", description="Terminate the active Appium Mac2 application or close the session.")
    def kill_app(self, params: MacOSKillAppParams) -> dict[str, object]:
        session = self._session
        if session is None:
            return self._passed()
        bundle_id = params.bundle_id or self.bundle_id
        if bundle_id:
            terminate = getattr(session, "terminate_app", None)
            if callable(terminate):
                terminate(bundle_id)
        if params.close_session:
            quit_session = getattr(session, "quit", None)
            if callable(quit_session):
                quit_session()
            self._session = None
        return self._passed({"bundle_id": bundle_id, "close_session": bool(params.close_session)})

    @_macos_driver_tool("clickOn", description="Click a macOS element or point resolved through Appium Mac2.")
    def click_on(self, params: MacOSClickOnParams) -> dict[str, object]:
        element = self._resolve_element_or_none(params)
        if element is not None:
            click = getattr(element, "click", None)
            if callable(click):
                click()
                return self._passed()
        point = self._point_from_params(params)
        if point is None:
            return self._target_missing(params)
        self._perform_pointer_click(point)
        return self._passed({"point": point.model_dump(mode="json")})

    @_macos_driver_tool("doubleClickOn", description="Double-click a macOS element or point.")
    def double_click_on(self, params: MacOSDoubleClickOnParams) -> dict[str, object]:
        return self._click_count(params, count=2)

    @_macos_driver_tool("rightClickOn", description="Right-click a macOS element or point.")
    def right_click_on(self, params: MacOSRightClickOnParams) -> dict[str, object]:
        point = self._point_from_params(params)
        if point is None:
            element = self._resolve_element_or_none(params)
            point = self._element_center(element) if element is not None else None
        if point is None:
            return self._target_missing(params)
        self._perform_pointer_click(point, button="right")
        return self._passed({"point": point.model_dump(mode="json")})

    @_macos_driver_tool("typeText", description="Type text into the active or resolved macOS element.")
    def type_text(self, params: MacOSTypeTextParams) -> dict[str, object]:
        element = self._resolve_element_or_none(params)
        if element is not None:
            click = getattr(element, "click", None)
            if callable(click):
                click()
            if params.clear:
                clear = getattr(element, "clear", None)
                if callable(clear):
                    clear()
            send_keys = getattr(element, "send_keys", None)
            if callable(send_keys):
                send_keys(params.text)
                return self._passed()
        session = self._require_session()
        send_keys = getattr(session, "send_keys", None)
        if callable(send_keys):
            send_keys(params.text)
            return self._passed()
        return self._failed("action_error", "Appium session cannot send keyboard input.")

    @_macos_driver_tool("pressKey", description="Send a keyboard shortcut or key to macOS.")
    def press_key(self, params: MacOSPressKeyParams) -> dict[str, object]:
        session = self._require_session()
        key_sequence = self._key_sequence(params)
        send_keys = getattr(session, "send_keys", None)
        if callable(send_keys):
            send_keys(key_sequence)
            return self._passed({"key": params.key, "modifiers": params.modifiers or []})
        return self._failed("action_error", "Appium session cannot send keyboard input.")

    @_macos_driver_tool("hoverOn", description="Move the pointer over a macOS element or point.")
    def hover_on(self, params: MacOSHoverOnParams) -> dict[str, object]:
        point = self._point_from_params(params)
        if point is None:
            element = self._resolve_element_or_none(params)
            point = self._element_center(element) if element is not None else None
        if point is None:
            return self._target_missing(params)
        self._perform_pointer_move(point)
        return self._passed({"point": point.model_dump(mode="json")})

    @_macos_driver_tool("dragTo", description="Drag from one macOS element or point to another.")
    def drag_to(self, params: MacOSDragToParams) -> dict[str, object]:
        source = self._point_from_endpoint(params.source)
        destination = self._point_from_endpoint(params.destination)
        if source is None or destination is None:
            return self._failed(
                "target_resolution_error",
                "Drag source or destination was not found.",
                metadata={"params": params.model_dump(mode="json", exclude_none=True)},
            )
        self._perform_pointer_drag(source, destination, duration_ms=params.duration_ms)
        return self._passed({"source": source.model_dump(mode="json"), "destination": destination.model_dump(mode="json")})

    @_macos_driver_tool("takeScreenshot", description="Capture a macOS screenshot through Appium Mac2.")
    def take_screenshot(self, params: MacOSTakeScreenshotParams) -> bytes:
        return self.screenshot(params)

    @_macos_driver_tool("uiSnapshot", description="Return the current macOS accessibility tree snapshot.")
    def ui_snapshot(self, params: MacOSUiSnapshotParams) -> dict[str, object]:
        session = self._require_session()
        source = getattr(session, "page_source", None)
        max_depth = params.max_depth or self.page_source_max_depth
        include_attributes = bool(params.include_attributes)
        return {
            "snapshot_type": "macos_accessibility_tree",
            "page_source": self._simplify_page_source(
                source if isinstance(source, str) else "",
                max_depth=max_depth,
                include_attributes=include_attributes,
            ),
            "max_depth": max_depth,
            "include_attributes": include_attributes,
        }

    @_macos_driver_tool("assertVisible", description="Assert that a macOS element is visible.")
    def assert_visible(self, params: MacOSAssertVisibleParams) -> dict[str, object]:
        element = self._resolve_element_or_none(params)
        if element is None:
            return self._target_missing(params)
        if self._element_displayed(element):
            return self._passed()
        return self._failed("assertion_error", "Target is present but not visible.")

    @_macos_driver_tool("assertElementsOrder", description="Assert that macOS elements appear in the expected visual order.")
    def assert_elements_order(self, params: MacOSAssertElementsOrderParams) -> dict[str, object]:
        entries: list[dict[str, object]] = []
        missing: list[int] = []
        for index, element_ref in enumerate(params.elements):
            element = self._resolve_element_or_none(element_ref)
            if element is None:
                missing.append(index)
                continue
            rect = self._element_rect(element)
            if rect is None:
                missing.append(index)
                continue
            entries.append(
                {
                    "index": index,
                    "coordinate": self._order_coordinate(rect, params.direction),
                    "rect": rect,
                }
            )
        actual_order = [int(entry["index"]) for entry in sorted(entries, key=lambda entry: float(entry["coordinate"]))]
        expected_order = params.expected_order or list(range(len(params.elements)))
        if not params.require_all:
            expected_order = [index for index in expected_order if index in actual_order]
        output = {
            "direction": params.direction,
            "elements_found": len(entries),
            "elements_total": len(params.elements),
            "actual_order": actual_order,
            "expected_order": expected_order,
            "positions": entries,
        }
        if missing and params.require_all:
            return self._failed(
                "target_resolution_error",
                "One or more ordered elements were not found.",
                output=output,
                metadata={"missing_indexes": missing},
            )
        if self._order_matches(entries, expected_order, params.tolerance or 0.0):
            return self._passed(output)
        return self._failed(
            "assertion_error",
            "Elements are not in the expected order.",
            output=output,
        )

    @_macos_driver_tool("assertWithAI", description="Evaluate an explicit macOS visual assertion with AI.")
    def assert_with_ai(self, params: MacOSAssertWithAIParams) -> dict[str, object]:
        return self._run_ai_assertion_tool(params)

    def screenshot(self, params: object | None = None) -> bytes:
        session = self._require_session()
        screenshot = getattr(session, "get_screenshot_as_png", None)
        if callable(screenshot):
            data = screenshot()
            if isinstance(data, bytes):
                return data
        raise ConfigurationError("Appium Mac2 screenshot capture returned no image.")

    def close(self) -> None:
        session = self._session
        if session is None:
            return
        quit_session = getattr(session, "quit", None)
        if callable(quit_session):
            quit_session()
        self._session = None

    def _ensure_session(self, params: MacOSLaunchAppParams | None = None) -> object:
        if self._session is not None:
            return self._session
        params = params or MacOSLaunchAppParams()
        capabilities: dict[str, object] = {
            "platformName": "Mac",
            "appium:automationName": "Mac2",
            "appium:newCommandTimeout": self.action_timeout_seconds,
        }
        bundle_id = params.bundle_id or self.bundle_id
        app_path = params.app_path or self.app_path
        if bundle_id:
            capabilities["appium:bundleId"] = bundle_id
        if app_path:
            capabilities["appium:app"] = app_path
        if params.arguments:
            capabilities["appium:arguments"] = params.arguments
        if params.environment:
            capabilities["appium:environment"] = params.environment
        if not bundle_id and not app_path:
            raise ConfigurationError("macOS Appium Mac2 session requires bundle_id or app_path.")
        try:
            from appium import webdriver
            from appium.options.mac import Mac2Options
        except ImportError as exc:
            raise ConfigurationError(
                "Appium Python client is required for AppiumMac2Driver.",
                context={"install": "pip install Appium-Python-Client"},
            ) from exc
        options = Mac2Options().load_capabilities(capabilities)
        self._session = webdriver.Remote(self.server_url, options=options)
        return self._session

    def _require_session(self) -> object:
        if self._session is None:
            raise ConfigurationError("Appium Mac2 session is not available. Call launchApp before macOS Appium actions.")
        if self._session is None:
            raise ConfigurationError("Appium Mac2 session is not available.")
        return self._session

    def _resolve_element_or_none(self, params: BaseModel) -> object | None:
        data = params.model_dump(mode="python", exclude_none=True)
        locator = data.get("locator")
        if isinstance(locator, dict):
            return self._element_from_locator(MacOSLocator.model_validate(locator))
        target = data.get("target")
        if isinstance(target, str) and target.strip():
            return self._element_by_accessibility_or_name(target.strip())
        return None

    def _element_from_locator(self, locator: MacOSLocator) -> object | None:
        session = self._require_session()
        if locator.accessibilityId:
            element = self._find_element(session, "accessibility id", locator.accessibilityId)
            if element is not None:
                return element
        if locator.xpath:
            element = self._find_element(session, "xpath", locator.xpath)
            if element is not None:
                return element
        if locator.predicate:
            element = self._find_element(session, "-ios predicate string", locator.predicate)
            if element is not None:
                return element
        for value in (locator.name, locator.label, locator.value):
            if value:
                element = self._element_by_accessibility_or_name(value)
                if element is not None:
                    return element
        if locator.role or locator.controlType or locator.className:
            predicate_parts: list[str] = []
            if locator.role:
                predicate_parts.append(f"role == '{locator.role}'")
            if locator.controlType:
                predicate_parts.append(f"type == '{locator.controlType}'")
            if locator.className:
                predicate_parts.append(f"type == '{locator.className}'")
            if predicate_parts:
                return self._find_element(session, "-ios predicate string", " AND ".join(predicate_parts))
        return None

    def _element_by_accessibility_or_name(self, value: str) -> object | None:
        session = self._require_session()
        for strategy, locator in (
            ("accessibility id", value),
            ("-ios predicate string", f"name == '{value}' OR label == '{value}' OR value == '{value}'"),
            ("xpath", f"//*[@name={self._xpath_literal(value)} or @label={self._xpath_literal(value)}]"),
        ):
            element = self._find_element(session, strategy, locator)
            if element is not None:
                return element
        return None

    def _find_element(self, session: object, strategy: str, locator: str) -> object | None:
        find_element = getattr(session, "find_element", None)
        if not callable(find_element):
            return None
        try:
            return find_element(strategy, locator)
        # Appium and Selenium locator failures use optional-backend exception classes outside the core contract.
        except Exception:  # noqa: BLE001
            return None

    def _click_count(self, params: BaseModel, *, count: int) -> dict[str, object]:
        point = self._point_from_params(params)
        if point is None:
            element = self._resolve_element_or_none(params)
            point = self._element_center(element) if element is not None else None
        if point is None:
            return self._target_missing(params)
        self._perform_pointer_click(point, click_count=count)
        return self._passed({"point": point.model_dump(mode="json"), "click_count": count})

    def _point_from_endpoint(self, endpoint: MacOSDragEndpoint) -> MacOSPoint | None:
        point = self._point_from_params(endpoint)
        if point is not None:
            return point
        element = self._resolve_element_or_none(endpoint)
        return self._element_center(element) if element is not None else None

    def _point_from_params(self, params: BaseModel) -> MacOSPoint | None:
        data = params.model_dump(mode="python", exclude_none=True)
        point = data.get("point")
        if isinstance(point, dict):
            return MacOSPoint.model_validate(point)
        locator = data.get("locator")
        if isinstance(locator, dict) and isinstance(locator.get("point"), dict):
            return MacOSPoint.model_validate(locator["point"])
        return None

    def _perform_pointer_click(self, point: MacOSPoint, *, button: str = "left", click_count: int = 1) -> None:
        session = self._require_session()
        try:
            from selenium.webdriver.common.actions.action_builder import ActionBuilder
        except ImportError as exc:
            raise ConfigurationError(
                "Selenium action builder is required for Appium Mac2 pointer actions.",
                context={"install": "pip install selenium"},
            ) from exc
        actions = ActionBuilder(session)
        pointer = actions.pointer_action
        pointer.move_to_location(point.x, point.y)
        button_index = 2 if button == "right" else 0
        for _ in range(click_count):
            pointer.pointer_down(button=button_index)
            pointer.pointer_up(button=button_index)
        actions.perform()

    def _perform_pointer_move(self, point: MacOSPoint) -> None:
        session = self._require_session()
        try:
            from selenium.webdriver.common.actions.action_builder import ActionBuilder
        except ImportError as exc:
            raise ConfigurationError(
                "Selenium action builder is required for Appium Mac2 pointer actions.",
                context={"install": "pip install selenium"},
            ) from exc
        actions = ActionBuilder(session)
        actions.pointer_action.move_to_location(point.x, point.y)
        actions.perform()

    def _perform_pointer_drag(self, source: MacOSPoint, destination: MacOSPoint, *, duration_ms: int | None) -> None:
        session = self._require_session()
        try:
            from selenium.webdriver.common.actions.action_builder import ActionBuilder
        except ImportError as exc:
            raise ConfigurationError(
                "Selenium action builder is required for Appium Mac2 pointer actions.",
                context={"install": "pip install selenium"},
            ) from exc
        actions = ActionBuilder(session)
        pointer = actions.pointer_action
        pointer.move_to_location(source.x, source.y)
        pointer.pointer_down()
        pointer.pause((duration_ms or 250) / 1000)
        pointer.move_to_location(destination.x, destination.y)
        pointer.pointer_up()
        actions.perform()

    def _key_sequence(self, params: MacOSPressKeyParams) -> str:
        modifiers = params.modifiers or []
        return "+".join([*modifiers, params.key]) if modifiers else params.key

    def _element_displayed(self, element: object) -> bool:
        displayed = getattr(element, "is_displayed", None)
        if callable(displayed):
            try:
                return bool(displayed())
            # Appium element state probes must treat any optional-backend lookup failure as not displayed.
            except Exception:  # noqa: BLE001
                return False
        return True

    def _element_center(self, element: object | None) -> MacOSPoint | None:
        rect = self._element_rect(element)
        if rect is None:
            return None
        x = rect.get("x")
        y = rect.get("y")
        width = rect.get("width")
        height = rect.get("height")
        if all(isinstance(value, (int, float)) for value in (x, y, width, height)):
            return MacOSPoint(x=int(float(x) + float(width) / 2), y=int(float(y) + float(height) / 2))
        return None

    def _element_rect(self, element: object | None) -> dict[str, float] | None:
        if element is None:
            return None
        rect = getattr(element, "rect", None)
        if isinstance(rect, dict):
            try:
                return {key: float(rect[key]) for key in ("x", "y", "width", "height")}
            except (KeyError, TypeError, ValueError):
                return None
        return None

    def _order_coordinate(self, rect: dict[str, float], direction: str) -> float:
        if direction == "horizontal":
            return rect["x"] + rect["width"] / 2
        return rect["y"] + rect["height"] / 2

    def _order_matches(self, entries: list[dict[str, object]], expected_order: list[int], tolerance: float) -> bool:
        coordinates_by_index = {int(entry["index"]): float(entry["coordinate"]) for entry in entries}
        if any(index not in coordinates_by_index for index in expected_order):
            return False
        expected_coordinates = [coordinates_by_index[index] for index in expected_order]
        return all(left <= right + tolerance for left, right in pairwise(expected_coordinates))

    def _simplify_page_source(self, source: str, *, max_depth: int, include_attributes: bool) -> dict[str, object]:
        if not source.strip():
            return {"format": "xml", "root": None, "source_length": 0}
        try:
            root = _parse_xml_safely(source)
        except ElementTree.ParseError as exc:
            preview = source[:DEFAULT_MACOS_SNAPSHOT_SOURCE_PREVIEW_CHARS]
            return {
                "format": "unparsed_xml",
                "source_preview": preview,
                "source_length": len(source),
                "truncated": len(source) > len(preview),
                "parse_error": str(exc),
            }
        return {
            "format": "xml",
            "source_length": len(source),
            "node_count": self._element_count(root),
            "root": self._element_snapshot(
                root,
                depth=1,
                max_depth=max_depth,
                include_attributes=include_attributes,
            ),
        }

    def _element_snapshot(
        self,
        element: ElementTree.Element,
        *,
        depth: int,
        max_depth: int,
        include_attributes: bool,
    ) -> dict[str, object]:
        children = list(element)
        snapshot: dict[str, object] = {"type": self._xml_name(element.tag)}
        attributes = self._snapshot_attributes(element.attrib, include_attributes=include_attributes)
        if attributes:
            snapshot["attributes"] = attributes
        text = (element.text or "").strip()
        if text:
            snapshot["text"] = text[:500]
        if depth >= max_depth:
            if children:
                snapshot["children_truncated"] = len(children)
            return snapshot
        if children:
            snapshot["children"] = [
                self._element_snapshot(
                    child,
                    depth=depth + 1,
                    max_depth=max_depth,
                    include_attributes=include_attributes,
                )
                for child in children
            ]
        return snapshot

    def _snapshot_attributes(self, attributes: dict[str, str], *, include_attributes: bool) -> dict[str, object]:
        selected: dict[str, object] = {}
        for key, value in attributes.items():
            normalized_key = self._xml_name(key)
            if include_attributes or normalized_key in DEFAULT_MACOS_SNAPSHOT_ATTRIBUTE_KEYS:
                selected[normalized_key] = value
        return selected

    def _element_count(self, element: ElementTree.Element) -> int:
        return 1 + sum(self._element_count(child) for child in list(element))

    def _xml_name(self, value: str) -> str:
        return value.rsplit("}", 1)[-1] if "}" in value else value

    def _window_size(self) -> tuple[int, int] | None:
        session = self._session
        if session is None:
            return None
        get_window_size = getattr(session, "get_window_size", None)
        if not callable(get_window_size):
            return None
        try:
            size = get_window_size()
        # Appium window probes use optional-backend exception classes outside the core contract.
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(size, dict):
            return None
        width = size.get("width")
        height = size.get("height")
        if isinstance(width, int) and isinstance(height, int):
            return width, height
        return None

    def _safe_attr(self, obj: object | None, name: str) -> object | None:
        if obj is None:
            return None
        try:
            return getattr(obj, name, None)
        # WebDriver properties may execute remote calls and raise optional-backend exception classes.
        except Exception:  # noqa: BLE001
            return None

    def _xpath_literal(self, value: str) -> str:
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"

    def _target_missing(self, params: BaseModel) -> dict[str, object]:
        return self._failed(
            "target_resolution_error",
            "Target was not found.",
            metadata={"params": params.model_dump(mode="json", exclude_none=True)},
        )

    def _passed(self, output: object | None = None) -> dict[str, object]:
        return {"status": "passed", "output": output}

    def _failed(
        self,
        failure_category: str,
        error_message: str,
        *,
        output: object | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        return {
            "status": "failed",
            "failure_category": failure_category,
            "error_message": error_message,
            "output": output,
            "metadata": metadata or {},
        }
