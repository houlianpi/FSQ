from typing import Any

from pydantic import ValidationError

from fsq_agent.models import (
    CapabilityDefinition,
    CapabilityRegistrySnapshot,
    ConfigurationError,
    ExecutableStep,
    FsqCase,
    SourceRef,
)


_OBSERVATION_ACTIONS = {"takeScreenshot", "startRecording", "stopRecording"}
class FsqExecutableStepAdapter:
    def __init__(self, registry_snapshot: CapabilityRegistrySnapshot) -> None:
        self.registry_snapshot = registry_snapshot

    def to_executable_steps(self, case: FsqCase) -> list[ExecutableStep]:
        return [self._to_step(case, command, index) for index, command in enumerate(case.commands)]

    def _to_step(self, case: FsqCase, command: Any, index: int) -> ExecutableStep:
        authored_action_name, payload = self._parse_command(case, command, index)
        capability = self.registry_snapshot.resolve(authored_action_name)
        action_name = capability.name if capability is not None else authored_action_name
        raw_params = self._normalize_params(payload)
        timeout_ms = self._timeout_ms(raw_params)
        params = self._canonical_params(case, authored_action_name, raw_params, index, capability)
        return ExecutableStep(
            step_id=f"{case.id}-step-{index + 1:03d}",
            source_ref=SourceRef(
                source_type="fsq",
                source_id=str(case.path),
                step_index=index,
                metadata={"case_name": case.config.name, "platform": case.config.platform},
            ),
            kind=self._step_kind(action_name, capability),
            action_name=action_name,
            params=params,
            timeout_ms=timeout_ms,
            metadata={
                "case_id": case.id,
                "case_name": case.config.name,
                "platform": case.config.platform,
                "authored_action_name": authored_action_name,
                "capability": capability.safe_metadata() if capability is not None else None,
                "raw_command": command,
            },
        )

    def _parse_command(self, case: FsqCase, command: Any, index: int) -> tuple[str, Any]:
        if isinstance(command, str):
            return command, None
        if isinstance(command, dict) and len(command) == 1:
            action_name, payload = next(iter(command.items()))
            return str(action_name), payload
        raise ConfigurationError(
            "Invalid FSQ command.",
            context={"path": str(case.path), "step_index": index},
        )

    def _normalize_params(self, payload: Any) -> dict[str, Any]:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return dict(payload)
        return {"value": payload}

    def _canonical_params(
        self,
        case: FsqCase,
        authored_action_name: str,
        params: dict[str, Any],
        index: int,
        capability: CapabilityDefinition | None,
    ) -> dict[str, Any]:
        if capability is None:
            return params
        driver_params = self._normalize_runtime_secret_text_param({key: value for key, value in params.items() if key != "timeout"})
        try:
            parsed = capability.params_model.model_validate(driver_params)
        except ValidationError as exc:
            raise ConfigurationError(
                "Invalid FSQ command parameters.",
                context={
                    "path": str(case.path),
                    "step_index": index,
                    "action_name": authored_action_name,
                    "validation_errors": self._validation_errors(exc),
                },
            ) from exc
        canonical = parsed.model_dump(mode="json", exclude_none=True)
        if "textType" not in driver_params and canonical.get("textType") == "literal":
            canonical.pop("textType", None)
        return canonical

    def _normalize_runtime_secret_text_param(self, params: dict[str, Any]) -> dict[str, Any]:
        text = params.get("text")
        if "textType" in params or not isinstance(text, dict):
            return params
        if set(text) != {"runtimeSecret"}:
            return params
        secret_name = text.get("runtimeSecret")
        if not isinstance(secret_name, str):
            return params
        return {**params, "text": secret_name, "textType": "runtimeSecret"}

    def _timeout_ms(self, params: dict[str, Any]) -> int | None:
        timeout = params.get("timeout")
        return timeout if isinstance(timeout, int) and timeout >= 1 else None

    def _validation_errors(self, error: ValidationError) -> list[dict[str, object]]:
        try:
            return error.errors(include_url=False, include_context=False)
        except TypeError:
            return error.errors()

    def _step_kind(self, action_name: str, capability: CapabilityDefinition | None) -> str:
        if capability is not None:
            return capability.step_kind
        if action_name in _OBSERVATION_ACTIONS:
            return "observation"
        return "action"
