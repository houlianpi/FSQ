# Module: execution

## Purpose

Coordinate complete dynamic and deterministic Case execution independently of CLI or HTTP transports. The module owns operation-level ordering, Workspace-wide Run identity allocation, Run lifecycle and ownership, freezing execution conclusions, Case lifecycle semantics, safe source provenance, and conversion of normalized execution facts into Run-local candidate Case recordings. It does not own shared model definitions, transport state, Case parsing, capability execution, platform automation, provider construction, evidence storage formats, report formats, or historical Run queries.

## Dependencies

- `agent`: Runs SDK-neutral dynamic Goal/reference tasks and returns normalized task results and events.
- `case_dsl`: Loads, validates, normalizes, serializes, and adapts Cases through public Case DSL contracts.
- `core`: Executes canonical steps, records evidence, resolves runtime secrets, and supplies harness interfaces.
- `models`: Owns shared task, Case, Run metadata, lifecycle, provenance, runner, evidence, event, and result contracts.
- `config`: Supplies validated lifecycle settings and contained Workspace Case paths.
- `report`: Generates reports from normalized execution facts.

Execution may receive provider-backed evaluators, registries, harnesses, cancellation callbacks, event sinks, and factories through explicit inputs. It must not import `adapters`, `application`, CLI/HTTP frameworks, concrete private drivers, or adapter-private modules.

## Public Interface

The package exports its supported services and result contracts through `execution.__init__`:

- `RunLifecycleService`: Shared Run allocation, owner heartbeat and read-only liveness inspection, source snapshotting, immutable execution-result freeze, processing finalization, and lineage-append boundary. Application and adapters supply validated inputs and collaborators; Agent receives a `models.RunExecutionContext` and returns a `models.DynamicAgentOutcome` without owning lifecycle persistence.
- `RunLifecycleService.read_evidence`: read-only facade over public `EvidenceRecorder.recover_bundle`, returning the normalized `models.EvidenceBundle` for Application and report coordination. Core Evidence is the only journal/checkpoint recovery implementation; Execution does not duplicate it, and Report receives the recovered value rather than replaying the journal.
- `DynamicExecutionService`: Coordinates one dynamic Goal or raw-reference task through the supplied Agent runtime, event sink, cancellation boundary, report generation, and optional recording policy.
- `DeterministicExecutionService`: Coordinates one parsed deterministic Case through the supplied registry, runtime-secret store, harness, Core runners, evidence recorder, cancellation boundary, and report generator.
- `LifecycleExecutionService`: Collects contained nested Cases and executes configuration-level and Case-level start/complete hooks plus the main Case with deterministic ordering and recursion protection.
- `RecordingService`: Converts normalized replayable capability results and safe events into a Run-local candidate through the shared Case DSL validator and serializer, and optionally publishes it to a supplied contained destination. It accepts an optional explicit Case name. `RecordingResult` exposes candidate path, stable Case name, publication outcome, draft state, and safe diagnostics. Mutable recorder state remains private.
- `publish_recorded_case`: Public contained publication boundary used by recording and Application save orchestration. It validates and serializes the candidate with the selected stable name, preserves the source, reuses identical destination bytes, and reports a conflict for differing existing bytes. It never silently replaces a different Case.
- `DynamicExecutionRequest`, `DynamicExecutionResult`, `DeterministicExecutionRequest`, `DeterministicExecutionResult`, `LifecycleExecutionRequest`, `LifecycleExecutionResult`, and `RecordingResult`: immutable execution-boundary contracts with no transport types.
- Run lifecycle operations allocate a collision-resistant Workspace-wide ID, atomically create its direct platform directory, write `fsq.run/v2` metadata before actions, advance monotonic active states, freeze execution facts, and atomically finalize one immutable terminal state. Allocation checks every configured platform and retries a collision at most five times. Existing `allocate_run`, `load_run_metadata`, `transition_run`, and `write_run_metadata` exports remain supported through the same lifecycle authority.
- `RunArtifactIndex`, `RunMetadata`, `RunResultSummary`, `RunRuntime`, `RunSource`, and `RunStepCounts` remain exported for compatibility and reference the canonical `models` objects rather than defining another model hierarchy.

Public services accept already resolved Workspace/platform settings and explicit collaborators. They return normalized results and safe artifact references; adapters alone map them to CLI output or HTTP/SSE state. Agent receives an allocated execution context and emits runtime and verification outcomes; Agent, Application, and adapters do not independently advance Run lifecycle or derive terminal verdicts from rendered reports.

Execution services are imported from `fsq_agent.execution`. The existing `run_fsq_core_case`, `run_strict_fsq_core_case`, `collect_strict_lifecycle_cases`, and `run_strict_lifecycle_case` compatibility operations use the same execution and evidence authorities. Package-root `_strict_lifecycle` and `_strict_case_recording` compatibility modules are absent.

## Internal Structure

- `__init__.py`: Public execution exports.
- `dynamic.py`: Dynamic Goal/reference coordination and normalized result assembly.
- `deterministic.py`: Strict Case preparation and ordered Core execution coordination.
- `lifecycle.py`: Lifecycle Case collection, contained nested execution, hook ordering, teardown, recursion, shell-hook, and cancellation semantics.
- `recording.py`: Replay-policy-driven candidate Case construction, private mutable recording state, validation, atomic Run-local persistence, and optional contained publication.
- `runs.py`: Public Run allocation, owner/liveness inspection, immutable execution-result persistence, source provenance, lineage append, and metadata lifecycle boundary.
- Private `_*.py` files may hold shared implementation details and are not imported across package boundaries.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: the execution services, `RunLifecycleService`, compatible Run allocation/lifecycle operations, and their immutable Request/Result contracts and shared model re-exports through `execution.__init__`.
- Internal modules: private helpers are confined to this package; the four named service modules are public resource boundaries.
- Domain boundaries: Execution owns operation-level orchestration, Run identity/metadata lifecycle, frozen conclusions, owner/liveness facts, and Case lifecycle/recording/provenance policy. Agent owns dynamic planning and verification; Case DSL owns Case syntax; Core owns individual capability execution and evidence mechanics; Application owns historical query; Report owns report rendering; adapters own presentation and task-state transport.
- Boundary models: operation Request/Result records wrap canonical `models` values and safe path/artifact references without Click, HTTP, SSE, or frontend values. Shared Run model compatibility exports preserve object identity.
- Dependency direction: adapters and Application may depend on Execution; Execution depends only on inward public APIs and injected collaborators; inward modules never import Execution unless the root architecture diagram explicitly permits it.
- Rationale: complete runs coordinate multiple side-effecting authorities, cancellation, lifecycle phases, evidence, reports, and recording, so Level 3 is warranted without Repository, Unit of Work, Clean Architecture, or DDD layers.

## Error Handling

Validation, path containment, registry resolution, and runtime-secret preflight failures occur before external Case actions. Lifecycle start failures skip remaining start/main work according to lifecycle policy while completion hooks and teardown still run. Cancellation is checked at operation and nested-Case boundaries and is propagated without being converted to success. Recording failures never change the completed dynamic execution status and expose only bounded, secret-safe warnings. Shell output, backend output, runtime-secret values, tracebacks, and hidden model reasoning are not included in public results.

Initial metadata, required source snapshot, or durable step-start failure prevents the external actions that depend on it. Cleanup removes only an empty request-created directory. Failure to freeze the execution result or finalize metadata preserves all produced evidence and is an infrastructure failure. An unpersisted conclusion is never presented as durably complete.

Active status transitions are `preparing` to `running` to `finalizing`; terminal states remain `success`, `failed`, `inconclusive`, `cancelled`, and `error` and cannot be rewritten by ordinary execution. Run status is the operation lifecycle summary; execution, verification, evidence health, and processing have separate typed conclusions. User cancellation is preserved as cancellation across CLI, Control Plane, dynamic, and strict paths. Evidence-policy failure remains blocking, while report, recording, publication, suggestion, and export errors do not turn a completed execution into a different execution verdict.

Metadata, frozen results, and source snapshots use same-directory temporary files, flush, `fsync`, and atomic replacement. Run metadata never contains secrets, unrestricted exceptions, hidden reasoning, or absolute Workspace paths. Historical `fsq.run/v1` metadata remains readable without in-place migration; missing v2 evidence and provenance remain unknown rather than being synthesized.

## Run Facts And Finalization

Execution allocates one Run and records the safe source context before actions. Dynamic and deterministic services share the same owner, cancellation, result-freeze, and finalization boundary. Strict execution resolves the root Case, nested Cases, lifecycle hooks, and allowed effective settings before constructing the execution inventory. The inventory assigns stable `source_step_id` values and occurrence-aware invocation paths; each actual attempt receives a Run-unique `step_execution_id` before starting. New result `step_id` is the compatibility alias for execution identity. Unattempted leaves have no fabricated execution ID. Repeated nested Case invocations remain distinct even when their source paths and step indexes are identical.

Strict inventory contains the planned executable leaves and structural hook containers. Each logical leaf invocation is identified by stable source identity plus invocation path and has an executed, explicitly skipped, or unresolved outcome and a safe reason; skipped dependent work references the blocking execution identity when known. Attempt records each have their own unique `step_execution_id` and belong to one logical leaf invocation. Summary total and outcome counts use logical leaf invocations as their shared denominator; `attempt_count` is separate, so retry does not add another planned test. Hook containers do not add a second action count for their children. Dynamic key-action plans, SDK summaries, and synthetic runtime records are not real capability steps. Summary counts, failed-step identity, and durations derive from the same normalized inventory and results for every entry point, with null and a reason for unknown values rather than zero-filled guesses.

After execution and required verification reach an outcome, Execution atomically writes `fsq.execution-result/v1` in `execution-result.json` before recording, report generation, or optional suggestion analysis. The document freezes execution and verification conclusions, evidence-policy disposition, normalized step accounting, and safe failure facts. Subsequent processing consumes this document and persisted evidence; it cannot invoke actions to improve or overwrite the completed result.

Operation verdicts follow the selected mode. Strict uses blocking leaf outcomes and required evidence, while Explore preserves the goal-verification policy and may complete successfully after recoverable failed attempts whose facts remain visible. Fatal execution failure and cancellation retain their precedence; required evidence remains fail-closed. An action-only success with no requested verification records verification as `not_requested` or `not_applicable` and makes no business-verification claim. Zero executed actions without a valid verification produces an inconclusive conclusion rather than a fabricated pass.

Run-local recording and initial reports finish, fail, or explicitly become unavailable before `run.json` reaches terminal state. Final metadata includes safe processing outcomes and the contained artifact index actually produced, including the frozen result and candidate Case where present. Processing failure is visible alongside the preserved execution verdict. Later analysis, export, publication, and Case-save outcomes are independent derived artifacts or lineage entries and cannot rewrite terminal metadata or the frozen result. An execution result with unfinished metadata remains distinguishable from a Run whose execution itself never completed.

`fsq.run/v2` preserves the existing identity, source, result, runtime, and artifacts fields and adds an `execution_result` reference plus evidence, processing, provenance, and lineage summaries. `result` retains summary, counts, and failed-step identity consistent with the frozen conclusion. Compatibility `TaskResult.report` remains a required `ReportArtifact`; when rich report generation fails, it may reference the already frozen minimal `execution-result.json`, while report processing still records failure. A processing error may be returned separately with a safe Run ID and preserved artifact references without changing the execution conclusion.

## Provenance And Ownership

Run provenance records the exact root and nested Case inputs, an explicit allowlist projection of effective non-secret configuration, producer/schema versions, and hashes of the safe persisted representations. Required input snapshots are captured before actions. Runtime-secret values, credentials, authorization data, and other sensitive values are neither persisted nor hashed; references may contain safe secret names and presence only. If sensitive source content must be omitted, provenance explicitly records the omission and does not claim a byte-identical original snapshot.

Recording relates Explore Run, candidate Case content identity, published or saved Case content identity, and Strict replay source. New generated YAML contains no Run provenance; `recording.json` and lineage retain source Run/Task identity and command-to-execution mapping. Readers and formatters may preserve existing `properties.recording` user data as legacy input, but recording does not add it. Saving or publishing after a Run is terminal appends a separately versioned lineage record rather than changing its terminal result. A replay link identifies the source content actually executed; filename similarity is not provenance.

The Run owner uses a separate local record with process identity, process-start identity, and heartbeat, scoped to the allocated Run. Execution exposes read-only liveness facts to Application; it verifies owner identity before treating a live process as this Run's owner. `alive`, confirmed `dead`, and `unknown` are distinct observations. A missing, stale, inaccessible, or unsupported owner check alone is not proof of death. Read-only inspection never converts every active status to `interrupted`, modifies historical metadata, resumes actions, or finalizes a Run.

## Verification Scope

- Dynamic, deterministic, lifecycle, and recording behavior is identical across CLI and Control Plane for equivalent inputs and collaborators.
- Lifecycle verification covers configuration and Case hook ordering, repeated actions, nested Cases, recursion, containment, start failure, completion hooks, teardown, cancellation, and platform shell selection.
- Recording verification covers replay-policy filtering, authored aliases, normalized safe params, browser lifecycle facts, runtime-secret exclusion, validation, atomic Run-local writes, optional publication, and failure isolation.
- Compatibility verification proves canonical and package-root lifecycle symbols share identity and no adapter contains an independent lifecycle engine or recorder. Recording verification exercises the public `RecordingService` boundary rather than importing its private recorder implementation.

## Current Invariants

- Dynamic and deterministic execution semantics are transport-neutral and have one canonical implementation.
- Execution is the single writer of authoritative Run lifecycle and frozen execution conclusions; rendered reports and transport task state are projections.
- Evidence journaling and checkpoint formats belong to Core Evidence; Execution supplies context and inventory and consumes the same durable facts for dynamic and strict execution.
- Run query, aggregation, filtering, historical inference, and HTML generation remain outside Execution. All execution entry points use the same Execution-owned Run allocation and metadata lifecycle rather than constructing IDs in adapters.
- Lifecycle hooks are metadata around a Case, not synthetic Case commands. Authored order is preserved, nested `runCase` paths remain contained below the selected platform Case root, and recursive chains fail before infinite execution.
- Trailing teardown steps and completion hooks remain eligible after an earlier blocking normal-step failure.
- Recording consumes final normalized capability results rather than low-level progress events as execution truth. It records only replayable non-observation facts allowed by capability metadata and never invents setup, cleanup, or browser lifecycle commands.
- Recording validation proves Case syntax and capability compatibility, not replay success. A Strict replay outcome requires its own execution evidence and provenance link.
- Runtime-secret values, sensitive raw arguments, subprocess output, and hidden reasoning are never persisted into generated Cases or returned in safe execution summaries.
- Adapters depend on `RecordingService` and `RecordingResult`; they do not import, inject, or expose the private mutable recording state or function-style recorder implementation.
- Adapters may supply transport-specific event sinks, cancellation callbacks, and progress recorders, but they do not determine lifecycle order, replayability, evidence policy, or recording content.

## Stable Case Identity And Publication

- Explicit names are safe suffix-free basenames using the same policy for CLI creation and Control Plane save. Without a name, a Goal recording uses `case-` plus the full lowercase SHA-256 of compact UTF-8 JSON `[platform, normalized_goal]`, with Unicode preserved. Goal normalization collapses whitespace as in Application Case creation; identity contains no Run ID, timestamp, random value, or host path.
- Goal descriptions use normalized Goal text with Task name as the blank-reference fallback. Non-Goal recording without an explicit name uses `case-` plus the full lowercase SHA-256 of compact UTF-8 JSON `[platform, task.name, task.description]`, with Unicode preserved, and uses the stable Task description without embedding a Run ID. Existing-source suggestion candidates preserve the source Case identity.
- Both successful and draft recordings use the same Case content rules. `recording.json` retains source Run/Task identity, status, draft state, required secret names, warnings, skipped calls, validation result, stable Case name, and publication outcome; these recording facts are not injected into newly generated YAML.
- Publication outcomes distinguish not requested, created, unchanged, conflict, and failed. Existing identical bytes are a successful no-op. Different contents or a competing different publication leave the destination intact, preserve the candidate, and return `case.publication_conflict`. Conflict does not change the completed execution result. Creation must be atomic and must not clobber a destination created concurrently.
- Candidate validation precedes atomic Run-local persistence. Invalid candidate data is reported in recording diagnostics without publishing invalid YAML. Recording uses safe replay parameters, retains actual action order, and never reconstructs parameters from secret-resolved values.
- Stable names and conflicts apply across CLI publication and explicit Control Plane saves. Explicit save changes only the destination Case name before shared serialization and leaves Run-local candidate bytes unchanged.
