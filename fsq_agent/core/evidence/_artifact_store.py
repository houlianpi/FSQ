# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import re
from pathlib import Path
from typing import Any

from fsq_agent.models import EvidenceArtifactKind, EvidenceArtifactRef, StepPhase

_ARTIFACT_DIRS: dict[EvidenceArtifactKind, str] = {
    "screenshot": "screenshots",
    "ui_tree": "ui-trees",
    "ui_snapshot": "ui-snapshots",
    "tool_call": "harness-calls",
    "log": "logs",
    "json": "raw",
    "text": "logs",
    "other": "raw",
}
_DEFAULT_EXTENSIONS: dict[EvidenceArtifactKind, str] = {
    "screenshot": "png",
    "ui_tree": "json",
    "ui_snapshot": "json",
    "tool_call": "json",
    "log": "txt",
    "json": "json",
    "text": "txt",
    "other": "bin",
}
_DEFAULT_MIME_TYPES: dict[EvidenceArtifactKind, str] = {
    "screenshot": "image/png",
    "ui_tree": "application/json",
    "ui_snapshot": "application/json",
    "tool_call": "application/json",
    "log": "text/plain",
    "json": "application/json",
    "text": "text/plain",
    "other": "application/octet-stream",
}


class ArtifactStore:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def write_json(
        self,
        *,
        kind: EvidenceArtifactKind,
        step_id: str,
        phase: StepPhase,
        name: str,
        payload: Any,
    ) -> EvidenceArtifactRef:
        artifact_id = self._artifact_id(step_id=step_id, phase=phase, name=name)
        relative_path = self._relative_path(kind=kind, artifact_id=artifact_id, extension="json")
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return self._artifact_ref(artifact_id=artifact_id, kind=kind, path=relative_path, step_id=step_id, phase=phase)

    def write_text(
        self,
        *,
        kind: EvidenceArtifactKind,
        step_id: str,
        phase: StepPhase,
        name: str,
        text: str,
    ) -> EvidenceArtifactRef:
        artifact_id = self._artifact_id(step_id=step_id, phase=phase, name=name)
        relative_path = self._relative_path(kind=kind, artifact_id=artifact_id, extension=_DEFAULT_EXTENSIONS[kind])
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return self._artifact_ref(artifact_id=artifact_id, kind=kind, path=relative_path, step_id=step_id, phase=phase)

    def write_bytes(
        self,
        *,
        kind: EvidenceArtifactKind,
        step_id: str,
        phase: StepPhase,
        name: str,
        data: bytes,
    ) -> EvidenceArtifactRef:
        artifact_id = self._artifact_id(step_id=step_id, phase=phase, name=name)
        relative_path = self._relative_path(kind=kind, artifact_id=artifact_id, extension=_DEFAULT_EXTENSIONS[kind])
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self._artifact_ref(artifact_id=artifact_id, kind=kind, path=relative_path, step_id=step_id, phase=phase)

    def _artifact_ref(
        self,
        *,
        artifact_id: str,
        kind: EvidenceArtifactKind,
        path: Path,
        step_id: str,
        phase: StepPhase,
    ) -> EvidenceArtifactRef:
        return EvidenceArtifactRef(
            artifact_id=artifact_id,
            kind=kind,
            path=path,
            mime_type=_DEFAULT_MIME_TYPES[kind],
            step_id=step_id,
            phase=phase,
        )

    def _relative_path(self, *, kind: EvidenceArtifactKind, artifact_id: str, extension: str) -> Path:
        return Path("artifacts") / _ARTIFACT_DIRS[kind] / f"{artifact_id}.{extension}"

    def _artifact_id(self, *, step_id: str, phase: StepPhase, name: str) -> str:
        return "-".join([self._slug(step_id), phase, self._slug(name)])

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        return slug or "artifact"
