# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar, get_type_hints

from pydantic import BaseModel

from fsq_agent.capabilities._catalog import CapabilityActionCatalog, CapabilityActionDefinition
from fsq_agent.models import (
    CapabilityExecutorKind,
    ConfigurationError,
    ExecutableStepKind,
    HarnessPlatform,
    ReplayPolicy,
)


F = TypeVar("F", bound=Callable[..., Any])
CAPABILITY_DECLARATION_ATTR = "__fsq_capability_declaration__"
_SAFE_METADATA_SCALARS = (str, int, float, bool, type(None))


@dataclass(frozen=True)
class CapabilityDeclaration:
    name: str | None
    executor_kind: CapabilityExecutorKind
    owner: str | None = None
    params_model: type[BaseModel] | None = None
    description: str = ""
    platform: HarnessPlatform | None = None
    backend: str | None = None
    step_kind: ExecutableStepKind = "action"
    post_action_delay_seconds: float | None = None
    sensitivity: bool = False
    replay: ReplayPolicy | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    action_name: str | None = None
    required_method_name: str | None = None


def capability(
    *,
    executor_kind: CapabilityExecutorKind,
    name: str | None = None,
    owner: str | None = None,
    params_model: type[BaseModel] | None = None,
    description: str = "",
    platform: HarnessPlatform | None = None,
    backend: str | None = None,
    step_kind: ExecutableStepKind = "action",
    post_action_delay_seconds: float | None = None,
    sensitivity: bool = False,
    replay: ReplayPolicy | None = None,
    metadata: dict[str, Any] | None = None,
    action_catalog: CapabilityActionCatalog | None = None,
    action_name: str | None = None,
) -> Callable[[F], F]:
    declaration = _declaration_from_args(
        name=name,
        executor_kind=executor_kind,
        owner=owner,
        params_model=params_model,
        description=description,
        platform=platform,
        backend=backend,
        step_kind=step_kind,
        post_action_delay_seconds=post_action_delay_seconds,
        sensitivity=sensitivity,
        replay=replay,
        metadata=metadata,
        action_catalog=action_catalog,
        action_name=action_name,
    )

    def decorate(method: F) -> F:
        _validate_method(declaration, method)
        setattr(method, CAPABILITY_DECLARATION_ATTR, declaration)
        return method

    return decorate


def platform_driver_capability(
    *,
    platform: HarnessPlatform,
    catalog: CapabilityActionCatalog,
    backend: str | None = None,
) -> Callable[..., Callable[[F], F]]:
    def declare(
        action_name: str,
        *,
        description: str,
        post_action_delay_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Callable[[F], F]:
        action_definition = _action_definition(catalog, action_name)
        return capability(
            executor_kind="driver",
            owner="driver",
            description=description,
            platform=platform,
            backend=backend,
            post_action_delay_seconds=post_action_delay_seconds,
            metadata=metadata,
            action_catalog=catalog,
            action_name=action_name,
        )

    return declare


def get_capability_declaration(candidate: object) -> CapabilityDeclaration | None:
    declaration = getattr(candidate, CAPABILITY_DECLARATION_ATTR, None)
    if isinstance(declaration, CapabilityDeclaration):
        return declaration
    underlying = getattr(candidate, "__func__", None)
    declaration = getattr(underlying, CAPABILITY_DECLARATION_ATTR, None)
    if isinstance(declaration, CapabilityDeclaration):
        return declaration
    return None


def _declaration_from_args(
    *,
    name: str | None,
    executor_kind: CapabilityExecutorKind,
    owner: str | None,
    params_model: type[BaseModel] | None,
    description: str,
    platform: HarnessPlatform | None,
    backend: str | None,
    step_kind: ExecutableStepKind,
    post_action_delay_seconds: float | None,
    sensitivity: bool,
    replay: ReplayPolicy | None,
    metadata: dict[str, Any] | None,
    action_catalog: CapabilityActionCatalog | None,
    action_name: str | None,
) -> CapabilityDeclaration:
    _validate_basic_combination(executor_kind, action_catalog, action_name)
    safe_metadata = dict(metadata or {})
    _validate_safe_metadata(safe_metadata)
    _validate_post_action_delay(post_action_delay_seconds)
    required_method_name: str | None = None
    resolved_post_action_delay_seconds = post_action_delay_seconds

    if action_catalog is not None:
        action_definition = _action_definition(action_catalog, action_name)
        _validate_post_action_delay(action_definition.post_action_delay_seconds)
        _validate_action_definition(action_definition, executor_kind, owner, params_model, step_kind, replay)
        name = name or action_definition.canonical_name
        owner = owner or action_definition.owner
        params_model = params_model or action_definition.params_model
        if step_kind == "action":
            step_kind = action_definition.step_kind
        replay = replay or action_definition.replay
        resolved_post_action_delay_seconds = (
            action_definition.post_action_delay_seconds
            if post_action_delay_seconds is None
            else post_action_delay_seconds
        )
        required_method_name = action_definition.method_name
        safe_metadata = {**action_definition.metadata, **safe_metadata}
        _validate_safe_metadata(safe_metadata)

    return CapabilityDeclaration(
        name=name,
        executor_kind=executor_kind,
        owner=owner,
        params_model=params_model,
        description=description,
        platform=platform,
        backend=backend,
        step_kind=step_kind,
        post_action_delay_seconds=resolved_post_action_delay_seconds,
        sensitivity=sensitivity,
        replay=replay,
        metadata=safe_metadata,
        action_name=action_name,
        required_method_name=required_method_name,
    )


def _validate_basic_combination(
    executor_kind: CapabilityExecutorKind,
    action_catalog: CapabilityActionCatalog | None,
    action_name: str | None,
) -> None:
    if executor_kind not in {"common", "driver"}:
        raise ConfigurationError("Invalid capability executor kind.", context={"executor_kind": executor_kind})
    if executor_kind == "common" and action_catalog is not None:
        raise ConfigurationError("Common capabilities must not use a platform action catalog.")
    if action_catalog is None and action_name is not None:
        raise ConfigurationError("Capability action_name requires an action_catalog.", context={"action_name": action_name})
    if action_catalog is not None and action_name is None:
        raise ConfigurationError("Capability action_catalog requires an action_name.")


def _validate_post_action_delay(value: float | None) -> None:
    if value is not None and value < 0:
        raise ConfigurationError("Capability post_action_delay_seconds must be non-negative.", context={"post_action_delay_seconds": value})


def _action_definition(catalog: CapabilityActionCatalog, action_name: str | None) -> CapabilityActionDefinition:
    if action_name is None:
        raise ConfigurationError("Capability action_catalog requires an action_name.")
    action_definition = catalog.get(action_name)
    if action_definition is None:
        raise ConfigurationError("Unknown platform capability action.", context={"action_name": action_name})
    return action_definition


def _validate_action_definition(
    action_definition: CapabilityActionDefinition,
    executor_kind: CapabilityExecutorKind,
    owner: str | None,
    params_model: type[BaseModel] | None,
    step_kind: ExecutableStepKind,
    replay: ReplayPolicy | None,
) -> None:
    if action_definition.executor_kind != executor_kind:
        raise ConfigurationError(
            "Platform action executor kind does not match the decorator.",
            context={
                "action_name": action_definition.action_name,
                "expected": action_definition.executor_kind,
                "actual": executor_kind,
            },
        )
    if owner is not None and owner != action_definition.owner:
        raise ConfigurationError(
            "Platform action owner does not match the decorator.",
            context={"action_name": action_definition.action_name, "expected": action_definition.owner, "actual": owner},
        )
    if params_model is not None and params_model is not action_definition.params_model:
        raise ConfigurationError(
            "Platform action parameter model does not match the catalog.",
            context={
                "action_name": action_definition.action_name,
                "expected_model": action_definition.params_model.__name__,
                "actual_model": getattr(params_model, "__name__", str(params_model)),
            },
        )
    if step_kind != "action" and step_kind != action_definition.step_kind:
        raise ConfigurationError(
            "Platform action step kind does not match the catalog.",
            context={"action_name": action_definition.action_name, "expected": action_definition.step_kind, "actual": step_kind},
        )
    if replay is not None and action_definition.replay is not None and replay != action_definition.replay:
        raise ConfigurationError("Platform action replay policy does not match the catalog.", context={"action_name": action_definition.action_name})


def _validate_method(declaration: CapabilityDeclaration, method: Callable[..., Any]) -> None:
    method_name = getattr(method, "__name__", "")
    if declaration.required_method_name is not None and method_name != declaration.required_method_name:
        raise ConfigurationError(
            "Capability method does not match the action catalog.",
            context={
                "action_name": declaration.action_name,
                "expected_method": declaration.required_method_name,
                "actual_method": method_name,
            },
        )
    needs_params_check = declaration.required_method_name is not None or "params" in getattr(method, "__annotations__", {})
    if not needs_params_check:
        return
    try:
        hints = get_type_hints(method)
    except Exception as exc:
        raise ConfigurationError(
            "Capability parameter model could not be resolved.",
            context={"method": method_name, "reason": str(exc)},
        ) from exc
    annotated_model = hints.get("params")
    if annotated_model is None and declaration.required_method_name is None:
        return
    if annotated_model is not declaration.params_model:
        raise ConfigurationError(
            "Capability parameter model does not match the action catalog.",
            context={
                "action_name": declaration.action_name,
                "method": method_name,
                "expected_model": getattr(declaration.params_model, "__name__", str(declaration.params_model)),
                "actual_model": getattr(annotated_model, "__name__", str(annotated_model)),
            },
        )


def _validate_safe_metadata(value: Any, *, path: str = "metadata") -> None:
    if isinstance(value, _SAFE_METADATA_SCALARS):
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_safe_metadata(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConfigurationError("Capability metadata keys must be strings.", context={"path": path, "key": repr(key)})
            _validate_safe_metadata(item, path=f"{path}.{key}")
        return
    raise ConfigurationError(
        "Capability metadata must contain only serializable scalar, list, and dict values.",
        context={"path": path, "type": type(value).__name__},
    )
