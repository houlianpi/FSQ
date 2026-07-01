from __future__ import annotations

from pathlib import Path
from typing import Any

from fsq_agent.core import (
    CapabilityRegistry,
    CommonPlatformTools,
    android_capability_definitions,
    macos_capability_definitions,
    web_capability_definitions,
    windows_capability_definitions,
)
from fsq_agent.models import CapabilityDefinition, ConfigurationError, HarnessPlatform
from fsq_agent.tools import DefaultAgentToolProvider, FileOps


def common_capability_definitions() -> list[CapabilityDefinition]:
    return CommonPlatformTools.capability_definitions()


def build_capability_registry(*, platform: HarnessPlatform = "android", include_ai_assertion: bool = True) -> CapabilityRegistry:
    return CapabilityRegistry.from_definitions(
        [
            *common_capability_definitions(),
            *_platform_capability_definitions(platform, include_ai_assertion=include_ai_assertion),
        ]
    )


def _platform_capability_definitions(platform: HarnessPlatform, *, include_ai_assertion: bool) -> list[CapabilityDefinition]:
    if platform == "android":
        return android_capability_definitions(include_ai_assertion=include_ai_assertion)
    if platform == "web":
        return web_capability_definitions(include_ai_assertion=include_ai_assertion)
    if platform == "windows":
        return windows_capability_definitions(include_ai_assertion=include_ai_assertion)
    if platform == "macos":
        return macos_capability_definitions(include_ai_assertion=include_ai_assertion)
    raise ConfigurationError("Unsupported harness platform.", context={"platform": platform, "supported": ["android", "web", "windows", "macos"]})


def build_agent_tool_provider(
    *,
    read_roots: list[Path] | None = None,
    write_root: Path | None = None,
    runtime_secret_settings: Any = None,
    local_tool_output_settings: Any = None,
    runs_dir: Path | None = None,
    run_id: str = "",
) -> DefaultAgentToolProvider:
    return DefaultAgentToolProvider(
        FileOps(read_roots=read_roots, write_root=write_root),
        runtime_secret_settings=runtime_secret_settings,
        local_tool_output_settings=local_tool_output_settings,
        runs_dir=runs_dir,
        run_id=run_id,
    )
