# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urljoin

from pydantic import BaseModel

from fsq_agent.core.harness._ai_assertion_tool import AIAssertionBackendToolMixin
from fsq_agent.core.harness._driver_tools import _web_driver_tool
from fsq_agent.models import (
    ConfigurationError,
    WebAssertNotVisibleParams,
    WebAssertTextParams,
    WebAssertVisibleParams,
    WebAssertWithAIParams,
    WebClickOnParams,
    WebCloseBrowserParams,
    WebHoverOnParams,
    WebNavigateBackParams,
    WebNavigateToParams,
    WebPageSnapshotParams,
    WebPressKeyParams,
    WebSelectOptionParams,
    WebStartBrowserParams,
    WebTakeScreenshotParams,
    WebTypeTextParams,
    WebWaitForParams,
)

DEFAULT_WEB_WAIT_TIMEOUT_MS = 10000
_BROWSER_NOT_STARTED_MESSAGE = "Browser is not started. Call startBrowser before Web page actions."
_T = TypeVar("_T")


class PlaywrightWebDriver(AIAssertionBackendToolMixin):
    backend = "playwright"

    def __init__(
        self,
        *,
        channel: str = "chrome",
        executable_path: str | Path | None = None,
        headless: bool = True,
        base_url: str | None = None,
        viewport: tuple[int, int] | None = None,
        page: object | None = None,
    ) -> None:
        self.channel = channel.strip() if isinstance(channel, str) else channel
        if self.channel != "chrome":
            raise ConfigurationError(
                "Unsupported Playwright browser channel.",
                context={"channel": self.channel, "supported": ["chrome"]},
            )
        self.executable_path = str(Path(executable_path)) if executable_path else None
        self.headless = headless
        self.base_url = base_url.rstrip("/") + "/" if isinstance(base_url, str) and base_url.strip() else None
        self.viewport = viewport
        self._playwright: object | None = None
        self._browser: object | None = None
        self._context: object | None = None
        self._executor: ThreadPoolExecutor | None = None
        self.page: object | None = page

    def context(self) -> dict[str, object]:
        return self._run_sync(self._context_payload)

    def _context_payload(self) -> dict[str, object]:
        viewport = self.viewport
        if viewport is None:
            viewport = self._page_viewport()
        return {
            "session_id": f"playwright:{self.channel}",
            "current_url": self._page_url(),
            "screen_size": viewport,
            "metadata": {
                "backend": self.backend,
                "channel": self.channel,
                "browser_executable_configured": self.executable_path is not None,
                "headless": self.headless,
                "base_url_configured": self.base_url is not None,
                "browser_started": self.page is not None,
            },
        }

    @_web_driver_tool("startBrowser", description="Start or reuse the configured Web browser.")
    def start_browser(self, params: WebStartBrowserParams) -> dict[str, object]:
        if self.page is None:
            self._ensure_executor()
        try:
            return self._run_sync(lambda: self._start_browser(params))
        except Exception:
            if self.page is None:
                self._shutdown_executor()
            raise

    def _start_browser(self, params: WebStartBrowserParams) -> dict[str, object]:
        if self.page is not None:
            return self._passed({"already_started": True, "url": self._page_url()})
        self.page = self._create_page()
        return self._passed({"already_started": False, "url": self._page_url()})

    @_web_driver_tool("closeBrowser", description="Close the active Web browser.")
    def close_browser(self, params: WebCloseBrowserParams) -> dict[str, object]:
        return self._run_sync(lambda: self._close_browser(params))

    def _close_browser(self, params: WebCloseBrowserParams) -> dict[str, object]:
        if self.page is None and self._context is None and self._browser is None and self._playwright is None:
            return self._passed({"already_closed": True})
        self._close()
        return self._passed({"already_closed": False})

    @_web_driver_tool("navigateTo", description="Navigate the current Web page to a URL.")
    def navigate_to(self, params: WebNavigateToParams) -> dict[str, object]:
        return self._run_sync(lambda: self._navigate_to(params))

    def _navigate_to(self, params: WebNavigateToParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        url = self._resolve_url(params.url)
        kwargs: dict[str, object] = {}
        if params.waitUntil is not None:
            kwargs["wait_until"] = params.waitUntil
        response = self.page.goto(url, **kwargs)
        status = getattr(response, "status", None)
        return self._passed({"url": self._page_url() or url, "status": status})

    @_web_driver_tool("navigateBack", description="Navigate the current Web page back in browser history.")
    def navigate_back(self, params: WebNavigateBackParams) -> dict[str, object]:
        return self._run_sync(lambda: self._navigate_back(params))

    def _navigate_back(self, params: WebNavigateBackParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        kwargs: dict[str, object] = {}
        if params.waitUntil is not None:
            kwargs["wait_until"] = params.waitUntil
        response = self.page.go_back(**kwargs)
        status = getattr(response, "status", None)
        return self._passed({"url": self._page_url(), "status": status})

    @_web_driver_tool("clickOn", description="Click a Web page target resolved from the page snapshot.")
    def click_on(self, params: WebClickOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._click_on(params))

    def _click_on(self, params: WebClickOnParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        locator = self._locator(params)
        if not self._wait_for_locator(locator, state="visible"):
            return self._target_missing(params)
        kwargs: dict[str, object] = {}
        if params.button is not None:
            kwargs["button"] = params.button
        if params.double:
            locator.dblclick(**kwargs)
        else:
            locator.click(**kwargs)
        return self._passed()

    @_web_driver_tool("typeText", description="Type text into a Web page target resolved from the page snapshot.")
    def type_text(self, params: WebTypeTextParams) -> dict[str, object]:
        return self._run_sync(lambda: self._type_text(params))

    def _type_text(self, params: WebTypeTextParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        locator = self._locator(params)
        if not self._wait_for_locator(locator, state="visible"):
            return self._target_missing(params)
        if params.clear:
            locator.fill(params.text)
        else:
            locator.click()
            locator.type(params.text)
        return self._passed()

    @_web_driver_tool("selectOption", description="Select an option in a Web select target.")
    def select_option(self, params: WebSelectOptionParams) -> dict[str, object]:
        return self._run_sync(lambda: self._select_option(params))

    def _select_option(self, params: WebSelectOptionParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        locator = self._locator(params)
        if not self._wait_for_locator(locator, state="visible"):
            return self._target_missing(params)
        option: object
        if params.values is not None:
            option = params.values
        elif params.value is not None:
            option = params.value
        elif params.label is not None:
            option = {"label": params.label}
        else:
            option = {"index": params.index}
        selected = locator.select_option(option)
        return self._passed({"selected": selected})

    @_web_driver_tool("hoverOn", description="Hover over a Web page target resolved from the page snapshot.")
    def hover_on(self, params: WebHoverOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._hover_on(params))

    def _hover_on(self, params: WebHoverOnParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        locator = self._locator(params)
        if not self._wait_for_locator(locator, state="visible"):
            return self._target_missing(params)
        locator.hover()
        return self._passed()

    @_web_driver_tool("pressKey", description="Press a keyboard key in the current Web page.")
    def press_key(self, params: WebPressKeyParams) -> dict[str, object]:
        return self._run_sync(lambda: self._press_key(params))

    def _press_key(self, params: WebPressKeyParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        self.page.keyboard.press(params.key)
        return self._passed({"key": params.key})

    @_web_driver_tool("waitFor", description="Wait for a Web page target, text, URL, or timeout condition.")
    def wait_for(self, params: WebWaitForParams) -> dict[str, object]:
        return self._run_sync(lambda: self._wait_for(params))

    def _wait_for(self, params: WebWaitForParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        timeout = params.timeout_ms or DEFAULT_WEB_WAIT_TIMEOUT_MS
        if params.target or params.locator:
            locator = self._locator(params)
            state = params.state or "visible"
            if self._wait_for_locator(locator, state=state, timeout=timeout):
                return self._passed({"state": state})
            return self._failed("timeout_error", "Timed out waiting for Web target.")
        if params.text:
            locator = self.page.get_by_text(params.text)
            if self._wait_for_locator(locator, state="visible", timeout=timeout):
                return self._passed({"text": params.text})
            return self._failed("timeout_error", "Timed out waiting for Web text.")
        if params.url:
            self.page.wait_for_url(params.url, timeout=timeout)
            return self._passed({"url": self._page_url()})
        self.page.wait_for_timeout(timeout)
        return self._passed({"timeout_ms": timeout})

    @_web_driver_tool("takeScreenshot", description="Capture a Web page screenshot for evidence or debugging.")
    def take_screenshot(self, params: WebTakeScreenshotParams) -> dict[str, object]:
        return self._run_sync(lambda: self._take_screenshot(params))

    def _take_screenshot(self, params: WebTakeScreenshotParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        return self._passed({"bytes": len(self._screenshot(params))})

    @_web_driver_tool("pageSnapshot", description="Return the current Web page accessibility snapshot.")
    def page_snapshot(self, params: WebPageSnapshotParams) -> dict[str, object]:
        return self._run_sync(lambda: self._page_snapshot(params))

    def ui_snapshot(self, params: object | None = None) -> dict[str, object]:
        return self.page_snapshot(WebPageSnapshotParams())

    def _page_snapshot(self, params: WebPageSnapshotParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        aria_snapshot = getattr(self.page, "aria_snapshot", None)
        if callable(aria_snapshot):
            try:
                snapshot = aria_snapshot(mode="ai")
            except TypeError:
                snapshot = aria_snapshot()
            if not isinstance(snapshot, str) or snapshot.strip():
                return {"url": self._page_url(), "snapshot_type": "aria", "snapshot": snapshot}
        return self._text_page_snapshot()

    def _text_page_snapshot(self) -> dict[str, object]:
        return {
            "url": self._page_url(),
            "snapshot_type": "text",
            "title": self._safe_page_title(),
            "text": self._safe_body_text(),
        }

    @_web_driver_tool("assertVisible", description="Assert that a Web page target is visible.")
    def assert_visible(self, params: WebAssertVisibleParams) -> dict[str, object]:
        return self._run_sync(lambda: self._assert_visible(params))

    def _assert_visible(self, params: WebAssertVisibleParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        locator = self._locator(params)
        if self._wait_for_locator(locator, state="visible"):
            return self._passed()
        return self._target_missing(params)

    @_web_driver_tool("assertNotVisible", description="Assert that a Web page target is not visible.")
    def assert_not_visible(self, params: WebAssertNotVisibleParams) -> dict[str, object]:
        return self._run_sync(lambda: self._assert_not_visible(params))

    def _assert_not_visible(self, params: WebAssertNotVisibleParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        locator = self._locator(params)
        if self._wait_for_locator(locator, state="hidden"):
            return self._passed()
        return self._failed("assertion_error", "Target is visible.")

    @_web_driver_tool("assertText", description="Assert text on a Web page target.")
    def assert_text(self, params: WebAssertTextParams) -> dict[str, object]:
        return self._run_sync(lambda: self._assert_text(params))

    def _assert_text(self, params: WebAssertTextParams) -> dict[str, object]:
        if self.page is None:
            return self._browser_not_started()
        locator = self._locator(params)
        if not self._wait_for_locator(locator, state="visible"):
            return self._target_missing(params)
        actual = locator.inner_text()
        contains = params.text.contains
        if isinstance(contains, str) and contains in actual:
            return self._passed({"text": actual})
        equals = params.text.equals
        if isinstance(equals, str) and equals == actual:
            return self._passed({"text": actual})
        return self._failed("assertion_error", "Text assertion failed.", output={"text": actual})

    @_web_driver_tool("assertWithAI", description="Evaluate an explicit Web visual assertion with AI.")
    def assert_with_ai(self, params: WebAssertWithAIParams) -> dict[str, object]:
        return self._run_ai_assertion_tool(params)

    def screenshot(self, params: WebTakeScreenshotParams | None = None) -> bytes:
        return self._run_sync(lambda: self._screenshot(params))

    def _screenshot(self, params: WebTakeScreenshotParams | None = None) -> bytes:
        if self.page is None:
            raise RuntimeError(_BROWSER_NOT_STARTED_MESSAGE)
        params = params or WebTakeScreenshotParams()
        return self.page.screenshot(full_page=bool(params.fullPage), omit_background=bool(params.omitBackground))

    def close(self) -> None:
        try:
            self._run_sync(self._close)
        finally:
            self._shutdown_executor()

    def _close(self) -> None:
        try:
            for candidate in [self._context, self._browser, self._playwright]:
                close = getattr(candidate, "close", None)
                stop = getattr(candidate, "stop", None)
                if callable(close):
                    close()
                elif callable(stop):
                    stop()
        finally:
            self.page = None
            self._context = None
            self._browser = None
            self._playwright = None

    def _run_sync(self, func: Callable[[], _T]) -> _T:
        if self._executor is None:
            return func()
        return self._executor.submit(func).result()

    def _ensure_executor(self) -> None:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fsq-playwright")

    def _shutdown_executor(self) -> None:
        executor = self._executor
        self._executor = None
        if executor is not None:
            executor.shutdown(wait=True)

    def _create_page(self) -> object:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ConfigurationError(
                "playwright is required for PlaywrightWebDriver.",
                context={"install": "pip install fsq-agent[web] && playwright install"},
            ) from exc
        playwright = sync_playwright().start()
        browser_factory = getattr(playwright, "chromium", None)
        if browser_factory is None:
            raise ConfigurationError(
                "Playwright chromium browser type is unavailable.",
                context={"channel": self.channel},
            )
        if self.executable_path is None:
            raise ConfigurationError(
                "Web browser executable path is required for PlaywrightWebDriver.",
                context={"executable_path_env": "FSQ_WEB_BROWSER_EXECUTABLE_PATH", "channel": self.channel},
            )
        launch_kwargs: dict[str, object] = {"headless": self.headless, "executable_path": self.executable_path}
        browser = browser_factory.launch(**launch_kwargs)
        context_kwargs: dict[str, object] = {}
        if self.viewport is not None:
            width, height = self.viewport
            context_kwargs["viewport"] = {"width": width, "height": height}
        context = browser.new_context(**context_kwargs)
        self._playwright = playwright
        self._browser = browser
        self._context = context
        return context.new_page()

    def _resolve_url(self, url: str) -> str:
        if url.startswith(("http://", "https://")):
            return url
        if self.base_url is None:
            raise ConfigurationError("Web navigation requires an absolute URL or configured harness.web.base_url.")
        return urljoin(self.base_url, url.lstrip("/"))

    def _locator(self, params: BaseModel) -> object:
        data = params.model_dump(mode="python", exclude_none=True)
        locator = data.get("locator")
        if isinstance(locator, dict):
            role = locator.get("role")
            name = locator.get("name")
            if isinstance(role, str) and role.strip():
                kwargs: dict[str, object] = {}
                if isinstance(name, str) and name.strip():
                    kwargs["name"] = name
                return self.page.get_by_role(role, **kwargs)
            for key, method_name in [
                ("text", "get_by_text"),
                ("label", "get_by_label"),
                ("placeholder", "get_by_placeholder"),
                ("testId", "get_by_test_id"),
                ("altText", "get_by_alt_text"),
                ("title", "get_by_title"),
            ]:
                value = locator.get(key)
                if isinstance(value, str) and value.strip():
                    return getattr(self.page, method_name)(value)
            css = locator.get("css")
            if isinstance(css, str) and css.strip():
                return self.page.locator(css)
            xpath = locator.get("xpath")
            if isinstance(xpath, str) and xpath.strip():
                return self.page.locator(f"xpath={xpath}")
        target = data.get("target")
        if isinstance(target, str) and target.strip():
            return self.page.get_by_text(target)
        return self.page.locator(":root")

    def _wait_for_locator(self, locator: object, *, state: str, timeout: int = DEFAULT_WEB_WAIT_TIMEOUT_MS) -> bool:
        try:
            locator.wait_for(state=state, timeout=timeout)
        # Playwright locator failures use optional-backend exception classes outside the core contract.
        except Exception:  # noqa: BLE001
            return False
        else:
            return True

    def _page_url(self) -> str | None:
        url = getattr(self.page, "url", None)
        return url if isinstance(url, str) else None

    def _page_viewport(self) -> tuple[int, int] | None:
        if self.page is None:
            return None
        viewport_size = getattr(self.page, "viewport_size", None)
        if not isinstance(viewport_size, dict):
            return None
        width = viewport_size.get("width")
        height = viewport_size.get("height")
        if isinstance(width, int) and isinstance(height, int):
            return width, height
        return None

    def _safe_page_title(self) -> str | None:
        title = getattr(self.page, "title", None)
        if not callable(title):
            return None
        try:
            value = title()
        # Playwright page probes must tolerate closed pages and optional-backend errors.
        except Exception:  # noqa: BLE001
            return None
        return value if isinstance(value, str) else None

    def _safe_body_text(self) -> str | None:
        try:
            locator = self.page.locator("body")
            inner_text = getattr(locator, "inner_text", None)
            if not callable(inner_text):
                return None
            return inner_text(timeout=1000)
        # Playwright page probes must tolerate closed pages and optional-backend errors.
        except Exception:  # noqa: BLE001
            return None

    def _target_missing(self, params: BaseModel) -> dict[str, object]:
        return self._failed(
            "target_resolution_error",
            "Target was not found.",
            metadata={"params": params.model_dump(mode="json", exclude_none=True)},
        )

    def _browser_not_started(self) -> dict[str, object]:
        return self._failed("context_error", _BROWSER_NOT_STARTED_MESSAGE)

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
