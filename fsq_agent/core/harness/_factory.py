# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from fsq_agent.core.harness._android import AndroidHarness
from fsq_agent.core.harness._appium_mac2_driver import AppiumMac2Driver
from fsq_agent.core.harness._macos import MacOSHarness
from fsq_agent.core.harness._playwright_driver import PlaywrightWebDriver
from fsq_agent.core.harness._pywinauto_driver import PywinautoWindowsDriver
from fsq_agent.core.harness._uiautomator2_driver import UiAutomator2AndroidDriver
from fsq_agent.core.harness._web import WebHarness
from fsq_agent.core.harness._windows import WindowsHarness
from fsq_agent.models import (
    AndroidHarnessSettings,
    ConfigurationError,
    HarnessPlatform,
    HarnessSettings,
    MacOSHarnessSettings,
    RuntimeSecretSettings,
    WebHarnessSettings,
    WindowsHarnessSettings,
)

if TYPE_CHECKING:
    from fsq_agent.core.evidence import ArtifactStore
    from fsq_agent.core.harness._android_driver import AndroidDriverInterface
    from fsq_agent.core.harness._interface import AIAssertionEvaluatorProtocol, HarnessInterface
    from fsq_agent.core.harness._macos_driver import MacOSDriverInterface
    from fsq_agent.core.harness._web_driver import WebDriverInterface
    from fsq_agent.core.harness._windows_driver import WindowsDriverInterface

_ANDROID_BACKENDS = ("uiautomator2",)
_WEB_BACKENDS = ("playwright",)
_WINDOWS_BACKENDS = ("pywinauto",)
_MACOS_BACKENDS = ("appium_mac2",)
_CAPABILITY_DRIVER_CLASSES: dict[HarnessPlatform, dict[str, type[object]]] = {
    "android": {"uiautomator2": cast("type[object]", UiAutomator2AndroidDriver)},
    "web": {"playwright": cast("type[object]", PlaywrightWebDriver)},
    "windows": {"pywinauto": cast("type[object]", PywinautoWindowsDriver)},
    "macos": {"appium_mac2": cast("type[object]", AppiumMac2Driver)},
}


class _DriverFactoryProtocol(Protocol):
    def create_android_driver(
        self,
        settings: AndroidHarnessSettings,
        *,
        app_id: str | None = None,
        serial: str | None = None,
    ) -> AndroidDriverInterface: ...

    def create_web_driver(self, settings: WebHarnessSettings) -> WebDriverInterface: ...

    def create_windows_driver(self, settings: WindowsHarnessSettings) -> WindowsDriverInterface: ...

    def create_macos_driver(self, settings: MacOSHarnessSettings) -> MacOSDriverInterface: ...


class _HarnessFactoryProtocol(Protocol):
    def create_harness(
        self,
        *,
        platform: HarnessPlatform,
        harness_settings: HarnessSettings,
        artifact_store: ArtifactStore | None = None,
        ai_assertion_evaluator: AIAssertionEvaluatorProtocol | None = None,
        runtime_secret_settings: RuntimeSecretSettings | None = None,
        app_id: str | None = None,
        serial: str | None = None,
    ) -> HarnessInterface: ...


class DriverFactory:
    def create_android_driver(
        self,
        settings: AndroidHarnessSettings,
        *,
        app_id: str | None = None,
        serial: str | None = None,
    ) -> AndroidDriverInterface:
        _ensure_backend(platform="android", backend=settings.backend, supported=_ANDROID_BACKENDS)
        return UiAutomator2AndroidDriver(
            app_id=app_id if app_id is not None else settings.app_id or "",
            serial=serial if serial is not None else settings.serial,
        )

    def create_web_driver(self, settings: WebHarnessSettings) -> WebDriverInterface:
        _ensure_backend(platform="web", backend=settings.backend, supported=_WEB_BACKENDS)
        return PlaywrightWebDriver(
            channel=settings.channel,
            executable_path=settings.browser_executable_path,
            headless=settings.headless,
            base_url=settings.base_url,
            viewport=_web_viewport(settings),
        )

    def create_windows_driver(self, settings: WindowsHarnessSettings) -> WindowsDriverInterface:
        _ensure_backend(platform="windows", backend=settings.backend, supported=_WINDOWS_BACKENDS)
        return PywinautoWindowsDriver(
            app_path=settings.app_path,
            backend_kind=settings.backend_kind,
            window_title_re=settings.window_title_re,
            launch_args=settings.launch_args,
        )

    def create_macos_driver(self, settings: MacOSHarnessSettings) -> MacOSDriverInterface:
        _ensure_backend(platform="macos", backend=settings.backend, supported=_MACOS_BACKENDS)
        return AppiumMac2Driver(
            server_url=settings.appium_server_url or "",
            bundle_id=settings.bundle_id,
            app_path=settings.app_path,
            page_source_max_depth=settings.page_source_max_depth,
            action_timeout_seconds=settings.action_timeout_seconds,
        )


class HarnessFactory:
    def __init__(self, driver_factory: _DriverFactoryProtocol | None = None) -> None:
        self.driver_factory = driver_factory or DriverFactory()

    def create_harness(
        self,
        *,
        platform: HarnessPlatform,
        harness_settings: HarnessSettings,
        artifact_store: ArtifactStore | None = None,
        ai_assertion_evaluator: AIAssertionEvaluatorProtocol | None = None,
        runtime_secret_settings: RuntimeSecretSettings | None = None,
        app_id: str | None = None,
        serial: str | None = None,
    ) -> HarnessInterface:
        if platform == "android":
            return AndroidHarness(
                driver=self.driver_factory.create_android_driver(
                    harness_settings.android,
                    app_id=app_id,
                    serial=serial,
                ),
                artifact_store=artifact_store,
                ai_assertion_evaluator=ai_assertion_evaluator,
                runtime_secret_settings=runtime_secret_settings,
            )
        if platform == "web":
            return WebHarness(
                driver=self.driver_factory.create_web_driver(harness_settings.web),
                artifact_store=artifact_store,
                ai_assertion_evaluator=ai_assertion_evaluator,
                runtime_secret_settings=runtime_secret_settings,
            )
        if platform == "windows":
            return WindowsHarness(
                driver=self.driver_factory.create_windows_driver(harness_settings.windows),
                artifact_store=artifact_store,
                ai_assertion_evaluator=ai_assertion_evaluator,
                runtime_secret_settings=runtime_secret_settings,
            )
        if platform == "macos":
            return MacOSHarness(
                driver=self.driver_factory.create_macos_driver(harness_settings.macos),
                artifact_store=artifact_store,
                ai_assertion_evaluator=ai_assertion_evaluator,
                runtime_secret_settings=runtime_secret_settings,
            )
        raise ConfigurationError(
            "Unsupported harness platform.",
            context={"platform": platform, "supported": ["android", "web", "windows", "macos"]},
        )


def _driver_class_for_backend(platform: HarnessPlatform, backend: str | None = None) -> type[object]:
    if platform == "android":
        selected = backend or _ANDROID_BACKENDS[0]
        _ensure_backend(platform=platform, backend=selected, supported=_ANDROID_BACKENDS)
        return _CAPABILITY_DRIVER_CLASSES[platform][selected]
    if platform == "web":
        selected = backend or _WEB_BACKENDS[0]
        _ensure_backend(platform=platform, backend=selected, supported=_WEB_BACKENDS)
        return _CAPABILITY_DRIVER_CLASSES[platform][selected]
    if platform == "windows":
        selected = backend or _WINDOWS_BACKENDS[0]
        _ensure_backend(platform=platform, backend=selected, supported=_WINDOWS_BACKENDS)
        return _CAPABILITY_DRIVER_CLASSES[platform][selected]
    if platform == "macos":
        selected = backend or _MACOS_BACKENDS[0]
        _ensure_backend(platform=platform, backend=selected, supported=_MACOS_BACKENDS)
        return _CAPABILITY_DRIVER_CLASSES[platform][selected]
    raise ConfigurationError(
        "Unsupported harness platform.",
        context={"platform": platform, "supported": ["android", "web", "windows", "macos"]},
    )


def _ensure_backend(*, platform: HarnessPlatform, backend: str, supported: tuple[str, ...]) -> None:
    if backend in supported:
        return
    raise ConfigurationError(
        f"Unsupported {platform} harness backend.",
        context={"platform": platform, "backend": backend, "supported": list(supported)},
    )


def _web_viewport(settings: WebHarnessSettings) -> tuple[int, int] | None:
    if settings.viewport_width is None or settings.viewport_height is None:
        return None
    return (settings.viewport_width, settings.viewport_height)
