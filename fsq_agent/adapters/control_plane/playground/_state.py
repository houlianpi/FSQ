# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Condition
from typing import Literal
from uuid import uuid4

from fsq_agent.models import FsqAgentError, RunEvent, TaskResult

TaskProgressStatus = Literal["running", "success", "failed", "inconclusive", "error", "cancelled"]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class PlaygroundSession:
    connected: bool = False
    device_id: str | None = None
    display_name: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        return {
            "connected": self.connected,
            "deviceId": self.device_id,
            "displayName": self.display_name,
            "metadata": self.metadata,
        }


@dataclass
class TaskProgress:
    request_id: str
    goal: str
    run_id: str | None = None
    status: TaskProgressStatus = "running"
    started_at: str = field(default_factory=_utc_now)
    completed_at: str | None = None
    events: list[dict[str, object]] = field(default_factory=list)
    preview: dict[str, object] | None = None
    active_step: dict[str, object] | None = None
    replay: dict[str, object] | None = None
    replay_reset: bool = False
    cancel_requested: bool = False
    result: dict[str, object] | None = None
    error: str | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "requestId": self.request_id,
            "runId": self.run_id,
            "goal": self.goal,
            "status": self.status,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "events": self.events,
            "preview": self.preview,
            "activeStep": self.active_step,
            "replay": self.replay,
            "cancelRequested": self.cancel_requested,
            "result": self.result,
            "error": self.error,
        }


class PlaygroundState:
    def __init__(self) -> None:
        self._lock = Condition()
        self._revision = 0
        self.server_id = str(uuid4())
        self.session = PlaygroundSession()
        self.current_request_id: str | None = None
        self.tasks: dict[str, TaskProgress] = {}
        self.last_run: dict[str, object] | None = None

    def _notify(self) -> None:
        self._revision += 1
        self._lock.notify_all()

    def wait_for_update(self, request_id: str, after_sequence: int, last_revision: int, timeout: float) -> tuple[dict[str, object] | None, int]:
        with self._lock:
            if self._revision == last_revision:
                self._lock.wait(timeout)
            task = self.tasks.get(request_id)
            if task is None:
                return None, self._revision
            payload = task.to_json()
            payload["events"] = [event for event in task.events if isinstance(event.get("sequence"), int) and event["sequence"] > after_sequence]
            return payload, self._revision

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "status": "ok",
                "id": self.server_id,
                "busy": self.current_request_id is not None,
                "session": self.session.to_json(),
                "lastRun": self.last_run,
            }

    def create_session(self, device_id: str) -> dict[str, object]:
        with self._lock:
            if self.current_request_id:
                raise BusyError("Cannot replace session while a task is running.")
            normalized = device_id.strip()
            self.session = PlaygroundSession(
                connected=True,
                device_id=normalized,
                display_name=normalized,
                metadata={"platform": "android"},
            )
            return self.session.to_json()

    def destroy_session(self) -> dict[str, object]:
        with self._lock:
            if self.current_request_id:
                raise BusyError("Cannot destroy session while a task is running.")
            self.session = PlaygroundSession()
            return self.session.to_json()

    def start_task(self, goal: str) -> str:
        with self._lock:
            if self.current_request_id:
                raise BusyError("Another task is already running.")
            request_id = str(uuid4())
            self.current_request_id = request_id
            self.tasks[request_id] = TaskProgress(request_id=request_id, goal=goal)
            return request_id

    def add_event(self, request_id: str, event: RunEvent) -> None:
        with self._lock:
            task = self.tasks.get(request_id)
            if task is None:
                return
            if event.run_id:
                task.run_id = event.run_id
            event_payload = event.model_dump(mode="json")
            if not isinstance(event_payload.get("sequence"), int) or event_payload["sequence"] <= 0:
                event_payload["sequence"] = len(task.events) + 1
            task.events.append(event_payload)
            self._notify()

    def bind_run_id(self, request_id: str, run_id: str) -> None:
        with self._lock:
            task = self.tasks.get(request_id)
            if task is not None:
                task.run_id = run_id

    def set_replay(self, request_id: str, replay: dict[str, object]) -> None:
        with self._lock:
            task = self.tasks.get(request_id)
            if task is None:
                return
            task.replay = replay

    def set_preview(self, request_id: str, preview: dict[str, object]) -> None:
        with self._lock:
            task = self.tasks.get(request_id)
            if task is None:
                return
            task.preview = preview
            self._notify()

    def set_active_step(self, request_id: str, active_step: dict[str, object] | None) -> None:
        with self._lock:
            task = self.tasks.get(request_id)
            if task is None:
                return
            task.active_step = active_step
            self._notify()

    def mark_replay_reset(self, request_id: str) -> bool:
        with self._lock:
            task = self.tasks.get(request_id)
            if task is None:
                return False
            if task.replay_reset:
                return False
            task.replay_reset = True
            return True

    def request_cancel(self, request_id: str) -> dict[str, object] | None:
        with self._lock:
            task = self.tasks.get(request_id)
            if task is None:
                return None
            if task.status != "running":
                return task.to_json()
            task.cancel_requested = True
            task.status = "cancelled"
            task.completed_at = _utc_now()
            task.active_step = None
            task.error = "Cancelled by user."
            if self.current_request_id == request_id:
                self.current_request_id = None
            self._notify()
            return task.to_json()

    def is_cancel_requested(self, request_id: str) -> bool:
        with self._lock:
            task = self.tasks.get(request_id)
            return bool(task and task.cancel_requested)

    def finish_task(self, request_id: str, result: TaskResult, recording: dict[str, object] | None = None) -> None:
        with self._lock:
            task = self.tasks[request_id]
            if task.cancel_requested:
                return
            task.run_id = result.report.run_id
            task.status = result.status
            task.completed_at = _utc_now()
            task.active_step = None
            task.result = {
                "taskId": result.task_id,
                "status": result.status,
                "summary": result.verification.summary,
                "runId": result.report.run_id,
                "reportPath": str(result.report.path),
                "durationMs": result.duration_ms,
                "recording": recording,
                "replay": task.replay,
            }
            self.last_run = task.result
            if self.current_request_id == request_id:
                self.current_request_id = None
            self._notify()

    def fail_task(self, request_id: str, error: BaseException | str) -> None:
        with self._lock:
            task = self.tasks.get(request_id)
            if task is not None:
                if task.cancel_requested:
                    return
                task.status = "error"
                task.completed_at = _utc_now()
                task.active_step = None
                if isinstance(error, FsqAgentError) and error.context:
                    details = json.dumps(error.context, ensure_ascii=False, default=str)
                    task.error = f"{str(error) or error.__class__.__name__} Context: {details}"
                else:
                    task.error = str(error) or error.__class__.__name__ if isinstance(error, BaseException) else str(error)
            if self.current_request_id == request_id:
                self.current_request_id = None
            self._notify()

    def get_task(self, request_id: str, after_sequence: int | None = None) -> dict[str, object] | None:
        with self._lock:
            task = self.tasks.get(request_id)
            if task is None:
                return None
            payload = task.to_json()
            if after_sequence is not None:
                payload["events"] = [event for event in task.events if isinstance(event.get("sequence"), int) and event["sequence"] > after_sequence]
            return payload

    def run_id_for_request(self, request_id: str) -> str | None:
        with self._lock:
            task = self.tasks.get(request_id)
            return task.run_id if task else None


class BusyError(RuntimeError):
    pass
