# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fsq_agent.adapters.control_plane.playground._state import PlaygroundSession
from fsq_agent.core import AndroidDeviceDiscovery, DriverFactory

if TYPE_CHECKING:
    from fsq_agent.config import Settings
    from fsq_agent.models import AndroidDevice


@dataclass(frozen=True)
class AndroidTarget:
    id: str
    label: str
    description: str = ""
    status: str = "device"
    is_default: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "status": self.status,
            "isDefault": self.is_default,
        }


def _project_android_targets(devices: list[AndroidDevice]) -> list[AndroidTarget]:
    targets: list[AndroidTarget] = []
    for device in devices:
        if device.state != "device":
            continue
        description_parts = [device.metadata.get("model"), device.metadata.get("device"), device.metadata.get("product")]
        description = " · ".join(value for value in description_parts if value)
        targets.append(
            AndroidTarget(
                id=device.serial,
                label=device.serial,
                description=description.replace("_", " ") or device.state,
                status=device.state,
                is_default=False,
            )
        )
    if len(targets) == 1:
        targets[0] = AndroidTarget(
            id=targets[0].id,
            label=targets[0].label,
            description=targets[0].description,
            status=targets[0].status,
            is_default=True,
        )
    return targets


def discover_adb_targets(timeout_seconds: float = 5.0) -> tuple[list[AndroidTarget], str | None]:
    result = AndroidDeviceDiscovery().discover(timeout_seconds=timeout_seconds)
    return _project_android_targets(result.devices), result.error_message


def build_android_setup_schema(settings: Settings) -> dict[str, object]:
    targets, error = discover_adb_targets()
    default_device_id = next((target.id for target in targets if target.is_default), None)
    _, auto_info = _resolve_auto_session_from_targets(targets, error)
    return {
        "title": "FSQ-Agent Android Playground",
        "description": "Select an available ADB device to run dynamic goals.",
        "primaryActionLabel": "Create Session",
        "autoSubmitWhenReady": len(targets) == 1,
        "notice": {"type": "warning", "message": "Android device discovery failed", "description": error} if error else None,
        "fields": [
            {
                "key": "deviceId",
                "label": "ADB device",
                "type": "select",
                "required": True,
                "options": [{"label": target.label, "value": target.id, "description": target.description} for target in targets],
                "defaultValue": default_device_id,
                "placeholder": "Select a connected Android device",
            }
        ],
        "targets": [target.to_json() for target in targets],
        "autoCreate": auto_info,
    }


def resolve_auto_session(settings: Settings) -> tuple[PlaygroundSession | None, dict[str, object]]:
    del settings
    targets, error = discover_adb_targets()
    return _resolve_auto_session_from_targets(targets, error)


def _resolve_auto_session_from_targets(
    targets: list[AndroidTarget],
    error: str | None,
) -> tuple[PlaygroundSession | None, dict[str, object]]:
    online_targets = [target for target in targets if target.status == "device"]
    target_payloads = [target.to_json() for target in targets]

    if len(online_targets) == 1:
        target = online_targets[0]
        return _session_from_target(target), {
            "available": True,
            "reason": "single_device",
            "deviceId": target.id,
            "targets": target_payloads,
        }
    if error and not online_targets:
        return None, {
            "available": False,
            "reason": "adb_error",
            "message": error,
            "targets": target_payloads,
        }
    if not online_targets:
        return None, {
            "available": False,
            "reason": "no_devices",
            "message": "No online Android devices found.",
            "targets": target_payloads,
        }
    return None, {
        "available": False,
        "reason": "multiple_devices",
        "message": "Multiple Android devices are online. Select one to continue.",
        "targets": target_payloads,
    }


def _session_from_target(target: AndroidTarget) -> PlaygroundSession:
    return PlaygroundSession(
        connected=True,
        device_id=target.id,
        display_name=target.label,
        metadata={"platform": "android", "description": target.description, "status": target.status},
    )


def capture_android_screenshot(settings: Settings, device_id: str | None) -> dict[str, object]:
    app_id = settings.harness.android.app_id
    if not app_id:
        return {"available": False, "error": "The workspace Android target app_id is required for screenshots."}
    driver = DriverFactory().create_android_driver(
        settings.harness.android,
        app_id=app_id,
        serial=device_id,
    )
    screenshot = driver.screenshot()
    return {
        "available": True,
        "screenshot": base64.b64encode(screenshot).decode("ascii"),
        "timestamp": int(time.time() * 1000),
    }
