# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Any

from pydantic import ValidationError

from fsq_agent.cli._capability_bootstrap import build_capability_registry
from fsq_agent.config import Settings
from fsq_agent.models import CapabilityRegistrySnapshot, ConfigurationError, ExecutableStep


def resolve_strict_replay_steps(
    steps: list[ExecutableStep],
    settings: Settings,
    *,
    registry_snapshot: CapabilityRegistrySnapshot | None = None,
) -> list[ExecutableStep]:
    allowed_names = set(settings.runtime_secrets.allowed_env_names)
    snapshot = registry_snapshot or build_capability_registry(platform=settings.harness.platform).snapshot()
    resolved_steps: list[ExecutableStep] = []
    for step in steps:
        _validate_runtime_secret_refs(step.params, allowed_names, step.step_id)
        _validate_resolved_params(step, step.params, snapshot)
        resolved_steps.append(step)
    return resolved_steps


def collect_runtime_secret_refs(value: Any) -> set[str]:
    names: set[str] = set()
    _collect_runtime_secret_refs(value, names)
    return names


def _validate_runtime_secret_refs(value: Any, allowed_names: set[str], step_id: str) -> None:
    ref_names = collect_runtime_secret_refs(value)
    for name in ref_names:
        if name not in allowed_names:
            raise ConfigurationError(
                "Runtime secret name is not allowed for strict replay.",
                context={"step_id": step_id, "name": name},
            )


def _collect_runtime_secret_refs(value: Any, names: set[str]) -> None:
    if isinstance(value, dict):
        text_type = value.get("textType")
        text = value.get("text")
        if text_type == "runtimeSecret" and isinstance(text, str) and text.strip():
            names.add(text.strip())
            return
        for item in value.values():
            _collect_runtime_secret_refs(item, names)
        return
    if isinstance(value, list):
        for item in value:
            _collect_runtime_secret_refs(item, names)


def _validate_resolved_params(step: ExecutableStep, params: dict[str, Any], registry_snapshot: CapabilityRegistrySnapshot) -> None:
    capability = registry_snapshot.resolve(step.action_name)
    if capability is None:
        return
    try:
        capability.params_model.model_validate(params)
    except ValidationError as exc:
        raise ConfigurationError(
            "Invalid strict replay command after runtime secret resolution.",
            context={
                "step_id": step.step_id,
                "action_name": step.action_name,
                "authored_action_name": step.metadata.get("authored_action_name"),
                "validation_errors": _validation_errors(exc),
            },
        ) from exc


def _validation_errors(error: ValidationError) -> list[dict[str, object]]:
    try:
        return error.errors(include_url=False, include_context=False)
    except TypeError:
        return error.errors()
