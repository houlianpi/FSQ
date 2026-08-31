# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fsq_agent._capability_bootstrap import build_capability_registry
from fsq_agent.case_dsl import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.core import CapabilityRegistry, EvidenceRecorder, HarnessInterface, RuntimeSecretStore, StepRunner, StepSequenceRunner
from fsq_agent.models import EvidenceBundle, ExecutableStep, PostActionDelaySettings, ReportArtifact, ReportGenerationError
from fsq_agent.report import CoreEvidenceReportGenerator


class ReportGenerator(Protocol):
    def generate_from_manifest(self, manifest_path: Path) -> ReportArtifact: ...


@dataclass(frozen=True)
class DeterministicExecutionRequest:
    case_path: str | Path
    harness: HarnessInterface
    output_dir: str | Path
    run_id: str
    registry: CapabilityRegistry | None = None
    steps: list[ExecutableStep] | None = None
    post_action_delay_seconds: PostActionDelaySettings | None = None
    runtime_secret_store: RuntimeSecretStore | None = None
    evidence_recorder: EvidenceRecorder | None = None
    cancellation_check: Callable[[], None] | None = None
    report_generator: ReportGenerator | None = None


@dataclass(frozen=True)
class DeterministicExecutionResult:
    evidence: EvidenceBundle
    report: ReportArtifact | None = None


class DeterministicExecutionService:
    def execute(self, request: DeterministicExecutionRequest, *, generate_report: bool = True) -> DeterministicExecutionResult:
        if request.cancellation_check is not None:
            request.cancellation_check()
        evidence = run_fsq_core_case(
            case_path=request.case_path,
            harness=request.harness,
            output_dir=request.output_dir,
            run_id=request.run_id,
            registry=request.registry,
            steps=request.steps,
            post_action_delay_seconds=request.post_action_delay_seconds,
            runtime_secret_store=request.runtime_secret_store,
            evidence_recorder=request.evidence_recorder,
            cancellation_check=request.cancellation_check,
        )
        report = None
        if generate_report:
            if evidence.manifest_path is None:
                raise ReportGenerationError(
                    "Strict core run did not produce an evidence manifest.",
                    context={"run_id": request.run_id},
                )
            generator = request.report_generator or CoreEvidenceReportGenerator()
            report = generator.generate_from_manifest(evidence.manifest_path)
        return DeterministicExecutionResult(evidence=evidence, report=report)


def run_fsq_core_case(
    *,
    case_path: str | Path,
    harness: HarnessInterface,
    output_dir: str | Path,
    run_id: str,
    registry: CapabilityRegistry | None = None,
    steps: list[ExecutableStep] | None = None,
    post_action_delay_seconds: PostActionDelaySettings | None = None,
    runtime_secret_store: RuntimeSecretStore | None = None,
    evidence_recorder: EvidenceRecorder | None = None,
    cancellation_check: Callable[[], None] | None = None,
) -> EvidenceBundle:
    registry = registry or build_capability_registry()
    if steps is None:
        case = FsqCaseLoader().load_case(Path(case_path))
        steps = FsqExecutableStepAdapter(registry_snapshot=registry.snapshot()).to_executable_steps(case)
    normal_steps, teardown_steps = _split_trailing_teardown_steps(steps)
    if cancellation_check is not None:
        cancellation_check()
    recorder = evidence_recorder or EvidenceRecorder(run_id=run_id, output_dir=Path(output_dir))
    bundle = StepSequenceRunner(
        step_runner=StepRunner(
            harness=harness,
            capability_registry=registry,
            post_action_delay_seconds=post_action_delay_seconds,
            runtime_secret_store=runtime_secret_store,
        ),
        evidence_recorder=recorder,
    ).run_steps(
        run_id=run_id,
        steps=normal_steps,
        teardown_steps=teardown_steps,
    )
    if cancellation_check is not None:
        cancellation_check()
    manifest_path = recorder.write_manifest()
    return bundle.model_copy(update={"manifest_path": manifest_path})


def _split_trailing_teardown_steps(steps: list[ExecutableStep]) -> tuple[list[ExecutableStep], list[ExecutableStep]]:
    split_at = len(steps)
    while split_at > 0 and steps[split_at - 1].kind == "teardown":
        split_at -= 1
    return steps[:split_at], steps[split_at:]


def run_strict_fsq_core_case(
    *,
    case_path: str | Path,
    harness: HarnessInterface,
    output_dir: str | Path,
    run_id: str,
    registry: CapabilityRegistry | None = None,
    steps: list[ExecutableStep] | None = None,
    post_action_delay_seconds: PostActionDelaySettings | None = None,
    runtime_secret_store: RuntimeSecretStore | None = None,
) -> ReportArtifact:
    bundle = run_fsq_core_case(
        case_path=case_path,
        harness=harness,
        output_dir=output_dir,
        run_id=run_id,
        registry=registry,
        steps=steps,
        post_action_delay_seconds=post_action_delay_seconds,
        runtime_secret_store=runtime_secret_store,
    )
    if bundle.manifest_path is None:
        raise ReportGenerationError(
            "Strict core run did not produce an evidence manifest.",
            context={"run_id": run_id},
        )
    return CoreEvidenceReportGenerator().generate_from_manifest(bundle.manifest_path)
