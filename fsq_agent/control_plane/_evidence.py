# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import json
import mimetypes
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fsq_agent.models import RunEvent, RunnerEvent, RunnerStepResult

    from ._state import ControlPlaneState

UI_SNAPSHOT_LIMIT_BYTES = 512 * 1024
_MANIFEST_LIMIT_BYTES = 8 * 1024 * 1024
_SECRET_PATTERN = re.compile(r"(?i)(bearer\s+|(?:api[_ -]?key|access[_ -]?token|token)[=:]\s*)[^\s,;]+")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/]|\\\\)[^\r\n\t\"'<>|]+")
_POSIX_PATH_PATTERN = re.compile(r"(?<![:\w])/(?:[^/\s]+/)+[^\s,;:)\]}]*")


def configured_secret_values(settings: Any | None) -> tuple[str, ...]:
    if settings is None:
        return ()
    runtime_secrets = getattr(settings, "runtime_secrets", None)
    names = getattr(runtime_secrets, "allowed_env_names", ())
    return tuple(value for name in names if (value := os.getenv(name)))


def safe_text(value: object, *, secret_values: tuple[str, ...] = (), limit: int = 1000) -> str:
    text = str(value)
    text = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}[redacted]", text)
    for secret in sorted({item for item in secret_values if item}, key=len, reverse=True):
        text = text.replace(secret, "[redacted]")
    text = _WINDOWS_PATH_PATTERN.sub("[local path]", text)
    text = _POSIX_PATH_PATTERN.sub("[local path]", text)
    return text[:limit]


def safe_exception_message(exc: BaseException, *, settings: Any | None = None, unexpected: bool = False, limit: int = 500) -> str:
    if unexpected:
        return "An unexpected Control Plane error occurred."
    message = str(exc).split(" Context:", 1)[0].strip() or exc.__class__.__name__
    return safe_text(message, secret_values=configured_secret_values(settings), limit=limit)


class EvidenceProjection:
    def __init__(self, state: ControlPlaneState, request_id: str, runs_dir: Path, secret_values: tuple[str, ...] = ()) -> None:
        self.state = state
        self.request_id = request_id
        self.runs_dir = runs_dir.resolve()
        self.secret_values = tuple(sorted({value for value in secret_values if value}, key=len, reverse=True))
        self.run_dir: Path | None = None
        self._seen_artifacts: set[tuple[str, Path]] = set()

    def project_run_event(self, event: RunEvent) -> None:
        if event.run_id:
            self.bind_run(event.run_id)
        status = _run_event_status(event)
        message = self.safe_text(event.message or event.title)
        self.state.add_event(
            self.request_id,
            {
                "time": event.timestamp.isoformat(),
                "phase": _run_phase(event.type),
                "label": self.safe_text(event.tool_name or event.title, limit=200),
                "tool": self.safe_text(event.tool_name or "", limit=100) or None,
                "status": status,
                "durationMs": event.duration_ms,
                "message": message,
                "level": "error" if status == "failed" else "info",
            },
        )
        self._consume_run_artifacts(event)

    def project_runner_event(self, event: RunnerEvent) -> None:
        payload = event.payload or {}
        status = str(payload.get("status") or _runner_event_status(event.event_type))
        label = str(payload.get("action_name") or event.step_id or event.event_type)
        self.state.add_event(
            self.request_id,
            {
                "time": event.timestamp.isoformat(),
                "phase": event.phase or "execution",
                "stepId": event.step_id,
                "label": self.safe_text(label, limit=200),
                "tool": self.safe_text(str(payload.get("tool") or ""), limit=100) or None,
                "status": status,
                "durationMs": payload.get("duration_ms") if isinstance(payload.get("duration_ms"), int) else None,
                "message": self.safe_text(str(payload.get("message") or event.event_type.replace("_", " "))),
                "level": "error" if event.event_type == "step_error" else "info",
            },
        )
        if event.event_type == "artifact_captured":
            self._consider_artifact(payload, step_id=event.step_id, timestamp=event.timestamp.isoformat())

    def project_step_result(self, result: RunnerStepResult) -> None:
        for phase in result.phase_reports:
            for ref in phase.artifact_refs:
                self._consider_artifact(ref.model_dump(mode="json"), step_id=result.step_id, timestamp=(ref.created_at.isoformat()))

    def bind_run(self, run_id: str) -> None:
        candidate = (self.runs_dir / run_id).resolve()
        if not _is_relative_to(candidate, self.runs_dir):
            return
        self.run_dir = candidate
        self.state.bind_run(self.request_id, run_id)

    def load_persisted_manifest(self) -> None:
        if self.run_dir is None:
            return
        manifest = self.run_dir / "evidence-manifest.json"
        try:
            if not manifest.is_file() or manifest.stat().st_size > _MANIFEST_LIMIT_BYTES:
                return
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
        if not isinstance(artifacts, list):
            return
        for artifact in artifacts:
            if isinstance(artifact, dict):
                self._consider_artifact(artifact, step_id=_optional_str(artifact.get("step_id")), timestamp=_optional_str(artifact.get("created_at")))

    def safe_text(self, value: str, *, limit: int = 1000) -> str:
        return safe_text(value, secret_values=self.secret_values, limit=limit)

    def _consume_run_artifacts(self, event: RunEvent) -> None:
        payload = event.payload or {}
        refs = payload.get("artifact_refs")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, dict):
                    self._consider_artifact(ref, step_id=_optional_str(ref.get("step_id")), timestamp=event.timestamp.isoformat())
        if isinstance(payload.get("artifact_ref"), dict):
            self._consider_artifact(payload["artifact_ref"], step_id=None, timestamp=event.timestamp.isoformat())
        artifact_path = payload.get("artifact_path")
        artifact_kind = payload.get("artifact_kind") or payload.get("kind")
        if isinstance(artifact_path, str) and artifact_kind in {"screenshot", "ui_snapshot"}:
            self._consider_artifact({"path": artifact_path, "kind": artifact_kind}, step_id=None, timestamp=event.timestamp.isoformat())

    def _consider_artifact(self, ref: dict[str, Any], *, step_id: str | None, timestamp: str | None) -> None:
        if self.run_dir is None:
            return
        kind = ref.get("kind")
        if kind not in {"screenshot", "ui_snapshot"}:
            return
        path_text = ref.get("path")
        if not isinstance(path_text, str) or not path_text:
            return
        path = Path(path_text)
        candidate = path.resolve() if path.is_absolute() else (self.run_dir / path).resolve()
        if not _is_relative_to(candidate, self.run_dir):
            return
        artifact_key = (str(kind), candidate)
        if artifact_key in self._seen_artifacts:
            return
        self._seen_artifacts.add(artifact_key)
        self.state.set_artifact(
            self.request_id,
            str(kind),
            {
                "path": candidate,
                "mimeType": _optional_str(ref.get("mime_type")) or mimetypes.guess_type(candidate.name)[0] or ("image/png" if kind == "screenshot" else "application/json"),
                "timestamp": timestamp,
                "stepId": step_id,
            },
        )


def read_screenshot(artifact: dict[str, Any] | None) -> tuple[bytes, dict[str, str]]:
    if not artifact:
        raise FileNotFoundError("No screenshot has been captured.")
    path = artifact.get("path")
    if not isinstance(path, Path):
        raise FileNotFoundError("Screenshot evidence is unavailable.")
    data = path.read_bytes()
    headers = {
        "Content-Type": str(artifact.get("mimeType") or "image/png"),
        "ETag": f'"{artifact.get("revision", 0)}"',
        "X-Evidence-Revision": str(artifact.get("revision", 0)),
        "X-Evidence-Timestamp": str(artifact.get("timestamp") or ""),
        "X-Evidence-Step": str(artifact.get("stepId") or ""),
    }
    return data, headers


def read_ui_snapshot(artifact: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, str]]:
    if not artifact:
        raise FileNotFoundError("No UI snapshot has been captured.")
    path = artifact.get("path")
    if not isinstance(path, Path):
        raise FileNotFoundError("UI snapshot evidence is unavailable.")
    size = path.stat().st_size
    if size > UI_SNAPSHOT_LIMIT_BYTES:
        raise OverflowError("UI snapshot exceeds the 512 KiB display limit.")
    text = path.read_text(encoding="utf-8")
    mime = str(artifact.get("mimeType") or "application/json")
    payload = {
        "revision": artifact.get("revision", 0),
        "timestamp": artifact.get("timestamp"),
        "stepId": artifact.get("stepId"),
        "mimeType": mime,
        "format": "json" if "json" in mime or path.suffix.casefold() == ".json" else "text",
        "content": text,
    }
    return payload, {"ETag": f'"{artifact.get("revision", 0)}"'}


def _run_event_status(event: RunEvent) -> str:
    if event.type in {"run_failed", "tool_call_failed"}:
        return "failed"
    if event.type in {"run_completed", "tool_call_completed", "step_completed"}:
        return str(event.payload.get("status") or "completed")
    return "running"


def _run_phase(event_type: str) -> str:
    if event_type.startswith("planning"):
        return "planning"
    if event_type.startswith("tool_call") or event_type == "step_completed":
        return "execution"
    if event_type.startswith("run_"):
        return "run"
    return "startup"


def _runner_event_status(event_type: str) -> str:
    if event_type == "step_error":
        return "failed"
    if event_type.endswith("finish"):
        return "completed"
    return "running"


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


__all__ = ["UI_SNAPSHOT_LIMIT_BYTES", "EvidenceProjection", "configured_secret_values", "read_screenshot", "read_ui_snapshot", "safe_exception_message", "safe_text"]
