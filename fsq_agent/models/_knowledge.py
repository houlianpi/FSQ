# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.items
