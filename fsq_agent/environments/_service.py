# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import platform
from typing import TYPE_CHECKING, Literal

from fsq_agent.environments.providers._android import ANDROID_RUNTIME_PROVIDER
from fsq_agent.environments.providers._macos import MACOS_RUNTIME_PROVIDER
from fsq_agent.environments.providers._web import WEB_NAMES, WEB_RUNTIME_PROVIDER, web_candidate_paths
from fsq_agent.environments.providers._windows import WINDOWS_RUNTIME_PROVIDER
from fsq_agent.models import PlatformRuntimeCheck, web_executable_matches_channel

if TYPE_CHECKING:
    from pathlib import Path

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
