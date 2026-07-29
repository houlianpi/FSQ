# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

from fsq_agent.knowledge import DirectoryKnowledgeProvider, PrivateKnowledgeLoader
from fsq_agent.models import KnowledgeBundle, Task


def test_directory_knowledge_provider_loads_project_knowledge_for_every_task(tmp_path: Path) -> None:
    (tmp_path / "project.md").write_text("Global Edge login knowledge.", encoding="utf-8")

    bundle = DirectoryKnowledgeProvider(tmp_path).load_for_task(Task(description="Run a case."))

    assert bundle.items["project.md"] == "Global Edge login knowledge."


def test_private_knowledge_loader_aggregates_provider_bundles(tmp_path: Path) -> None:
    class StaticProvider:
        def load_for_task(self, task: Task) -> KnowledgeBundle:
            return KnowledgeBundle(items={"static": task.description}, warnings=["static warning"])

    bundle = PrivateKnowledgeLoader(tmp_path, providers=[StaticProvider()]).load_for_task(Task(description="Use provider."))

    assert bundle.items == {"static": "Use provider."}
    assert bundle.warnings == ["static warning"]


def test_directory_knowledge_provider_keeps_task_references(tmp_path: Path) -> None:
    (tmp_path / "project.md").write_text("Global knowledge.", encoding="utf-8")
    (tmp_path / "case.md").write_text("Case-specific knowledge.", encoding="utf-8")

    bundle = DirectoryKnowledgeProvider(tmp_path).load_for_task(Task(description="Run.", knowledge_refs=["case.md"]))

    assert bundle.items["project.md"] == "Global knowledge."
    assert bundle.items["case.md"] == "Case-specific knowledge."
