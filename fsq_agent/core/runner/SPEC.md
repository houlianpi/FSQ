# Module: core.runner

## Purpose

Own platform-neutral capability execution for one canonical step and ordered step sequences. Runner applies capability metadata, parameter validation, runtime-secret resolution, evidence policy, timing, sensitivity, result normalization, and teardown ordering without owning transports or concrete platforms.

## Dependencies

- `models`: canonical steps, capability definitions, events, results, evidence references, and execution settings.
- `capabilities`: resolved neutral declaration metadata only where registry construction requires it.
- `core.interfaces`: harness, capability-executor, observation, runtime-secret, evidence-recorder, and cancellation boundaries.

Runner must not import adapters, Application, Agent SDK types, concrete harnesses, concrete drivers, or report renderers.

## Public Interface

- `StepRunner`: executes one canonical capability invocation through public interfaces.
- `StepSequenceRunner`: executes ordered normal steps, stops on blocking failure, and always executes supplied teardown steps.

Both symbols are exported from `core.runner` and re-exported from `core` with identical object identity.

## Internal Structure

- `__init__.py`: public exports.
- `_runner.py`: single-step metadata-driven execution.
- `_sequence.py`: ordered sequence and teardown coordination.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: `StepRunner` and `StepSequenceRunner`.
- Internal modules: `_runner.py` and `_sequence.py`.
- Domain boundaries: capability execution policy and ordering only.
- Boundary models: public execution models come from `models`; collaborator protocols come from `core.interfaces`.
- Dependency direction: Execution depends on Runner; Runner depends on Interfaces; concrete implementations point inward to Interfaces.
- Rationale: execution coordinates validation, secrets, timing, evidence, and side effects, requiring Level 3 without a domain framework.

## Error Handling

Runner normalizes expected harness/backend failures into safe step results and events, preserves cancellation, and never exposes runtime-secret values. Registry, parameter, or unresolved-secret failures occur before the external invocation they protect.

## Current Invariants

- Capability metadata, not action-name branches, controls routing, replay metadata, timing, sensitivity, and evidence policy.
- Automatic evidence depends on step kind and normalized observation interfaces.
- Positive post-action delay occurs after invocation and before final after-action evidence without creating synthetic steps.
- Teardown steps remain eligible after normal-step failure.
