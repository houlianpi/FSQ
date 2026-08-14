# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import os
from pathlib import Path

from fsq_agent.application._contracts import EnvironmentSummary, ProviderSummary, RunSummary, WorkspaceRequest
from fsq_agent.application._workspace import require_initialized_workspace
from fsq_agent.config import load_platform_settings, validate_strict_core_settings


def list_runs(runs_dir: Path) -> list[RunSummary]:
    if not runs_dir.exists():
        return []
    return [RunSummary(run_id=path.name, path=path) for path in sorted(runs_dir.iterdir(), reverse=True) if path.is_dir()]


def show_run(runs_dir: Path, run_id: str) -> dict[str, object]:
    run_dir = _contained_run_dir(runs_dir, run_id)
    files = sorted(path.name for path in run_dir.iterdir() if path.is_file())
    return {"run_id": run_id, "path": str(run_dir), "artifacts": files}


def read_run_logs(runs_dir: Path, run_id: str) -> list[dict[str, object]]:
    events_path = _contained_run_dir(runs_dir, run_id) / "events.jsonl"
    if not events_path.is_file():
        return []
    records: list[dict[str, object]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def list_providers() -> list[ProviderSummary]:
    selected = os.getenv("FSQ_LLM_PROVIDER", "github_copilot")
    return [
        ProviderSummary(name="github_copilot", configured=selected == "github_copilot", selected=selected == "github_copilot"),
        ProviderSummary(name="azure_openai", configured=selected == "azure_openai", selected=selected == "azure_openai"),
    ]


def list_environments(current_directory: Path, platform: str | None = None) -> list[EnvironmentSummary]:
    workspace = require_initialized_workspace(WorkspaceRequest(current_directory=current_directory))
    platforms = [platform] if platform else ["android", "web", "windows", "macos"]
    environments: list[EnvironmentSummary] = []
    for item in platforms:
        try:
            settings = load_platform_settings(item, workspace.workspace)
            validate_strict_core_settings(settings)
        except Exception as exc:  # noqa: BLE001 - diagnostic operation returns safe readiness.
            environments.append(EnvironmentSummary(name=f"local-{item}", platform=item, ready=False, message=str(exc)))
        else:
            environments.append(EnvironmentSummary(name=f"local-{item}", platform=item, ready=True, message="ready"))
    return environments


def _contained_run_dir(runs_dir: Path, run_id: str) -> Path:
    root = runs_dir.resolve()
    candidate = (root / run_id).resolve()
    if candidate.parent != root or not candidate.is_dir():
        raise FileNotFoundError(f"Run not found: {run_id}")
    return candidate
