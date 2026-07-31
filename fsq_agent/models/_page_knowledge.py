# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PAGE_KNOWLEDGE_INDEX_SCHEMA_VERSION = "page_knowledge_index_v1"
PAGE_KNOWLEDGE_PAGE_SCHEMA_VERSION = "page_knowledge_page_v1"
GOAL_PRE_PLAN_SCHEMA_VERSION = "goal_pre_plan_v1"


class PageKnowledgeIndexEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: str
    file: str
    name: str
    intents: list[str] = Field(default_factory=list)


class PageKnowledgeIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["page_knowledge_index_v1"] = PAGE_KNOWLEDGE_INDEX_SCHEMA_VERSION
    product: str
    platform: str
    pages_root: str = "pages"
    pages: list[PageKnowledgeIndexEntry] = Field(default_factory=list)


class PageIdentifier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str


class PageImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    description: str


class ReferenceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str
    selector: str
    confidence: Literal["high", "medium", "low"] = "medium"
    notes: str = ""


class OperationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "navigate",
        "state_change",
        "verify",
        "open_dialog",
        "close_dialog",
        "no_navigation",
    ]
    to_page_id: str | None = None
    description: str


class ElementOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    result: OperationResult


class PageElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: str
    reference_locators: list[ReferenceLocator] = Field(default_factory=list)
    operations: list[ElementOperation] = Field(default_factory=list)


class PageKnowledgePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["page_knowledge_page_v1"] = PAGE_KNOWLEDGE_PAGE_SCHEMA_VERSION
    page_id: str
    name: str
    identifiers: list[PageIdentifier] = Field(default_factory=list)
    images: list[PageImage] = Field(default_factory=list)
    elements: list[PageElement] = Field(default_factory=list)


class GoalKeyAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: int = Field(ge=1)
    action: str
    source_page_ids: list[str] = Field(default_factory=list)
    target_page_id: str | None = None
    notes: str = ""


class GoalPrePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["goal_pre_plan_v1"] = GOAL_PRE_PLAN_SCHEMA_VERSION
    goal: str
    key_actions: list[GoalKeyAction] = Field(default_factory=list)
    verification_goal: str
    relevant_page_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
