from __future__ import annotations

from dataclasses import dataclass
import base64
import subprocess
import time

from fsq_agent.config import Settings
from fsq_agent.core import DriverFactory
from fsq_agent.playground._state import PlaygroundSession


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


def parse_adb_devices(output: str) -> list[AndroidTarget]:
    targets: list[AndroidTarget] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("List of devices"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        serial, status = parts[0], parts[1]
        if status != "device":
            continue
        metadata = _parse_adb_metadata(parts[2:])
        description_parts = [metadata.get("model"), metadata.get("device"), metadata.get("product")]
        description = " · ".join(value for value in description_parts if value)
        targets.append(
            AndroidTarget(
                id=serial,
                label=serial,
                description=description or status,
                status=status,
                is_default=False,
            )
        )
    if targets:
        targets[0] = AndroidTarget(
            id=targets[0].id,
            label=targets[0].label,
            description=targets[0].description,
            status=targets[0].status,
            is_default=True,
        )
    return targets


def discover_adb_targets(timeout_seconds: float = 5.0) -> tuple[list[AndroidTarget], str | None]:
    try:
        completed = subprocess.run(
            ["adb", "devices", "-l"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return [], "adb was not found on PATH. Install Android platform tools and try again."
    except subprocess.TimeoutExpired:
        return [], "adb device discovery timed out."
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "adb devices failed"
        return [], detail
    return parse_adb_devices(completed.stdout), None


def build_android_setup_schema(settings: Settings) -> dict[str, object]:
    targets, error = discover_adb_targets()
    configured_serial = settings.harness.android.serial
    default_device_id = configured_serial or next((target.id for target in targets if target.is_default), None)
    _, auto_info = _resolve_auto_session_from_targets(settings, targets, error)
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
                "options": [
                    {"label": target.label, "value": target.id, "description": target.description}
                    for target in targets
                ],
                "defaultValue": default_device_id,
                "placeholder": "Select a connected Android device",
            }
        ],
        "targets": [target.to_json() for target in targets],
        "autoCreate": auto_info,
    }


def resolve_auto_session(settings: Settings) -> tuple[PlaygroundSession | None, dict[str, object]]:
    targets, error = discover_adb_targets()
    return _resolve_auto_session_from_targets(settings, targets, error)


def _resolve_auto_session_from_targets(
    settings: Settings,
    targets: list[AndroidTarget],
    error: str | None,
) -> tuple[PlaygroundSession | None, dict[str, object]]:
    online_targets = [target for target in targets if target.status == "device"]
    target_payloads = [target.to_json() for target in targets]
    configured_serial = settings.harness.android.serial

    if configured_serial:
        matched = next((target for target in online_targets if target.id == configured_serial), None)
        if matched is not None:
            return _session_from_target(matched), {
                "available": True,
                "reason": "configured_serial",
                "deviceId": matched.id,
                "targets": target_payloads,
            }
        return None, {
            "available": False,
            "reason": "configured_serial_offline",
            "message": f"Configured FSQ_ANDROID_SERIAL is not online: {configured_serial}",
            "configuredSerial": configured_serial,
            "targets": target_payloads,
        }

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
        return {"available": False, "error": "FSQ_ANDROID_APP_ID is required for screenshots."}
    driver = DriverFactory().create_android_driver(
        settings.harness.android,
        app_id=app_id,
        serial=device_id or settings.harness.android.serial,
    )
    screenshot = driver.screenshot()
    return {
        "available": True,
        "screenshot": base64.b64encode(screenshot).decode("ascii"),
        "timestamp": int(time.time() * 1000),
    }


def _parse_adb_metadata(parts: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for part in parts:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        if key and value:
            metadata[key] = value.replace("_", " ")
    return metadata