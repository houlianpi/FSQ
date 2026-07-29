# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import time

from pydantic import ValidationError

from fsq_agent.capabilities import capability, discover_capability_definitions
from fsq_agent.models import (
    CapabilityDefinition,
    CapabilityExecutionResult,
    ExecutableStep,
    HarnessActionResult,
    HarnessFunctionSchema,
    HarnessPlatform,
    ReplayPolicy,
    WaitMsParams,
)


class CommonPlatformTools:
    def __init__(self, *, platform: HarnessPlatform = "android") -> None:
        self.platform = platform

    @classmethod
    def capability_definitions(cls) -> list[CapabilityDefinition]:
        capabilities = {definition.name: definition for definition in discover_capability_definitions(cls)}
        return [capabilities[name] for name in ("wait_ms",) if name in capabilities]

    @capability(
        name="wait_ms",
        description="Wait without touching or changing platform state.",
        executor_kind="common",
        owner="common",
        params_model=WaitMsParams,
        replay=ReplayPolicy(kind="fsq_command", alias="waitMs"),
    )
    def _wait_ms_result(self, params: WaitMsParams) -> CapabilityExecutionResult:
        started = time.perf_counter()
        time.sleep(params.duration_ms / 1000)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return CapabilityExecutionResult(
            capability_name="wait_ms",
            executor_kind="common",
            status="passed",
            output={
                "type": "wait_completed",
                "duration_ms": params.duration_ms,
                "elapsed_ms": elapsed_ms,
                "reason": params.reason,
            },
            duration_ms=elapsed_ms,
            replay=ReplayPolicy(kind="fsq_command", alias="waitMs"),
            safe_replay_params={"duration_ms": params.duration_ms, "reason": params.reason},
            metadata={"duration_ms": params.duration_ms, "reason": params.reason},
        )

    def invoke_common_tool(self, step: ExecutableStep) -> HarnessActionResult:
        capability_definition = self.common_capability_for(step.action_name)
        if capability_definition is None:
            return HarnessActionResult(
                status="failed",
                action_name=step.action_name,
                failure_category="configuration_error",
                error_message=f"Unsupported common action: {step.action_name}",
            )
        try:
            params = capability_definition.params_model.model_validate(step.params)
        except ValidationError as exc:
            return HarnessActionResult(
                status="failed",
                action_name=step.action_name,
                failure_category="configuration_error",
                error_message=f"Invalid common parameters for {step.action_name}.",
                metadata={"validation_errors": exc.errors(include_url=False, include_context=False)},
            )
        method = getattr(self, f"_{capability_definition.name}_result")
        result = method(params)
        status = "passed" if result.status == "passed" else "failed"
        metadata = dict(result.metadata)
        metadata.update(
            {
                "capability_name": result.capability_name,
                "executor_kind": result.executor_kind,
                "sensitivity": result.sensitivity,
            }
        )
        if result.replay is not None:
            metadata["replay"] = result.replay.model_dump(mode="json")
        if result.safe_replay_params:
            metadata["safe_replay_params"] = dict(result.safe_replay_params)
        if result.output is not None and not result.sensitivity:
            metadata["common_output"] = result.output
        if result.sensitivity:
            metadata["common_output_redacted"] = True
        return HarnessActionResult(
            status=status,
            action_name=step.action_name,
            output=result.output,
            failure_category=result.failure_category,
            error_message=result.error_message,
            metadata=metadata,
        )

    def common_action_space(self) -> list[HarnessFunctionSchema]:
        return [self._common_schema_from_capability(definition) for definition in self.capability_definitions()]

    def common_capability_for(self, name_or_alias: str) -> CapabilityDefinition | None:
        for definition in self.capability_definitions():
            if definition.name == name_or_alias or definition.fsq_command_alias == name_or_alias:
                return definition
        return None

    def _common_schema_from_capability(self, definition: CapabilityDefinition) -> HarnessFunctionSchema:
        metadata = definition.safe_metadata()
        return HarnessFunctionSchema(
            name=definition.name,
            description=definition.description,
            params_json_schema=definition.params_json_schema,
            platform=self.platform,
            driver_method=definition.name,
            fsq_action_name=definition.replay.alias if definition.replay and definition.replay.kind == "fsq_command" else None,
            metadata=metadata,
        )
