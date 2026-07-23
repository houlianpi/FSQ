from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import json
from math import ceil, hypot
from pathlib import Path
import subprocess
import time
from typing import Any, TypeVar

from pydantic import BaseModel

from fsq_agent.core.harness._ai_assertion_tool import AIAssertionBackendToolMixin
from fsq_agent.core.harness._driver_tools import _windows_driver_tool
from fsq_agent.models import (
    ConfigurationError,
    WindowsAssertWithAIParams,
    WindowsAssertVisibleParams,
    WindowsClickOnParams,
    WindowsDoubleClickOnParams,
    WindowsDragToParams,
    WindowsHoverOnParams,
    WindowsKillAppParams,
    WindowsLaunchAppParams,
    WindowsPressKeyParams,
    WindowsRightClickOnParams,
    WindowsScrollOnParams,
    WindowsTypeTextParams,
    WindowsUiSnapshotParams,
)


DEFAULT_WINDOWS_WAIT_TIMEOUT_SECONDS = 10.0
WINDOW_READY_TIMEOUT_SECONDS = 30.0
WINDOW_LAUNCH_WAIT_FOR = "exists visible enabled"
UI_SNAPSHOT_MAX_DEPTH = 20
UI_SNAPSHOT_MAX_NODES = 1200
UI_SNAPSHOT_MAX_CHILDREN = 60
UI_SNAPSHOT_MAX_BYTES = 800000
MOUSE_DRAG_STEP_PIXELS = 15
_T = TypeVar("_T")


class PywinautoWindowsDriver(AIAssertionBackendToolMixin):
    backend = "pywinauto"

    def __init__(
        self,
        *,
        app_path: str | Path | None = None,
        backend_kind: str = "uia",
        window_title_re: str | None = None,
        launch_args: list[str] | None = None,
    ) -> None:
        self.app_path = str(Path(app_path)) if app_path else None
        self.backend_kind = backend_kind
        self.window_title_re = window_title_re.strip() if isinstance(window_title_re, str) and window_title_re.strip() else None
        self.launch_args = list(launch_args) if launch_args else []
        self._app: object | None = None
        self._executor: ThreadPoolExecutor | None = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fsq-pywinauto")

    def context(self) -> dict[str, object]:
        return self._run_sync(self._context_payload)

    def _context_payload(self) -> dict[str, object]:
        return {
            "session_id": f"pywinauto:{self.backend_kind}",
            "current_url": None,
            "screen_size": self._window_size(),
            "metadata": {
                "backend": self.backend,
                "backend_kind": self.backend_kind,
                "app_path_configured": self.app_path is not None,
                "window_title_re_configured": self.window_title_re is not None,
            },
        }

    @_windows_driver_tool(
        "launchApp",
        description="Launch the configured Windows desktop application.",
        capture_evidence=True,
        metadata={"evidence_capture_on_failure": False},
    )
    def launch_app(self, params: WindowsLaunchAppParams) -> dict[str, object]:
        return self._run_sync(lambda: self._launch_app(params))

    def _launch_app(self, params: WindowsLaunchAppParams) -> dict[str, object]:
        app_path = self.app_path
        if not app_path:
            return self._failed("configuration_error", "Windows app path is not configured.")
        application_cls = self._application_cls()
        launch_args = [*self.launch_args, *(params.extra_args or [])]
        cmd = subprocess.list2cmdline([app_path, *launch_args])
        self._app = application_cls(backend=self.backend_kind).start(cmd)
        self._resolve_main_window(wait=True, wait_for=WINDOW_LAUNCH_WAIT_FOR)
        return self._passed({"app_path": app_path, "launch_args": launch_args, "window_title_re": self.window_title_re})

    def _resolve_main_window(self, *, wait: bool = False, wait_for: str = "exists visible") -> object:
        application_cls = self._application_cls()
        deadline = time.monotonic() + WINDOW_READY_TIMEOUT_SECONDS if wait else None
        while True:
            try:
                if self.window_title_re:
                    connected = application_cls(backend=self.backend_kind).connect(title_re=self.window_title_re)
                    window = connected.window(title_re=self.window_title_re, control_type="Window")
                else:
                    connected = application_cls(backend=self.backend_kind).connect(active_only=True)
                    window = connected.top_window()
                window.wait(wait_for, timeout=2 if wait else 0)
                self._app = connected
                return window
            except Exception as exc:  # noqa: BLE001 - retry until the window appears or timeout.
                details = (
                    f"title_re={self.window_title_re!r}, wait_for={wait_for!r}, "
                    f"backend={self.backend_kind!r}; last error: {exc}"
                )
                if deadline is None:
                    raise RuntimeError(f"Failed to resolve Windows main window ({details})") from exc
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out after {WINDOW_READY_TIMEOUT_SECONDS:.1f} seconds resolving Windows main window "
                        f"({details})"
                    ) from exc
                time.sleep(1.0)

    @_windows_driver_tool("killApp", description="Stop the launched Windows desktop application.", capture_evidence=True)
    def kill_app(self, params: WindowsKillAppParams) -> dict[str, object]:
        return self._run_sync(self._kill_app)

    def _kill_app(self) -> dict[str, object]:
        if self._app is not None:
            kill = getattr(self._app, "kill", None)
            if callable(kill):
                kill()
        self._app = None
        return self._passed()

    @_windows_driver_tool("clickOn", description="Click a Windows control resolved from the UI snapshot.", capture_evidence=True)
    def click_on(self, params: WindowsClickOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._click_on(params))

    def _click_on(self, params: WindowsClickOnParams) -> dict[str, object]:
        control = self._control(params)
        button = params.button or "left"
        if params.double:
            control.double_click_input(button=button)
        else:
            control.click_input(button=button)
        return self._passed()

    @_windows_driver_tool("doubleClickOn", description="Double-click a Windows control.", capture_evidence=True)
    def double_click_on(self, params: WindowsDoubleClickOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._double_click_on(params))

    def _double_click_on(self, params: WindowsDoubleClickOnParams) -> dict[str, object]:
        control = self._control(params)
        control.double_click_input(button=params.button or "left")
        return self._passed()

    @_windows_driver_tool("rightClickOn", description="Right-click a Windows control.", capture_evidence=True)
    def right_click_on(self, params: WindowsRightClickOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._right_click_on(params))

    def _right_click_on(self, params: WindowsRightClickOnParams) -> dict[str, object]:
        control = self._control(params)
        control.click_input(button="right")
        return self._passed()

    @_windows_driver_tool("typeText", description="Type text into a Windows control.", capture_evidence=True)
    def type_text(self, params: WindowsTypeTextParams) -> dict[str, object]:
        return self._run_sync(lambda: self._type_text(params))

    def _type_text(self, params: WindowsTypeTextParams) -> dict[str, object]:
        control = self._control(params)
        control.click_input()
        if params.clear:
            control.type_keys("^a{BACKSPACE}", with_spaces=True)
        control.type_keys(params.text, with_spaces=True)
        return self._passed()

    @_windows_driver_tool("pressKey", description="Send a keyboard key sequence to the active Windows window.", capture_evidence=True)
    def press_key(self, params: WindowsPressKeyParams) -> dict[str, object]:
        return self._run_sync(lambda: self._press_key(params))

    def _press_key(self, params: WindowsPressKeyParams) -> dict[str, object]:
        window = self._require_window()
        window.type_keys(params.key, with_spaces=True, set_foreground=True)
        return self._passed({"key": params.key})

    @_windows_driver_tool("hoverOn", description="Move the mouse over a Windows control.")
    def hover_on(self, params: WindowsHoverOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._hover_on(params))

    def _hover_on(self, params: WindowsHoverOnParams) -> dict[str, object]:
        point = self._control_center(self._control(params))
        self._mouse_module().move(coords=point)
        return self._passed()

    @_windows_driver_tool("scrollOn", description="Scroll over a Windows control.", capture_evidence=True)
    def scroll_on(self, params: WindowsScrollOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._scroll_on(params))

    def _scroll_on(self, params: WindowsScrollOnParams) -> dict[str, object]:
        point = self._control_center(self._control(params))
        self._mouse_module().scroll(coords=point, wheel_dist=params.wheel_dist)
        return self._passed()

    @_windows_driver_tool("dragTo", description="Drag between Windows controls or points.", capture_evidence=True)
    def drag_to(self, params: WindowsDragToParams) -> dict[str, object]:
        return self._run_sync(lambda: self._drag_to(params))

    def _drag_to(self, params: WindowsDragToParams) -> dict[str, object]:
        start = self._mouse_source_point(params)
        end = self._mouse_destination_point(params, start)
        mouse = self._mouse_module()
        pressed = False
        try:
            mouse.press(coords=start, button=params.mouse_button)
            pressed = True
            for point in self._drag_path(start, end):
                mouse.move(coords=point)
            mouse.release(coords=end, button=params.mouse_button)
            pressed = False
        finally:
            if pressed:
                try:
                    mouse.release(coords=end, button=params.mouse_button)
                except Exception:
                    pass
        return self._passed()

    @_windows_driver_tool("assertVisible", description="Assert that a Windows control is visible.")
    def assert_visible(self, params: WindowsAssertVisibleParams) -> dict[str, object]:
        return self._run_sync(lambda: self._assert_visible(params))

    def _assert_visible(self, params: WindowsAssertVisibleParams) -> dict[str, object]:
        control = self._control(params)
        if control.is_visible():
            return self._passed()
        return self._target_missing(params)

    @_windows_driver_tool("assertWithAI", description="Evaluate an explicit Windows visual assertion with AI.")
    def assert_with_ai(self, params: WindowsAssertWithAIParams) -> dict[str, object]:
        return self._run_ai_assertion_tool(params)

    @_windows_driver_tool("uiSnapshot", description="Return the current Windows window control tree snapshot.")
    def ui_snapshot(self, params: WindowsUiSnapshotParams) -> dict[str, object]:
        return self._run_sync(self._ui_snapshot)

    def _ui_snapshot(self) -> dict[str, object]:
        window = self._require_window()
        state = {"count": 0, "bytes": 0, "truncated": False}
        root = self._extract_element(window, depth=0, seen=set(), state=state)
        return {
            "snapshot_type": "control_tree",
            "node_count": state["count"],
            "byte_size": state["bytes"],
            "truncated": state["truncated"],
            "root": root,
        }

    def _extract_element(self, element: Any, *, depth: int, seen: set, state: dict[str, Any]) -> dict[str, Any] | None:
        if state["count"] >= UI_SNAPSHOT_MAX_NODES or state["bytes"] >= UI_SNAPSHOT_MAX_BYTES:
            state["truncated"] = True
            return None
        runtime_id = self._element_runtime_id(element)
        if runtime_id is not None and runtime_id in seen:
            return None
        control_type = self._element_attr(element, "control_type")
        info: dict[str, Any] = {
            "title": self._safe_call(getattr(element, "window_text", None)),
            "control_type": control_type,
            "automation_id": self._element_attr(element, "automation_id"),
            "class_name": self._element_attr(element, "class_name"),
            "rectangle": self._element_rectangle(element),
        }
        value = self._safe_call(getattr(element, "get_value", None))
        if isinstance(value, str) and value:
            info["value"] = value
        if control_type == "CheckBox":
            toggle = self._safe_call(getattr(element, "get_toggle_state", None))
            if isinstance(toggle, int):
                info["is_checked"] = toggle == 1
        node_bytes = len(json.dumps(info, ensure_ascii=False, default=str))
        if state["bytes"] + node_bytes > UI_SNAPSHOT_MAX_BYTES:
            state["truncated"] = True
            return None
        if runtime_id is not None:
            seen.add(runtime_id)
        state["count"] += 1
        state["bytes"] += node_bytes
        children: list[dict[str, Any]] = []
        if depth < UI_SNAPSHOT_MAX_DEPTH:
            child_elements = self._safe_call(getattr(element, "children", None)) or []
            for child in list(child_elements)[:UI_SNAPSHOT_MAX_CHILDREN]:
                if state["count"] >= UI_SNAPSHOT_MAX_NODES or state["bytes"] >= UI_SNAPSHOT_MAX_BYTES:
                    state["truncated"] = True
                    break
                child_info = self._extract_element(child, depth=depth + 1, seen=seen, state=state)
                if child_info is not None:
                    children.append(child_info)
        info["children"] = children
        return info

    def _safe_call(self, func: Any) -> Any:
        if not callable(func):
            return None
        try:
            return func()
        except Exception:
            return None

    def _element_attr(self, element: Any, name: str) -> str | None:
        info = getattr(element, "element_info", None)
        value = getattr(info, name, None)
        return value if isinstance(value, str) and value else None

    def _element_rectangle(self, element: Any) -> dict[str, int] | None:
        rect = self._safe_call(getattr(element, "rectangle", None))
        if rect is None:
            return None
        try:
            return {"left": int(rect.left), "top": int(rect.top), "right": int(rect.right), "bottom": int(rect.bottom)}
        except (AttributeError, TypeError, ValueError):
            return None

    def _element_runtime_id(self, element: Any) -> tuple | None:
        info = getattr(element, "element_info", None)
        runtime_id = getattr(info, "runtime_id", None)
        if isinstance(runtime_id, (list, tuple)) and runtime_id:
            return tuple(runtime_id)
        return None

    def screenshot(self, params: object | None = None) -> bytes:
        return self._run_sync(self._screenshot)

    def _screenshot(self) -> bytes:
        from io import BytesIO

        window = self._require_window()
        image = window.capture_as_image()
        if image is None:
            raise ConfigurationError(
                "Windows screenshot capture returned no image. Pillow is required for pywinauto screenshots.",
                context={"install": "pip install fsq-agent[windows]"},
            )
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def close(self) -> None:
        try:
            self._run_sync(self._kill_app)
        finally:
            self._shutdown_executor()

    def _run_sync(self, func: Callable[[], _T]) -> _T:
        if self._executor is None:
            return func()
        return self._executor.submit(func).result()

    def _shutdown_executor(self) -> None:
        executor = self._executor
        self._executor = None
        if executor is not None:
            executor.shutdown(wait=True)

    def _application_cls(self) -> Any:
        try:
            from pywinauto import Application
        except ImportError as exc:
            raise ConfigurationError(
                "pywinauto is required for PywinautoWindowsDriver.",
                context={"install": "pip install fsq-agent[windows]"},
            ) from exc
        return Application

    def _mouse_module(self) -> Any:
        try:
            from pywinauto import mouse
        except ImportError as exc:
            raise ConfigurationError(
                "pywinauto is required for Windows mouse actions.",
                context={"install": "pip install fsq-agent[windows]"},
            ) from exc
        return mouse

    def _control_center(self, control: Any) -> tuple[int, int]:
        midpoint = control.rectangle().mid_point()
        if hasattr(midpoint, "x") and hasattr(midpoint, "y"):
            return int(midpoint.x), int(midpoint.y)
        x, y = midpoint
        return int(x), int(y)

    def _mouse_source_point(self, params: WindowsDragToParams) -> tuple[int, int]:
        if params.source.locator is not None:
            locator = params.source.locator.model_dump(mode="python", exclude_none=True)
            return self._control_center(self._control_from_kwargs(locator))
        point = params.source.point
        if point is None:
            raise ValueError("Windows drag source is missing.")
        return point.x, point.y

    def _mouse_destination_point(self, params: WindowsDragToParams, start: tuple[int, int]) -> tuple[int, int]:
        destination = params.destination
        if destination.locator is not None:
            locator = destination.locator.model_dump(mode="python", exclude_none=True)
            return self._control_center(self._control_from_kwargs(locator))
        if destination.point is not None:
            return destination.point.x, destination.point.y
        offset = destination.offset
        if offset is None:
            raise ValueError("Windows drag destination is missing.")
        return start[0] + offset.x, start[1] + offset.y

    def _drag_path(self, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        distance = hypot(end[0] - start[0], end[1] - start[1])
        steps = max(1, ceil(distance / MOUSE_DRAG_STEP_PIXELS))
        return [
            (
                round(start[0] + (end[0] - start[0]) * index / steps),
                round(start[1] + (end[1] - start[1]) * index / steps),
            )
            for index in range(1, steps + 1)
        ]

    def _require_window(self) -> Any:
        return self._resolve_main_window()

    def _control(self, params: BaseModel) -> Any:
        data = params.model_dump(mode="python", exclude_none=True)
        return self._control_from_kwargs(data["locator"])

    def _control_from_kwargs(self, locator: dict[str, Any]) -> Any:
        kwargs: dict[str, Any] = {}
        title = locator.get("title")
        if isinstance(title, str):
            kwargs["title"] = title
        if isinstance(locator.get("control_type"), str):
            kwargs["control_type"] = locator["control_type"]
        if isinstance(locator.get("automation_id"), str):
            kwargs["auto_id"] = locator["automation_id"]
        if isinstance(locator.get("class_name"), str):
            kwargs["class_name"] = locator["class_name"]
        index = locator.get("index")
        kwargs["found_index"] = (index - 1) if isinstance(index, int) and index >= 1 else 0
        if not kwargs:
            raise LookupError("Windows control query is empty. query_dict={}")
        control = self._child_window(**kwargs)
        if control is not None and control.exists():
            return control.wrapper_object()
        if not isinstance(title, str):
            raise self._control_not_found(kwargs)
        regex_kwargs = {key: value for key, value in kwargs.items() if key != "title"}
        regex_kwargs["title_re"] = title
        control = self._child_window(**regex_kwargs)
        if control is not None and control.exists():
            return control.wrapper_object()
        raise self._control_not_found(regex_kwargs)

    def _control_not_found(self, query: dict[str, Any]) -> LookupError:
        query_dict = json.dumps(query, ensure_ascii=False, sort_keys=True)
        return LookupError(f"Windows control was not found. query_dict={query_dict}")

    def _child_window(self, **kwargs: Any) -> Any:
        window = self._require_window()
        return window.child_window(**kwargs)

    def _window_size(self) -> tuple[int, int] | None:
        try:
            window = self._require_window()
            rectangle = getattr(window, "rectangle", None)
            if not callable(rectangle):
                return None
            rect = rectangle()
            width = getattr(rect, "width", None)
            height = getattr(rect, "height", None)
            if callable(width) and callable(height):
                return int(width()), int(height())
        except Exception:  # noqa: BLE001 - context must tolerate a missing or closed window.
            return None
        return None

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
