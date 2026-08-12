# Module: control_plane

## Purpose

Serve the local, single-user FSQ Control Plane browser application. The module owns Control Plane HTTP and static delivery, safe workspace bootstrap data, per-request platform context, platform readiness, local target discovery, strict-case discovery, one-active-run state, cancellation, resumable progress streaming, and current screenshot/UI-snapshot/log projection for the Devices page.

The module is an entry-layer application. It composes existing configuration, dynamic-agent, strict FSQ, execution-core, provider, evidence, recording, and report contracts. It does not own a second model/tool loop, capability implementation, FSQ parser, strict lifecycle semantics, evidence schema, report generator, platform driver, or Playground behavior.

## Dependencies

- `models`: Uses shared task, result, run-event, runner-event, evidence, report, configuration-error, and capability-registry contracts.
- `config`: Loads one committed platform preset per request or run, resolves the current directory workspace, and validates provider, dynamic, and strict readiness.
- `agent`: Runs Explore tasks through `FsqAgent` and emits existing safe `RunEvent` values.
- `fsq`: Discovers and validates strict cases through `FsqCaseLoader` and adapts validated commands through the active registry snapshot.
- `core`: Builds active platform harnesses through public factories and executes canonical strict steps through the shared runner/evidence contracts.
- `providers`: Uses `prepare_model_provider_session(..., interactive_auth=False)` for non-interactive readiness and public AI-assertion evaluator construction where Explore or authored `assertWithAI` requires a provider.
- `report`: Uses existing report generation and report-artifact contracts.
- Package-private entry composition: may use `fsq_agent._capability_bootstrap`, `fsq_agent._strict_lifecycle`, and `fsq_agent._strict_case_recording` as shared entry-layer composition used by CLI/Playground/Control Plane. These helpers compose owning-module public APIs and do not expose a Control Plane public contract.
- External dependencies: Python standard-library HTTP, threading, subprocess, path, MIME, JSON, and browser-opening facilities. Optional platform backend dependencies remain lazy runtime concerns of their owning modules.

The module must not import `playground`, `cli`, `capabilities`, module-private `_*.py` files from another public module, concrete private harnesses/drivers, OpenAI Agents SDK runtime types, or frontend source. Other domain/runtime modules must not import `control_plane`; `cli` may import its public server API.

## Public Interface

Current `__init__.py` exports via explicit `__all__`:

- `ControlPlaneServer`: Local HTTP/static server wrapper bound to one current-directory FSQ workspace and one in-memory task state.
- `ControlPlaneServerOptions`: Host, port, open-browser flag, workspace path, and optional static-path override used by tests.
- `run_control_plane(options: ControlPlaneServerOptions) -> None`: Blocking server entry used by CLI.

The public HTTP prefix is `/api/control-plane`.

### Bootstrap and discovery

- `GET /api/control-plane/bootstrap`: Returns API version, supported platform ids/labels, safe workspace summary, busy state, and the active in-memory task summary when present.
- `GET /api/control-plane/readiness?platform=<id>`: Loads the selected platform preset and returns independent `workspace`, `provider`, `target`, and provider-independent `strict` records with `ready`, `unavailable`, or `error`, plus safe messages/actions. Workspace readiness reflects the initialized resolved workspace root and does not depend on the configured cases directory. Strict readiness reflects strict runtime/configuration validation and does not depend on whether authored cases currently exist. Provider readiness uses non-interactive provider preparation, may silently refresh a provider token from a valid cached GitHub OAuth token, never starts device-code authentication, and does not send a model request or expose secret values.
- `GET /api/control-plane/targets?platform=<id>`: Returns normalized local target records containing `id`, `label`, `description`, `status`, `selectable`, `isDefault`, and safe metadata. Android uses bounded ADB discovery. Web represents the configured Chrome target. Windows represents the configured application/pywinauto target. macOS represents the configured Appium Mac2 application target.
- `GET /api/control-plane/cases?platform=<id>`: Recursively discovers `*.codex.yaml` under the selected preset's resolved `cases.dir`, enforces root containment, returns at most 500 sorted entries plus a `truncated` indicator, validates through `FsqCaseLoader` and the active registry, and returns safe metadata including path, id/name, platform, command count, `requiresAiAssertion`, validation status, selectability, and diagnostics. An absent configured cases directory is a successful empty discovery result with `cases=[]` and `truncated=false`; Control Plane does not create the directory. The endpoint does not return full source, execute hooks, or resolve runtime secrets.

Target labels are platform-specific presentation metadata: Android uses Device, Web uses Browser, and Windows/macOS use Application. Missing tools, offline/unauthorized Android targets, invalid local paths, unavailable backend packages, and unusable Appium settings remain visible unselectable discovery/readiness results rather than success-shaped empty data.

### Runs

- `POST /api/control-plane/runs`: Accepts exactly one discriminated source. Explore uses `mode="explore"`, `platform`, `targetId`, and non-empty `goal`. Strict uses `mode="strict"`, `platform`, `targetId`, and contained `casePath`. The server reloads platform settings, revalidates readiness and target, and for Strict re-resolves/reloads the case and determines provider-backed AI assertion requirements before external actions. Success returns `202` and a request id.
- `POST /api/control-plane/runs/{request_id}/cancel`: Requests cooperative cancellation and idempotently returns the current run snapshot.
- `GET /api/control-plane/runs/{request_id}`: Returns one complete safe task snapshot for initial load, reconnect, or polling fallback.
- `GET /api/control-plane/runs/{request_id}/stream?afterSequence=<n>`: Streams SSE snapshots containing status, new normalized timeline/log events, active step, run/result summary, and latest screenshot/UI-snapshot revisions. It resumes after the supplied sequence and closes after a terminal state.
- `GET /api/control-plane/runs/{request_id}/screen`: Returns the latest contained screenshot bytes with MIME type, ETag/revision, timestamp, and safe step/platform metadata, or an explicit unavailable response.
- `GET /api/control-plane/runs/{request_id}/ui-snapshot`: Returns the latest contained normalized `ui_snapshot` text with revision, MIME/format, timestamp, and safe step metadata. It enforces a 512 KiB text-size limit and reports oversized/unreadable evidence without changing task status.

Explore delegates to the existing dynamic agent, pre-plan, harness, verification, event persistence, dynamic recording, and report paths. Strict delegates to active-platform capability bootstrap, `FsqCaseLoader`, shared strict lifecycle composition, `StepRunner`/`StepSequenceRunner`, evidence recording, runtime-secret resolution, optional provider-backed `assertWithAI`, and strict report generation. Control Plane does not infer replayability, evidence policy, lifecycle order, or capability semantics from action names.

Every run freezes its selected platform, settings, target, mode, and source before `running`. The service permits one active task across `preparing`, `running`, and `finalizing`; concurrent starts return `409`. Platform and target selection remain client-side idle context and cannot mutate an active run.

Task status is `preparing`, `running`, `finalizing`, `success`, `failed`, `inconclusive`, `cancelled`, or `error`. Cancellation is distinct from infrastructure error. Terminal snapshots include a safe summary, run id when allocated, and evidence/report availability.

### Evidence and event projection

Control Plane projects existing execution facts into:

- Timeline rows with sequence, time, phase, step/tool label, status, duration, and safe message.
- Safe logs with level, phase, tool, status, and message.
- The newest screenshot artifact reference and monotonically changing revision.
- The newest normalized `ui_snapshot` artifact reference and monotonically changing revision.

SSE payloads do not embed screenshot bytes, large UI snapshots, hidden reasoning, secret values, or unrestricted backend objects. Artifact paths are resolved only below the frozen run directory. Evidence absence or read failure is explicit and does not imply run success or failure.

All API errors use `code`, `message`, `action`, and optional safe `details`.

## Internal Structure

- `__init__.py`: Public exports only.
- `_server.py`: HTTP routing, SSE, static serving/fallback, request decoding, response encoding, and server lifecycle.
- `_state.py`: Thread-safe one-task state machine, sequence/revision coordination, cancellation state, reconnect snapshots, and wait/notification behavior.
- `_readiness.py`: Per-platform settings loading and safe workspace/provider/target/strict readiness projection.
- `_targets.py`: Independent Android ADB discovery and normalized Web/Windows/macOS local target projection.
- `_cases.py`: Contained recursive strict-case discovery, stable sorting, bounded results, `FsqCaseLoader` validation, and safe summaries.
- `_execution.py`: Explore and Strict entry orchestration through existing agent/core/FSQ/provider/report and package-private shared entry-composition contracts.
- `_evidence.py`: Safe event normalization and latest contained screenshot/UI-snapshot projection.
- `static/`: Untracked Vite-generated Control Plane assets included in the wheel.
- `SPEC.md`: Module contract.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: `ControlPlaneServer`, `ControlPlaneServerOptions`, `run_control_plane`, and the documented local HTTP endpoints.
- Internal modules: all `_*.py` files and generated `static` content are private implementation details.
- Domain boundaries: Control Plane owns local HTTP/UI entry orchestration, discovery, in-memory task state, and safe presentation projections. Owning modules retain configuration, execution, parsing, capability, evidence, provider, recording, and report semantics.
- Boundary models: HTTP request/response dictionaries and private immutable discovery/projection records sit at the transport boundary; shared runtime facts use `models` contracts.
- Dependency direction: CLI may import Control Plane public APIs; Control Plane imports owning module public APIs and named package-private entry-composition helpers; owning modules and Playground do not import Control Plane.
- Rationale: The module coordinates transport, configuration, external local targets, two execution paths, state streaming, evidence persistence, and static delivery, so Level 3 is required. Additional repository/domain layers would only pass data through.

## Error Handling

Unsupported platforms, malformed query/body values, missing targets, stale/disappeared targets, invalid or escaped case paths, changed or malformed cases, missing readiness, and ambiguous execution sources fail before external actions. Busy conflicts return `409`. Missing requests/evidence return `404` or an explicit unavailable payload according to endpoint semantics. Oversized UI snapshots return `413` without changing run status.

ADB discovery is bounded and reports missing executable, timeout, nonzero exit, offline, and unauthorized states safely. Provider/auth failures identify safe configuration actions and never return tokens, keys, runtime-secret values, or hidden model reasoning. Unexpected boundary exceptions are normalized without tracebacks.

SSE disconnection does not mutate execution status. Clients may resume by sequence and fall back to snapshots. A process restart does not recreate an in-memory active task; bootstrap reports only the new process state. Persisted run browsing is not a Devices-page responsibility.

Static serving rejects path traversal and cross-entry fallback. Missing generated assets fail before binding with the repository frontend build instruction.

## Verification Scope

- Verification covers four-platform readiness/target discovery, safe case discovery, Explore/Strict validation and delegation, strict AI-assertion provider gating, one-task locking, state transitions, cancellation, SSE resume, latest evidence projection, safe errors, static serving, and isolated-wheel startup.
- Security boundaries cover path containment, bounded reads/discovery, secret/reasoning redaction, no browser-supplied artifact paths, and no imports from Playground or module-private implementation files.
- Integration verification proves at least one available platform can start Explore and Strict runs, emit progress/evidence, switch evidence views through the API, cancel, and reach a truthful terminal state.

## Current Invariants

- Control Plane is independent from Playground and does not delegate to it.
- Control Plane composes shared execution authority; it never implements a second agent loop, strict runner, parser, lifecycle engine, capability table, evidence schema, recorder, or report generator.
- Each request names a platform; settings are reloaded from the committed platform preset and frozen per run.
- Exactly one task may be active across preparation, execution, and finalization.
- Run-start validation is authoritative even when discovery/readiness data was previously returned to a client.
- Provider readiness blocks Explore and Strict cases containing `assertWithAI`, but not provider-free Strict cases.
- Automatic live evidence uses `screenshot` and normalized `ui_snapshot`; UI labels do not change artifact semantics.
- Browser-visible events and errors are safe projections, not raw internal objects.
- Generated frontend assets are build artifacts, not source files.
