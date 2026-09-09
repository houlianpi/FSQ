# Module: core.runner

## Purpose

Own platform-neutral capability execution for one canonical step and ordered step sequences. Runner applies capability metadata, parameter validation, runtime-secret resolution, evidence policy, measured timing, sensitivity, result normalization, and teardown ordering. It emits durable execution facts through public sink interfaces without owning filesystem formats, Run lifecycle, transports, or concrete platforms.

## Dependencies

- `models`: canonical steps, capability definitions, events, results, evidence references, and execution settings.
- `capabilities`: resolved neutral declaration metadata only where registry construction requires it.
- `core.interfaces`: harness, capability-executor, observation, runtime-secret, evidence-recorder, and cancellation boundaries.

Runner must not import adapters, Application, Agent SDK types, concrete harnesses, concrete drivers, or report renderers.

## Public Interface

- `StepRunner`: executes one canonical capability invocation through public interfaces and publishes step start, phase boundaries, action result, artifact outcome, and final step result to the supplied evidence journal sink as they occur. Its existing `run_step`, `events`, and `last_capability_execution_result` surfaces remain supported; buffered events are a compatibility projection, not the durable evidence authority.
- `StepSequenceRunner`: executes ordered normal steps, stops on blocking failure, records explicit outcomes for unexecuted planned leaves, and preserves supplied teardown eligibility. Its existing `run_steps` call remains supported.

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

Runner normalizes prepare, invoke, settle, finalize, and capture failures into safe phase and step facts, preserves cancellation, and never exposes runtime-secret values. Registry, parameter, or unresolved-secret failures occur before the external invocation they protect. A durable step-start acknowledgement precedes external invocation; failure to persist required execution facts is an infrastructure failure and blocks dependent work. The last successfully persisted state remains usable when subsequent persistence fails.

Action failure is the primary execution failure. Capture or persistence errors remain separate evidence errors and never overwrite the original action category, message, or assertion verdict. Required evidence failure continues to prevent a successful step under the existing fail-closed policy; when evidence failure is the only failure, the compatibility failure category is `artifact_error`. Independent screenshot and UI snapshot capture outcomes remain visible even when one capture fails.

Cancellation, an earlier normal-step failure, and teardown failure have distinct records. Teardown and completion work retain their execution-policy eligibility; failure in one teardown does not erase the original failure or already persisted evidence. A process interruption without an acknowledged result is unknown, not a manufactured passed, failed, or skipped result.

## Current Invariants

- Capability metadata, not action-name branches, controls routing, replay metadata, timing, sensitivity, and evidence policy.
- Automatic evidence depends on step kind and normalized observation interfaces.
- Every invocation carries a stable `source_step_id` and a Run-unique `step_execution_id` allocated from its invocation occurrence and attempt. New result `step_id` values alias `step_execution_id`; repeated nested Cases and repeated actions never reuse execution identity. Runner does not infer identity from a display label or artifact filename.
- Strict planned logical leaf invocations retain explicit executed, skipped, or unresolved outcomes and safe reasons, including the blocking execution identity when known. Each attempt belongs to its source-plus-invocation-path leaf and has a separate `step_execution_id`. Hook containers, dynamic key-action plans, and SDK summaries are not counted as executed capabilities. Attempt counts remain separate from logical leaf outcome totals.
- Step and phase boundaries carry measured UTC timestamps; elapsed durations use a monotonic clock. Exclusive `prepare`, `invoke`, `settle`, and `finalize` durations do not overlap. Capture durations may be displayed as nested components but are not added to their containing phase a second time. Missing measurements use null with a reason; zero means a measured zero.
- Positive post-action delay is represented by the measured `settle` phase after invocation and before final evidence, while retaining configured-delay metadata. It creates no synthetic wait command, evidence step, or replay result.
- Runner adds no automatic retries; when an execution policy requests another attempt, its execution identity and outcome remain separate.
- Teardown steps remain eligible after normal-step failure.
