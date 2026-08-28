# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fsq_agent.application.contracts import (
    ApplicationError,
    ApplicationErrorCategory,
    ApplicationErrorCode,
    GenerateRunHtmlRequest,
    GenerateRunHtmlResult,
    ListRunsRequest,
    ListRunsResult,
    ReadRunLogsRequest,
    ReadRunLogsResult,
    RunDetail,
    RunLogEvent,
    RunSummary,
    ShowRunRequest,
    ShowRunResult,
    WorkspaceRequest,
)
from fsq_agent.application.workspace import require_initialized_workspace
from fsq_agent.config import inspect_registered_workspace, list_workspace_registry
from fsq_agent.execution import RunArtifactIndex, RunMetadata, RunResultSummary, RunSource, load_run_metadata
from fsq_agent.report import generate_static_run_report

PLATFORMS = ("android", "web", "windows", "macos")


def list_runs(request: ListRunsRequest) -> ListRunsResult:
    name, root, platforms = _workspace_scope(request.current_directory, request.platform)
    summaries = [_summary(path, platform, name) for platform in platforms for path in _run_directories(root, platform)]
    warnings = _mark_conflicts(summaries)
    threshold = _since_threshold(request.since)
    selected = [item for item in summaries if _matches(item, request, threshold)]
    selected.sort(key=lambda item: (item.started_at is None, -(item.started_at.timestamp()) if item.started_at else 0, item.run_id, item.platform))
    returned = tuple(selected[: request.limit])
    return ListRunsResult(
        workspace=name,
        platforms=platforms,
        filters={"platform": request.platform, "statuses": request.statuses, "mode": request.mode, "since": request.since, "case_id": request.case_id, "limit": request.limit},
        matched_count=len(selected),
        returned_count=len(returned),
        truncated=len(selected) > len(returned),
        runs=returned,
        warnings=tuple(warnings),
    )


def show_run(request: ShowRunRequest) -> ShowRunResult:
    name, root, platforms = _workspace_scope(request.current_directory, request.platform)
    platform, run_dir = _find_run(root, platforms, request.run_id)
    metadata, warnings = _metadata(run_dir, platform, name)
    html = str((run_dir / "report.html").relative_to(root)) if (run_dir / "report.html").is_file() else None
    if metadata.status in {"preparing", "running", "finalizing"}:
        metadata = metadata.model_copy(update={"status": "interrupted"})
        warnings = (*warnings, "Persisted Run has no terminal result and is displayed as interrupted.")
    return ShowRunResult(workspace=name, run=RunDetail.model_validate(metadata.model_dump()), html_path=html, warnings=warnings)


def read_run_logs(request: ReadRunLogsRequest) -> ReadRunLogsResult:
    _, root, platforms = _workspace_scope(request.current_directory, request.platform)
    platform, run_dir = _find_run(root, platforms, request.run_id)
    path = run_dir / "events.jsonl"
    if not path.is_file():
        raise _error(ApplicationErrorCode.RUN_LOGS_UNAVAILABLE, "Run logs are unavailable.", "Inspect the Run artifacts or execute the Case again.")
    events, warnings = _read_events(path)
    levels = {value.casefold() for value in request.levels}
    phases = {value.casefold() for value in request.phases}
    matched = [event for event in events if (not levels or (event.level or "").casefold() in levels) and (not phases or (event.phase or "").casefold() in phases)]
    chosen = matched[-request.limit :]
    return ReadRunLogsResult(
        run_id=request.run_id,
        platform=platform,
        filters={"levels": request.levels, "phases": request.phases, "limit": request.limit},
        matched_count=len(matched),
        returned_count=len(chosen),
        truncated=len(matched) > len(chosen),
        events=tuple(chosen),
        warnings=warnings,
    )


def generate_run_html(request: GenerateRunHtmlRequest) -> GenerateRunHtmlResult:
    shown = show_run(request)
    root = request.current_directory.expanduser().resolve()
    run_dir = root / ".fsq" / "runs" / shown.run.platform / shown.run.run_id
    try:
        path = generate_static_run_report(run_dir, shown.run.model_dump(mode="json"))
    except Exception as exc:
        raise _error(ApplicationErrorCode.RUN_REPORT_GENERATION_FAILED, "Static Run report generation failed.", "Inspect the Run artifacts and retry.", internal=True) from exc
    return GenerateRunHtmlResult(run_id=shown.run.run_id, platform=shown.run.platform, html_path=str(path.relative_to(root)))


def _workspace_scope(current: Path, platform: str | None) -> tuple[str, Path, tuple]:
    workspace = require_initialized_workspace(WorkspaceRequest(current_directory=current))
    entry = next(item for item in list_workspace_registry() if item.root_path.resolve() == workspace.workspace)
    status = inspect_registered_workspace(entry.name)
    configured = tuple(item.platform for item in status.platforms)
    if platform is not None and platform not in configured:
        raise _error(ApplicationErrorCode.CONFIGURATION_INVALID, "The requested Workspace platform is not configured.", "Configure that platform and retry.")
    return entry.name, workspace.workspace, (platform,) if platform else configured


def _run_directories(root: Path, platform: str):
    path = root / ".fsq" / "runs" / platform
    return sorted((item for item in path.iterdir() if item.is_dir() and not item.is_symlink()), key=lambda item: item.name) if path.is_dir() else []


def _metadata(run_dir: Path, platform: str, workspace: str):
    path = run_dir / "run.json"
    if path.is_file():
        try:
            value = load_run_metadata(run_dir)
        except Exception as exc:
            raise _error(ApplicationErrorCode.RUN_METADATA_INVALID, "Run metadata is invalid.", "Repair or remove the damaged Run directory.") from exc
        if value.run_id != run_dir.name or value.platform != platform or value.workspace.get("name") != workspace:
            raise _error(ApplicationErrorCode.RUN_METADATA_INVALID, "Run metadata identity is invalid.", "Repair or remove the damaged Run directory.")
        return value, ()
    return _infer_metadata(run_dir, platform, workspace), ("Historical Run metadata was inferred from persisted artifacts.",)


def _infer_metadata(run_dir: Path, platform: str, workspace: str) -> RunMetadata:
    report = None
    for name in ("report.json", "core-report.json", "report-fallback.json", "evidence-manifest.json"):
        candidate = run_dir / name
        if candidate.is_file():
            try:
                value = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    report = value
                    break
            except (OSError, ValueError):
                pass
    started = _persisted_started_at(report)
    if report is None and not (run_dir / "events.jsonl").is_file():
        raise _error(ApplicationErrorCode.RUN_METADATA_INVALID, "Historical Run metadata cannot be inferred.", "Inspect or remove the damaged Run directory.")
    summary = report.get("summary", {}) if report else {}
    status = str(summary.get("status", "error")) if isinstance(summary, dict) else "error"
    normalized = {"passed": "success", "failed": "failed", "success": "success"}.get(status, "error")
    artifacts = RunArtifactIndex(
        report=next((name for name in ("report.json", "core-report.json", "report-fallback.json") if (run_dir / name).is_file()), None),
        events="events.jsonl" if (run_dir / "events.jsonl").is_file() else None,
        evidence_manifest="evidence-manifest.json" if (run_dir / "evidence-manifest.json").is_file() else None,
    )
    return RunMetadata(
        run_id=run_dir.name,
        workspace={"name": workspace},
        platform=platform,
        mode="strict" if (run_dir / "core-report.json").is_file() else "explore",
        status=normalized,
        started_at=started,
        source=RunSource(kind="goal", goal_summary=run_dir.name[:120]),
        result=RunResultSummary(summary="Historical Run."),
        artifacts=artifacts,
    )


def _persisted_started_at(report: dict[str, object] | None) -> datetime | None:
    if report is None:
        return None
    candidates = [report.get("started_at"), report.get("generated_at"), report.get("timestamp")]
    summary = report.get("summary")
    if isinstance(summary, dict):
        candidates.extend((summary.get("started_at"), summary.get("generated_at")))
    for candidate in candidates:
        if isinstance(candidate, str):
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is not None:
                return parsed.astimezone(UTC)
    return None


def _summary(path: Path, platform: str, workspace: str) -> RunSummary:
    try:
        metadata, warnings = _metadata(path, platform, workspace)
        status = "interrupted" if metadata.status in {"preparing", "running", "finalizing"} else metadata.status
        if status == "interrupted":
            warnings = (*warnings, "Persisted Run has no terminal result and is displayed as interrupted.")
        return RunSummary(
            run_id=metadata.run_id,
            platform=metadata.platform,
            mode=metadata.mode,
            status=status,
            started_at=metadata.started_at,
            duration_ms=metadata.duration_ms,
            source=metadata.source,
            warnings=warnings,
        )
    except ApplicationError:
        return RunSummary(run_id=path.name, platform=platform, status="error", warnings=("Run metadata is damaged.",))


def _mark_conflicts(items):
    counts = {}
    for item in items:
        counts[item.run_id] = counts.get(item.run_id, 0) + 1
    conflicts = {key for key, count in counts.items() if count > 1}
    for index, item in enumerate(items):
        if item.run_id in conflicts:
            items[index] = item.model_copy(update={"warnings": (*item.warnings, "Run ID conflicts with another platform.")})
    return [f"Run ID conflict: {key}" for key in sorted(conflicts)]


def _find_run(root: Path, platforms: tuple, run_id: str):
    if not run_id or Path(run_id).name != run_id:
        raise _error(ApplicationErrorCode.RUN_NOT_FOUND, "Run was not found.", "Provide a valid Run ID.", request=True)
    runs_root = (root / ".fsq" / "runs").resolve()
    matches = []
    for platform in platforms:
        platform_root = (runs_root / platform).resolve()
        candidate = platform_root / run_id
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if not resolved.is_relative_to(platform_root):
            continue
        matches.append((platform, resolved))
    if not matches:
        raise _error(ApplicationErrorCode.RUN_NOT_FOUND, "Run was not found.", "List Runs and provide an existing Run ID.", request=True)
    if len(matches) > 1:
        raise _error(ApplicationErrorCode.RUN_ID_CONFLICT, "Run ID exists on multiple platforms.", "Specify --platform and repair the historical conflict.")
    return matches[0]


def _since_threshold(value):
    if value is None:
        return None
    match = re.fullmatch(r"([1-9]\d*)([mhd])", value)
    if match is None:
        raise _error(ApplicationErrorCode.CASE_INVALID, "Invalid --since duration.", "Use a positive duration such as 30m, 24h, or 7d.", request=True)
    seconds = int(match.group(1)) * {"m": 60, "h": 3600, "d": 86400}[match.group(2)]
    return datetime.now(UTC) - timedelta(seconds=seconds)


def _matches(item, request, threshold):
    return (
        (not request.statuses or item.status in request.statuses)
        and (request.mode is None or item.mode == request.mode)
        and (threshold is None or (item.started_at is not None and item.started_at >= threshold))
        and (request.case_id is None or (item.source is not None and item.source.case_id == request.case_id.strip()))
    )


def _read_events(path):
    events = []
    warnings = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            value = _event_object(json.loads(line))
            value = _safe_event(_sanitize(value))
            sequence = value.get("sequence")
            _validate_sequence(sequence)
            if sequence is None:
                warnings.append("Historical event has no sequence; file order was preserved.")
            events.append((sequence if sequence is not None else index, index, RunLogEvent.model_validate(value)))
        except Exception as exc:
            raise _error(ApplicationErrorCode.RUN_LOGS_INVALID, "Run logs are invalid.", "Inspect the Run log and execute the Case again if needed.") from exc
    if [item[0] for item in events] != sorted(item[0] for item in events) or len({item[0] for item in events}) != len(events):
        warnings.append("Event sequence was normalized for display.")
    events.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in events], tuple(dict.fromkeys(warnings))


def _event_object(value):
    if not isinstance(value, dict):
        raise TypeError("event must be an object")
    return value


def _safe_event(value: dict[str, object]) -> dict[str, object]:
    allowed = ("sequence", "time", "level", "phase", "tool", "label", "status", "message")
    return {key: value[key] for key in allowed if key in value}


def _validate_sequence(sequence):
    if sequence is not None and (not isinstance(sequence, int) or sequence < 0):
        raise ValueError("event sequence is invalid")


def _sanitize(value):
    secret_keys = ("token", "api_key", "apikey", "authorization", "cookie", "secret", "password", "passwd", "pwd")
    if isinstance(value, dict):
        return {str(key): ("[REDACTED]" if any(part in str(key).casefold() for part in secret_keys) else _sanitize(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(authorization|cookie)\s*[:=]\s*[^\r\n]+", r"\1=[REDACTED]", value)
        return re.sub(r"(?i)(bearer|token|api[_-]?key|secret|password|passwd|pwd)\s*[:=]?\s*[^\s,;]+", r"\1=[REDACTED]", value)
    return value


def _error(code, message, action, *, request=False, internal=False):
    category = ApplicationErrorCategory.INTERNAL if internal else ApplicationErrorCategory.REQUEST_VALIDATION if request else ApplicationErrorCategory.CONFIGURATION
    return ApplicationError(code=code, category=category, message=message, action=action)


__all__ = ["generate_run_html", "list_runs", "read_run_logs", "show_run"]
