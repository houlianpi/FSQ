# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path

from fsq_agent.application.contracts import RunSummary

__all__ = ["list_runs", "read_run_logs", "show_run"]


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
    records = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def _contained_run_dir(runs_dir: Path, run_id: str) -> Path:
    root = runs_dir.resolve()
    candidate = (root / run_id).resolve()
    if candidate.parent != root or not candidate.is_dir():
        raise FileNotFoundError(f"Run not found: {run_id}")
    return candidate
