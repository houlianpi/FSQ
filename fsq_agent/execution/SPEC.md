# Module: execution

## Purpose

Coordinate complete dynamic and deterministic Case execution independently of CLI or HTTP transports. The module owns operation-level execution ordering, Workspace-wide Run identity allocation, authoritative Run metadata lifecycle, Case lifecycle semantics, and conversion of normalized execution facts into Run-local candidate Case recordings. It does not own transport state, Case parsing, capability execution, platform automation, provider construction, evidence storage formats, report formats, or historical Run queries.

## Dependencies

- `agent`: Runs SDK-neutral dynamic Goal/reference tasks and returns normalized task results and events.
- `case_dsl`: Loads and adapts deterministic Case input through its public Case DSL contracts.
- `core`: Executes canonical steps, records evidence, resolves runtime secrets, and supplies harness interfaces.
- `models`: Supplies task, Case, lifecycle, runner, evidence, event, and result contracts.
- `config`: Supplies validated lifecycle settings and contained Workspace Case paths.
- `report`: Generates reports from normalized execution facts.

Execution may receive provider-backed evaluators, registries, harnesses, cancellation callbacks, event sinks, and factories through explicit inputs. It must not import `adapters`, `application`, CLI/HTTP frameworks, concrete private drivers, or adapter-private modules.

## Public Interface

The package exports its supported services and result contracts through `execution.__init__`:

- `DynamicExecutionService`: Coordinates one dynamic Goal or raw-reference task through the supplied Agent runtime, event sink, cancellation boundary, report generation, and optional recording policy.
- `DeterministicExecutionService`: Coordinates one parsed deterministic Case through the supplied registry, runtime-secret store, harness, Core runners, evidence recorder, cancellation boundary, and report generator.
- `LifecycleExecutionService`: Collects contained nested Cases and executes configuration-level and Case-level start/complete hooks plus the main Case with deterministic ordering and recursion protection.
- `RecordingService`: Converts normalized replayable capability results and persisted safe events into one Run-local candidate `*.fsq.yaml` recording and optionally publishes a validated Goal recording to an explicitly supplied contained destination.
- `DynamicExecutionRequest`, `DynamicExecutionResult`, `DeterministicExecutionRequest`, `DeterministicExecutionResult`, `LifecycleExecutionRequest`, `LifecycleExecutionResult`, and `RecordingResult`: immutable execution-boundary contracts with no transport types.
- Run lifecycle operations allocate a collision-resistant Workspace-wide ID, atomically create its direct platform directory, write `fsq.run/v1` metadata before actions, advance monotonic active states, and atomically finalize one immutable terminal state. Allocation checks every configured platform and retries a collision at most five times.

Public services accept already resolved Workspace/platform settings and explicit collaborators. They return normalized results and safe artifact references; adapters alone map them to CLI output, HTTP/SSE state, or Playground responses.

Execution services are imported from `fsq_agent.execution`. Package-root `_strict_lifecycle` and `_strict_case_recording` compatibility modules are absent.

## Internal Structure

- `__init__.py`: Public execution exports.
- `dynamic.py`: Dynamic Goal/reference coordination and normalized result assembly.
- `deterministic.py`: Strict Case preparation and ordered Core execution coordination.
- `lifecycle.py`: Lifecycle Case collection, contained nested execution, hook ordering, teardown, recursion, shell-hook, and cancellation semantics.
- `recording.py`: Replay-policy-driven candidate Case construction, validation, atomic Run-local persistence, and optional contained publication.
- `runs.py`: Public Run allocation and metadata lifecycle boundary.
- Private `_*.py` files may hold shared implementation details and are not imported across package boundaries.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: the four execution services, Run allocation/lifecycle operations, and their immutable Request/Result/metadata contracts exported from `execution.__init__`.
- Internal modules: private helpers are confined to this package; the four named service modules are public resource boundaries.
- Domain boundaries: Execution owns operation-level orchestration, Run identity/metadata lifecycle, and Case lifecycle/recording policy. Agent owns dynamic planning and verification; Case DSL owns Case syntax; Core owns individual capability execution and evidence mechanics; Application owns historical query; Report owns report rendering; adapters own presentation and task-state transport.
- Boundary models: execution Request/Result records wrap public shared models and safe path/artifact references without Click, HTTP, SSE, or frontend values.
- Dependency direction: adapters and Application may depend on Execution; Execution depends only on inward public APIs and injected collaborators; inward modules never import Execution unless the root architecture diagram explicitly permits it.
- Rationale: complete runs coordinate multiple side-effecting authorities, cancellation, lifecycle phases, evidence, reports, and recording, so Level 3 is warranted without Repository, Unit of Work, Clean Architecture, or DDD layers.

## Error Handling

Validation, path containment, registry resolution, and runtime-secret preflight failures occur before external Case actions. Lifecycle start failures skip remaining start/main work according to lifecycle policy while completion hooks and teardown still run. Cancellation is checked at operation and nested-Case boundaries and is propagated without being converted to success. Recording failures never change the completed dynamic execution status and expose only bounded, secret-safe warnings. Shell output, backend output, runtime-secret values, tracebacks, and hidden model reasoning are not included in public results.

Initial metadata failure prevents external actions and removes only an empty request-created directory. Final metadata failure preserves produced evidence and is an infrastructure failure. Active status transitions are `preparing` to `running` to `finalizing`; terminal states are `success`, `failed`, `inconclusive`, `cancelled`, and `error` and cannot be rewritten by ordinary execution. Metadata writes use same-directory temporary files, flush, `fsync`, and atomic replacement. Run metadata never contains secrets, unrestricted exceptions, hidden reasoning, or absolute Workspace paths.

## Verification Scope

- Dynamic, deterministic, lifecycle, and recording behavior is identical across CLI, Control Plane, and Playground for equivalent inputs and collaborators.
- Lifecycle verification covers configuration and Case hook ordering, repeated actions, nested Cases, recursion, containment, start failure, completion hooks, teardown, cancellation, and platform shell selection.
- Recording verification covers replay-policy filtering, authored aliases, normalized safe params, browser lifecycle facts, runtime-secret exclusion, validation, atomic Run-local writes, optional publication, and failure isolation.
- Compatibility verification proves canonical and package-root lifecycle/recording symbols share identity and no adapter contains an independent lifecycle engine or recorder.

## Current Invariants

- Dynamic and deterministic execution semantics are transport-neutral and have one canonical implementation.
- Run query, aggregation, filtering, historical inference, and HTML generation remain outside Execution. All execution entry points use the same Execution-owned Run allocation and metadata lifecycle rather than constructing IDs in adapters.
- Lifecycle hooks are metadata around a Case, not synthetic Case commands. Authored order is preserved, nested `runCase` paths remain contained below the selected platform Case root, and recursive chains fail before infinite execution.
- Trailing teardown steps and completion hooks remain eligible after an earlier blocking normal-step failure.
- Recording consumes final normalized capability results rather than low-level progress events as execution truth. It records only replayable non-observation facts allowed by capability metadata and never invents setup, cleanup, or browser lifecycle commands.
- Runtime-secret values, sensitive raw arguments, subprocess output, and hidden reasoning are never persisted into generated Cases or returned in safe execution summaries.
- Adapters may supply transport-specific event sinks, cancellation callbacks, and progress recorders, but they do not determine lifecycle order, replayability, evidence policy, or recording content.
