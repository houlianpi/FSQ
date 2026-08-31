# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pydantic import BaseModel, ConfigDict


class ProviderConfigurationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: str = "success"
    provider: str
    model: str
    configured: bool = True


class ProviderStatusResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: str
    configured: bool
    provider: str | None = None
    model: str | None = None
    authenticated: bool
    message: str
    action: str | None = None


__all__ = ["ProviderConfigurationResult", "ProviderStatusResult"]
