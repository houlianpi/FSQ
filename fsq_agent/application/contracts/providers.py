# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, ConfigDict


class ProviderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    configured: bool
    selected: bool
