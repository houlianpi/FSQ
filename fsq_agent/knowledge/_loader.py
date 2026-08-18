# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
from typing import Any, Protocol

import yaml

from fsq_agent.models import FsqAgentError, KnowledgeBundle, Task


class KnowledgeProvider(Protocol):
    def load_for_task(self, task: Task) -> KnowledgeBundle:
        pass


class DirectoryKnowledgeProvider:
    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir.resolve()

    def load_for_task(self, task: Task) -> KnowledgeBundle:
        items: dict[str, Any] = {}
        warnings: list[str] = []
        project_path = self._resolve_path("project.md")
        if project_path.exists():
            try:
                project_knowledge = self._load_path(project_path)
            except OSError as exc:
                raise FsqAgentError("Unable to load project knowledge.", context={"path": str(project_path)}) from exc
            if isinstance(project_knowledge, str) and project_knowledge.strip():
                items["project.md"] = project_knowledge
        for reference in task.knowledge_refs:
            path = self._resolve_path(reference)
            if not path.exists():
                warnings.append(f"Knowledge reference not found: {reference}")
                continue
            try:
                items[reference] = self._load_path(path)
            except OSError as exc:
                raise FsqAgentError("Unable to load knowledge reference.", context={"path": str(path)}) from exc
        return KnowledgeBundle(items=items, warnings=warnings)

    def _resolve_path(self, reference: str) -> Path:
        path = (self.knowledge_dir / reference).resolve()
        try:
            path.relative_to(self.knowledge_dir)
        except ValueError as exc:
            raise FsqAgentError(
                "Knowledge reference must stay within the workspace knowledge directory.",
                context={"reference": reference},
            ) from exc
        return path

    def _load_path(self, path: Path) -> Any:
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        return path.read_text(encoding="utf-8")


class PrivateKnowledgeLoader:
    def __init__(self, knowledge_dir: Path, providers: list[KnowledgeProvider] | None = None) -> None:
        self.knowledge_dir = knowledge_dir
        self.providers = providers or [DirectoryKnowledgeProvider(knowledge_dir)]

    def load_for_task(self, task: Task) -> KnowledgeBundle:
        merged = KnowledgeBundle()
        for provider in self.providers:
            bundle = provider.load_for_task(task)
            merged.items.update(bundle.items)
            merged.warnings.extend(bundle.warnings)
        return merged
