# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import importlib.util
import platform
from dataclasses import dataclass

from fsq_agent.models import PlatformRuntimeCheck


@dataclass(frozen=True)
class RuntimeProvider:
    platform: str
    module: str
    required_host: str | None = None

    def check(self) -> PlatformRuntimeCheck:
        unsupported_action = self.unsupported_action()
        if unsupported_action is not None:
            return PlatformRuntimeCheck(platform=self.platform, status="unsupported", ready=False, message=f"{self.platform} platform runtime is unsupported on this host.", action=unsupported_action)
        if importlib.util.find_spec(self.module) is not None:
            return PlatformRuntimeCheck(platform=self.platform, status="ready", ready=True, message="Platform runtime is installed.")
        return PlatformRuntimeCheck(
            platform=self.platform,
            status="missing",
            ready=False,
            message=f"{self.platform} Python runtime dependency is missing from the fsq-agent installation.",
            action=f"Reinstall or repair fsq-agent; the {self.platform} Python runtime dependency is missing.",
        )

    def unsupported_action(self) -> str | None:
        if self.required_host is None or platform.system() == self.required_host:
            return None
        label = "Windows" if self.platform == "windows" else "macOS"
        return f"Run {label} platform tests on a {label} host."
