from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Literal

import yaml

from fsq_agent.config import Settings
from fsq_agent.cli._capability_bootstrap import build_capability_registry
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import ConfigurationError, RunEvent, Task, TaskResult


RecordingStatus = Literal["recorded", "skipped", "failed"]


@dataclass
class StrictCaseRecording:
    status: RecordingStatus
    recording_path: Path
    recorded_case_path: Path | None = None
    command_count: int = 0
    required_runtime_secret_names: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_status: str = "not_run"
    draft: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "recording_path": str(self.recording_path),
            "recorded_case_path": str(self.recorded_case_path) if self.recorded_case_path else None,
            "command_count": self.command_count,
            "required_runtime_secret_names": self.required_runtime_secret_names,
            "warnings": self.warnings,
            "skipped_tool_calls": self.skipped_tool_calls,
            "errors": self.errors,
            "validation_status": self.validation_status,
            "draft": self.draft,
        }


def record_dynamic_run_as_strict_case(
    *,
    run_dir: Path,
    task: Task,
    result: TaskResult,
    settings: Settings,
    allow_failure: bool = False,
) -> StrictCaseRecording:
    run_dir.mkdir(parents=True, exist_ok=True)
    recording_path = run_dir / "recording.json"
    recorded_case_path = run_dir / "recorded.codex.yaml"
    draft = result.status != "success"
    if draft and not allow_failure:
        recording = StrictCaseRecording(
            status="skipped",
            recording_path=recording_path,
            warnings=["Run did not finish successfully; use --record-on-failure to write a draft recording."],
            draft=draft,
        )
        _write_recording(recording)
        return recording
    if recorded_case_path.exists():
        recording = StrictCaseRecording(
            status="failed",
            recording_path=recording_path,
            recorded_case_path=recorded_case_path,
            errors=["recorded.codex.yaml already exists for this run."],
            draft=draft,
        )
        _write_recording(recording)
        return recording

    collector = _RecordingCollector()
    events = _load_events(run_dir / "events.jsonl")
    commands = collector.collect(events)
    if not commands:
        recording = StrictCaseRecording(
            status="failed",
            recording_path=recording_path,
            errors=["No replayable commands were found in the dynamic run event log."],
            skipped_tool_calls=collector.skipped_tool_calls,
            warnings=collector.warnings,
            draft=draft,
        )
        _write_recording(recording)
        return recording

    required_secret_names = sorted(collector.required_runtime_secret_names)
    warnings = list(collector.warnings)
    metadata_doc = _metadata_doc(task, result, settings, required_secret_names, warnings, draft)
    recorded_case_path.write_text(
        yaml.safe_dump_all([metadata_doc, commands], sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    recording = StrictCaseRecording(
        status="recorded",
        recording_path=recording_path,
        recorded_case_path=recorded_case_path,
        command_count=len(commands),
        required_runtime_secret_names=required_secret_names,
        warnings=warnings,
        skipped_tool_calls=collector.skipped_tool_calls,
        validation_status="not_run",
        draft=draft,
    )
    try:
        generated_case = FsqCaseLoader().load_case(recorded_case_path)
        FsqExecutableStepAdapter(registry_snapshot=build_capability_registry(platform=settings.harness.platform).snapshot()).to_executable_steps(generated_case)
        recording.validation_status = "passed"
    except ConfigurationError as exc:
        recording.status = "failed"
        recording.validation_status = "failed"
        recording.errors.append(str(exc))
    _write_recording(recording)
    return recording


class _RecordingCollector:
    def __init__(self) -> None:
        self.required_runtime_secret_names: set[str] = set()
        self.warnings: list[str] = []
        self.skipped_tool_calls: list[dict[str, Any]] = []
        self._pending_runtime_secret_names: list[str] = []
        self._active_runtime_secret_name: str | None = None
        self._used_runtime_secret_ref = False

    def collect(self, events: list[RunEvent]) -> list[dict[str, Any]]:
        commands: list[dict[str, Any]] = []
        starts_by_call_id: dict[str, RunEvent] = {}
        unpaired_starts: list[RunEvent] = []
        for event in events:
            if event.type == "tool_call_started":
                if event.tool_call_id:
                    starts_by_call_id[event.tool_call_id] = event
                else:
                    unpaired_starts.append(event)
                continue
            if event.type not in {"tool_call_completed", "tool_call_failed"}:
                continue

            if self._has_replayable_common_policy(event):
                self._collect_common(event, commands)
                continue

            start = starts_by_call_id.get(event.tool_call_id or "") if event.tool_call_id else self._pop_unpaired_start(unpaired_starts, event)
            if start is None:
                continue
            if self._origin(start, event) not in {"platform", "harness"}:
                continue
            self._collect_harness(start, event, commands)
        return commands

    def _collect_common(self, event: RunEvent, commands: list[dict[str, Any]]) -> None:
        payload = event.payload
        if event.type != "tool_call_completed":
            self._skip(event.tool_name, "common tool did not complete successfully")
            return
        replay = self._replay_policy(payload)
        if replay.get("kind") == "dependency" and replay.get("alias") == "runtimeSecret":
            name = payload.get("runtime_secret_name")
            if isinstance(name, str) and name.strip():
                self._pending_runtime_secret_names.append(name)
                self.required_runtime_secret_names.add(name)
            return
        if replay.get("kind") == "fsq_command" and replay.get("alias") == "waitMs":
            duration_ms = payload.get("duration_ms")
            if not isinstance(duration_ms, int):
                self._skip(event.tool_name, "wait_ms event did not include duration_ms")
                return
            params: dict[str, Any] = {"duration_ms": duration_ms}
            reason = payload.get("reason")
            if isinstance(reason, str) and reason:
                params["reason"] = reason
            commands.append({"waitMs": params})

    def _collect_harness(self, start: RunEvent, event: RunEvent, commands: list[dict[str, Any]]) -> None:
        payload = event.payload
        replay = self._replay_policy(payload) or self._replay_policy(start.payload)
        if replay.get("kind") != "fsq_command":
            self._skip(start.tool_name, "platform tool did not include fsq_command replay metadata")
            return
        if self._step_kind(start, event) == "observation":
            self._skip(start.tool_name, "observation tool is not recorded")
            return
        fsq_action_name = replay.get("alias")
        if not isinstance(fsq_action_name, str) or not fsq_action_name:
            self._skip(start.tool_name, "platform tool did not include fsq_command replay alias")
            return
        if event.type != "tool_call_completed" or payload.get("status") not in {"passed", "success", None}:
            self._skip(start.tool_name, f"platform action status was {payload.get('status') or event.type}")
            return
        safe_replay_params = payload.get("safe_replay_params")
        args = dict(safe_replay_params) if isinstance(safe_replay_params, dict) else _event_arguments(start.tool_arguments)
        if args is None:
            self._skip(start.tool_name, "platform tool arguments were not a JSON object")
            return
        try:
            self._active_runtime_secret_name = None
            self._used_runtime_secret_ref = False
            resolved_args = self._replace_redacted_values(args)
        except ConfigurationError as exc:
            self._skip(start.tool_name, str(exc))
            return
        finally:
            self._active_runtime_secret_name = None
        if self._used_runtime_secret_ref:
            self._pending_runtime_secret_names.clear()
        commands.append({fsq_action_name: resolved_args})

    def _replace_redacted_values(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._replace_redacted_values(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._replace_redacted_values(item) for item in value]
        if value == "***":
            secret_name = self._active_runtime_secret_name or self._single_pending_runtime_secret_name()
            if not secret_name:
                raise ConfigurationError("Redacted harness argument has no matching runtime secret dependency.")
            self._active_runtime_secret_name = secret_name
            self._used_runtime_secret_ref = True
            self.required_runtime_secret_names.add(secret_name)
            return {"runtimeSecret": secret_name}
        return value

    def _single_pending_runtime_secret_name(self) -> str | None:
        unique_names = sorted(set(self._pending_runtime_secret_names))
        if not unique_names:
            return None
        if len(unique_names) > 1:
            raise ConfigurationError("Ambiguous runtime secret binding for redacted harness argument.")
        return unique_names[0]

    def _origin(self, start: RunEvent, event: RunEvent) -> str:
        origin = start.payload.get("tool_origin") or event.payload.get("tool_origin")
        return str(origin) if origin else "unknown"

    def _has_replayable_common_policy(self, event: RunEvent) -> bool:
        return event.payload.get("tool_origin") == "common" and bool(self._replay_policy(event.payload))

    def _replay_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        replay = payload.get("replay")
        if isinstance(replay, dict):
            return replay
        replay_kind = payload.get("replay_kind")
        # Legacy event logs used replay_kind before structured replay metadata existed.
        # New recorder behavior must not infer replayability from tool names or fsq_action_name.
        if replay_kind == "runtimeSecret":
            return {"kind": "dependency", "alias": "runtimeSecret"}
        if replay_kind == "waitMs":
            return {"kind": "fsq_command", "alias": "waitMs"}
        if isinstance(replay_kind, str) and replay_kind:
            return {"kind": "fsq_command", "alias": replay_kind}
        return {}

    def _step_kind(self, start: RunEvent, event: RunEvent) -> str | None:
        for payload in (event.payload, start.payload):
            value = payload.get("step_kind")
            if isinstance(value, str):
                return value
            metadata = payload.get("metadata")
            if isinstance(metadata, dict):
                value = metadata.get("step_kind")
                if isinstance(value, str):
                    return value
        return None

    def _pop_unpaired_start(self, starts: list[RunEvent], event: RunEvent) -> RunEvent | None:
        if event.tool_name:
            for index, start in enumerate(starts):
                if start.tool_name == event.tool_name:
                    return starts.pop(index)
        return starts.pop(0) if starts else None

    def _skip(self, tool_name: str | None, reason: str) -> None:
        self.skipped_tool_calls.append({"tool_name": tool_name or "unknown", "reason": reason})
        self.warnings.append(f"Skipped {tool_name or 'unknown'}: {reason}")


def _load_events(path: Path) -> list[RunEvent]:
    if not path.exists():
        return []
    events: list[RunEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(RunEvent.model_validate_json(line))
        except ValueError:
            continue
    return events


def _event_arguments(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _metadata_doc(
    task: Task,
    result: TaskResult,
    settings: Settings,
    required_secret_names: list[str],
    warnings: list[str],
    draft: bool,
) -> dict[str, Any]:
    app_id = settings.harness.android.app_id if settings.harness.platform == "android" else None
    doc: dict[str, Any] = {
        "schemaVersion": "fsq.ai-test/v1",
        "name": f"Recorded: {task.name}",
        "description": f"Generated from dynamic run {result.report.run_id}.",
        "platform": settings.harness.platform,
        "tags": ["recorded", "dynamic-llm"],
        "properties": {
            "recording": {
                "source_run_id": result.report.run_id,
                "source_task_id": task.id,
                "source_status": result.status,
                "draft": draft,
                "required_runtime_secret_names": required_secret_names,
                "warnings": warnings,
            }
        },
    }
    if app_id:
        doc["appId"] = app_id
    return doc


def _write_recording(recording: StrictCaseRecording) -> None:
    recording.recording_path.write_text(json.dumps(recording.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")