from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import json
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
    WindowsKillAppParams,
    WindowsLaunchAppParams,
    WindowsPressKeyParams,
    WindowsRightClickOnParams,
    WindowsTypeTextParams,
    WindowsUiSnapshotParams,
)


DEFAULT_WINDOWS_WAIT_TIMEOUT_SECONDS = 10.0
WINDOW_READY_TIMEOUT_SECONDS = 30.0
UI_SNAPSHOT_MAX_DEPTH = 20
UI_SNAPSHOT_MAX_NODES = 1200
UI_SNAPSHOT_MAX_CHILDREN = 60
UI_SNAPSHOT_MAX_BYTES = 800000
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
        window: object | None = None,
    ) -> None:
        self.app_path = str(Path(app_path)) if app_path else None
        self.backend_kind = backend_kind
        self.window_title_re = window_title_re.strip() if isinstance(window_title_re, str) and window_title_re.strip() else None
        self.launch_args = list(launch_args) if launch_args else []
        self._app: object | None = None
        self._window: object | None = window
        self._executor: ThreadPoolExecutor | None = None if window is not None else ThreadPoolExecutor(max_workers=1, thread_name_prefix="fsq-pywinauto")

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
        metadata={"evidence_capture_before": False, "evidence_capture_on_failure": False},
    )
    def launch_app(self, params: WindowsLaunchAppParams) -> dict[str, object]:
        return self._run_sync(lambda: self._launch_app(params))

    def _launch_app(self, params: WindowsLaunchAppParams) -> dict[str, object]:
        app_path = params.app_path or self.app_path
        if not app_path:
            return self._failed("configuration_error", "Windows app path is not configured.")
        application_cls = self._application_cls()
        launch_args = [*self.launch_args, *(params.extra_args or [])]
        cmd = subprocess.list2cmdline([app_path, *launch_args])
        application_cls(backend=self.backend_kind).start(cmd)
        self._window = self._resolve_main_window()
        return self._passed({"app_path": app_path, "launch_args": launch_args, "window_title_re": self.window_title_re})

    def _resolve_main_window(self) -> object:
        if not self.window_title_re:
            connected = self._application_cls()(backend=self.backend_kind).connect(active_only=True)
            self._app = connected
            return connected.top_window()
        # Find the application window by title across the desktop. Multi-process apps such
        # as Microsoft Edge own their visible window in a different process than the one
        # launched, so connect by title instead of scoping to the launched process id.
        application_cls = self._application_cls()
        deadline = time.monotonic() + WINDOW_READY_TIMEOUT_SECONDS
        while True:
            try:
                connected = application_cls(backend=self.backend_kind).connect(title_re=self.window_title_re)
                window = connected.window(title_re=self.window_title_re, control_type="Window")
                window.wait("exists visible enabled", timeout=2)
                self._app = connected
                return window
            except Exception:  # noqa: BLE001 - retry until the window appears or timeout.
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1.0)

    @_windows_driver_tool("killApp", description="Stop the launched Windows desktop application.")
    def kill_app(self, params: WindowsKillAppParams) -> dict[str, object]:
        return self._run_sync(self._kill_app)

    def _kill_app(self) -> dict[str, object]:
        if self._app is not None:
            kill = getattr(self._app, "kill", None)
            if callable(kill):
                kill()
        self._app = None
        self._window = None
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

    def _require_window(self) -> Any:
        if self._window is None:
            raise ConfigurationError("Windows window is not available; launch the app first.")
        return self._window

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
        if self._window is None:
            return None
        rectangle = getattr(self._window, "rectangle", None)
        if not callable(rectangle):
            return None
        rect = rectangle()
        width = getattr(rect, "width", None)
        height = getattr(rect, "height", None)
        if callable(width) and callable(height):
            return int(width()), int(height())
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
