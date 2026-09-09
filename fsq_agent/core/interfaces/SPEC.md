# Module: core.interfaces

## Purpose

Own public platform-neutral protocols and stable construction boundaries used by Execution, Runner, Agent, harnesses, and drivers. Interfaces invert platform and external-system dependencies without owning concrete automation behavior.

## Dependencies

- `models`: canonical invocation, result, observation, configuration, capability, and artifact boundary models.

Protocol-definition modules depend on Models only and must not import adapters, Application, Agent SDK types, concrete harnesses/drivers, backend libraries, or sibling Core implementations. The public factory composition boundary is the following named exception; it does not extend to protocol definitions.

`_factories.py` owns the compatibility `DriverFactory` and `HarnessFactory` composition wrappers. Only this file may lazily import `drivers._factory._DriverFactoryImplementation` and `harnesses._factory._HarnessFactoryImplementation`, and use `core.evidence.ArtifactStore` for type annotation. These private implementation selectors are explicit cross-module composition exceptions, not public concrete driver or harness classes. Drivers and Harnesses consume protocol-definition modules and never import this factory wrapper. Construction remains lazy and does not start a browser, device, or application. The exception preserves the documented zero-argument factory construction and Core/Interfaces export identity; it is revisited if factory ownership or another implementation selector is introduced.

## Public Interface

The package exports the approved protocols and factories used across module boundaries:

- `HarnessInterface`, `DriverObservationInterface`, and `AIAssertionEvaluatorProtocol`.
- `AndroidDriverInterface`, `WebDriverInterface`, `WindowsDriverInterface`, and `MacOSDriverInterface`.
- `CapabilityRegistryInterface`, `RuntimeSecretResolver`, `CancellationCheck`, and `EvidenceSink` protocols required by Runner and Execution. Existing `EvidenceSink.record_event`, `record_step_result`, and `build_bundle` calls remain supported.
- `EvidenceJournalSink`: synchronous durable acknowledgement boundary for incremental step, phase, action-result, artifact-outcome, and completion facts using canonical `models` values. Core Runner depends on this protocol; Core Evidence implements persistence and checkpoint reconstruction. Sink failure is explicit and cannot be silently converted into a successful acknowledgement.
- `DriverFactory` and `HarnessFactory` as stable composition boundaries while their concrete selection implementations remain private.

`core` re-exports these same objects. The existing `core.harness` compatibility surface preserves its supported protocol and factory object identities. Concrete harness and backend driver classes are not public.

## Internal Structure

- `__init__.py`: public protocol and factory exports.
- Private protocol modules group execution, observation, driver, harness, secret, cancellation, and evidence boundaries without platform implementation code.

## Python Architecture

- Architecture level: Level 2 Simple Package.
- Public API: named protocols and approved factories exported through `__init__.py`.
- Internal modules: private protocol definitions and factory implementation forwarding.
- Domain boundaries: interface definitions and stable construction contracts only.
- Boundary models: shared values come from `models`; no duplicate DTO hierarchy is introduced.
- Dependency direction: Runner, Evidence, Execution, Agent, Harnesses, and Drivers depend on the Models-only protocol boundary. The separate named factory composition boundary points outward to the two private implementation selectors and uses Evidence only for its artifact-store annotation. Concrete implementations never depend back on the factory wrapper.
- Rationale: focused protocols provide dependency inversion; Clean Architecture or a DI container would add no value.

## Error Handling

Protocols preserve normalized safe failure and cancellation contracts. Optional backend absence must remain a runtime unsupported/unavailable outcome rather than an import-time failure.

## Current Invariants

- Public interfaces expose no concrete platform/backend types.
- Factory selection remains lazy for optional backend dependencies.
- Re-exports preserve exact class/protocol identity and do not duplicate mutable state.
- No service locator or dependency-injection container exists.
- Journal contracts carry stable source identity, unique execution identity, measured timing, safe action outcomes, and artifact availability without containing filesystem implementation, SDK events, or report structures. A `models.RunExecutionContext` contains safe allocated Run values; live sinks, cancellation callbacks, identity allocators, and owner operations remain explicit collaborators rather than serialized context data.
- Evidence delivery is separate from presentation. A transport sink or SDK event mapper cannot manufacture a durable acknowledgement or replace a Core action outcome.
