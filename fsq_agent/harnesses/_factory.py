# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from fsq_agent.drivers._factory import _DriverFactoryImplementation
from fsq_agent.harnesses._android import AndroidHarness
from fsq_agent.harnesses._macos import MacOSHarness
from fsq_agent.harnesses._web import WebHarness
from fsq_agent.harnesses._windows import WindowsHarness
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
    from fsq_agent.core.interfaces import (
        AIAssertionEvaluatorProtocol,
        AndroidDriverInterface,
        HarnessInterface,
        MacOSDriverInterface,
        WebDriverInterface,
        WindowsDriverInterface,
    )


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


class _HarnessFactoryImplementation:
    def __init__(self, driver_factory: _DriverFactoryProtocol | None = None) -> None:
        self.driver_factory = driver_factory or _DriverFactoryImplementation()

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
