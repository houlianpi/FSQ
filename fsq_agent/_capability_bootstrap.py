from __future__ import annotations

from pathlib import Path
from typing import Any

from fsq_agent.core import (
    CapabilityRegistry,
    CommonPlatformTools,
    DefaultCapabilityDefinitionFactory,
)
from fsq_agent.models import CapabilityDefinition, HarnessPlatform
from fsq_agent.tools import DefaultAgentToolProvider, FileOps


_DEFAULT_CAPABILITY_DEFINITION_FACTORY = DefaultCapabilityDefinitionFactory()


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
    return _DEFAULT_CAPABILITY_DEFINITION_FACTORY.platform_definitions(
        platform=platform,
        include_ai_assertion=include_ai_assertion,
    )


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
