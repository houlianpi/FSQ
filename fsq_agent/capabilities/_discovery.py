# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import BaseModel

from fsq_agent.capabilities._decorators import CapabilityDeclaration, get_capability_declaration
from fsq_agent.models import CapabilityDefinition, ConfigurationError


def discover_capability_definitions(
    target: object,
    *,
    metadata: dict[str, object] | None = None,
) -> list[CapabilityDefinition]:
    definitions: list[CapabilityDefinition] = []
    for method_name, method in inspect.getmembers(_target_type(target), predicate=callable):
        declaration = get_capability_declaration(method)
        if declaration is None:
            continue
        definitions.append(_definition_from_declaration(method_name, method, declaration, metadata or {}))
    return definitions


def _definition_from_declaration(
    method_name: str,
    method: Callable[..., Any],
    declaration: CapabilityDeclaration,
    metadata: dict[str, object],
) -> CapabilityDefinition:
    params_model = declaration.params_model or _infer_params_model(method_name, method)
    capability_metadata: dict[str, Any] = dict(metadata)
    capability_metadata.update(declaration.metadata)
    if declaration.executor_kind == "driver":
        capability_metadata.setdefault("driver_method", method_name)
    if declaration.action_name is not None:
        capability_metadata.setdefault("fsq_action_name", declaration.action_name)
    return CapabilityDefinition(
        name=declaration.name or method_name,
        executor_kind=declaration.executor_kind,
        params_model=params_model,
        step_kind=declaration.step_kind,
        description=declaration.description,
        platform=declaration.platform,
        backend=declaration.backend or _metadata_str(capability_metadata, "backend"),
        owner=declaration.owner,
        post_action_delay_seconds=declaration.post_action_delay_seconds,
        sensitivity=declaration.sensitivity,
        replay=declaration.replay,
        metadata=capability_metadata,
    )


def _target_type(target: object) -> type:
    return target if isinstance(target, type) else type(target)


def _infer_params_model(method_name: str, method: Callable[..., Any]) -> type[BaseModel]:
    try:
        hints = get_type_hints(method)
    except Exception as exc:
        raise ConfigurationError(
            "Capability parameter model could not be resolved.",
            context={"method": method_name, "reason": str(exc)},
        ) from exc
    model = hints.get("params")
    if isinstance(model, type) and issubclass(model, BaseModel):
        return model
    raise ConfigurationError(
        "Capability requires a Pydantic params model annotation or explicit params_model.",
        context={"method": method_name},
    )


def _metadata_str(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) else None
