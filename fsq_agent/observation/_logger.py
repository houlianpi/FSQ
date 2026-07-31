# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fsq_agent.models import RunEvent


class ExecutionLogger:
    def __init__(self, log_root: Path) -> None:
        self.log_root = log_root
        self.log_root.mkdir(parents=True, exist_ok=True)

    def write_event(self, run_id: str, event: str, payload: dict[str, Any]) -> None:
        path = self.log_root / f"{run_id}.jsonl"
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "event": event,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def write_run_event(self, event: RunEvent) -> None:
        path = self.log_root / event.run_id / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write(event.model_dump_json() + "\n")
