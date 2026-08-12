# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from typing import Any

from fsq_agent.config import Settings, validate_strict_core_settings

from ._evidence import safe_exception_message

_TARGET_LABELS = {"android": "Device", "web": "Browser", "windows": "Application", "macos": "Application"}
_BACKEND_MODULES = {"android": "uiautomator2", "web": "playwright", "windows": "pywinauto", "macos": "appium"}


def discover_targets(settings: Settings, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    platform = settings.harness.platform
    if platform == "android":
        targets = _discover_android(settings, timeout_seconds)
    else:
        targets = [_configured_target(settings)]
    return {"platform": platform, "targetLabel": _TARGET_LABELS[platform], "targets": targets}


def validate_target(settings: Settings, target_id: str) -> dict[str, Any]:
    normalized = target_id.strip()
    if not normalized:
        raise ValueError("targetId is required.")
    module = _BACKEND_MODULES[settings.harness.platform]
    if importlib.util.find_spec(module) is None:
        raise ValueError(f"The {settings.harness.platform} backend package is not installed.")
    targets = discover_targets(settings)["targets"]
    for target in targets:
        if target["id"] == normalized and target["selectable"]:
            return target
    raise ValueError("The selected target is unavailable. Refresh targets and select an available target.")


def target_readiness(settings: Settings) -> tuple[bool, str, str]:
    module = _BACKEND_MODULES[settings.harness.platform]
    if importlib.util.find_spec(module) is None:
        return False, f"The {settings.harness.platform} backend package is not installed.", "Install the platform optional dependencies."
    try:
        validate_strict_core_settings(settings)
    except Exception as exc:  # noqa: BLE001 - readiness turns boundary failures into safe status.
        return False, safe_exception_message(exc, settings=settings), "Configure the selected platform target and retry."
    if settings.harness.platform == "android":
        targets = _discover_android(settings, 5.0)
        if not any(target["selectable"] for target in targets):
            return False, str(targets[0]["description"]), "Connect and authorize an Android device, then refresh."
    return True, "Target configuration is ready.", ""


def _discover_android(settings: Settings, timeout_seconds: float) -> list[dict[str, Any]]:
    adb_path = shutil.which("adb")
    if adb_path is None:
        return [_unavailable("adb-missing", "ADB is not installed or not on PATH.", "missing")]
    try:
        completed = subprocess.run(  # noqa: S603 - executes a fixed local ADB discovery command without shell input.
            [adb_path, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return [_unavailable("adb-missing", "ADB is not installed or not on PATH.", "missing")]
    except subprocess.TimeoutExpired:
        return [_unavailable("adb-timeout", "ADB target discovery timed out.", "timeout")]
    except OSError:
        return [_unavailable("adb-error", "ADB target discovery could not start.", "error")]
    if completed.returncode != 0:
        return [_unavailable("adb-error", "ADB target discovery failed.", "error")]

    default_serial = settings.harness.android.serial
    targets: list[dict[str, Any]] = []
    for raw_line in completed.stdout.splitlines()[1:]:
        line = raw_line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[:2]
        metadata = _adb_metadata(parts[2:])
        selectable = state == "device"
        label = str(metadata.get("model") or metadata.get("device") or serial)
        description = "Android device is online." if selectable else f"Android device is {state}."
        targets.append(
            {
                "id": serial,
                "label": label,
                "description": description,
                "status": "ready" if selectable else state,
                "selectable": selectable,
                "isDefault": serial == default_serial or (default_serial is None and selectable and not any(item["selectable"] for item in targets)),
                "metadata": {"transport": "adb", **metadata},
            }
        )
    return targets or [_unavailable("adb-empty", "No Android devices were discovered.", "unavailable")]


def _adb_metadata(parts: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for part in parts:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        if key in {"model", "device", "product", "transport_id"}:
            metadata[key] = value
    return metadata


def _configured_target(settings: Settings) -> dict[str, Any]:
    platform = settings.harness.platform
    ready, message, _ = target_readiness_without_discovery(settings)
    if platform == "web":
        target_id = "chrome"
        label = "Chrome"
        metadata = {"channel": settings.harness.web.channel, "headless": settings.harness.web.headless}
    elif platform == "windows":
        target_id = "windows-app"
        app_path = settings.harness.windows.app_path
        label = app_path.stem if app_path else "Windows application"
        metadata = {"backend": settings.harness.windows.backend_kind}
    else:
        target_id = "macos-app"
        app_path = settings.harness.macos.app_path
        label = settings.harness.macos.bundle_id or (app_path.stem if app_path else "macOS application")
        metadata = {"backend": settings.harness.macos.backend}
    return {
        "id": target_id,
        "label": label,
        "description": message,
        "status": "ready" if ready else "unavailable",
        "selectable": ready,
        "isDefault": ready,
        "metadata": metadata,
    }


def target_readiness_without_discovery(settings: Settings) -> tuple[bool, str, str]:
    module = _BACKEND_MODULES[settings.harness.platform]
    if importlib.util.find_spec(module) is None:
        return False, f"The {settings.harness.platform} backend package is not installed.", "Install the platform optional dependencies."
    try:
        validate_strict_core_settings(settings)
    except Exception as exc:  # noqa: BLE001
        return False, safe_exception_message(exc, settings=settings), "Configure the selected platform target and retry."
    return True, "Configured local target is ready.", ""


def _unavailable(target_id: str, description: str, status: str) -> dict[str, Any]:
    return {"id": target_id, "label": "Unavailable", "description": description, "status": status, "selectable": False, "isDefault": False, "metadata": {}}


__all__ = ["discover_targets", "target_readiness", "validate_target"]
