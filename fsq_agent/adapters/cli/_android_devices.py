# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from typing import TYPE_CHECKING

from fsq_agent.core import AndroidDeviceDiscovery
from fsq_agent.models import AndroidDevice, ConfigurationError

if TYPE_CHECKING:
    from fsq_agent.config import Settings


def select_android_serial(settings: Settings, requested_serial: str | None) -> str | None:
    serial = requested_serial.strip() if requested_serial is not None else None
    if requested_serial is not None and not serial:
        raise ConfigurationError("--android-serial requires a non-empty serial.")
    if settings.harness.platform != "android":
        if serial is not None:
            raise ConfigurationError("--android-serial is only supported for Android workspaces.")
        return None

    discovery = AndroidDeviceDiscovery().discover()
    if discovery.error_code is not None:
        raise ConfigurationError(
            discovery.error_message or "ADB device discovery failed.",
            context={"code": discovery.error_code},
        )
    devices = discovery.devices
    if serial is not None:
        matched = next((device for device in devices if device.serial == serial), None)
        if matched is None:
            raise ConfigurationError(
                f"Android device {serial} was not discovered.",
                context={"serial": serial, "devices": _device_states(devices)},
            )
        if matched.state != "device":
            raise ConfigurationError(
                f"Android device {serial} is not online (state: {matched.state}).",
                context={"serial": serial, "state": matched.state},
            )
        settings.harness.android.serial = serial
        return serial

    online_devices = [device for device in devices if device.state == "device"]
    if not online_devices:
        raise ConfigurationError(
            "No online Android devices were discovered.",
            context={"devices": _device_states(devices)},
        )
    if len(online_devices) > 1:
        raise ConfigurationError(
            "Multiple online Android devices were discovered; select one with --android-serial.",
            context={"serials": [device.serial for device in online_devices]},
        )
    selected_serial = online_devices[0].serial
    settings.harness.android.serial = selected_serial
    return selected_serial


def _device_states(devices: list[AndroidDevice]) -> dict[str, str]:
    return {device.serial: device.state for device in devices}
