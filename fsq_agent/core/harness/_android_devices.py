# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import shutil
import subprocess

from fsq_agent.models import AndroidDevice, AndroidDeviceDiscoveryResult


class AndroidDeviceDiscovery:
    def discover(self, *, timeout_seconds: float = 5.0) -> AndroidDeviceDiscoveryResult:
        adb_path = shutil.which("adb")
        if adb_path is None:
            return _failure("adb_missing", "ADB is not installed or is not available on PATH.")
        try:
            completed = subprocess.run(  # noqa: S603 - executes the resolved ADB binary with fixed discovery arguments.
                [adb_path, "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            return _failure("adb_missing", "ADB is not installed or is not available on PATH.")
        except subprocess.TimeoutExpired:
            return _failure("adb_timeout", "ADB device discovery timed out.")
        except OSError:
            return _failure("adb_start_failed", "ADB device discovery could not start.")
        if completed.returncode != 0:
            return _failure("adb_failed", "ADB device discovery failed.")
        return AndroidDeviceDiscoveryResult(devices=_parse_devices(completed.stdout))


def _parse_devices(output: str) -> list[AndroidDevice]:
    devices: list[AndroidDevice] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("List of devices", "*")):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        devices.append(
            AndroidDevice(
                serial=parts[0],
                state=parts[1],
                metadata=_parse_metadata(parts[2:]),
            )
        )
    return devices


def _parse_metadata(parts: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for part in parts:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        if key and value:
            metadata[key] = value
    return metadata


def _failure(
    error_code: str,
    error_message: str,
) -> AndroidDeviceDiscoveryResult:
    return AndroidDeviceDiscoveryResult(error_code=error_code, error_message=error_message)
