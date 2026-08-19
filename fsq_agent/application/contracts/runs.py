# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    path: Path
