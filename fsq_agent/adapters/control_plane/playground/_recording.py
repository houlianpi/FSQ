# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fsq_agent.config import Settings
    from fsq_agent.models import Task, TaskResult


def record_dynamic_result(settings: Settings, task: Task, result: TaskResult, *, allow_failure: bool) -> dict[str, object]:
    run_dir = Path(settings.output.runs_dir) / result.report.run_id
    try:
        recording = _record_dynamic_run_as_strict_case(
            run_dir=run_dir,
            task=task,
            result=result,
            settings=settings,
            allow_failure=allow_failure,
        )
        return recording.to_json()
    except Exception as exc:  # noqa: BLE001 - recording must not change dynamic run status.
        recording_path = run_dir / "recording.json"
        recording = {
            "status": "failed",
            "recording_path": str(recording_path),
            "recorded_case_path": None,
            "published_case_path": None,
            "command_count": 0,
            "required_runtime_secret_names": [],
            "warnings": [],
            "skipped_tool_calls": [],
            "errors": [str(exc)],
            "validation_status": "not_run",
            "draft": False,
        }
        try:
            recording_path.parent.mkdir(parents=True, exist_ok=True)
            recording_path.write_text(json.dumps(recording, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return recording


def _record_dynamic_run_as_strict_case(**kwargs: Any):
    from fsq_agent.execution import record_dynamic_run_as_strict_case

    return record_dynamic_run_as_strict_case(**kwargs)
