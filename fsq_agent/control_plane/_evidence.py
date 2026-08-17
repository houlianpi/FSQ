# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fsq_agent.models import RunEvent, RunnerEvent, RunnerStepResult

    from ._state import ControlPlaneState

UI_SNAPSHOT_LIMIT_BYTES = 512 * 1024
_MANIFEST_LIMIT_BYTES = 8 * 1024 * 1024
_SCREENSHOT_LIMIT_BYTES = 8 * 1024 * 1024
_REPLAY_TOTAL_LIMIT_BYTES = 64 * 1024 * 1024
_SECRET_PATTERN = re.compile(r"(?i)(bearer\s+|(?:api[_ -]?key|access[_ -]?token|token)[=:]\s*)[^\s,;]+")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/]|\\\\)[^\r\n\t\"'<>|]+")
_POSIX_PATH_PATTERN = re.compile(r"(?<![:\w])/(?:[^/\s]+/)+[^\s,;:)\]}]*")


def configured_secret_values(settings: Any | None) -> tuple[str, ...]:
    if settings is None:
        return ()
    runtime_secrets = getattr(settings, "runtime_secrets", None)
    private_values = getattr(runtime_secrets, "private_values", None)
    if not callable(private_values):
        return ()
    return tuple(value for value in private_values().values() if value)


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
        projected = {
            "time": event.timestamp.isoformat(),
            "phase": _run_phase(event.type),
            "label": self.safe_text(event.tool_name or event.title, limit=200),
            "tool": self.safe_text(event.tool_name or "", limit=100) or None,
            "durationMs": event.duration_ms,
            "message": message,
            "level": "error" if status == "failed" else "info",
        }
        if status:
            projected["status"] = status
        if event.tool_call_id:
            projected["toolCallId"] = self.safe_text(event.tool_call_id, limit=100)
        if event.tool_arguments is not None:
            projected["toolArguments"] = _safe_details(event.tool_arguments, self.safe_text)
        if event.tool_output_preview is not None:
            projected["toolOutputPreview"] = _safe_details(event.tool_output_preview, self.safe_text)
        if event.payload:
            projected["payload"] = _safe_details(event.payload, self.safe_text)
        step_id = (
            _optional_str((event.payload or {}).get("runner_step_id") or (event.payload or {}).get("step_id")) if event.type in {"tool_call_completed", "tool_call_failed", "step_completed"} else None
        )
        if step_id:
            projected["stepId"] = step_id
        self.state.add_event(self.request_id, projected)
        self._consume_run_artifacts(event)

    def project_runner_event(self, event: RunnerEvent) -> None:
        payload = event.payload or {}
        status = str(payload.get("status") or _runner_event_status(event.event_type))
        label = str(payload.get("action_name") or event.step_id or event.event_type)
        projected = {
            "time": event.timestamp.isoformat(),
            "phase": event.phase or "execution",
            "stepId": event.step_id,
            "label": self.safe_text(label, limit=200),
            "tool": self.safe_text(str(payload.get("tool") or ""), limit=100) or None,
            "status": status,
            "durationMs": payload.get("duration_ms") if isinstance(payload.get("duration_ms"), int) else None,
            "message": self.safe_text(str(payload.get("message") or event.event_type.replace("_", " "))),
            "level": "error" if event.event_type == "step_error" else "info",
        }
        if payload:
            projected["payload"] = _safe_details(payload, self.safe_text)
        self.state.add_event(self.request_id, projected)
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
        self.state.bind_run(self.request_id, run_id, candidate)

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

    def load_persisted_step_ids(self) -> None:
        if self.run_dir is None:
            return
        events_path = self.run_dir / "events.jsonl"
        try:
            lines = events_path.read_text(encoding="utf-8").splitlines() if events_path.is_file() else []
        except OSError:
            return
        parsed_events: list[dict[str, Any]] = []
        step_ids_by_tool_call: dict[str, str] = {}
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            parsed_events.append(event)
            if event.get("type") not in {"tool_call_completed", "tool_call_failed"}:
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            runner_result = payload.get("runner_result") if isinstance(payload.get("runner_result"), dict) else {}
            step_id = _optional_str(payload.get("runner_step_id") or payload.get("step_id") or runner_result.get("step_id"))
            tool_call_id = _optional_str(event.get("tool_call_id"))
            if tool_call_id and step_id:
                step_ids_by_tool_call[tool_call_id] = step_id

        for event in parsed_events:
            sequence = event.get("sequence")
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            runner_result = payload.get("runner_result") if isinstance(payload.get("runner_result"), dict) else {}
            tool_call_id = _optional_str(event.get("tool_call_id"))
            step_id = _optional_str(payload.get("runner_step_id") or payload.get("step_id") or runner_result.get("step_id"))
            if not step_id and tool_call_id:
                step_id = step_ids_by_tool_call.get(tool_call_id)
            if isinstance(sequence, int) and sequence > 0 and step_id:
                self.state.annotate_event_step(self.request_id, sequence, step_id)

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


def read_step_artifacts(run_dir: Path, step_id: str) -> dict[str, Any]:
    if not step_id or step_id.isdecimal():
        raise ValueError("A non-numeric step id is required.")
    refs = [ref for ref in _persisted_artifact_refs(run_dir) if _artifact_step_id(ref) == step_id]
    payloads = [_artifact_payload(run_dir, ref) for ref in sorted(refs, key=_artifact_sort_key)]
    artifacts = [payload for payload in payloads if payload is not None]
    return {"available": bool(artifacts), "stepId": step_id, "artifacts": artifacts, "message": None if artifacts else "No artifacts for this step."}


def read_replay_frames(run_dir: Path) -> dict[str, Any]:
    screenshots = [ref for ref in _persisted_artifact_refs(run_dir) if ref.get("kind") == "screenshot"]
    frames: list[dict[str, Any]] = []
    seen: set[Path] = set()
    total = 0
    for ref in sorted(screenshots, key=lambda item: (_timestamp_ms(item.get("created_at") or item.get("timestamp")) or 0, str(item.get("path") or ""))):
        resolved = _contained_artifact_path(run_dir, ref.get("path"))
        if resolved is None or resolved in seen:
            continue
        seen.add(resolved)
        common = {
            "index": len(frames) + 1,
            "timestamp": _timestamp_ms(ref.get("created_at") or ref.get("timestamp")),
            "mimeType": _optional_str(ref.get("mime_type") or ref.get("mimeType")) or mimetypes.guess_type(resolved.name)[0] or "image/png",
        }
        try:
            if not resolved.is_file():
                raise FileNotFoundError
            size = resolved.stat().st_size
        except OSError:
            frames.append({**common, "error": "Replay frame is unreadable."})
            continue
        if size > _SCREENSHOT_LIMIT_BYTES or total + size > _REPLAY_TOTAL_LIMIT_BYTES:
            frames.append({**common, "error": "Replay frame exceeds the display limit.", "sizeBytes": size})
            continue
        total += size
        try:
            data = resolved.read_bytes()
        except OSError:
            frames.append({**common, "error": "Replay frame is unreadable."})
            continue
        frames.append({**common, "contentBase64": base64.b64encode(data).decode("ascii")})
    available = any("contentBase64" in frame for frame in frames)
    return {"available": available, "frames": frames, "message": None if available else "No readable replay frames were captured."}


def _persisted_artifact_refs(run_dir: Path) -> list[dict[str, Any]]:
    root = run_dir.resolve()
    manifest_path = root / "evidence-manifest.json"
    refs: list[dict[str, Any]] = []
    try:
        if manifest_path.is_file() and manifest_path.stat().st_size <= _MANIFEST_LIMIT_BYTES:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("bundle"), dict):
                payload = payload["bundle"]
            artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
            if isinstance(artifacts, list):
                refs.extend(dict(ref) for ref in artifacts if isinstance(ref, dict))
    except (OSError, ValueError):
        pass
    events_path = root / "events.jsonl"
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines() if events_path.is_file() else []
    except OSError:
        lines = []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_refs = payload.get("artifact_refs")
        if isinstance(event_refs, list):
            refs.extend({**ref, "created_at": ref.get("created_at") or event.get("timestamp")} for ref in event_refs if isinstance(ref, dict))
    deduped: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    for ref in refs:
        key = (str(ref.get("kind") or ""), str(ref.get("path") or ""), str(_artifact_step_id(ref) or ""), _artifact_phase(ref))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(ref)
    return deduped


def _artifact_payload(run_dir: Path, ref: dict[str, Any]) -> dict[str, Any] | None:
    kind = ref.get("kind")
    if kind not in {"screenshot", "ui_snapshot"}:
        return None
    path = _contained_artifact_path(run_dir, ref.get("path"))
    if path is None:
        return None
    phase = _artifact_phase(ref)
    mime = _optional_str(ref.get("mime_type") or ref.get("mimeType")) or mimetypes.guess_type(path.name)[0] or ("image/png" if kind == "screenshot" else "application/json")
    common = {"kind": kind, "phase": phase, "timestamp": _optional_str(ref.get("created_at") or ref.get("timestamp")), "mimeType": mime}
    try:
        if not path.is_file():
            raise FileNotFoundError
        size = path.stat().st_size
    except OSError:
        return {**common, "error": f"{'Screenshot' if kind == 'screenshot' else 'UI snapshot'} is unreadable."}
    if kind == "screenshot":
        if size > _SCREENSHOT_LIMIT_BYTES:
            return {**common, "error": "Screenshot exceeds the display limit.", "sizeBytes": size}
        try:
            return {**common, "contentBase64": base64.b64encode(path.read_bytes()).decode("ascii")}
        except OSError:
            return {**common, "error": "Screenshot is unreadable."}
    if size > UI_SNAPSHOT_LIMIT_BYTES:
        return {**common, "error": "UI snapshot exceeds the 512 KiB display limit.", "sizeBytes": size}
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {**common, "error": "UI snapshot is unreadable or is not UTF-8."}
    return {**common, "format": "json" if "json" in mime or path.suffix.casefold() == ".json" else "text", "content": content}


def _contained_artifact_path(run_dir: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    root = run_dir.resolve()
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    return resolved if _is_relative_to(resolved, root) else None


def _artifact_step_id(ref: dict[str, Any]) -> str | None:
    return _optional_str(ref.get("step_id") or ref.get("stepId"))


def _artifact_phase(ref: dict[str, Any]) -> str:
    value = str(ref.get("phase") or ref.get("reason") or "").casefold()
    if "before" in value or "prepare" in value:
        return "before"
    if "after" in value or "finalize" in value:
        return "after"
    return value or "capture"


def _artifact_sort_key(ref: dict[str, Any]) -> tuple[int, int, int, str]:
    kind_order = 0 if ref.get("kind") == "screenshot" else 1
    phase_order = {"before": 0, "after": 1}.get(_artifact_phase(ref), 2)
    return (kind_order, phase_order, _timestamp_ms(ref.get("created_at") or ref.get("timestamp")) or 0, str(ref.get("path") or ""))


def _timestamp_ms(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def _safe_details(value: Any, sanitizer, *, depth: int = 0) -> Any:
    if depth >= 4:
        return "[details omitted]"
    if isinstance(value, dict):
        return {sanitizer(str(key), limit=100): _safe_details(item, sanitizer, depth=depth + 1) for key, item in list(value.items())[:80]}
    if isinstance(value, list):
        return [_safe_details(item, sanitizer, depth=depth + 1) for item in value[:80]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitizer(str(value), limit=1000)


def _run_event_status(event: RunEvent) -> str | None:
    if event.type in {"run_failed", "tool_call_failed"}:
        return "failed"
    if event.type in {"run_completed", "tool_call_completed", "step_completed"}:
        return str(event.payload.get("status") or "completed")
    return _optional_str((event.payload or {}).get("status"))


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


__all__ = [
    "UI_SNAPSHOT_LIMIT_BYTES",
    "EvidenceProjection",
    "configured_secret_values",
    "read_replay_frames",
    "read_screenshot",
    "read_step_artifacts",
    "read_ui_snapshot",
    "safe_exception_message",
    "safe_text",
]
