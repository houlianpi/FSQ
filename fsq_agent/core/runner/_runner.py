import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import ValidationError

from fsq_agent.core._capabilities import CapabilityRegistry
from fsq_agent.core._runtime_secrets import RuntimeSecretStore
from fsq_agent.core.harness import HarnessInterface
from fsq_agent.models import (
    CapabilityDefinition,
    CapabilityExecutionResult,
    ConfigurationError,
    EvidenceArtifactRef,
    EvidencePolicy,
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    HarnessArtifactRef,
    PostActionDelaySettings,
    ReplayPolicy,
    RunnerEvent,
    RunnerEventType,
    RunnerStatus,
    RunnerStepResult,
    StepPhase,
    StepPhaseReport,
)


@dataclass
class _StepExecutionState:
    started: float = field(default_factory=time.perf_counter)
    phase_reports: list[StepPhaseReport] = field(default_factory=list)
    failure_category: FailureCategory | None = None
    error_message: str | None = None
    artifact_error_message: str | None = None


class StepRunner:
    def __init__(
        self,
        harness: HarnessInterface,
        *,
        capability_registry: CapabilityRegistry | None = None,
        post_action_delay_seconds: PostActionDelaySettings | None = None,
        runtime_secret_store: RuntimeSecretStore | None = None,
    ) -> None:
        self.harness = harness
        self.capability_registry = capability_registry or CapabilityRegistry()
        self.post_action_delay_seconds = post_action_delay_seconds or PostActionDelaySettings(platform=0.0, common=0.0)
        self.runtime_secret_store = runtime_secret_store or RuntimeSecretStore.empty()
        self._events: list[RunnerEvent] = []
        self._last_capability_execution_result: CapabilityExecutionResult | None = None

    @property
    def events(self) -> Sequence[RunnerEvent]:
        return tuple(self._events)

    @property
    def last_capability_execution_result(self) -> CapabilityExecutionResult | None:
        return self._last_capability_execution_result

    def run_step(self, run_id: str, step: ExecutableStep) -> RunnerStepResult:
        self._events = []
        self._last_capability_execution_result = None
        capability, step = self._resolve_capability_step(step)
        step = self._with_effective_evidence_policy(step, capability)
        state = self._start_step(run_id, step)
        return self._run_harness_step(run_id, step, capability, state)

    def _resolve_capability_step(self, step: ExecutableStep) -> tuple[CapabilityDefinition | None, ExecutableStep]:
        capability = self.capability_registry.resolve(step.action_name)
        if capability is not None and capability.name != step.action_name:
            return capability, step.model_copy(update={"action_name": capability.name})
        return capability, step

    def _with_effective_evidence_policy(
        self,
        step: ExecutableStep,
        capability: CapabilityDefinition | None,
    ) -> ExecutableStep:
        return step.model_copy(update={"evidence_policy": self._step_kind_evidence_policy(step, capability)})

    def _step_kind_evidence_policy(
        self,
        step: ExecutableStep,
        capability: CapabilityDefinition | None,
    ) -> EvidencePolicy:
        if capability is None:
            return EvidencePolicy(capture_after=False)
        if step.kind == "action":
            capture_before = True
            capture_after = True
        elif step.kind == "assertion":
            capture_before = True
            capture_after = False
        elif step.kind == "setup":
            capture_before = False
            capture_after = True
        elif step.kind == "teardown":
            capture_before = True
            capture_after = False
        else:
            return EvidencePolicy(capture_after=False)
        return EvidencePolicy(
            capture_before=capture_before,
            capture_after=capture_after,
            capture_on_failure=False,
            artifact_kinds=["screenshot", "ui_snapshot"],
        )

    def _start_step(self, run_id: str, step: ExecutableStep) -> _StepExecutionState:
        state = _StepExecutionState()
        self._emit(run_id=run_id, event_type="step_start", step=step)
        return state

    def _run_harness_step(
        self,
        run_id: str,
        step: ExecutableStep,
        capability: CapabilityDefinition | None,
        state: _StepExecutionState,
    ) -> RunnerStepResult:
        delay_seconds = self._effective_post_action_delay_seconds(capability)
        context = self._run_harness_prepare_phase(run_id, step, state)
        action_result = self._run_harness_invoke_phase(run_id, step, capability, state, context, delay_seconds)
        self._apply_post_action_delay(delay_seconds)
        self._run_harness_finalize_phase(run_id, step, state, context, action_result)
        status = self._result_status(action_result, state.failure_category, state.artifact_error_message)
        return self._finish_step(
            run_id,
            step,
            state,
            status=status,
            failure_category="artifact_error" if state.artifact_error_message else state.failure_category,
            error_message=state.artifact_error_message or state.error_message,
        )

    def _run_harness_prepare_phase(self, run_id: str, step: ExecutableStep, state: _StepExecutionState) -> object:
        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="prepare")
        context = self.harness.get_context()
        prepare_artifacts, prepare_error = self._capture_artifacts(
            run_id=run_id,
            step=step,
            context=context,
            phase="prepare",
            reason="before-action",
            enabled=step.evidence_policy.capture_before,
        )
        if prepare_error:
            state.artifact_error_message = prepare_error
        self.harness.before_action(step, context)
        self._append_phase_report(
            state,
            step=step,
            phase="prepare",
            status="failed" if prepare_error else "passed",
            failure_category="artifact_error" if prepare_error else None,
            error_message=prepare_error,
            artifact_refs=prepare_artifacts,
        )
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="prepare")
        return context

    def _run_harness_invoke_phase(
        self,
        run_id: str,
        step: ExecutableStep,
        capability: CapabilityDefinition | None,
        state: _StepExecutionState,
        context: object,
        delay_seconds: float,
    ) -> HarnessActionResult | None:
        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="invoke")
        self._emit(run_id=run_id, event_type="harness_call_start", step=step, phase="invoke")
        invoke_step = step
        action_result: HarnessActionResult | None = None
        phase_status: RunnerStatus = "failed"
        try:
            validated_step = self._with_validated_params(step, capability)
            invoke_step = self._resolve_runtime_secret_text_step(validated_step, capability)
            action_result = self.harness.invoke_action(invoke_step, context)
            self._last_capability_execution_result = self._capability_execution_result(action_result, invoke_step, capability, context)
            phase_status = action_result.status
            self._emit(run_id=run_id, event_type="harness_call_finish", step=step, phase="invoke")
            if action_result.status in {"failed", "cancelled", "skipped"}:
                state.failure_category = action_result.failure_category
                state.error_message = action_result.error_message
                self._emit(run_id=run_id, event_type="step_error", step=step, phase="invoke")
            self._append_phase_report(
                state,
                step=step,
                phase="invoke",
                status=action_result.status,
                artifact_refs=self._action_result_artifacts(run_id, step, action_result, "invoke"),
                metadata=self._with_post_action_delay_metadata(
                    self._action_result_metadata(action_result, step, invoke_step, capability, context),
                    delay_seconds,
                ),
            )
        except ConfigurationError as exc:
            state.failure_category = "configuration_error"
            state.error_message = str(exc)
            self._emit(run_id=run_id, event_type="harness_call_finish", step=step, phase="invoke")
            self._emit(run_id=run_id, event_type="step_error", step=step, phase="invoke")
            self._append_phase_report(
                state,
                step=step,
                phase="invoke",
                status="failed",
                failure_category=state.failure_category,
                error_message=state.error_message,
                metadata=self._post_action_delay_metadata(delay_seconds),
            )
        except Exception as exc:  # noqa: BLE001 - runner converts phase exceptions into structured results.
            state.failure_category = self.harness.classify_error(exc, "invoke", step)
            state.error_message = str(exc)
            self._emit(run_id=run_id, event_type="harness_call_finish", step=step, phase="invoke")
            self._emit(run_id=run_id, event_type="step_error", step=step, phase="invoke")
            self._append_phase_report(
                state,
                step=step,
                phase="invoke",
                status="failed",
                failure_category=state.failure_category,
                error_message=state.error_message,
                metadata=self._post_action_delay_metadata(delay_seconds),
            )
        self._emit(
            run_id=run_id,
            event_type="phase_finish",
            step=step,
            phase="invoke",
            payload={"status": phase_status, "post_action_delay_seconds": delay_seconds},
        )
        return action_result

    def _with_validated_params(self, step: ExecutableStep, capability: CapabilityDefinition | None) -> ExecutableStep:
        if capability is None:
            return step
        try:
            parsed = capability.params_model.model_validate(step.params)
        except ValidationError as exc:
            raise ConfigurationError(
                "Invalid capability parameters.",
                context={
                    "step_id": step.step_id,
                    "action_name": step.action_name,
                    "validation_errors": self._validation_errors(exc),
                },
            ) from exc
        return step.model_copy(update={"params": parsed.model_dump(mode="json", exclude_none=True)})

    def _validation_errors(self, error: ValidationError) -> list[dict[str, object]]:
        try:
            return error.errors(include_url=False, include_context=False)
        except TypeError:
            return error.errors()

    def _resolve_runtime_secret_text_step(self, step: ExecutableStep, capability: CapabilityDefinition | None) -> ExecutableStep:
        if capability is None:
            return step
        params = dict(step.params)
        if params.get("textType") != "runtimeSecret":
            return step
        text = params.get("text")
        if not isinstance(text, str):
            raise ConfigurationError(
                "Runtime secret text input requires a string text value.",
                context={"step_id": step.step_id, "action_name": step.action_name},
            )
        params["text"] = self.runtime_secret_store.resolve(text)
        params["textType"] = "literal"
        return step.model_copy(update={"params": params})

    def _run_harness_finalize_phase(
        self,
        run_id: str,
        step: ExecutableStep,
        state: _StepExecutionState,
        context: object,
        action_result: HarnessActionResult | None,
    ) -> None:
        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="finalize")
        self.harness.after_action(step, context, action_result)
        finalize_artifacts: list[EvidenceArtifactRef] = []
        finalize_errors: list[str] = []
        after_artifacts, after_error = self._capture_artifacts(
            run_id=run_id,
            step=step,
            context=context,
            phase="finalize",
            reason="after-action",
            enabled=step.evidence_policy.capture_after,
        )
        finalize_artifacts.extend(after_artifacts)
        if after_error:
            finalize_errors.append(after_error)

        if self._is_failed_result(action_result, state.failure_category):
            failure_artifacts, failure_error = self._capture_artifacts(
                run_id=run_id,
                step=step,
                context=context,
                phase="finalize",
                reason="failure",
                enabled=step.evidence_policy.capture_on_failure,
            )
            finalize_artifacts.extend(failure_artifacts)
            if failure_error:
                finalize_errors.append(failure_error)

        if finalize_errors:
            state.artifact_error_message = "; ".join(finalize_errors)
        self._append_phase_report(
            state,
            step=step,
            phase="finalize",
            status="failed" if finalize_errors else "passed",
            failure_category="artifact_error" if finalize_errors else None,
            error_message="; ".join(finalize_errors) if finalize_errors else None,
            artifact_refs=finalize_artifacts,
        )
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="finalize")

    def _record_passed_empty_phase(
        self,
        run_id: str,
        step: ExecutableStep,
        state: _StepExecutionState,
        phase: StepPhase,
    ) -> None:
        self._emit(run_id=run_id, event_type="phase_start", step=step, phase=phase)
        self._append_phase_report(state, step=step, phase=phase, status="passed")
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase=phase)

    def _append_phase_report(
        self,
        state: _StepExecutionState,
        *,
        step: ExecutableStep,
        phase: StepPhase,
        status: RunnerStatus,
        duration_ms: int = 0,
        failure_category: FailureCategory | None = None,
        error_message: str | None = None,
        artifact_refs: list[EvidenceArtifactRef] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        state.phase_reports.append(
            StepPhaseReport(
                step_id=step.step_id,
                phase=phase,
                status=status,
                duration_ms=duration_ms,
                failure_category=failure_category,
                error_message=error_message,
                artifact_refs=artifact_refs or [],
                metadata=metadata or {},
            )
        )

    def _finish_step(
        self,
        run_id: str,
        step: ExecutableStep,
        state: _StepExecutionState,
        *,
        status: RunnerStatus,
        failure_category: FailureCategory | None,
        error_message: str | None,
    ) -> RunnerStepResult:
        self._emit(run_id=run_id, event_type="step_finish", step=step)
        return RunnerStepResult(
            step_id=step.step_id,
            source_ref=step.source_ref,
            status=status,
            duration_ms=self._duration_ms(state.started),
            phase_reports=state.phase_reports,
            max_attempts=step.retry_policy.max_attempts,
            failure_category=failure_category,
            error_message=error_message,
        )

    def _effective_post_action_delay_seconds(self, capability: CapabilityDefinition | None) -> float:
        if capability is None:
            return 0.0
        if capability.post_action_delay_seconds is not None:
            return capability.post_action_delay_seconds
        if capability.executor_kind == "common":
            return self.post_action_delay_seconds.common
        return self.post_action_delay_seconds.platform

    def _apply_post_action_delay(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def _post_action_delay_metadata(self, seconds: float) -> dict[str, object]:
        return {"post_action_delay_seconds": seconds}

    def _with_post_action_delay_metadata(self, metadata: dict[str, object], seconds: float) -> dict[str, object]:
        metadata["post_action_delay_seconds"] = seconds
        return metadata

    def _emit(
        self,
        *,
        run_id: str,
        event_type: RunnerEventType,
        step: ExecutableStep,
        phase: StepPhase | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        self._events.append(
            RunnerEvent(
                event_type=event_type,
                run_id=run_id,
                step_id=step.step_id,
                phase=phase,
                payload=payload or {},
            )
        )

    def _capture_artifacts(
        self,
        *,
        run_id: str,
        step: ExecutableStep,
        context: object,
        phase: StepPhase,
        reason: str,
        enabled: bool,
    ) -> tuple[list[EvidenceArtifactRef], str | None]:
        if not enabled or not step.evidence_policy.artifact_kinds:
            return [], None

        refs: list[EvidenceArtifactRef] = []
        for kind in step.evidence_policy.artifact_kinds:
            try:
                harness_ref = self.harness.capture_artifact(
                    kind=kind,
                    reason=reason,
                    context=context,
                    step_id=step.step_id,
                    phase=phase,
                )
            except Exception as exc:  # noqa: BLE001 - artifact capture failures are recorded as phase facts.
                return refs, str(exc)
            ref = self._to_evidence_artifact_ref(harness_ref, step.step_id, phase)
            refs.append(ref)
            self._emit(
                run_id=run_id,
                event_type="artifact_captured",
                step=step,
                phase=phase,
                payload={
                    "artifact_id": ref.artifact_id,
                    "kind": ref.kind,
                    "path": ref.path.as_posix(),
                    "reason": reason,
                    "phase": phase,
                },
            )
        return refs, None

    def _to_evidence_artifact_ref(
        self,
        ref: HarnessArtifactRef,
        step_id: str,
        phase: StepPhase,
    ) -> EvidenceArtifactRef:
        return EvidenceArtifactRef(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            path=ref.path,
            mime_type=ref.mime_type,
            created_at=ref.created_at,
            step_id=step_id,
            phase=phase,
            metadata=dict(ref.metadata),
        )

    def _action_result_artifacts(
        self,
        run_id: str,
        step: ExecutableStep,
        action_result: HarnessActionResult,
        phase: StepPhase,
    ) -> list[EvidenceArtifactRef]:
        refs: list[EvidenceArtifactRef] = []
        for harness_ref in action_result.artifact_refs:
            ref = self._to_evidence_artifact_ref(harness_ref, step.step_id, phase)
            refs.append(ref)
            self._emit(
                run_id=run_id,
                event_type="artifact_captured",
                step=step,
                phase=phase,
                payload={
                    "artifact_id": ref.artifact_id,
                    "kind": ref.kind,
                    "path": ref.path.as_posix(),
                    "reason": "action-result",
                    "phase": phase,
                },
            )
        return refs

    def _action_result_metadata(
        self,
        action_result: HarnessActionResult,
        original_step: ExecutableStep,
        invoke_step: ExecutableStep,
        capability: CapabilityDefinition | None,
        context: object,
    ) -> dict[str, object]:
        if action_result.metadata.get("executor_kind") == "common":
            metadata = dict(action_result.metadata)
            if action_result.output is not None and not metadata.get("sensitivity"):
                metadata.setdefault("common_output", action_result.output)
            return metadata
        metadata: dict[str, object] = self._capability_metadata(capability, original_step, context)
        if action_result.metadata:
            metadata["harness_metadata"] = action_result.metadata
        if action_result.output is not None and not self._used_runtime_secret_text(original_step, invoke_step):
            metadata["harness_output"] = action_result.output
        return metadata

    def _used_runtime_secret_text(self, original_step: ExecutableStep, invoke_step: ExecutableStep) -> bool:
        return original_step.params.get("textType") == "runtimeSecret" and original_step.params != invoke_step.params

    def _capability_metadata(
        self,
        capability: CapabilityDefinition | None,
        step: ExecutableStep,
        context: object,
    ) -> dict[str, object]:
        if capability is None:
            return {}
        metadata: dict[str, object] = {
            "capability_name": capability.name,
            "executor_kind": capability.executor_kind,
            "step_kind": capability.step_kind,
            "platform": capability.platform,
            "backend": capability.backend,
            "owner": capability.owner,
            "replay": capability.replay.model_dump(mode="json") if capability.replay else None,
            "sensitivity": capability.sensitivity,
        }
        safe_replay_params = self._safe_replay_params(step, capability, context)
        if safe_replay_params:
            metadata["safe_replay_params"] = safe_replay_params
        return metadata

    def _safe_replay_params(
        self,
        step: ExecutableStep,
        capability: CapabilityDefinition,
        context: object,
    ) -> dict[str, object]:
        params = dict(step.params)
        if params.get("textType") == "runtimeSecret":
            return params
        if capability.name not in {"tap_at", "swipe"}:
            return {}
        if capability.name == "swipe" and not self._has_swipe_points(params):
            return {}
        if "reference_screen_size" in params:
            return params
        screen_size = getattr(context, "screen_size", None)
        if not isinstance(screen_size, tuple) or len(screen_size) != 2:
            return params
        width, height = screen_size
        if not isinstance(width, int) or not isinstance(height, int) or width < 1 or height < 1:
            return params
        params["reference_screen_size"] = {"width": width, "height": height}
        return params

    def _has_swipe_points(self, params: dict[str, object]) -> bool:
        return isinstance(params.get("start"), dict) and isinstance(params.get("end"), dict)

    def _capability_execution_result(
        self,
        action_result: HarnessActionResult,
        step: ExecutableStep,
        capability: CapabilityDefinition | None,
        context: object,
    ) -> CapabilityExecutionResult | None:
        metadata = action_result.metadata
        if metadata.get("executor_kind") != "common":
            if capability is None:
                return None
            metadata = self._capability_metadata(capability, step, context)
            replay = metadata.get("replay")
            safe_replay_params = metadata.get("safe_replay_params")
            return CapabilityExecutionResult(
                capability_name=capability.name,
                executor_kind=capability.executor_kind,
                status=action_result.status,
                output=action_result.output,
                artifact_refs=list(action_result.artifact_refs),
                error_message=action_result.error_message,
                failure_category=action_result.failure_category,
                duration_ms=action_result.duration_ms,
                replay=ReplayPolicy.model_validate(replay) if isinstance(replay, dict) else None,
                sensitivity=capability.sensitivity,
                safe_replay_params=safe_replay_params if isinstance(safe_replay_params, dict) else {},
                metadata=metadata,
            )
        replay = metadata.get("replay")
        safe_replay_params = metadata.get("safe_replay_params")
        duration_ms = metadata.get("duration_ms")
        return CapabilityExecutionResult(
            capability_name=str(metadata.get("capability_name") or action_result.action_name),
            executor_kind="common",
            status=action_result.status,
            output=action_result.output,
            error_message=action_result.error_message,
            failure_category=action_result.failure_category,
            duration_ms=duration_ms if isinstance(duration_ms, int) else 0,
            replay=ReplayPolicy.model_validate(replay) if isinstance(replay, dict) else None,
            sensitivity=bool(metadata.get("sensitivity")),
            safe_replay_params=safe_replay_params if isinstance(safe_replay_params, dict) else {},
            metadata=dict(metadata),
        )

    def _is_failed_result(
        self,
        action_result: HarnessActionResult | None,
        failure_category: FailureCategory | None,
    ) -> bool:
        return bool(failure_category) or bool(action_result and action_result.status in {"failed", "cancelled", "skipped"})

    def _result_status(
        self,
        action_result: HarnessActionResult | None,
        failure_category: FailureCategory | None,
        artifact_error_message: str | None,
    ) -> RunnerStatus:
        if artifact_error_message:
            return "failed"
        if action_result and action_result.status in {"failed", "cancelled", "skipped"}:
            return action_result.status
        if failure_category:
            return "failed"
        return "passed"

    def _duration_ms(self, started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))
