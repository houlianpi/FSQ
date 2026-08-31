# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import logging
import subprocess
import sys
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from fsq_agent.adapters.cli._strict_replay import resolve_strict_replay_steps
from fsq_agent.adapters.cli._task_loader import resolve_case_yaml_path
from fsq_agent.case_dsl import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.core import CapabilityRegistry, EvidenceRecorder, HarnessInterface, RuntimeSecretStore, StepRunner, StepSequenceRunner
from fsq_agent.models import (
    CapabilityRegistrySnapshot,
    CaseLifecycleSettings,
    ConfigurationError,
    ExecutableStep,
    FsqCase,
    FsqCaseHook,
    FsqCaseHookAction,
    PostActionDelaySettings,
    ReportArtifact,
    RunnerEvent,
    RunnerStepResult,
    SourceRef,
    StepPhaseReport,
)
from fsq_agent.report import CoreEvidenceReportGenerator

if TYPE_CHECKING:
    from pathlib import Path

    from fsq_agent.config import Settings

LifecyclePhase = Literal["onCaseStart", "case", "onCaseComplete"]
logger = logging.getLogger("fsq_agent.adapters.cli._case_lifecycle")
_PHASE_LABELS = {
    "onCaseStart": "before case",
    "case": "main case",
    "onCaseComplete": "after case",
}


def case_has_lifecycle_hooks(case: FsqCase) -> bool:
    return bool(case.config.on_case_start or case.config.on_case_complete)


def lifecycle_settings_have_hooks(case_lifecycle: CaseLifecycleSettings) -> bool:
    return bool(case_lifecycle.on_case_start or case_lifecycle.on_case_complete)


def collect_lifecycle_cases(
    *,
    case_path: Path,
    case: FsqCase,
    cases_dir: Path | None,
    case_lifecycle: CaseLifecycleSettings | None = None,
    loader: FsqCaseLoader | None = None,
) -> list[tuple[Path, FsqCase]]:
    collector = _LifecycleCaseCollector(cases_dir=cases_dir, loader=loader or FsqCaseLoader())
    return collector.collect(case_path.resolve(), case, case_lifecycle=case_lifecycle)


def run_strict_fsq_lifecycle_case(
    *,
    case_path: Path,
    case: FsqCase,
    settings: Settings,
    harness: HarnessInterface,
    output_dir: Path,
    run_id: str,
    registry: CapabilityRegistry,
    registry_snapshot: CapabilityRegistrySnapshot | None = None,
    post_action_delay_seconds: PostActionDelaySettings | None = None,
) -> ReportArtifact:
    executor = _StrictLifecycleExecutor(
        case_path=case_path.resolve(),
        case=case,
        settings=settings,
        harness=harness,
        output_dir=output_dir,
        run_id=run_id,
        registry=registry,
        registry_snapshot=registry_snapshot or registry.snapshot(),
        post_action_delay_seconds=post_action_delay_seconds,
    )
    return executor.run()


class _LifecycleCaseCollector:
    def __init__(self, *, cases_dir: Path | None, loader: FsqCaseLoader) -> None:
        self.cases_dir = cases_dir
        self.loader = loader
        self.cases: list[tuple[Path, FsqCase]] = []

    def collect(
        self,
        case_path: Path,
        case: FsqCase,
        *,
        case_lifecycle: CaseLifecycleSettings | None = None,
    ) -> list[tuple[Path, FsqCase]]:
        self._collect(case_path, case, stack=(), case_lifecycle=case_lifecycle)
        return list(self.cases)

    def _collect(
        self,
        case_path: Path,
        case: FsqCase,
        stack: tuple[Path, ...],
        *,
        case_lifecycle: CaseLifecycleSettings | None = None,
    ) -> None:
        if case_path in stack:
            raise ConfigurationError(
                "Recursive lifecycle hook runCase detected.",
                context={"case_path": str(case_path), "chain": [str(path) for path in (*stack, case_path)]},
            )
        stack = (*stack, case_path)
        self.cases.append((case_path, case))
        for action in _iter_lifecycle_run_actions(case, case_lifecycle=case_lifecycle):
            child_path = resolve_case_yaml_path(action.value, self.cases_dir)
            child_case = self.loader.load_case(child_path)
            self._collect(child_path, child_case, stack)


class _StrictLifecycleExecutor:
    def __init__(
        self,
        *,
        case_path: Path,
        case: FsqCase,
        settings: Settings,
        harness: HarnessInterface,
        output_dir: Path,
        run_id: str,
        registry: CapabilityRegistry,
        registry_snapshot: CapabilityRegistrySnapshot,
        post_action_delay_seconds: PostActionDelaySettings | None,
    ) -> None:
        self.case_path = case_path
        self.case = case
        self.settings = settings
        self.harness = harness
        self.output_dir = output_dir
        self.run_id = run_id
        self.registry = registry
        self.registry_snapshot = registry_snapshot
        self.step_runner = StepRunner(
            harness=harness,
            capability_registry=registry,
            post_action_delay_seconds=post_action_delay_seconds,
            runtime_secret_store=RuntimeSecretStore.from_settings(settings.runtime_secrets),
        )
        self.recorder = _StrictLifecycleEvidenceRecorder(
            EvidenceRecorder(
                run_id=run_id,
                output_dir=output_dir,
                metadata={"root_case_path": str(case_path), "root_case_id": case.id},
            )
        )
        self.loader = FsqCaseLoader()
        self._shell_step_index = 0
        self._run_case_step_index = 0
        self._logged_phase_starts: set[LifecyclePhase] = set()

    def run(self) -> ReportArtifact:
        self._execute_case(self.case_path, self.case, stack=())
        manifest_path = self.recorder.write_manifest()
        return CoreEvidenceReportGenerator().generate_from_manifest(manifest_path)

    def _execute_case(
        self,
        case_path: Path,
        case: FsqCase,
        stack: tuple[Path, ...],
        parent_hook_action: dict[str, object] | None = None,
    ) -> bool:
        if case_path in stack:
            raise ConfigurationError(
                "Recursive lifecycle hook runCase detected.",
                context={"case_path": str(case_path), "chain": [str(path) for path in (*stack, case_path)]},
            )
        stack = (*stack, case_path)
        is_root_case = parent_hook_action is None and case_path == self.case_path
        config_start_ok = True
        if is_root_case:
            config_start_ok = self._execute_hooks(
                case_path,
                case,
                "onCaseStart",
                self.settings.case_lifecycle.on_case_start,
                stack,
                hook_origin="config",
                continue_after_failure=False,
            )
        start_ok = False
        if config_start_ok:
            start_ok = self._execute_hooks(
                case_path,
                case,
                "onCaseStart",
                case.config.on_case_start,
                stack,
                hook_origin="case",
                continue_after_failure=False,
            )
        main_ok = False
        if start_ok:
            main_ok = self._execute_case_commands(case_path, case, "case", stack, parent_hook_action)
        complete_ok = self._execute_hooks(
            case_path,
            case,
            "onCaseComplete",
            case.config.on_case_complete,
            stack,
            hook_origin="case",
            continue_after_failure=True,
        )
        config_complete_ok = True
        if is_root_case:
            config_complete_ok = self._execute_hooks(
                case_path,
                case,
                "onCaseComplete",
                self.settings.case_lifecycle.on_case_complete,
                stack,
                hook_origin="config",
                continue_after_failure=True,
            )
        return config_start_ok and start_ok and main_ok and complete_ok and config_complete_ok

    def _execute_hooks(
        self,
        case_path: Path,
        case: FsqCase,
        phase: LifecyclePhase,
        hooks: list[FsqCaseHook],
        stack: tuple[Path, ...],
        *,
        hook_origin: str,
        continue_after_failure: bool,
    ) -> bool:
        if hooks:
            self._log_phase_start(phase)
        all_passed = True
        for hook_index, hook in enumerate(hooks, start=1):
            for action_index, action in enumerate(hook.actions, start=1):
                passed = self._execute_hook_action(case_path, case, phase, hook_index, action_index, action, stack, hook_origin)
                all_passed = all_passed and passed
                if not passed and not continue_after_failure:
                    return False
        return all_passed

    def _execute_hook_action(
        self,
        case_path: Path,
        case: FsqCase,
        phase: LifecyclePhase,
        hook_index: int,
        action_index: int,
        action: FsqCaseHookAction,
        stack: tuple[Path, ...],
        hook_origin: str,
    ) -> bool:
        metadata = {
            "lifecycle_phase": phase,
            "hook_index": hook_index,
            "hook_action_index": action_index,
            "hook_action_name": action.action_name,
            "hook_origin": hook_origin,
            "root_case_path": str(self.case_path),
            "case_path": str(case_path),
            "case_id": case.id,
            "hook_chain": [str(path) for path in stack],
            "value": action.value,
        }
        if action.action_name == "runCase":
            child_path = resolve_case_yaml_path(action.value, self.settings.cases.dir)
            child_case = self.loader.load_case(child_path)
            started_at = datetime.now(UTC)
            started = time.perf_counter()
            passed = self._execute_case(child_path, child_case, stack, parent_hook_action=metadata)
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            self._record_run_case_hook(action.value, metadata, passed, started_at, duration_ms)
            return passed
        return self._execute_shell_hook(action.value, metadata)

    def _execute_case_commands(
        self,
        case_path: Path,
        case: FsqCase,
        phase: LifecyclePhase,
        stack: tuple[Path, ...],
        parent_hook_action: dict[str, object] | None,
    ) -> bool:
        steps = FsqExecutableStepAdapter(registry_snapshot=self.registry_snapshot).to_executable_steps(case)
        steps = resolve_strict_replay_steps(steps, self.settings, registry_snapshot=self.registry_snapshot)
        steps = [self._annotate_step(step, case_path, case, phase, stack, parent_hook_action) for step in steps]
        if steps:
            self._log_phase_start(_effective_lifecycle_phase(phase, parent_hook_action))
        normal_steps, teardown_steps = _split_trailing_teardown_steps(steps)
        step_count_before = len(self.recorder.build_bundle().steps)
        StepSequenceRunner(step_runner=self.step_runner, evidence_recorder=self.recorder).run_steps(
            run_id=self.run_id,
            steps=normal_steps,
            teardown_steps=teardown_steps,
        )
        new_steps = self.recorder.build_bundle().steps[step_count_before:]
        return all(step.status == "passed" for step in new_steps)

    def _annotate_step(
        self,
        step: ExecutableStep,
        case_path: Path,
        case: FsqCase,
        phase: LifecyclePhase,
        stack: tuple[Path, ...],
        parent_hook_action: dict[str, object] | None,
    ) -> ExecutableStep:
        parent_metadata = {"parent_hook_action": parent_hook_action} if parent_hook_action is not None else {}
        if parent_hook_action is not None and "hook_origin" in parent_hook_action:
            parent_metadata["hook_origin"] = parent_hook_action["hook_origin"]
        metadata = {
            **step.metadata,
            "lifecycle_phase": phase,
            "root_case_path": str(self.case_path),
            "case_path": str(case_path),
            "hook_chain": [str(path) for path in stack],
            **parent_metadata,
        }
        source_ref = step.source_ref
        if source_ref is not None:
            source_ref = source_ref.model_copy(
                update={
                    "metadata": {
                        **source_ref.metadata,
                        "lifecycle_phase": phase,
                        "root_case_path": str(self.case_path),
                        **parent_metadata,
                    }
                }
            )
        if phase != "case" or case_path != self.case_path:
            step_id = f"{case.id}-{phase}-step-{step.source_ref.step_index + 1:03d}" if step.source_ref else step.step_id
            return step.model_copy(update={"step_id": step_id, "metadata": metadata, "source_ref": source_ref})
        return step.model_copy(update={"metadata": metadata, "source_ref": source_ref})

    def _execute_shell_hook(self, command: str, metadata: dict[str, object]) -> bool:
        self._shell_step_index += 1
        step_id = f"{self.case.id}-hook-shell-{self._shell_step_index:03d}"
        started_at = datetime.now(UTC)
        started = time.perf_counter()
        self.recorder.record_event(RunnerEvent(run_id=self.run_id, event_type="step_start", step_id=step_id))
        self.recorder.record_event(RunnerEvent(run_id=self.run_id, event_type="phase_start", step_id=step_id, phase="invoke"))
        try:
            completed = _run_shell_command(command)
            exit_code = completed.returncode
            stdout_length = len((completed.stdout or "").encode("utf-8", errors="replace"))
            stderr_length = len((completed.stderr or "").encode("utf-8", errors="replace"))
            error_message = None if exit_code == 0 else f"Shell hook failed with exit code {exit_code}."
        except Exception as exc:  # noqa: BLE001 - shell hook failures become structured evidence.
            exit_code = None
            stdout_length = 0
            stderr_length = 0
            error_message = f"Shell hook failed to start: {exc}"
        ended_at = datetime.now(UTC)
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        status = "passed" if error_message is None else "failed"
        failure_category = None if status == "passed" else "action_error"
        phase_metadata = {
            **metadata,
            "command": command,
            "exit_code": exit_code,
            "stdout_bytes": stdout_length,
            "stderr_bytes": stderr_length,
        }
        phase_report = StepPhaseReport(
            step_id=step_id,
            phase="invoke",
            status=status,
            duration_ms=duration_ms,
            failure_category=failure_category,
            error_message=error_message,
            metadata=phase_metadata,
        )
        source_ref = SourceRef(
            source_type="fsq_hook",
            source_id=str(metadata["case_path"]),
            metadata={key: value for key, value in metadata.items() if key != "hook_chain"},
        )
        result = RunnerStepResult(
            step_id=step_id,
            source_ref=source_ref,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            phase_reports=[phase_report],
            failure_category=failure_category,
            error_message=error_message,
            metadata=phase_metadata,
        )
        self.recorder.record_event(
            RunnerEvent(
                run_id=self.run_id,
                event_type="phase_finish",
                step_id=step_id,
                phase="invoke",
                payload={"status": status, "exit_code": exit_code},
            )
        )
        if status != "passed":
            self.recorder.record_event(RunnerEvent(run_id=self.run_id, event_type="step_error", step_id=step_id, phase="invoke"))
        self.recorder.record_event(RunnerEvent(run_id=self.run_id, event_type="step_finish", step_id=step_id, payload={"status": status}))
        self.recorder.record_step_result(result)
        return status == "passed"

    def _record_run_case_hook(
        self,
        target: str,
        metadata: dict[str, object],
        passed: bool,
        started_at: datetime,
        duration_ms: int,
    ) -> None:
        self._run_case_step_index += 1
        step_id = f"{self.case.id}-hook-run-case-{self._run_case_step_index:03d}"
        status = "passed" if passed else "failed"
        failure_category = None if passed else "action_error"
        error_message = None if passed else f"Hook runCase failed: {target}"
        phase_metadata = {
            **metadata,
            "target": target,
        }
        source_ref = SourceRef(
            source_type="fsq_hook",
            source_id=str(metadata["case_path"]),
            metadata={key: value for key, value in phase_metadata.items() if key != "hook_chain"},
        )
        phase_report = StepPhaseReport(
            step_id=step_id,
            phase="invoke",
            status=status,
            duration_ms=duration_ms,
            failure_category=failure_category,
            error_message=error_message,
            metadata=phase_metadata,
        )
        result = RunnerStepResult(
            step_id=step_id,
            source_ref=source_ref,
            status=status,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            duration_ms=duration_ms,
            phase_reports=[phase_report],
            failure_category=failure_category,
            error_message=error_message,
            metadata=phase_metadata,
        )
        if status != "passed":
            self.recorder.record_event(RunnerEvent(run_id=self.run_id, event_type="step_error", step_id=step_id, phase="invoke"))
        self.recorder.record_event(RunnerEvent(run_id=self.run_id, event_type="step_finish", step_id=step_id, payload={"status": status}))
        self.recorder.record_step_result(result)

    def _log_phase_start(self, phase: LifecyclePhase) -> None:
        if phase in self._logged_phase_starts:
            return
        self._logged_phase_starts.add(phase)
        logger.info("Strict phase %s: start", _phase_label(phase))


class _StrictLifecycleEvidenceRecorder:
    def __init__(self, recorder: EvidenceRecorder) -> None:
        self.recorder = recorder

    def record_event(self, event: RunnerEvent) -> None:
        self.recorder.record_event(event)

    def record_step_result(self, result: RunnerStepResult) -> None:
        self.recorder.record_step_result(result)
        action = _result_action_label(result)
        phase = _phase_label(_result_lifecycle_phase(result))
        suffix = f": {result.error_message}" if result.status != "passed" and result.error_message else ""
        logger.info("Strict %s action %s: %s%s", phase, action, result.status, suffix)

    def build_bundle(self):
        return self.recorder.build_bundle()

    def write_manifest(self) -> Path:
        return self.recorder.write_manifest()


def _iter_lifecycle_run_actions(
    case: FsqCase,
    *,
    case_lifecycle: CaseLifecycleSettings | None = None,
) -> list[FsqCaseHookAction]:
    actions: list[FsqCaseHookAction] = []
    if case_lifecycle is not None:
        for hook in [*case_lifecycle.on_case_start, *case_lifecycle.on_case_complete]:
            actions.extend(action for action in hook.actions if action.action_name == "runCase")
    for hook in [*case.config.on_case_start, *case.config.on_case_complete]:
        actions.extend(action for action in hook.actions if action.action_name == "runCase")
    return actions


def _effective_lifecycle_phase(phase: LifecyclePhase, parent_hook_action: dict[str, object] | None) -> LifecyclePhase:
    if parent_hook_action is None:
        return phase
    parent_phase = parent_hook_action.get("lifecycle_phase")
    if parent_phase in {"onCaseStart", "onCaseComplete"}:
        return parent_phase  # type: ignore[return-value]
    return phase


def _result_lifecycle_phase(result: RunnerStepResult) -> LifecyclePhase:
    source_metadata = result.source_ref.metadata if result.source_ref is not None else {}
    parent = source_metadata.get("parent_hook_action") or result.metadata.get("parent_hook_action")
    if isinstance(parent, dict) and parent.get("lifecycle_phase") in {"onCaseStart", "onCaseComplete"}:
        return parent["lifecycle_phase"]  # type: ignore[return-value]
    lifecycle = source_metadata.get("lifecycle_phase") or result.metadata.get("lifecycle_phase")
    if lifecycle in {"onCaseStart", "onCaseComplete", "case"}:
        return lifecycle  # type: ignore[return-value]
    return "case"


def _phase_label(phase: LifecyclePhase) -> str:
    return _PHASE_LABELS[phase]


def _result_action_label(result: RunnerStepResult) -> str:
    source_metadata = result.source_ref.metadata if result.source_ref is not None else {}
    hook_action = source_metadata.get("hook_action_name") or result.metadata.get("hook_action_name")
    command = result.metadata.get("command") or _phase_metadata_value(result, "command")
    if hook_action == "runShell":
        return f"runShell: {command}" if command else "runShell"
    if hook_action == "runCase":
        target = result.metadata.get("value") or result.metadata.get("target")
        return f"runCase: {target}" if target else "runCase"
    replay_alias = _phase_metadata_value(result, "replay", nested_key="alias")
    if isinstance(replay_alias, str) and replay_alias.strip():
        return replay_alias
    capability_name = _phase_metadata_value(result, "capability_name")
    if isinstance(capability_name, str) and capability_name.strip():
        return capability_name
    return str(hook_action or "unknown")


def _phase_metadata_value(result: RunnerStepResult, key: str, *, nested_key: str | None = None) -> object | None:
    for phase_report in result.phase_reports:
        if key not in phase_report.metadata:
            continue
        value = phase_report.metadata[key]
        if nested_key is None:
            return value
        if isinstance(value, dict):
            return value.get(nested_key)
    return None


def _run_shell_command(command: str) -> subprocess.CompletedProcess[str]:
    if sys.platform == "win32":
        # PowerShell is a fixed platform executable; only trusted, operator-authored command text is dynamic.
        return subprocess.run(  # noqa: S603
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    # POSIX lifecycle hooks intentionally execute operator-authored shell syntax through the local system shell.
    return subprocess.run(command, shell=True, capture_output=True, text=True, check=False)  # noqa: S602


def _split_trailing_teardown_steps(steps: list[ExecutableStep]) -> tuple[list[ExecutableStep], list[ExecutableStep]]:
    split_at = len(steps)
    while split_at > 0 and steps[split_at - 1].kind == "teardown":
        split_at -= 1
    return steps[:split_at], steps[split_at:]
