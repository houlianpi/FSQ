# Module: control_plane

## Purpose

Serve the local, single-user FSQ Control Plane browser application. The module owns Control Plane HTTP and static delivery; trusted-local Provider and workspace-management transport; GitHub device-flow task state; connection-test orchestration; registry-backed workspace list/create/detail/update and bounded read-only browsing; and the temporarily isolated legacy Devices readiness, discovery, run, cancellation, streaming, and evidence projections.

The module is an entry-layer application. It composes existing configuration, dynamic-agent, strict FSQ, execution-core, provider, evidence, recording, and report contracts. It does not own a second model/tool loop, capability implementation, FSQ parser, strict lifecycle semantics, evidence schema, report generator, platform driver, or Playground behavior.

## Dependencies

- `models`: Uses shared task, result, run-event, runner-event, evidence, report, configuration-error, and capability-registry contracts.
- `config`: Loads/saves the user-level active provider and workspace registry, creates/updates registered workspace configurations, resolves explicit registered paths, loads one committed preset plus legacy Devices settings where applicable, and validates provider, workspace, dynamic, and strict readiness.
- `agent`: Runs Explore tasks through `FsqAgent` and emits existing safe `RunEvent` values.
- `fsq`: Discovers and validates strict cases through `FsqCaseLoader` and adapts validated commands through the active registry snapshot.
- `core`: Builds active platform harnesses through public factories and executes canonical strict steps through the shared runner/evidence contracts.
- `providers`: Uses non-interactive provider preparation for readiness, observable GitHub device-flow operations for Config, live connection testing, and public AI-assertion evaluator construction where Explore or authored `assertWithAI` requires a provider.
- `report`: Uses existing report generation and report-artifact contracts.
- Package-private entry composition: may use `fsq_agent._capability_bootstrap`, `fsq_agent._strict_lifecycle`, and `fsq_agent._strict_case_recording` as shared entry-layer composition used by CLI/Playground/Control Plane. These helpers compose owning-module public APIs and do not expose a Control Plane public contract.
- External dependencies: Python standard-library HTTP, threading, subprocess, path, MIME, JSON, and browser-opening facilities. Optional platform backend dependencies remain lazy runtime concerns of their owning modules.

The module must not import `playground`, `cli`, `capabilities`, module-private `_*.py` files from another public module, concrete private harnesses/drivers, OpenAI Agents SDK runtime types, or frontend source. Other domain/runtime modules must not import `control_plane`; `cli` may import its public server API.

## Public Interface

Current `__init__.py` exports via explicit `__all__`:

- `ControlPlaneServer`: Local HTTP/static server wrapper with registry-backed workspace management and one isolated legacy Devices in-memory task state.
- `ControlPlaneServerOptions`: Host, port, open-browser flag, startup-directory path retained for legacy Devices, optional static-path override, and optional user-config-root override used by tests.
- `run_control_plane(options: ControlPlaneServerOptions) -> None`: Blocking server entry used by CLI.

The public HTTP prefix is `/api/control-plane`.

### Bootstrap and discovery

- `GET /api/control-plane/bootstrap`: Returns API version, supported platform ids/labels, safe legacy Devices workspace summary, busy state, and the active in-memory Devices task summary when present. New workspace registry state comes only from the workspace APIs.
- `GET /api/control-plane/readiness?platform=<id>`: Loads the selected platform preset and returns independent `workspace`, `provider`, `target`, and provider-independent `strict` records with `ready`, `unavailable`, or `error`, plus safe messages/actions. Workspace readiness reflects the initialized resolved workspace root and does not depend on the configured cases directory. Strict readiness reflects strict runtime/configuration validation and does not depend on whether authored cases currently exist. Provider readiness uses non-interactive provider preparation, may silently refresh a provider token from a valid cached GitHub OAuth token, never starts device-code authentication, and does not send a model request or expose secret values.
- `GET /api/control-plane/targets?platform=<id>`: Returns normalized local target records containing `id`, `label`, `description`, `status`, `selectable`, `isDefault`, and safe metadata. Android uses bounded ADB discovery. Web represents the configured Chrome target. Windows represents the configured application/pywinauto target. macOS represents the configured Appium Mac2 application target.
- `GET /api/control-plane/cases?platform=<id>`: Recursively discovers only exact lowercase `*.fsq.yaml` files under the selected preset's resolved `cases.dir`, enforces root containment, returns at most 500 sorted entries plus a `truncated` indicator, validates through `FsqCaseLoader` and the active registry, and returns safe metadata including path, id/name, platform, command count, `requiresAiAssertion`, validation status, selectability, and diagnostics. An absent configured cases directory is a successful empty discovery result with `cases=[]` and `truncated=false`; Control Plane does not create the directory. The endpoint does not return full source, execute hooks, or resolve runtime secrets. Strict run `casePath` values must identify a contained `.fsq.yaml` case.

Target labels are platform-specific presentation metadata: Android uses Device, Web uses Browser, and Windows/macOS use Application. Missing tools, offline/unauthorized Android targets, invalid local paths, unavailable backend packages, and unusable Appium settings remain visible unselectable discovery/readiness results rather than success-shaped empty data.

### Provider configuration

Config JSON keys use camelCase. Every Config response uses `Cache-Control: no-store`; GitHub token values are never returned.

- `GET /api/control-plane/config`: Returns `{"configured": false, "provider": null}` or one active provider. Azure presentation contains `type="azure_openai"`, `modelName`, normalized `baseUrl`, and the complete local `apiKey`. GitHub presentation contains `type="github_copilot"`, `modelName`, and `authenticated=true`.
- `PUT /api/control-plane/config/azure`: Accepts exactly non-empty `baseUrl`, `modelName`, and `apiKey`; normalizes and validates the complete candidate, persists it through `config`, deletes GitHub credentials only after activation succeeds, and returns the refreshed Config representation.
- `POST /api/control-plane/config/github/device-flow`: Accepts exactly one non-empty `modelName`. When no other device flow is waiting, it requests a device code and returns `authRequestId`, `verificationUri`, `userCode`, `expiresAt`, `pollIntervalSeconds`, and `status="waiting"`, then polls in a cancellable background task.
- `GET /api/control-plane/config/github/device-flow/{authRequestId}`: Returns `waiting`, `success`, `failed`, `expired`, or `cancelled` with concise safe details. Success means the requested model and both new GitHub token files are committed, GitHub is active, and Azure credentials were removed.
- `DELETE /api/control-plane/config/github/device-flow/{authRequestId}`: Cooperatively and idempotently cancels a waiting flow without changing the active provider.
- `POST /api/control-plane/config/test-connection`: Accepts no provider fields, tests only the latest saved configuration through `providers`, and returns success with provider, model, and elapsed duration or the standard structured error.

Device-flow state is independent of run state. One model run and one device flow may coexist because configuration changes affect only subsequently constructed complete tasks. The server permits one waiting device flow, bounds retained terminal authentication records, and cancels active polling during shutdown.

Provider Config and workspace-management endpoints are available only when the configured bind host resolves exclusively to loopback and the requesting peer is loopback. Other access receives a structured unavailable/forbidden response and no editable Provider/workspace data. Cross-origin writes are rejected, CORS is not enabled, and every response uses `Cache-Control: no-store`.

### Workspace management

Workspace JSON keys use camelCase. All routes below re-read registry/config truth for the request and never accept a client-supplied workspace root. List responses omit workspace `env` values; detail/update responses may contain complete values only through this trusted-local boundary. Values never appear in URLs, errors, logs, SSE, readiness, directory metadata, or file content.

- `GET /api/control-plane/workspaces`: Returns registered entries in user-config order. Available entries include immutable `name`, normalized absolute `configPath`, derived `rootPath`, `platform`, `status="available"`, and a safe message. Missing, unreadable, invalid, unsupported-version, or name-mismatched entries remain in place as `status="unavailable"`, retain only registry identity plus safe path metadata, and include concise repair guidance without parser internals or config values.
- `POST /api/control-plane/workspaces`: Accepts exactly `name`, `parentPath`, `platform`, complete platform-discriminated `target`, and complete `env`. The final root is exactly `<parentPath>/<name>`. Before writing, validate request shape, workspace/registry name uniqueness, parent and final paths, target fields and required local files, and env names/string values. The final path must not exist or must be an empty directory; non-empty roots, legacy markers, and existing `.fsq` are rejected without merge or overwrite. Creation stages managed directories/config, writes empty UTF-8 `knowledge/project.md`, atomically commits `.fsq/config.yaml`, then atomically appends the registry entry while preserving Provider state. Ordinary failure rolls back request-created content, leaves a pre-existing empty root empty, removes a request-created root only when empty, and never removes a user-owned parent. Cross-file process-crash atomicity is not promised; config commit precedes registry commit so a crash may leave a complete unregistered workspace but not a registry entry for a partial workspace. Success returns workspace detail and revision.
- `GET /api/control-plane/workspaces/{workspaceName}`: Resolves the exact registry entry and returns immutable `name`, `rootPath`, `configPath`, `platform`, complete target, complete env values, and opaque `revision="sha256:..."` derived from exact config bytes. A registry/config name mismatch is unavailable rather than silently rebound.
- `PUT /api/control-plane/workspaces/{workspaceName}`: Accepts exactly complete `target`, complete `env`, and `expectedRevision`; identity changes are not accepted. Reload and validate registry/config truth, compare the exact-content revision, validate the complete replacement, and atomically replace only `.fsq/config.yaml`. A mismatch returns `409 workspace_conflict` and preserves both disk state and unsaved client values.
- `GET /api/control-plane/workspaces/{workspaceName}/entries?path=<relative>`: A root request exposes exactly the virtual `cases/` and `knowledge/` roots. Descendant requests return only direct children, with bounded depth/result count and stable directory-first/name sorting, using relative path, name, kind, safe size, and safe modified time. Absolute paths, `..`, `.fsq`, containment escapes, and symlink escapes are rejected. Disappearing entries produce a scoped unavailable response.
- `GET /api/control-plane/workspaces/{workspaceName}/file?path=<relative>`: Reads one contained regular file below `cases/` or `knowledge/`, checks a fixed byte limit before decoding, requires UTF-8 text, and returns relative path, media/presentation kind, byte size, optional line count, safe modified time, and content. Directories, binary/invalid UTF-8/oversized content, `.fsq`, absolute/traversing paths, and path/symlink escapes return explicit safe errors.

There are no workspace import, unregister, delete, rename, move, platform-change, file-write, file-create, file-delete, search, download, or raw-root APIs.

### Legacy Devices boundary

Control Plane may start from any directory. Workspace management always uses the user registry and explicit registered config paths; startup directory never selects a new workspace. For this cycle only, existing Devices endpoints and execution remain bound to `<startup-directory>/.fsq-agent-workspace/output/runs/<run-id>/` and the committed platform presets. Devices does not consume selected workspace state, registry target/env values, or new workspace run directories. This exception is isolated to Devices and must not leak into workspace APIs or CLI workspace loading.

### Legacy Devices runs

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
- `_config.py`: Config response projection, loopback/cross-origin checks, Azure save and connection-test orchestration, and safe error mapping.
- `_provider_auth.py`: One-active-device-flow state, background polling/cancellation, bounded terminal record retention, and shutdown cleanup.
- `_workspaces.py`: Trusted-local registry list/detail projection, workspace creation/update orchestration, revision checks, atomic handoff to `config`, rollback coordination, and safe error mapping.
- `_workspace_files.py`: Registry-resolved, bounded, contained, symlink-safe workspace directory metadata and UTF-8 file reads.
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
- Domain boundaries: Control Plane owns local HTTP/UI entry orchestration, trusted-local Provider/workspace transport, workspace-operation sequencing and safe projections, device-flow task lifecycle, and isolated legacy Devices discovery/run state. Config owns user Provider/registry/workspace config persistence and settings composition; providers owns protocol/client behavior; other owning modules retain execution, parsing, capability, evidence, recording, and report semantics.
- Boundary models: HTTP request/response dictionaries and private immutable discovery/projection records sit at the transport boundary; shared runtime facts use `models` contracts.
- Dependency direction: CLI may import Control Plane public APIs; Control Plane imports owning module public APIs and named package-private entry-composition helpers; owning modules and Playground do not import Control Plane.
- Rationale: The module coordinates trusted local transport, multi-file workspace creation, read-only filesystem browsing, Provider configuration, external local targets, two legacy Devices execution paths, state streaming, evidence persistence, and static delivery, so Level 3 is required. Additional repository/domain layers would only pass data through.

## Error Handling

Unsupported platforms, malformed query/body values, missing targets, stale/disappeared targets, invalid or escaped case paths, changed or malformed cases, missing readiness, and ambiguous execution sources fail before external actions. Run busy conflicts return `409`. Missing requests/evidence return `404` or an explicit unavailable payload according to endpoint semantics. Oversized UI snapshots return `413` without changing run status.

Config errors distinguish unconfigured state, missing/invalid fields, file IO/validation failure, non-loopback access, cross-origin writes, an active device flow, device-code request/poll failure, denial, expiration, cancellation, Copilot plan/token exchange failure, provider authorization, unavailable model/deployment, rate limiting, malformed provider response, and timeout. Failed Azure saves and incomplete GitHub flows preserve the previous provider. Config errors and responses never expose GitHub tokens, authorization headers, tracebacks, or hidden reasoning.

Workspace errors distinguish untrusted access, malformed fields, invalid/duplicate names, invalid parent/final paths, non-empty/existing managed roots, legacy-format conflicts, invalid/unsupported configs, registry/config identity mismatch, unavailable target files, invalid env names/values, revision conflict, atomic-write/registry failure, rollback failure, missing/disappearing entries, traversal/containment/symlink escape, forbidden `.fsq`, excessive depth/results/bytes, directories, binary content, and invalid UTF-8. Validation failures happen before mutation; ordinary create failures perform bounded rollback; update conflicts and failures preserve the previous file. Safe errors never include env values, raw YAML/parser internals, arbitrary file content, or tracebacks.

ADB discovery is bounded and reports missing executable, timeout, nonzero exit, offline, and unauthorized states safely. Provider/auth failures identify safe configuration actions and never return tokens, keys, runtime-secret values, or hidden model reasoning. Unexpected boundary exceptions are normalized without tracebacks.

SSE disconnection does not mutate execution status. Clients may resume by sequence and fall back to snapshots. A process restart does not recreate an in-memory active task; bootstrap reports only the new process state. Persisted run browsing is not a Devices-page responsibility.

Static serving rejects path traversal and cross-entry fallback. Missing generated assets fail before binding with the repository frontend build instruction.

## Verification Scope

- Verification covers Provider Config plus workspace route methods/shapes, registry-order list projection, all four platform creation/update variants, immutable identity, exact revisions/conflicts, atomic writes, rollback, unavailable registry entries, bounded tree/file browsing, no-store behavior, loopback/same-origin gates, independent device-flow lifecycle, saved-only connection testing, retained Devices discovery/execution, static serving, and isolated-wheel startup.
- Security boundaries cover trusted-local Provider/workspace data, list/detail secret separation, `.fsq` denial, path/symlink containment, bounded reads/discovery, secret/reasoning redaction, no browser-supplied roots/artifact paths, no CORS, and no imports from Playground or module-private implementation files.
- Compatibility verification proves Control Plane can start outside a new workspace, workspace APIs use only registry paths, and Devices alone continues writing under the startup directory's legacy `.fsq-agent-workspace/output/runs` root without consuming selected workspace state.
- Integration verification proves at least one available platform can start Explore and Strict runs, emit progress/evidence, switch evidence views through the API, cancel, and reach a truthful terminal state.

## Current Invariants

- Control Plane is independent from Playground and does not delegate to it.
- Control Plane composes shared execution authority; it never implements a second agent loop, strict runner, parser, lifecycle engine, capability table, evidence schema, recorder, or report generator.
- Control Plane transport never owns Provider/registry/config file formats, GitHub protocol behavior, token exchange, or model invocation. It delegates persistence/settings rules to `config` and provider protocols to `providers`.
- Provider Config and workspace APIs require a loopback bind and peer, reject cross-origin writes, disable caching, and do not enable CORS. The complete Azure key and workspace env values are returned only through their documented trusted-local detail surfaces; GitHub tokens are never returned.
- Workspace list results preserve registry order and never expose env values. Detail/update resolve by registry identity on every request; browser-supplied roots are never trusted.
- Workspace name, root path, config path, and platform are immutable after creation. Update replaces only complete target/env content after exact revision comparison.
- Workspace browsing exposes only bounded read-only UTF-8 content under `cases/` and `knowledge/`; `.fsq`, path escapes, symlink escapes, writes, and raw workspace access are forbidden.
- Exactly one GitHub device flow may wait at a time. Device-flow state is independent of the one-active-run state, and only a complete successful flow changes Provider configuration.
- Each legacy Devices run request names a platform; settings are reloaded from the committed preset and frozen per run. New workspace selection/configuration does not mutate Devices state.
- Exactly one task may be active across preparation, execution, and finalization.
- Run-start validation is authoritative even when discovery/readiness data was previously returned to a client.
- Provider readiness blocks Explore and Strict cases containing `assertWithAI`, but not provider-free Strict cases.
- Automatic live evidence uses `screenshot` and normalized `ui_snapshot`; UI labels do not change artifact semantics.
- Browser-visible events and errors are safe projections, not raw internal objects.
- Only the legacy Devices runtime derives files from the Control Plane startup directory. New workspace operations use explicit registered config paths and do not require the server to start inside a workspace.
- Generated frontend assets are build artifacts, not source files.
