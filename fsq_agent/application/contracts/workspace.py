# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path = Field(description="Current directory selected by the calling adapter.")


class WorkspaceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path
    workspace: Path


class WorkspaceInitializeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path
    platform: Literal["android", "web", "windows", "macos"]
    name: str | None = None
    app_id: str | None = None
    browser_channel: Literal["chromium", "chrome", "chrome-beta", "chrome-dev", "chrome-canary", "msedge", "msedge-beta", "msedge-dev", "msedge-canary"] | None = None
    browser_executable_path: Path | None = None
    app_path: Path | None = None
    window_title_re: str | None = None
    launch_args: str | None = None
    bundle_id: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    install_driver: bool = False
    update_existing: bool = False
    user_config_root: Path | None = None


class WorkspaceInitializeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["initialized", "platform_added", "unchanged", "updated"]
    name: str
    root_path: Path
    platform: Literal["android", "web", "windows", "macos"]
    driver_status: Literal["ready", "installed"]
    browser_executable_path: Path | None = None
