# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import importlib.util
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Literal

from fsq_agent.models import PlatformRuntimeCheck, web_executable_matches_channel

Platform = Literal["android", "web", "windows", "macos"]

_MODULES = {"android": "uiautomator2", "web": "playwright", "windows": "pywinauto", "macos": "appium"}
_EXTRAS = {"android": "android", "web": "web", "windows": "windows", "macos": "macos"}
_WEB_NAMES = {
    "chromium": ("chromium",),
    "chrome": ("google chrome", "google-chrome", "chrome.exe"),
    "chrome-beta": ("google chrome beta", "google-chrome-beta"),
    "chrome-dev": ("google chrome dev", "google-chrome-unstable"),
    "chrome-canary": ("google chrome canary", "chrome sxs"),
    "msedge": ("microsoft edge", "msedge.exe"),
    "msedge-beta": ("microsoft edge beta",),
    "msedge-dev": ("microsoft edge dev",),
    "msedge-canary": ("microsoft edge canary", "edge sxs"),
}
def _web_candidate_paths(channel: str) -> list[Path]:
    names = _WEB_NAMES[channel]
    if platform.system() == "Windows":
        roots = [Path(value) for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA") if (value := os.environ.get(key))]
        relative_paths = {
            "chrome": (Path("Google/Chrome/Application/chrome.exe"),),
            "chrome-beta": (Path("Google/Chrome Beta/Application/chrome.exe"),),
            "chrome-dev": (Path("Google/Chrome Dev/Application/chrome.exe"),),
            "chrome-canary": (Path("Google/Chrome SxS/Application/chrome.exe"),),
            "msedge": (Path("Microsoft/Edge/Application/msedge.exe"),),
            "msedge-beta": (Path("Microsoft/Edge Beta/Application/msedge.exe"),),
            "msedge-dev": (Path("Microsoft/Edge Dev/Application/msedge.exe"),),
            "msedge-canary": (Path("Microsoft/Edge SxS/Application/msedge.exe"),),
            "chromium": (Path("Chromium/Application/chrome.exe"),),
        }
        return [root / relative for root in roots for relative in relative_paths[channel]]
    roots = [Path("/Applications"), Path.home() / "Applications"]
    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for app in root.glob("*.app"):
            if any(name in app.name.casefold() for name in names):
                executable = app / "Contents" / "MacOS" / app.stem
                candidates.append(executable)
    for directory in (Path("/usr/bin"), Path("/usr/local/bin"), Path("/opt/homebrew/bin")):
        candidates.extend(directory / name for name in names)
    return candidates


class PlatformRuntimeService:
    def check(self, platform: Platform) -> PlatformRuntimeCheck:
        unsupported_action = _unsupported_action(platform)
        if unsupported_action is not None:
            return PlatformRuntimeCheck(platform=platform, status="unsupported", ready=False, message=f"{platform} platform runtime is unsupported on this host.", action=unsupported_action)
        module = _MODULES[platform]
        if importlib.util.find_spec(module) is not None:
            return PlatformRuntimeCheck(platform=platform, status="ready", ready=True, message="Platform runtime is installed.")
        action = f"{sys.executable} -m pip install 'fsq-agent[{_EXTRAS[platform]}]'"
        return PlatformRuntimeCheck(platform=platform, status="missing", ready=False, message=f"{platform} platform runtime is not installed.", action=action)

    def install(self, platform: Platform) -> PlatformRuntimeCheck:
        unsupported_action = _unsupported_action(platform)
        if unsupported_action is not None:
            return PlatformRuntimeCheck(platform=platform, status="unsupported", ready=False, message=f"Automatic {platform} runtime installation is unsupported on this host.", action=unsupported_action)
        command = [sys.executable, "-m", "pip", "install", f"fsq-agent[{_EXTRAS[platform]}]"]
        try:
            completed = subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)  # noqa: S603
        except (OSError, subprocess.TimeoutExpired):
            return PlatformRuntimeCheck(platform=platform, status="missing", ready=False, message="Platform runtime installation failed.", action="Install the platform extra manually and retry.")
        if completed.returncode != 0:
            return PlatformRuntimeCheck(platform=platform, status="missing", ready=False, message="Platform runtime installation failed.", action="Install the platform extra manually and retry.")
        return self.check(platform)

    def discover_web_executables(self, channel: str) -> list[Path]:
        candidates = _web_candidate_paths(channel)
        if platform.system() == "Windows":
            matches = {candidate.expanduser().resolve() for candidate in candidates if candidate.is_file()}
            return sorted(matches)
        names = _WEB_NAMES[channel]
        matches = {candidate.expanduser().resolve() for candidate in candidates if candidate.is_file() and any(name in str(candidate).casefold() for name in names)}
        return sorted(matches)

    def web_executable_matches_channel(self, channel: str, executable: Path) -> bool:
        """Return whether an explicit executable path identifies the selected channel."""
        return web_executable_matches_channel(channel, executable)  # type: ignore[arg-type]


def _unsupported_action(target: Platform) -> str | None:
    host = platform.system()
    if target == "windows" and host != "Windows":
        return "Run Windows platform tests on a Windows host."
    if target == "macos" and host != "Darwin":
        return "Run macOS platform tests on a macOS host."
    return None
