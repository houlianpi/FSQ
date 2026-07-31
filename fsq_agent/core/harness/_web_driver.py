# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Protocol, runtime_checkable

from fsq_agent.core.harness._interface import DriverObservationInterface
from fsq_agent.models import (
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


@runtime_checkable
class WebDriverInterface(DriverObservationInterface, Protocol):
    def context(self) -> dict[str, object]: ...

    def start_browser(self, params: WebStartBrowserParams) -> dict[str, object]: ...

    def close_browser(self, params: WebCloseBrowserParams) -> dict[str, object]: ...

    def navigate_to(self, params: WebNavigateToParams) -> dict[str, object]: ...

    def navigate_back(self, params: WebNavigateBackParams) -> dict[str, object]: ...

    def click_on(self, params: WebClickOnParams) -> dict[str, object]: ...

    def type_text(self, params: WebTypeTextParams) -> dict[str, object]: ...

    def select_option(self, params: WebSelectOptionParams) -> dict[str, object]: ...

    def hover_on(self, params: WebHoverOnParams) -> dict[str, object]: ...

    def press_key(self, params: WebPressKeyParams) -> dict[str, object]: ...

    def wait_for(self, params: WebWaitForParams) -> dict[str, object]: ...

    def take_screenshot(self, params: WebTakeScreenshotParams) -> dict[str, object]: ...

    def page_snapshot(self, params: WebPageSnapshotParams) -> dict[str, object]: ...

    def assert_visible(self, params: WebAssertVisibleParams) -> dict[str, object]: ...

    def assert_not_visible(self, params: WebAssertNotVisibleParams) -> dict[str, object]: ...

    def assert_text(self, params: WebAssertTextParams) -> dict[str, object]: ...

    def assert_with_ai(self, params: WebAssertWithAIParams) -> dict[str, object]: ...

    def screenshot(self, params: WebTakeScreenshotParams | None = None) -> bytes: ...
