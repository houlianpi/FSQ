# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import time
from pathlib import Path

from fsq_agent._capability_bootstrap import build_capability_registry, provider_required_capability_names, steps_require_provider
from fsq_agent.application.contracts import (
    ApplicationError,
    ApplicationErrorCategory,
    ApplicationErrorCode,
    CaseTestRequest,
    CaseTestResult,
    WorkspaceRequest,
)
from fsq_agent.application.workspace import require_initialized_workspace
from fsq_agent.case_dsl import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.config import load_platform_settings, validate_strict_core_settings
from fsq_agent.core import ArtifactStore, HarnessFactory, RuntimeSecretStore
from fsq_agent.execution import collect_strict_lifecycle_cases, run_strict_lifecycle_case
from fsq_agent.providers import build_ai_assertion_evaluator


def test_case(request: CaseTestRequest) -> CaseTestResult:
    workspace = require_initialized_workspace(WorkspaceRequest(current_directory=request.current_directory))
    settings = load_platform_settings(request.platform, workspace.workspace)
    try:
        case_path = _resolve_case_path(request.case_path, settings.cases.dir, request.current_directory)
    except FileNotFoundError as exc:
        raise ApplicationError(
            code=ApplicationErrorCode.CASE_NOT_FOUND,
            category=ApplicationErrorCategory.REQUEST_VALIDATION,
            message=str(exc),
            action="Provide an existing *.fsq.yaml Case path.",
        ) from exc
    source_before = case_path.read_bytes()
    case = FsqCaseLoader().load_case(case_path)
    if case.config.platform != request.platform:
        raise ApplicationError(
            code=ApplicationErrorCode.CASE_INVALID,
            category=ApplicationErrorCategory.REQUEST_VALIDATION,
            message="Case platform does not match the requested platform.",
            details={"case_platform": case.config.platform, "requested_platform": request.platform},
        )

    registry = build_capability_registry(platform=request.platform)
    snapshot = registry.snapshot()
    lifecycle_cases = collect_strict_lifecycle_cases(case_path=case_path, case=case, settings=settings)
    resolved_steps = {path.resolve(): FsqExecutableStepAdapter(registry_snapshot=snapshot).to_executable_steps(item) for path, item in lifecycle_cases}
    requires_ai = any(steps_require_provider(steps, snapshot, provider_required_capability_names(request.platform)) for steps in resolved_steps.values())
    validate_strict_core_settings(settings, requires_ai_assertion=requires_ai)
    run_id = f"{case.id}-{time.strftime('%Y-%m-%d_%H-%M-%S')}"
    run_dir = Path(settings.output.runs_dir) / run_id
    evaluator = build_ai_assertion_evaluator(settings) if requires_ai else None
    harness = HarnessFactory().create_harness(
        platform=request.platform,
        harness_settings=settings.harness,
        artifact_store=ArtifactStore(run_dir=run_dir),
        ai_assertion_evaluator=evaluator,
        runtime_secret_settings=settings.runtime_secrets,
        app_id=(settings.harness.android.app_id or case.config.app_id) if request.platform == "android" else None,
    )
    artifact = run_strict_lifecycle_case(
        case_path=case_path,
        case=case,
        settings=settings,
        harness=harness,
        output_dir=run_dir,
        run_id=run_id,
        registry=registry,
        registry_snapshot=snapshot,
        resolve_steps=lambda steps, _case: steps,
        post_action_delay_seconds=settings.execution.post_action_delay_seconds,
        runtime_secret_store=RuntimeSecretStore.from_settings(settings.runtime_secrets),
        resolved_steps_by_path=resolved_steps,
        cases_by_path={path.resolve(): item for path, item in lifecycle_cases},
    )
    if case_path.read_bytes() != source_before:
        raise RuntimeError("Case source was modified during testing.")
    status, summary = _report_status(artifact.path)
    suggestion_path = _write_suggestion(run_dir, case_path, status, summary) if request.suggest else None
    return CaseTestResult(
        run_id=run_id,
        status="success" if status == "passed" else "failed",
        summary=summary,
        report_path=artifact.path,
        evidence_manifest_path=artifact.evidence_manifest_path,
        suggestion_path=suggestion_path,
        warnings=["case.suffix_deprecated: rename this Case to *.fsq.yaml"] if case_path.name.endswith(".codex.yaml") else [],
    )


def _resolve_case_path(value: Path, cases_dir: Path, current_directory: Path) -> Path:
    candidates = [value] if value.is_absolute() else [cases_dir / value, current_directory / value]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"Case not found: {value}")


def _report_status(path: Path) -> tuple[str, str]:
    payload = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    status = str(summary.get("status", "failed"))
    failed = summary.get("failed_steps", 0)
    return status, "Case passed." if status == "passed" else f"Case failed with {failed} failed step(s)."


def _write_suggestion(run_dir: Path, case_path: Path, status: str, summary: str) -> Path:
    suggestions = (
        [
            {
                "kind": "review_failed_steps",
                "message": "Review failed step evidence before changing the Case.",
                "evidence": "core-report.json",
            }
        ]
        if status != "passed"
        else [
            {
                "kind": "no_change_recommended",
                "message": "The Case passed; no source modification is recommended from this Run.",
                "evidence": "core-report.json",
            }
        ]
    )
    path = run_dir / "case-suggestions.json"
    path.write_text(
        json.dumps(
            {
                "source_case": str(case_path),
                "source_case_immutable": True,
                "status": status,
                "summary": summary,
                "suggestions": suggestions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
