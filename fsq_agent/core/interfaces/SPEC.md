# Module: core.interfaces

## Purpose

Own public platform-neutral protocols and stable construction boundaries used by Execution, Runner, Agent, harnesses, and drivers. Interfaces invert platform and external-system dependencies without owning concrete automation behavior.

## Dependencies

- `models`: canonical invocation, result, observation, configuration, capability, and artifact boundary models.

Interfaces must not import adapters, Application, Agent SDK types, concrete harnesses, concrete drivers, platform backend libraries, or private modules from sibling Core packages.

## Public Interface

The package exports the approved protocols and factories used across module boundaries:

- `HarnessInterface`, `DriverObservationInterface`, and `AIAssertionEvaluatorProtocol`.
- `AndroidDriverInterface`, `WebDriverInterface`, `WindowsDriverInterface`, and `MacOSDriverInterface`.
- capability executor, runtime-secret, cancellation, observation, and evidence sink protocols required by Runner and Execution.
- `DriverFactory` and `HarnessFactory` as stable composition boundaries while their concrete selection implementations remain private and move outward in later platform batches.

`core` and the existing `core.harness` compatibility surface re-export these same objects. Concrete harness and backend driver classes are not public.

## Internal Structure

- `__init__.py`: public protocol and factory exports.
- Private protocol modules group execution, observation, driver, harness, secret, cancellation, and evidence boundaries without platform implementation code.

## Python Architecture

- Architecture level: Level 2 Simple Package.
- Public API: named protocols and approved factories exported through `__init__.py`.
- Internal modules: private protocol definitions and factory implementation forwarding.
- Domain boundaries: interface definitions and stable construction contracts only.
- Boundary models: shared values come from `models`; no duplicate DTO hierarchy is introduced.
- Dependency direction: Runner, Evidence, Execution, Agent, harnesses, and drivers depend on Interfaces; Interfaces depend only on shared models.
- Rationale: focused protocols provide dependency inversion; Clean Architecture or a DI container would add no value.

## Error Handling

Protocols preserve normalized safe failure and cancellation contracts. Optional backend absence must remain a runtime unsupported/unavailable outcome rather than an import-time failure.

## Current Invariants

- Public interfaces expose no concrete platform/backend types.
- Factory selection remains lazy for optional backend dependencies.
- Re-exports preserve exact class/protocol identity and do not duplicate mutable state.
- No service locator or dependency-injection container exists.
