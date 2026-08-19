# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import importlib.util
import platform
import subprocess
import sys
from dataclasses import dataclass

from fsq_agent.models import PlatformRuntimeCheck


@dataclass(frozen=True)
class RuntimeProvider:
    platform: str
    module: str
    extra: str
    required_host: str | None = None

    def check(self) -> PlatformRuntimeCheck:
        unsupported_action = self.unsupported_action()
        if unsupported_action is not None:
            return PlatformRuntimeCheck(platform=self.platform, status="unsupported", ready=False, message=f"{self.platform} platform runtime is unsupported on this host.", action=unsupported_action)
        if importlib.util.find_spec(self.module) is not None:
            return PlatformRuntimeCheck(platform=self.platform, status="ready", ready=True, message="Platform runtime is installed.")
        return PlatformRuntimeCheck(
            platform=self.platform, status="missing", ready=False, message=f"{self.platform} platform runtime is not installed.", action=f"{sys.executable} -m pip install 'fsq-agent[{self.extra}]'"
        )

    def install(self) -> PlatformRuntimeCheck:
        unsupported_action = self.unsupported_action()
        if unsupported_action is not None:
            return PlatformRuntimeCheck(
                platform=self.platform, status="unsupported", ready=False, message=f"Automatic {self.platform} runtime installation is unsupported on this host.", action=unsupported_action
            )
        command = [sys.executable, "-m", "pip", "install", f"fsq-agent[{self.extra}]"]
        try:
            completed = subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)  # noqa: S603
        except (OSError, subprocess.TimeoutExpired):
            return self._install_failed()
        return self.check() if completed.returncode == 0 else self._install_failed()

    def unsupported_action(self) -> str | None:
        if self.required_host is None or platform.system() == self.required_host:
            return None
        label = "Windows" if self.platform == "windows" else "macOS"
        return f"Run {label} platform tests on a {label} host."

    def _install_failed(self) -> PlatformRuntimeCheck:
        return PlatformRuntimeCheck(platform=self.platform, status="missing", ready=False, message="Platform runtime installation failed.", action="Install the platform extra manually and retry.")
