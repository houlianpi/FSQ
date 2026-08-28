# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import platform
import shutil
import socket
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlparse

from fsq_agent.environments.providers._android import ANDROID_RUNTIME_PROVIDER, android_application_is_installed, discover_android_devices
from fsq_agent.environments.providers._macos import MACOS_RUNTIME_PROVIDER
from fsq_agent.environments.providers._web import WEB_NAMES, WEB_RUNTIME_PROVIDER, web_candidate_paths
from fsq_agent.environments.providers._windows import WINDOWS_RUNTIME_PROVIDER
from fsq_agent.models import PlatformRuntimeCheck, web_executable_matches_channel

if TYPE_CHECKING:
    from fsq_agent.environments.providers._runtime import RuntimeProvider

Platform = Literal["android", "web", "windows", "macos"]
_PROVIDERS: dict[Platform, RuntimeProvider] = {
    "android": ANDROID_RUNTIME_PROVIDER,
    "web": WEB_RUNTIME_PROVIDER,
    "windows": WINDOWS_RUNTIME_PROVIDER,
    "macos": MACOS_RUNTIME_PROVIDER,
}


def _web_candidate_paths(channel: str) -> list[Path]:
    return web_candidate_paths(channel)


class PlatformRuntimeService:
    def check(self, platform: Platform) -> PlatformRuntimeCheck:
        return _PROVIDERS[platform].check()

    def discover_web_executables(self, channel: str) -> list[Path]:
        candidates = _web_candidate_paths(channel)
        if platform.system() == "Windows":
            return sorted({candidate.expanduser().resolve() for candidate in candidates if candidate.is_file()})
        names = WEB_NAMES[channel]
        return sorted({candidate.expanduser().resolve() for candidate in candidates if candidate.is_file() and any(name in str(candidate).casefold() for name in names)})

    def web_executable_matches_channel(self, channel: str, executable: Path) -> bool:
        return web_executable_matches_channel(channel, executable)  # type: ignore[arg-type]

    def check_target_configuration(self, settings) -> tuple[bool, str, str]:
        try:
            valid = _target_configuration_valid(settings, self)
        except (AttributeError, TypeError, ValueError):
            return False, "Platform Target configuration is invalid.", "Repair the selected platform Target configuration."
        if not valid:
            return False, "Platform Target configuration is invalid.", "Repair the selected platform Target configuration."
        return True, "Platform Target configuration is ready.", ""

    def check_target_availability(self, settings) -> tuple[bool, str, str]:
        configured, message, action = self.check_target_configuration(settings)
        if not configured:
            return configured, message, action
        selected = settings.harness.platform
        if selected == "web":
            executable = Path(settings.harness.web.browser_executable_path)
            if executable.is_file() and self.web_executable_matches_channel(settings.harness.web.channel, executable):
                return True, "Configured browser Target is available.", ""
            return False, "The configured browser Target is unavailable.", "Repair or reselect the browser Target."
        if selected == "windows":
            if Path(settings.harness.windows.app_path).is_file():
                return True, "Configured Windows application Target is available.", ""
            return False, "The configured Windows application Target is unavailable.", "Repair or reselect the Windows application Target."
        if selected == "macos":
            if not _endpoint_available(settings.harness.macos.appium_server_url):
                return False, "The configured macOS Appium endpoint is unavailable.", "Start or repair the configured Appium server."
            app_path = settings.harness.macos.app_path
            if app_path is not None and Path(app_path).exists():
                return True, "Configured macOS application Target is available.", ""
            if settings.harness.macos.bundle_id and _macos_bundle_is_installed(settings.harness.macos.bundle_id):
                return True, "Configured macOS application Target is available.", ""
            return False, "The configured macOS application Target is unavailable.", "Repair or reselect the macOS application Target."
        from fsq_agent.models import AndroidDeviceDiscoveryResult

        discovery = discover_android_devices()
        if not isinstance(discovery, AndroidDeviceDiscoveryResult):
            return False, "No online authorized Android device is available.", "Connect and authorize an Android device."
        if discovery.error_code == "adb_missing":
            return False, "ADB is unavailable for Android Target discovery.", "Install Android platform tools and make adb available on PATH."
        if discovery.error_code:
            return False, "Android Target discovery could not be completed.", "Run environment diagnostics and repair ADB connectivity."
        serial = (settings.harness.android.serial or "").strip()
        online = [device for device in discovery.devices if device.state == "device"]
        if serial:
            online = [device for device in online if device.serial == serial]
        if not online:
            return False, "The configured Android device is not online and authorized.", "Connect and authorize the configured Android device."
        if not serial and len(online) != 1:
            return False, "Android Target selection is ambiguous.", "Configure an exact Android device serial."
        selected_device = online[0]
        if not android_application_is_installed(selected_device.serial, settings.harness.android.app_id):
            return False, "The configured Android application is not installed on the selected device.", "Install the application on the selected Android device."
        return True, "The configured Android device and application are available.", ""


def _target_configuration_valid(settings, service: PlatformRuntimeService) -> bool:
    selected = settings.harness.platform
    if selected == "android":
        app_id = (settings.harness.android.app_id or "").strip()
        serial = (settings.harness.android.serial or "").strip()
        return bool(app_id) and not any(character.isspace() for character in app_id) and not any(character.isspace() for character in serial)
    if selected == "web":
        executable = settings.harness.web.browser_executable_path
        return executable is not None and Path(executable).is_file() and service.web_executable_matches_channel(settings.harness.web.channel, Path(executable))
    if selected == "windows":
        executable = settings.harness.windows.app_path
        return executable is not None and Path(executable).is_file()
    if selected == "macos":
        executable = settings.harness.macos.app_path
        has_identity = bool((settings.harness.macos.bundle_id or "").strip()) or executable is not None
        endpoint = urlparse(settings.harness.macos.appium_server_url or "")
        path_valid = executable is None or (Path(executable).exists() and (Path(executable).suffix.casefold() == ".app" or Path(executable).is_file()))
        return has_identity and path_valid and endpoint.scheme in {"http", "https"} and bool(endpoint.hostname) and endpoint.port is not None
    return False


def _macos_bundle_is_installed(bundle_id: str, timeout_seconds: float = 5.0) -> bool:
    metadata_query = shutil.which("mdfind")
    if platform.system() != "Darwin" or metadata_query is None:
        return False
    try:
        completed = subprocess.run(  # noqa: S603 - resolved system metadata tool with a read-only exact bundle-id query.
            [metadata_query, f"kMDItemCFBundleIdentifier == '{bundle_id}'"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and any(Path(line).exists() for line in completed.stdout.splitlines() if line.strip())


def _endpoint_available(url: str, timeout_seconds: float = 1.0) -> bool:
    parsed = urlparse(url)
    if parsed.hostname is None or parsed.port is None:
        return False
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=timeout_seconds):
            return True
    except OSError:
        return False
