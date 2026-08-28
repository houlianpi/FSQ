# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import shutil
import subprocess

from fsq_agent.environments.providers._runtime import RuntimeProvider
from fsq_agent.models import AndroidDevice, AndroidDeviceDiscoveryResult

ANDROID_RUNTIME_PROVIDER = RuntimeProvider(platform="android", module="uiautomator2")


def discover_android_devices(timeout_seconds: float = 5.0) -> AndroidDeviceDiscoveryResult:
    adb_path = shutil.which("adb")
    if adb_path is None:
        return AndroidDeviceDiscoveryResult(error_code="adb_missing", error_message="ADB is unavailable.")
    try:
        completed = subprocess.run(  # noqa: S603 - resolved ADB binary with fixed read-only discovery arguments.
            [adb_path, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return AndroidDeviceDiscoveryResult(error_code="adb_timeout", error_message="ADB discovery timed out.")
    except OSError:
        return AndroidDeviceDiscoveryResult(error_code="adb_failed", error_message="ADB discovery failed.")
    if completed.returncode != 0:
        return AndroidDeviceDiscoveryResult(error_code="adb_failed", error_message="ADB discovery failed.")
    devices = []
    for line in completed.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and not line.startswith(("List of devices", "*")):
            devices.append(AndroidDevice(serial=parts[0], state=parts[1]))
    return AndroidDeviceDiscoveryResult(devices=devices)


def android_application_is_installed(serial: str, app_id: str, timeout_seconds: float = 5.0) -> bool:
    adb_path = shutil.which("adb")
    if adb_path is None:
        return False
    try:
        completed = subprocess.run(  # noqa: S603 - fixed read-only package query for an exact device and app id.
            [adb_path, "-s", serial, "shell", "pm", "path", app_id],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and any(line.startswith("package:") for line in completed.stdout.splitlines())
