# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import os
import platform
from pathlib import Path

from fsq_agent.environments.providers._runtime import RuntimeProvider

WEB_RUNTIME_PROVIDER = RuntimeProvider(platform="web", module="playwright", extra="web")
WEB_NAMES = {
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
WINDOWS_RELATIVE_PATHS = {
    "chrome": "Google/Chrome/Application/chrome.exe",
    "chrome-beta": "Google/Chrome Beta/Application/chrome.exe",
    "chrome-dev": "Google/Chrome Dev/Application/chrome.exe",
    "chrome-canary": "Google/Chrome SxS/Application/chrome.exe",
    "msedge": "Microsoft/Edge/Application/msedge.exe",
    "msedge-beta": "Microsoft/Edge Beta/Application/msedge.exe",
    "msedge-dev": "Microsoft/Edge Dev/Application/msedge.exe",
    "msedge-canary": "Microsoft/Edge SxS/Application/msedge.exe",
    "chromium": "Chromium/Application/chrome.exe",
}


def web_candidate_paths(channel: str) -> list[Path]:
    names = WEB_NAMES[channel]
    if platform.system() == "Windows":
        roots = [Path(value) for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA") if (value := os.environ.get(key))]
        return [root / WINDOWS_RELATIVE_PATHS[channel] for root in roots]
    roots = [Path("/Applications"), Path.home() / "Applications"]
    candidates = [app / "Contents" / "MacOS" / app.stem for root in roots if root.is_dir() for app in root.glob("*.app") if any(name in app.name.casefold() for name in names)]
    for directory in (Path("/usr/bin"), Path("/usr/local/bin"), Path("/opt/homebrew/bin")):
        candidates.extend(directory / name for name in names)
    return candidates
