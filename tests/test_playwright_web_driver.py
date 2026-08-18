# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys
import threading
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from fsq_agent.core.harness._playwright_driver import PlaywrightWebDriver
from fsq_agent.models import ConfigurationError, WebClickOnParams, WebCloseBrowserParams, WebNavigateToParams, WebStartBrowserParams, WebUiSnapshotParams


class _FakeResponse:
    status = 200


class _FakePage:
    def __init__(self, *, aria_snapshot: str = '- document "Example" [ref=e1]') -> None:
        self.url = "about:blank"
        self.viewport_size = {"width": 800, "height": 600}
        self._aria_snapshot = aria_snapshot
        self.thread_ids: list[int] = []
        self.aria_kwargs: dict[str, object] | None = None

    def _record_thread(self) -> None:
        self.thread_ids.append(threading.get_ident())

    def goto(self, url: str, **kwargs: object) -> _FakeResponse:
        self._record_thread()
        self.url = url
        return _FakeResponse()

    def aria_snapshot(self, **kwargs: object) -> str:
        self._record_thread()
        self.aria_kwargs = kwargs
        return self._aria_snapshot


class _ThreadedFakePlaywrightDriver(PlaywrightWebDriver):
    def _create_page(self) -> object:
        self.create_thread_id = threading.get_ident()
        self.fake_page = _FakePage()
        return self.fake_page


class _FakeLocator:
    def inner_text(self, **kwargs: object) -> str:
        return "Search box\nResults"


class _ClickFakeLocator:
    def __init__(self, count: int = 1, visible: bool = True) -> None:
        self.match_count = count
        self.visible = visible
        self.clicked = False
        self.filters: list[object] = []

    def filter(self, **kwargs: object) -> "_ClickFakeLocator":
        self.filters.append(kwargs)
        return self

    def and_(self, other: object) -> "_ClickFakeLocator":
        self.filters.append({"and": other})
        return self

    def count(self) -> int:
        return self.match_count

    def is_visible(self) -> bool:
        return self.visible

    def click(self, **kwargs: object) -> None:
        self.clicked = True


class _ClickFakePage(_FakePage):
    def __init__(self, locator: _ClickFakeLocator) -> None:
        super().__init__()
        self.result = locator
        self.role_calls: list[tuple[str, dict[str, object]]] = []

    def get_by_role(self, role: str, **kwargs: object) -> _ClickFakeLocator:
        self.role_calls.append((role, kwargs))
        return self.result

    def get_by_text(self, text: object) -> _ClickFakeLocator:
        return self.result


class _TextFallbackFakePage(_FakePage):
    def __init__(self) -> None:
        super().__init__(aria_snapshot="")
        self.url = "https://example.com"

    def title(self) -> str:
        return "Example Search"

    def locator(self, selector: str) -> _FakeLocator:
        assert selector == "body"
        return _FakeLocator()


class _LaunchFakeContext:
    def __init__(self, page: _FakePage) -> None:
        self.page = page
        self.closed = False

    def new_page(self) -> _FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class _LaunchFakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self.context = _LaunchFakeContext(page)
        self.context_kwargs: dict[str, object] | None = None
        self.closed = False

    def new_context(self, **kwargs: object) -> _LaunchFakeContext:
        self.context_kwargs = kwargs
        return self.context

    def close(self) -> None:
        self.closed = True


class _LaunchFakeBrowserType:
    def __init__(self, browser: _LaunchFakeBrowser) -> None:
        self.browser = browser
        self.launch_kwargs: dict[str, object] | None = None

    def launch(self, **kwargs: object) -> _LaunchFakeBrowser:
        self.launch_kwargs = kwargs
        return self.browser


class _LaunchFakePlaywright:
    def __init__(self, browser_type: _LaunchFakeBrowserType) -> None:
        self.chromium = browser_type
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _LaunchFakeSyncPlaywright:
    def __init__(self, playwright: _LaunchFakePlaywright) -> None:
        self.playwright = playwright

    def start(self) -> _LaunchFakePlaywright:
        return self.playwright


def test_playwright_web_driver_runs_page_operations_on_one_worker_thread() -> None:
    driver = _ThreadedFakePlaywrightDriver()
    start = driver.start_browser(WebStartBrowserParams())
    external_thread_ids: set[int] = set()

    def navigate(url: str) -> dict[str, object]:
        external_thread_ids.add(threading.get_ident())
        return driver.navigate_to(WebNavigateToParams(url=url))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                navigate,
                ["https://example.com/one", "https://example.com/two"],
            )
        )

    snapshot = driver.ui_snapshot(WebUiSnapshotParams())
    context = driver.context()
    driver.close()

    assert start == {"status": "passed", "output": {"already_started": False, "url": "about:blank"}}
    assert [result["status"] for result in results] == ["passed", "passed"]
    assert snapshot == {
        "url": "https://example.com/two",
        "snapshot_type": "aria",
        "snapshot": '- document "Example" [ref=e1]',
    }
    assert driver.fake_page.aria_kwargs == {"mode": "ai"}
    assert context["current_url"] == "https://example.com/two"
    assert set(driver.fake_page.thread_ids) == {driver.create_thread_id}
    assert driver.create_thread_id not in external_thread_ids


def test_playwright_web_driver_ui_snapshot_falls_back_when_aria_snapshot_is_empty() -> None:
    driver = PlaywrightWebDriver(page=_TextFallbackFakePage())

    snapshot = driver.ui_snapshot(WebUiSnapshotParams())

    assert snapshot == {
        "url": "https://example.com",
        "snapshot_type": "text",
        "title": "Example Search",
        "text": "Search box\nResults",
    }


def test_playwright_web_driver_launches_configured_chrome_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage()
    browser = _LaunchFakeBrowser(page)
    browser_type = _LaunchFakeBrowserType(browser)
    playwright = _LaunchFakePlaywright(browser_type)
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: _LaunchFakeSyncPlaywright(playwright)
    playwright_package = types.ModuleType("playwright")
    playwright_package.sync_api = sync_api
    monkeypatch.setitem(sys.modules, "playwright", playwright_package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    driver = PlaywrightWebDriver(channel="chrome", executable_path="C:/Chrome/chrome.exe", headless=False, viewport=(1024, 768))
    try:
        start = driver.start_browser(WebStartBrowserParams())
        context = driver.context()
    finally:
        driver.close()

    assert start == {"status": "passed", "output": {"already_started": False, "url": "about:blank"}}
    assert browser_type.launch_kwargs == {"headless": False, "channel": "chrome", "executable_path": str(Path("C:/Chrome/chrome.exe"))}
    assert browser.context_kwargs == {"viewport": {"width": 1024, "height": 768}}
    assert context["metadata"]["channel"] == "chrome"
    assert context["metadata"]["browser_executable_configured"] is True
    assert browser.context.closed is True
    assert browser.closed is True
    assert playwright.stopped is True


def test_playwright_web_driver_rejects_unsupported_channel() -> None:
    with pytest.raises(ConfigurationError, match="Unsupported Playwright browser channel"):
        PlaywrightWebDriver(channel="firefox", page=_FakePage())


@pytest.mark.parametrize(
    "channel",
    ["chromium", "chrome", "chrome-beta", "chrome-dev", "chrome-canary", "msedge", "msedge-beta", "msedge-dev", "msedge-canary"],
)
def test_playwright_web_driver_accepts_all_supported_channels(channel: str) -> None:
    driver = PlaywrightWebDriver(channel=channel, page=_FakePage())
    try:
        assert driver.context()["metadata"]["channel"] == channel
    finally:
        driver.close()


def test_click_on_parses_truncated_snapshot_target_as_prefix() -> None:
    locator = _ClickFakeLocator()
    page = _ClickFakePage(locator)
    driver = PlaywrightWebDriver(page=page)

    result = driver.click_on(WebClickOnParams(target='link "GitHub - microsoft/FSQ: FSQ is an evidence-first agent ..." [ref=e12]'))

    assert result["status"] == "passed"
    role, kwargs = page.role_calls[0]
    assert role == "link"
    assert kwargs["name"].match("GitHub - microsoft/FSQ: FSQ is an evidence-first agent harness")
    assert locator.clicked is True


def test_click_on_composes_role_and_text_locator() -> None:
    locator = _ClickFakeLocator()
    page = _ClickFakePage(locator)
    driver = PlaywrightWebDriver(page=page)

    result = driver.click_on(WebClickOnParams(locator={"role": "link", "text": "microsoft/FSQ"}))

    assert result["status"] == "passed"
    assert len(locator.filters) == 1


def test_click_on_reports_ambiguous_target() -> None:
    driver = PlaywrightWebDriver(page=_ClickFakePage(_ClickFakeLocator(count=2)))

    result = driver.click_on(WebClickOnParams(locator={"role": "link"}))

    assert result["failure_category"] == "target_ambiguous"
    assert result["metadata"]["match_count"] == 2


def test_playwright_web_driver_does_not_launch_until_start_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: pytest.fail("Playwright must not be imported or started during construction")
    playwright_package = types.ModuleType("playwright")
    playwright_package.sync_api = sync_api
    monkeypatch.setitem(sys.modules, "playwright", playwright_package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    driver = PlaywrightWebDriver(channel="chrome", executable_path="C:/Chrome/chrome.exe")

    try:
        context = driver.context()
        result = driver.navigate_to(WebNavigateToParams(url="https://example.com"))
    finally:
        driver.close()

    assert context["current_url"] is None
    assert context["metadata"]["browser_started"] is False
    assert result["status"] == "failed"
    assert result["failure_category"] == "context_error"
    assert result["error_message"] == "Browser is not started. Call startBrowser before Web page actions."


def test_playwright_web_driver_start_and_close_browser_are_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage()
    browser = _LaunchFakeBrowser(page)
    browser_type = _LaunchFakeBrowserType(browser)
    playwright = _LaunchFakePlaywright(browser_type)
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: _LaunchFakeSyncPlaywright(playwright)
    playwright_package = types.ModuleType("playwright")
    playwright_package.sync_api = sync_api
    monkeypatch.setitem(sys.modules, "playwright", playwright_package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    driver = PlaywrightWebDriver(channel="chrome", executable_path="C:/Chrome/chrome.exe")
    first_start = driver.start_browser(WebStartBrowserParams())
    second_start = driver.start_browser(WebStartBrowserParams())
    first_close = driver.close_browser(WebCloseBrowserParams())
    second_close = driver.close_browser(WebCloseBrowserParams())
    driver.close()

    assert first_start == {"status": "passed", "output": {"already_started": False, "url": "about:blank"}}
    assert second_start == {"status": "passed", "output": {"already_started": True, "url": "about:blank"}}
    assert first_close == {"status": "passed", "output": {"already_closed": False}}
    assert second_close == {"status": "passed", "output": {"already_closed": True}}
    assert browser.context.closed is True
    assert browser.closed is True
    assert playwright.stopped is True
