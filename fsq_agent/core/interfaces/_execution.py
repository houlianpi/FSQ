# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Protocol, runtime_checkable

from fsq_agent.models import CapabilityDefinition, EvidenceBundle, RunnerEvent, RunnerStepResult


@runtime_checkable
class CapabilityRegistryInterface(Protocol):
    def resolve(self, name: str) -> CapabilityDefinition | None: ...


@runtime_checkable
class RuntimeSecretResolver(Protocol):
    def resolve(self, name: str) -> str: ...


@runtime_checkable
class EvidenceSink(Protocol):
    def record_event(self, event: RunnerEvent) -> None: ...

    def record_step_result(self, result: RunnerStepResult) -> None: ...

    def build_bundle(self) -> EvidenceBundle: ...


@runtime_checkable
class CancellationCheck(Protocol):
    def __call__(self) -> None: ...
