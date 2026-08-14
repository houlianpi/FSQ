# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

from fsq_agent.config import load_platform_settings


def initialize_workspace(current_directory: Path, platform: str) -> Path:
    settings = load_platform_settings(platform, current_directory / ".fsq-agent-workspace")
    return Path(settings.workspace.root_dir)
