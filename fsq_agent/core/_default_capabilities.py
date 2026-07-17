from fsq_agent.core.harness._driver_tools import _discover_driver_capability_definitions
from fsq_agent.core.harness._appium_mac2_driver import AppiumMac2Driver
from fsq_agent.core.harness._playwright_driver import PlaywrightWebDriver
from fsq_agent.core.harness._pywinauto_driver import PywinautoWindowsDriver
from fsq_agent.core.harness._uiautomator2_driver import UiAutomator2AndroidDriver
from fsq_agent.models import CapabilityDefinition, ConfigurationError, HarnessPlatform


class DefaultCapabilityDefinitionFactory:
    def platform_definitions(
        self,
        *,
        platform: HarnessPlatform,
        include_ai_assertion: bool = True,
    ) -> list[CapabilityDefinition]:
        if platform == "android":
            return android_capability_definitions(include_ai_assertion=include_ai_assertion)
        if platform == "web":
            return web_capability_definitions(include_ai_assertion=include_ai_assertion)
        if platform == "windows":
            return windows_capability_definitions(include_ai_assertion=include_ai_assertion)
        if platform == "macos":
            return macos_capability_definitions(include_ai_assertion=include_ai_assertion)
        raise ConfigurationError(
            "Unsupported harness platform.",
            context={"platform": platform, "supported": ["android", "web", "windows", "macos"]},
        )


def android_capability_definitions(*, include_ai_assertion: bool = True) -> list[CapabilityDefinition]:
    metadata: dict[str, object] = {"driver_class": UiAutomator2AndroidDriver.__name__, "backend": UiAutomator2AndroidDriver.backend}
    definitions = _discover_driver_capability_definitions(
        UiAutomator2AndroidDriver,
        platform="android",
        metadata=metadata,
    )
    if not include_ai_assertion:
        definitions = [definition for definition in definitions if definition.name != "assert_with_ai"]
    return definitions


def web_capability_definitions(*, include_ai_assertion: bool = True) -> list[CapabilityDefinition]:
    metadata: dict[str, object] = {"driver_class": PlaywrightWebDriver.__name__, "backend": PlaywrightWebDriver.backend}
    definitions = _discover_driver_capability_definitions(
        PlaywrightWebDriver,
        platform="web",
        metadata=metadata,
    )
    if not include_ai_assertion:
        definitions = [definition for definition in definitions if definition.name != "assert_with_ai"]
    return definitions


def windows_capability_definitions(*, include_ai_assertion: bool = True) -> list[CapabilityDefinition]:
    metadata: dict[str, object] = {"driver_class": PywinautoWindowsDriver.__name__, "backend": PywinautoWindowsDriver.backend}
    definitions = _discover_driver_capability_definitions(
        PywinautoWindowsDriver,
        platform="windows",
        metadata=metadata,
    )
    if not include_ai_assertion:
        definitions = [definition for definition in definitions if definition.name != "assert_with_ai"]
    return definitions


def macos_capability_definitions(*, include_ai_assertion: bool = True) -> list[CapabilityDefinition]:
    metadata: dict[str, object] = {"driver_class": AppiumMac2Driver.__name__, "backend": AppiumMac2Driver.backend}
    definitions = _discover_driver_capability_definitions(
        AppiumMac2Driver,
        platform="macos",
        metadata=metadata,
    )
    if not include_ai_assertion:
        definitions = [definition for definition in definitions if definition.name != "assert_with_ai"]
    return definitions
