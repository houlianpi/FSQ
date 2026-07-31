# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    path: Path
    format: Literal["markdown", "json", "html"] = "markdown"
    evidence_manifest_path: Path | None = None
    evidence_bundle_path: Path | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
