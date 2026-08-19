# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, ConfigDict


class EnvironmentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    platform: str
    ready: bool
    message: str | None = None
