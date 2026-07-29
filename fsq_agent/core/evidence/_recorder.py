# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path

from fsq_agent.models import EvidenceArtifactRef, EvidenceBundle, RunnerEvent, RunnerStepResult


class EvidenceRecorder:
    def __init__(
        self,
        *,
        run_id: str,
        output_dir: Path,
        bundle_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.run_id = run_id
        self.output_dir = output_dir
        self.bundle_id = bundle_id or f"{run_id}-evidence"
        self.metadata = metadata or {}
        self._events: list[RunnerEvent] = []
        self._steps: list[RunnerStepResult] = []

    def record_event(self, event: RunnerEvent) -> None:
        self._events.append(event)

    def record_step_result(self, result: RunnerStepResult) -> None:
        self._steps.append(result)

    def build_bundle(self) -> EvidenceBundle:
        return EvidenceBundle(
            bundle_id=self.bundle_id,
            run_id=self.run_id,
            events=list(self._events),
            steps=list(self._steps),
            artifacts=self._artifact_refs(),
            metadata=dict(self.metadata),
        )

    def write_manifest(self, filename: str = "evidence-manifest.json") -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.output_dir / filename
        bundle = self.build_bundle().model_copy(update={"manifest_path": manifest_path})
        manifest_path.write_text(
            json.dumps(bundle.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return manifest_path

    def _artifact_refs(self) -> list[EvidenceArtifactRef]:
        artifacts: list[EvidenceArtifactRef] = []
        for step in self._steps:
            for phase_report in step.phase_reports:
                artifacts.extend(phase_report.artifact_refs)
        return artifacts
