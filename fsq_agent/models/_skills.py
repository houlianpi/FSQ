# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SkillKind = Literal["markdown", "inline_bundle"]


class SkillConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    kind: SkillKind = "markdown"
    path: Path | None = None
    content: str | None = None
    required: bool = False


class SkillBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    kind: SkillKind
    instructions: str = ""
    files: list[Path] = Field(default_factory=list)
