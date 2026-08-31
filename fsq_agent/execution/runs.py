# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import os
import re
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SafeText = str | None


class RunSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["case", "goal"]
    case_id: str | None = None
    case_path: str | None = None
    goal_summary: str | None = None

    @field_validator("case_id", "case_path", "goal_summary")
    @classmethod
    def bound_source_text(cls, value: SafeText) -> SafeText:
        if value is not None and (not value.strip() or len(value) > 500):
            raise ValueError("Run source text must be non-blank and at most 500 characters.")
        return value


class RunStepCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    total: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)


class RunResultSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    summary: str = Field(default="", max_length=2000)
    steps: RunStepCounts = Field(default_factory=RunStepCounts)
    failed_step: str | None = Field(default=None, max_length=500)


class RunRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=200)


class RunArtifactIndex(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    report: str | None = None
    report_markdown: str | None = None
    events: str | None = None
    evidence_manifest: str | None = None
    suggestions: str | None = None
    candidate_case: str | None = None
    html_report: str | None = None


class RunMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["fsq.run/v1"] = "fsq.run/v1"
    run_id: str
    workspace: dict[Literal["name"], str]
    platform: Literal["android", "web", "windows", "macos"]
    mode: Literal["strict", "explore"]
    status: Literal["preparing", "running", "finalizing", "success", "failed", "inconclusive", "cancelled", "error"]
    started_at: datetime | None
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    source: RunSource
    result: RunResultSummary = Field(default_factory=RunResultSummary)
    runtime: RunRuntime = Field(default_factory=RunRuntime)
    artifacts: RunArtifactIndex = Field(default_factory=RunArtifactIndex)

    @model_validator(mode="after")
    def validate_relative_paths(self) -> "RunMetadata":
        paths = [self.source.case_path, *self.artifacts.model_dump().values()]
        for value in paths:
            if value is None:
                continue
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Run paths must be contained relative paths.")
        if self.source.kind == "case" and not self.source.case_id:
            raise ValueError("Case Run source requires case_id.")
        if self.source.kind == "goal" and self.source.case_id is not None:
            raise ValueError("Goal Run source cannot contain case_id.")
        for moment in (self.started_at, self.completed_at):
            if moment is not None and (moment.tzinfo is None or moment.utcoffset() != UTC.utcoffset(moment)):
                raise ValueError("Run timestamps must be UTC.")
        if self.completed_at and self.started_at and self.completed_at < self.started_at:
            raise ValueError("Run completion cannot precede its start.")
        return self


def allocate_run(
    *,
    workspace: Path,
    workspace_name: str,
    platform: str,
    source_id: str,
    mode: str,
    source: RunSource,
    platform_runs_dir: Path | None = None,
    now: datetime | None = None,
) -> RunMetadata:
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    slug = re.sub(r"[^a-z0-9]+", "-", source_id.casefold()).strip("-")[:60] or "run"
    runs_root = workspace / ".fsq" / "runs"
    target_root = (platform_runs_dir or runs_root / platform).resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    for _ in range(5):
        run_id = f"{slug}-{moment.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"
        if any((runs_root / candidate / run_id).exists() for candidate in ("android", "web", "windows", "macos")):
            continue
        run_dir = target_root / run_id
        try:
            run_dir.mkdir()
        except FileExistsError:
            continue
        metadata = RunMetadata(run_id=run_id, workspace={"name": workspace_name}, platform=platform, mode=mode, status="preparing", started_at=moment, source=source)
        try:
            write_run_metadata(run_dir, metadata)
        except Exception:
            try:
                run_dir.rmdir()
            except OSError:
                pass
            raise
        return metadata
    raise RuntimeError("Unable to allocate a unique Run ID.")


def transition_run(run_dir: Path, metadata: RunMetadata, status: str, *, completed_at: datetime | None = None, **updates: object) -> RunMetadata:
    terminal = {"success", "failed", "inconclusive", "cancelled", "error"}
    persisted = load_run_metadata(run_dir)
    if persisted.run_id != metadata.run_id or persisted.platform != metadata.platform or persisted.workspace != metadata.workspace:
        raise ValueError("Run metadata identity changed on disk.")
    if persisted.status in terminal:
        raise ValueError("Terminal Run metadata is immutable.")
    if persisted != metadata:
        raise ValueError("Run metadata is stale.")
    order = {"preparing": 0, "running": 1, "finalizing": 2}
    if status not in terminal and order.get(status, -1) <= order.get(metadata.status, -1):
        raise ValueError("Run status transition must move forward.")
    values = {"status": status, **updates}
    if status in terminal:
        finished = (completed_at or datetime.now(UTC)).astimezone(UTC)
        duration_ms = max(0, int((finished - metadata.started_at).total_seconds() * 1000)) if metadata.started_at else None
        values.update(completed_at=finished, duration_ms=duration_ms)
    changed = RunMetadata.model_validate({**metadata.model_dump(), **values})
    write_run_metadata(run_dir, changed)
    return changed


def write_run_metadata(run_dir: Path, metadata: RunMetadata) -> None:
    run_dir = run_dir.resolve()
    path = run_dir / "run.json"
    data = metadata.model_dump_json(indent=2).encode() + b"\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".run.", suffix=".tmp", dir=run_dir)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except Exception:
        try:
            Path(temporary).unlink()
        except FileNotFoundError:
            pass
        raise


def load_run_metadata(run_dir: Path) -> RunMetadata:
    return RunMetadata.model_validate(json.loads((run_dir / "run.json").read_text(encoding="utf-8")))


__all__ = ["RunArtifactIndex", "RunMetadata", "RunResultSummary", "RunRuntime", "RunSource", "RunStepCounts", "allocate_run", "load_run_metadata", "transition_run", "write_run_metadata"]
