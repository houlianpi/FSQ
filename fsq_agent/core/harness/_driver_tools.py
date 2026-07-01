from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from fsq_agent.capabilities import CapabilityActionDefinition, driver_capability, discover_capability_definitions, platform_driver_capability
from fsq_agent.models import (
    ANDROID_ACTION_DEFINITIONS,
    MACOS_ACTION_DEFINITIONS,
    WEB_ACTION_DEFINITIONS,
    WINDOWS_ACTION_DEFINITIONS,
    CapabilityDefinition,
    HarnessFunctionSchema,
    HarnessPlatform,
    ReplayPolicy,
)


F = TypeVar("F", bound=Callable[..., Any])


ANDROID_DRIVER_ACTION_CATALOG = {
    definition.fsq_action_name: CapabilityActionDefinition(
        action_name=definition.fsq_action_name,
        canonical_name=definition.driver_method,
        executor_kind="driver",
        owner=definition.owner,
        params_model=definition.params_model,
        step_kind=definition.step_kind,
        method_name=definition.driver_method,
        replay=ReplayPolicy(kind="fsq_command", alias=definition.fsq_action_name),
        strict=definition.strict,
    )
    for definition in ANDROID_ACTION_DEFINITIONS
    if definition.owner == "driver"
}
_android_driver_capability = platform_driver_capability(
    platform="android",
    backend=None,
    catalog=ANDROID_DRIVER_ACTION_CATALOG,
)

WEB_DRIVER_ACTION_CATALOG = {
    definition.fsq_action_name: CapabilityActionDefinition(
        action_name=definition.fsq_action_name,
        canonical_name=definition.driver_method,
        executor_kind="driver",
        owner=definition.owner,
        params_model=definition.params_model,
        step_kind=definition.step_kind,
        method_name=definition.driver_method,
        replay=ReplayPolicy(kind="fsq_command", alias=definition.fsq_action_name),
        strict=definition.strict,
        capture_evidence=definition.capture_evidence,
    )
    for definition in WEB_ACTION_DEFINITIONS
    if definition.owner == "driver"
}
_web_driver_capability = platform_driver_capability(
    platform="web",
    backend=None,
    catalog=WEB_DRIVER_ACTION_CATALOG,
)


WINDOWS_DRIVER_ACTION_CATALOG = {
    definition.fsq_action_name: CapabilityActionDefinition(
        action_name=definition.fsq_action_name,
        canonical_name=definition.driver_method,
        executor_kind="driver",
        owner=definition.owner,
        params_model=definition.params_model,
        step_kind=definition.step_kind,
        method_name=definition.driver_method,
        replay=ReplayPolicy(kind="fsq_command", alias=definition.fsq_action_name),
        strict=definition.strict,
        capture_evidence=definition.capture_evidence,
    )
    for definition in WINDOWS_ACTION_DEFINITIONS
    if definition.owner == "driver"
}
_windows_driver_capability = platform_driver_capability(
    platform="windows",
    backend=None,
    catalog=WINDOWS_DRIVER_ACTION_CATALOG,
)

MACOS_DRIVER_ACTION_CATALOG = {
    definition.fsq_action_name: CapabilityActionDefinition(
        action_name=definition.fsq_action_name,
        canonical_name=definition.driver_method,
        executor_kind="driver",
        owner=definition.owner,
        params_model=definition.params_model,
        step_kind=definition.step_kind,
        method_name=definition.driver_method,
        replay=ReplayPolicy(kind="fsq_command", alias=definition.fsq_action_name),
        strict=definition.strict,
        capture_evidence=definition.capture_evidence,
    )
    for definition in MACOS_ACTION_DEFINITIONS
    if definition.owner == "driver"
}
_macos_driver_capability = platform_driver_capability(
    platform="macos",
    backend=None,
    catalog=MACOS_DRIVER_ACTION_CATALOG,
)


def driver_tool(
    *,
    description: str,
    params_model: type[BaseModel] | None = None,
    fsq_action_name: str | None = None,
    strict: bool = True,
    capture_evidence: bool = False,
    metadata: dict[str, object] | None = None,
) -> Callable[[F], F]:
    def decorate(method: F) -> F:
        method_name = getattr(method, "__name__", None)
        aliases = [fsq_action_name] if fsq_action_name and fsq_action_name != method_name else []
        declaration_metadata = dict(metadata or {})
        if fsq_action_name is not None:
            declaration_metadata["fsq_action_name"] = fsq_action_name
        return driver_capability(
            name=method_name,
            description=description,
            params_model=params_model,
            aliases=aliases,
            replay=ReplayPolicy(kind="fsq_command", alias=fsq_action_name) if fsq_action_name else None,
            strict=strict,
            capture_evidence=capture_evidence,
            metadata=declaration_metadata,
        )(method)

    return decorate


def _android_driver_tool(
    fsq_action_name: str,
    *,
    description: str,
    strict: bool | None = None,
    capture_evidence: bool = False,
    metadata: dict[str, object] | None = None,
) -> Callable[[F], F]:
    return _android_driver_capability(
        fsq_action_name,
        description=description,
        strict=strict,
        capture_evidence=capture_evidence,
        metadata=metadata,
    )


def _web_driver_tool(
    fsq_action_name: str,
    *,
    description: str,
    strict: bool | None = None,
    capture_evidence: bool | None = None,
    metadata: dict[str, object] | None = None,
) -> Callable[[F], F]:
    return _web_driver_capability(
        fsq_action_name,
        description=description,
        strict=strict,
        capture_evidence=capture_evidence,
        metadata=metadata,
    )


def _windows_driver_tool(
    fsq_action_name: str,
    *,
    description: str,
    strict: bool | None = None,
    capture_evidence: bool | None = None,
    metadata: dict[str, object] | None = None,
) -> Callable[[F], F]:
    return _windows_driver_capability(
        fsq_action_name,
        description=description,
        strict=strict,
        capture_evidence=capture_evidence,
        metadata=metadata,
    )


def _macos_driver_tool(
    fsq_action_name: str,
    *,
    description: str,
    strict: bool | None = None,
    capture_evidence: bool | None = None,
    metadata: dict[str, object] | None = None,
) -> Callable[[F], F]:
    return _macos_driver_capability(
        fsq_action_name,
        description=description,
        strict=strict,
        capture_evidence=capture_evidence,
        metadata=metadata,
    )


def _discover_driver_function_schemas(
    driver: object,
    *,
    platform: HarnessPlatform,
    metadata: dict[str, object] | None = None,
) -> list[HarnessFunctionSchema]:
    schemas: list[HarnessFunctionSchema] = []
    for definition in _discover_driver_capability_definitions(driver, platform=platform, metadata=metadata):
        driver_method = _metadata_str(definition.metadata, "driver_method") or definition.name
        fsq_action_name = _metadata_str(definition.metadata, "fsq_action_name")
        schema_metadata = dict(definition.metadata)
        schema_metadata.update(
            {
                "capability_name": definition.name,
                "executor_kind": definition.executor_kind,
                "driver_method": driver_method,
                "owner": definition.owner,
                "step_kind": definition.step_kind,
                "replay": definition.replay.model_dump(mode="json") if definition.replay else None,
            }
        )
        if fsq_action_name is not None:
            schema_metadata["fsq_action_name"] = fsq_action_name
        schemas.append(
            HarnessFunctionSchema(
                name=definition.name,
                description=definition.description,
                params_json_schema=definition.params_json_schema,
                strict=definition.strict,
                platform=definition.platform or platform,
                driver_method=driver_method,
                fsq_action_name=fsq_action_name,
                capture_evidence=definition.capture_evidence,
                metadata=schema_metadata,
            )
        )
    return schemas


def _discover_driver_capability_definitions(
    driver: object,
    *,
    platform: HarnessPlatform,
    metadata: dict[str, object] | None = None,
) -> list[CapabilityDefinition]:
    definitions: list[CapabilityDefinition] = []
    for definition in discover_capability_definitions(driver, metadata=metadata):
        if definition.executor_kind != "driver":
            continue
        updates: dict[str, object] = {}
        if definition.platform is None:
            updates["platform"] = platform
        if definition.backend is None:
            backend = _metadata_str(definition.metadata, "backend")
            if backend is not None:
                updates["backend"] = backend
        definitions.append(definition.model_copy(update=updates) if updates else definition)
    return definitions


def _metadata_str(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) else None
