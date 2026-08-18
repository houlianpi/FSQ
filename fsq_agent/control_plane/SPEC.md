# Module: control_plane

## Purpose

Serve the local, single-user FSQ Control Plane browser application. The module owns Control Plane HTTP and static delivery; trusted-local Provider and multi-platform workspace-management transport; pending GitHub authorization/model-selection transaction state; connection-test orchestration; registry-backed workspace list/create/summary/platform-detail/platform-add/platform-update and bounded read-only browsing; and workspace-aware Devices selection, readiness, target/case discovery, one-active-run state, cancellation, resumable progress streaming, current and per-step evidence projection, persisted screenshot replay frames, and replay-video storage/range transport.

The module is an entry-layer application. It composes existing configuration, dynamic-agent, strict FSQ, execution-core, provider, evidence, recording, and report contracts. It does not own a second model/tool loop, capability implementation, FSQ parser, strict lifecycle semantics, evidence schema, report generator, platform driver, or Playground behavior.

## Dependencies

- `models`: Uses shared task, result, run-event, runner-event, evidence, report, configuration-error, and capability-registry contracts.
- `config`: Loads/saves the user-level active provider and root-based workspace registry, discovers platform status, creates workspaces, adds/updates independent platform configurations, resolves explicit registered roots, loads one selected platform config plus its committed preset, and validates provider, workspace-platform, dynamic, and strict readiness.
- `agent`: Runs Explore tasks through `FsqAgent` and emits existing safe `RunEvent` values.
- `fsq`: Discovers and validates strict cases through `FsqCaseLoader` and adapts validated commands through the active registry snapshot.
- `core`: Supplies shared Android device discovery, builds active platform harnesses through public factories, and executes canonical strict steps through the shared runner/evidence contracts.
- `providers`: Uses non-interactive provider preparation for readiness, observable GitHub device authorization/model discovery/selected-model activation for Config, live connection testing, and public AI-assertion evaluator construction where Explore or authored `assertWithAI` requires a provider.
- `report`: Uses existing report generation and report-artifact contracts.
- Package-private entry composition: may use `fsq_agent._capability_bootstrap`, `fsq_agent._strict_lifecycle`, and `fsq_agent._strict_case_recording` as shared entry-layer composition used by CLI/Playground/Control Plane. These helpers compose owning-module public APIs and do not expose a Control Plane public contract.
- External dependencies: Python standard-library HTTP, threading, subprocess, path, MIME, JSON, base64, and browser-opening facilities. Optional platform backend dependencies remain lazy runtime concerns of their owning modules.

The module must not import `playground`, `cli`, `capabilities`, module-private `_*.py` files from another public module, concrete private harnesses/drivers, OpenAI Agents SDK runtime types, or frontend source. Other domain/runtime modules must not import `control_plane`; `cli` may import its public server API.

## Public Interface

Current `__init__.py` exports via explicit `__all__`:

- `ControlPlaneServer`: Local HTTP/static server wrapper with registry-backed workspace management and one workspace-aware Devices in-memory task state.
- `ControlPlaneServerOptions`: Host, port, open-browser flag, optional static-path override, and optional user-config-root override used by tests.
- `run_control_plane(options: ControlPlaneServerOptions) -> None`: Blocking server entry used by CLI.

The public HTTP prefix is `/api/control-plane`.

### Bootstrap and discovery

- `GET /api/control-plane/bootstrap`: Returns API version, supported platform ids/labels, busy state, and the active in-memory Devices task summary when present. Workspace registry state comes only from the workspace APIs.
- `GET /api/control-plane/readiness?workspace=<name>&platform=<id>`: Resolves the registered workspace and selected valid platform config, then returns independent `workspace`, `platform`, `provider`, `target`, and provider-independent `strict` records with `ready`, `unavailable`, or `error`, plus safe messages/actions. Workspace/platform readiness does not depend on the selected cases directory. Strict readiness reflects strict runtime/configuration validation and does not depend on whether authored cases currently exist. Provider readiness uses non-interactive provider preparation, may silently refresh a provider token from a valid cached GitHub OAuth token, never starts device-code authentication, and does not send a model request or expose secret values.
- `GET /api/control-plane/targets?workspace=<name>&platform=<id>`: Returns normalized local target records for the selected workspace platform containing `id`, `label`, `description`, `status`, `selectable`, `isDefault`, and safe metadata. Android uses bounded ADB discovery, persists no serial, and may mark only a sole online selectable device as the unambiguous default. Web, Windows, and macOS represent the selected platform config's validated application target plus preset-owned backend policy.
- `GET /api/control-plane/cases?workspace=<name>&platform=<id>`: Recursively discovers only exact lowercase `*.fsq.yaml` files under the resolved `cases/<platform>` root, enforces root containment, returns at most 500 sorted entries plus a `truncated` indicator, validates through `FsqCaseLoader` and the active registry, and returns safe metadata including path, id/name, platform, command count, `requiresAiAssertion`, validation status, selectability, and diagnostics. An absent configured cases directory is a successful empty discovery result with `cases=[]` and `truncated=false`; Control Plane does not create the directory. The endpoint does not return full source, execute hooks, or resolve runtime secrets. Strict run `casePath` values must identify a contained `.fsq.yaml` case.

Target labels are platform-specific presentation metadata: Android uses Device, Web uses Browser, and Windows/macOS use Application. Missing tools, offline/unauthorized Android targets, invalid local paths, unavailable backend packages, and unusable Appium settings remain visible unselectable discovery/readiness results rather than success-shaped empty data.

### Provider configuration

Config JSON keys use camelCase. Every Config response uses `Cache-Control: no-store`; GitHub token values are never returned.

- `GET /api/control-plane/config`: Returns `{"configured": false, "provider": null}` or one active provider. Azure presentation contains `type="azure_openai"`, `modelName`, normalized `baseUrl`, and the complete local `apiKey`. GitHub presentation contains `type="github_copilot"`, `modelName`, and `authenticated=true`.
- `PUT /api/control-plane/config/azure`: Accepts exactly non-empty `baseUrl`, `modelName`, and `apiKey`; normalizes and validates the complete candidate, persists it through `config`, deletes GitHub credentials only after activation succeeds, and returns the refreshed Config representation.
- `POST /api/control-plane/config/github/device-flow`: Accepts exactly an empty object. When no other unsaved GitHub transaction is active, it requests a device code and returns `authRequestId`, `verificationUri`, `userCode`, device-code `expiresAt`, `pollIntervalSeconds`, and `status="waiting"`, then completes authorization and authenticated model discovery in a cancellable background task without writing Provider configuration.
- `GET /api/control-plane/config/github/device-flow/{authRequestId}`: Returns the current `waiting`, `loading_models`, `ready`, `model_error`, `failed`, `expired`, `cancelled`, or `success` discriminated state with concise safe details. Waiting contains device-code fields; loading contains a bounded poll interval; ready contains only ordered `{id, name}` models plus the pending-transaction expiration. Pending credentials and upstream response bodies are never returned.
- `POST /api/control-plane/config/github/device-flow/{authRequestId}/models`: Accepts exactly an empty object and restarts model discovery for a non-expired `model_error` transaction or a ready transaction whose filtered list is empty, without repeating device authorization.
- `PUT /api/control-plane/config/github/device-flow/{authRequestId}`: Accepts exactly one non-empty `modelName`, requires a non-expired ready transaction, validates the submitted id against that transaction's server-side offered-model allowlist, and atomically activates the complete GitHub candidate. Success changes the transaction to `success`; activation failure leaves the prior provider and retryable ready transaction unchanged.
- `DELETE /api/control-plane/config/github/device-flow/{authRequestId}`: Cooperatively and idempotently cancels any unsaved transaction, scrubs pending credentials/models, and does not change the active provider.
- `POST /api/control-plane/config/test-connection`: Accepts no provider fields, tests only the latest saved configuration through `providers`, and returns success with provider, model, and elapsed duration or the standard structured error.

GitHub transaction state is independent of run state. One model run and one provider transaction may coexist because configuration changes affect only subsequently constructed complete tasks. The server permits one unsaved GitHub transaction across authorization, discovery, ready, and model-error states. A completed authorization expires ten minutes later; expiration, cancellation, success, and shutdown scrub all pending credentials and offered models. Terminal authentication records are bounded and contain presentation-safe fields only.

Provider Config and workspace-management endpoints are available only when the configured bind host resolves exclusively to loopback and the requesting peer is loopback. Other access receives a structured unavailable/forbidden response and no editable Provider/workspace data. Cross-origin writes are rejected, CORS is not enabled, and every response uses `Cache-Control: no-store`.

### Workspace management

Workspace JSON keys use camelCase. All routes below re-read registry/config truth for the request and never accept a client-supplied workspace root. List and workspace-summary responses omit all `env` values. Complete values exist only in create/add request bodies and the selected available platform detail/update trusted-local boundary; they never appear in URLs, workspace summaries, errors, logs, SSE, readiness, directory metadata, or file content.

- `GET /api/control-plane/workspaces`: Returns registered entries in user-config order with immutable `name`, normalized absolute `rootPath`, workspace `status`, safe `message`/`action`, and platform status records in canonical Android, Web, Windows, macOS order. Available and partial entries expose no target or env data. Missing, unreadable, unsafe, unsupported legacy-only, or no-valid-platform roots remain in place as `status="unavailable"` with concise repair guidance without parser internals or config values.
- `POST /api/control-plane/workspaces`: Accepts exactly `name`, `parentPath`, and a non-empty `platforms` array whose unique items contain `platform`, complete discriminated `target`, and complete `env`. The final root is exactly `<parentPath>/<name>`. Before writing, validate the whole request, registry/root uniqueness, parent and final paths, every target and required local file, and every env mapping. The final path must not exist or must be an empty directory. Creation stages per-platform cases/knowledge/runs directories, writes absent empty UTF-8 `knowledge/<platform>/project.md` files, atomically commits every `.fsq/config/config.<platform>.yaml`, then atomically appends the root registry entry while preserving Provider state. Ordinary failure rolls back only request-created content, leaves a pre-existing empty root empty, removes a request-created root only when empty, and never removes a user-owned parent. Config commits precede registry commit, so a process crash may leave a complete unregistered workspace but never intentionally registers a partially committed request. Success returns the safe workspace summary.
- `GET /api/control-plane/workspaces/{workspaceName}`: Returns immutable `name`/`rootPath`, workspace status, and canonically ordered platform summaries. Each available platform summary contains safe target presentation values, env names/configured state, config path, and independent `revision="sha256:..."`, but no env values. Invalid platform summaries contain only safe identity/status guidance. A registry/config identity mismatch is unavailable rather than silently rebound.
- `GET /api/control-plane/workspaces/{workspaceName}/platforms/{platform}`: Returns one available platform's immutable workspace/platform identity, complete target, complete env values, config path, and independent revision. Invalid or absent platforms cannot enter browser edit mode.
- `POST /api/control-plane/workspaces/{workspaceName}/platforms`: Accepts exactly `platform`, complete `target`, and complete `env`; adds only an absent exact platform config, preserving adoptable contained platform directories and existing project knowledge, and returns the refreshed workspace summary plus added platform detail. An existing config file, including an invalid one, is a conflict and is never overwritten as Add.
- `PUT /api/control-plane/workspaces/{workspaceName}/platforms/{platform}`: Accepts exactly complete `target`, complete `env`, and `expectedRevision`; identity fields and other platform configs are not accepted. Reload and validate the exact platform truth, compare its exact-content revision, validate the complete replacement, and atomically replace only `.fsq/config/config.<platform>.yaml`. A mismatch returns `409 workspace_conflict` and preserves disk truth plus unsaved client values.
- `GET /api/control-plane/workspaces/{workspaceName}/entries?path=<relative>`: A root request exposes exactly the virtual `cases/` and `knowledge/` roots. Descendant requests return only direct children, with bounded depth/result count and stable directory-first/name sorting, using relative path, name, kind, safe size, and safe modified time. Absolute paths, `..`, `.fsq`, containment escapes, and symlink escapes are rejected. Disappearing entries produce a scoped unavailable response.
- `GET /api/control-plane/workspaces/{workspaceName}/file?path=<relative>`: Reads one contained regular file below `cases/` or `knowledge/`, checks a fixed byte limit before decoding, requires UTF-8 text, and returns relative path, media/presentation kind, byte size, optional line count, safe modified time, and content. Directories, binary/invalid UTF-8/oversized content, `.fsq`, absolute/traversing paths, and path/symlink escapes return explicit safe errors.

There are no workspace import, unregister, delete, rename, move, platform-delete, platform-rename/replacement, file-write, file-create, file-delete, search, download, or raw-root APIs.

### Workspace-Aware Devices Runs

Control Plane may start from any directory. Workspace management and Devices always use the user registry, explicit browser workspace selection, and explicit configured platform selection; the process startup directory never selects configuration or output.

- `POST /api/control-plane/runs`: Accepts exactly one discriminated source. Explore uses `mode="explore"`, `workspaceName`, `platform`, `targetId`, and non-empty `goal`. Strict uses `mode="strict"`, `workspaceName`, `platform`, `targetId`, and contained `casePath`. The server re-resolves registry and exact platform config truth, revalidates readiness and target, and for Strict re-resolves/reloads the case and determines provider-backed AI assertion requirements before external actions. Success returns `202` and a request id.
- `POST /api/control-plane/runs/{request_id}/cancel`: Requests cooperative cancellation and idempotently returns the current run snapshot.
- `GET /api/control-plane/runs/{request_id}`: Returns one complete safe task snapshot for initial load, reconnect, or polling fallback.
- `GET /api/control-plane/runs/{request_id}/stream?afterSequence=<n>`: Streams SSE snapshots containing status, new normalized timeline/log events, active step, run/result summary, and latest screenshot/UI-snapshot revisions. It resumes after the supplied sequence and closes after a terminal state.
- `GET /api/control-plane/runs/{request_id}/screen`: Returns the latest contained screenshot bytes with MIME type, ETag/revision, timestamp, and safe step/platform metadata, or an explicit unavailable response.
- `GET /api/control-plane/runs/{request_id}/ui-snapshot`: Returns the latest contained normalized `ui_snapshot` text with revision, MIME/format, timestamp, and safe step metadata. It enforces a 512 KiB text-size limit and reports oversized/unreadable evidence without changing task status.
- `GET /api/control-plane/runs/{request_id}/step-artifacts/{step_id}`: For a terminal run, resolves the exact non-empty server-issued step id against contained persisted evidence and returns safe ordered screenshot and normalized `ui_snapshot` artifacts for that step. Each item includes kind, capture phase, timestamp, MIME/format, and either bounded base64 image content or bounded UTF-8 text/error metadata. Browser-supplied paths and numeric evidence indices are not accepted.
- `GET /api/control-plane/runs/{request_id}/replay`: For a terminal run, returns contained persisted screenshot frames in chronological capture order with index, timestamp, MIME type, and bounded base64 image content. Duplicate paths are returned once. A known run with no readable frames returns `200` with `available=false`; frame read failures are reported per frame without exposing paths.
- `GET /api/control-plane/runs/{request_id}/replay-video`: Returns metadata and the request-scoped stored-video URL when a contained run-local Control Plane replay WebM exists.
- `POST /api/control-plane/runs/{request_id}/replay-video`: Accepts one bounded `video/webm` or `video/webm;codecs=...` base64 payload only after the run is terminal, atomically stores it as `control-plane-replay/replay.webm` below the frozen run directory, and returns the stored-video URL. A second valid upload replaces the same Control Plane replay file rather than creating arbitrary files.
- `GET /api/control-plane/runs/{request_id}/replay-video/file`: Returns stored WebM bytes and honors one valid HTTP byte range with `206`, `Content-Range`, and `Accept-Ranges: bytes` so native playback can seek.

Explore delegates to the existing dynamic agent, pre-plan, harness, verification, event persistence, dynamic recording, Goal recording publication, and report paths. A validated Explore recording, including a valid draft, is atomically published as `cases/<platform>/<run-id>.fsq.yaml`; publication failure is a secret-safe recording warning and does not change execution or valid recording status. Strict delegates to active-platform capability bootstrap, `FsqCaseLoader`, shared strict lifecycle composition, `StepRunner`/`StepSequenceRunner`, evidence recording, runtime-secret resolution, optional provider-backed `assertWithAI`, and strict report generation and does not publish through the dynamic recording path. Control Plane does not infer replayability, evidence policy, lifecycle order, or capability semantics from action names.

Every run freezes its workspace name/root, selected platform config revision, settings including platform-private env, cases/knowledge/runs roots, target, mode, and source before `running`. Safe run snapshots include `workspaceName` and platform. The service permits one active task across `preparing`, `running`, and `finalizing`; concurrent starts return `409`. Workspace, platform, and target selection remain client-side idle context and cannot mutate an active run.

Task status is `preparing`, `running`, `finalizing`, `success`, `failed`, `inconclusive`, `cancelled`, or `error`. Cancellation is distinct from infrastructure error. Terminal snapshots include a safe summary, run id when allocated, and evidence/report availability.

### Evidence and event projection

Control Plane projects existing execution facts into:

- Timeline rows with sequence, time, phase, stable step id when normalized execution metadata supplies one, step/tool label, duration, and safe message. The `status` field is included only when the source event carries an explicit result/progress status; Control Plane does not fabricate `running` for generic RunEvent updates that have no explicit status. Safe event details may include bounded/redacted `payload`, `toolCallId`, `toolArguments`, and `toolOutputPreview` fields when present on the source event.
- Strict run source step rows with the authored action index, authored action name, canonical action name, step kind, and final result facts when available. Final strict action status, duration, failure category, and safe error/message text come from the matching `RunnerStepResult` or persisted manifest `steps[]` entry for the same `step_id`, not from low-level `RunnerEvent` records such as `step_finish`, `phase_finish`, `harness_call_finish`, or finalize artifact events. Low-level events remain log/progress facts only and must not override a failed, cancelled, skipped, or passed final step result. When a terminal strict run contains an authored action step with no matching final step result because execution stopped before that command, Control Plane marks that action as `skipped` for presentation instead of leaving it pending.
- Safe logs with level, phase, tool, status, and message.
- The newest screenshot artifact reference and monotonically changing revision.
- The newest normalized `ui_snapshot` artifact reference and monotonically changing revision.
- A contained ordered per-step evidence index sourced from persisted event artifact references and `evidence-manifest.json`.
- A contained chronological screenshot-frame sequence used only by the explicit replay endpoint.

SSE payloads do not embed screenshot bytes, large UI snapshots, replay frames/video, hidden reasoning, secret values, or unrestricted backend objects. Artifact paths are resolved only below the frozen run directory. Evidence absence or read failure is explicit and does not imply run success or failure. Control Plane replay storage is independent of Playground replay storage and neither module imports or delegates to the other.

All API errors use `code`, `message`, `action`, and optional safe `details`.

## Internal Structure

- `__init__.py`: Public exports only.
- `_server.py`: HTTP routing, SSE, static serving/fallback, request decoding, response encoding, and server lifecycle.
- `_state.py`: Thread-safe one-task state machine, sequence/revision coordination, cancellation state, reconnect snapshots, and wait/notification behavior.
- `_config.py`: Config response projection, loopback/cross-origin checks, Azure save and connection-test orchestration, and safe error mapping.
- `_provider_auth.py`: One-active pending GitHub transaction, background authorization/model-discovery polling, offered-model allowlisting, ten-minute expiration, selected-model activation, cancellation, bounded safe terminal retention, and shutdown cleanup.
- `_workspaces.py`: Trusted-local registry list/summary/platform-detail projection, multi-platform creation plus platform-add/update orchestration, independent revision checks, atomic handoff to `config`, rollback coordination, and safe error mapping.
- `_workspace_files.py`: Registry-resolved, bounded, contained, symlink-safe workspace directory metadata and UTF-8 file reads.
- `_readiness.py`: Registered workspace-platform settings loading and safe workspace/platform/provider/target/strict readiness projection.
- `_targets.py`: Control Plane target/error projection over shared `core` Android discovery plus normalized Web/Windows/macOS local target projection.
- `_cases.py`: Contained recursive strict-case discovery, stable sorting, bounded results, `FsqCaseLoader` validation, and safe summaries.
- `_execution.py`: Explore and Strict entry orchestration through existing agent/core/FSQ/provider/report and package-private shared entry-composition contracts, including shared Goal recording publication.
- `_evidence.py`: Safe event normalization, latest contained evidence projection, persisted per-step artifact lookup, and replay-frame discovery.
- `_replay.py`: Bounded Control Plane replay-video validation, atomic run-local persistence, metadata lookup, and HTTP byte-range reads.
- `static/`: Untracked Vite-generated Control Plane assets included in the wheel.
- `SPEC.md`: Module contract.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: `ControlPlaneServer`, `ControlPlaneServerOptions`, `run_control_plane`, and the documented local HTTP endpoints.
- Internal modules: all `_*.py` files and generated `static` content are private implementation details.
- Domain boundaries: Control Plane owns local HTTP/UI entry orchestration, trusted-local Provider/workspace transport, workspace-operation sequencing and safe projections, device-flow task lifecycle, workspace-aware Devices discovery/run state, safe evidence presentation projections, and Control Plane replay-video transport. Config owns user Provider/registry/platform-config persistence and settings composition; providers owns protocol/client behavior; other owning modules retain execution, parsing, capability, evidence, recording, and report semantics; browser code owns video generation.
- Boundary models: HTTP request/response dictionaries and private immutable discovery/projection records sit at the transport boundary; shared runtime facts use `models` contracts.
- Dependency direction: CLI may import Control Plane public APIs; Control Plane imports owning module public APIs and named package-private entry-composition helpers; owning modules and Playground do not import Control Plane.
- Rationale: The module coordinates trusted local transport, multi-file workspace creation and platform mutation, read-only filesystem browsing, Provider configuration, workspace-selected local targets, two Devices execution paths, state streaming, evidence persistence, and static delivery, so Level 3 is required. Additional repository/domain layers would only pass data through.

## Error Handling

Missing workspace/platform selections, unsupported/unconfigured/unavailable platforms, malformed query/body values, missing targets, stale/disappeared targets, invalid or escaped case paths, changed or malformed cases, missing readiness, and ambiguous execution sources fail before external actions or run writes. Run busy conflicts return `409`. Missing requests/evidence/video return `404` or an explicit unavailable payload according to endpoint semantics. Oversized UI snapshots, artifact text/images, replay frames, request bodies, and replay videos return bounded errors without changing run status. Step-artifact requests and replay-video mutations made before terminal state return `409`.

Config errors distinguish unconfigured state, missing/invalid fields, file IO/validation failure, non-loopback access, cross-origin writes, an active GitHub transaction, device-code request/poll failure, denial, device-code or pending-transaction expiration, cancellation, Copilot plan/token exchange failure, model-discovery authorization/HTTP/timeout/malformed-response failure, empty eligible models, unavailable or unoffered model, provider activation failure, rate limiting, malformed provider response, and timeout. Failed Azure saves and every unsaved GitHub state preserve the previous provider. Config errors and responses never expose GitHub tokens, authorization headers, upstream response bodies, tracebacks, or hidden reasoning.

Workspace errors distinguish untrusted access, malformed fields, invalid/duplicate names or roots, empty/duplicate platform sets, invalid parent/final paths, non-empty/existing managed roots, legacy-format conflicts, invalid/unsupported/unconfigured platform configs, filename/platform/target mismatch, sibling or registry identity mismatch, unavailable target files, invalid env names/values, duplicate Add including malformed existing config, revision conflict, atomic-write/registry failure, rollback failure, missing/disappearing entries, traversal/containment/symlink escape, forbidden `.fsq`, excessive depth/results/bytes, directories, binary content, and invalid UTF-8. Validation failures happen before mutation; ordinary create/add failures perform bounded rollback; update conflicts and failures preserve the previous platform file. Safe errors never include env values, raw YAML/parser internals, arbitrary file content, or tracebacks.

Shared `core` ADB discovery is bounded; Control Plane projects missing executable, timeout, process-start, nonzero exit, offline, and unauthorized states safely. Provider/auth failures identify safe configuration actions and never return tokens, keys, runtime-secret values, or hidden model reasoning. Unexpected boundary exceptions are normalized without tracebacks.

SSE disconnection does not mutate execution status. Clients may resume by sequence and fall back to snapshots. A process restart does not recreate an in-memory active task; bootstrap reports only the new process state. Persisted run browsing is not a Devices-page responsibility.

Static serving rejects path traversal and cross-entry fallback. Missing generated assets fail before binding with the repository frontend build instruction.

## Verification Scope

- Verification covers Provider Config plus workspace list/summary/create/platform-detail/add/update route methods and shapes, registry/canonical platform ordering, partial/unavailable projection, all four platform target variants, immutable identity, independent exact revisions/conflicts, no platform deletion path, atomic writes, rollback/adoption preservation, bounded tree/file browsing, no-store behavior, loopback/same-origin gates, independent GitHub authorization/discovery/save lifecycle, offered-model validation, expiration/cancellation/shutdown scrubbing, saved-only connection testing, workspace-platform readiness/target discovery, safe platform-scoped case discovery, Explore/Strict validation and delegation, strict AI-assertion provider gating, frozen workspace-platform run state, one-task locking, state transitions, cancellation, SSE resume, latest and per-step evidence projection, replay-frame ordering, replay-video validation/storage/range reads, safe errors, static serving, and isolated-wheel startup.
- Security boundaries cover trusted-local Provider/workspace data, list/detail secret separation, `.fsq` denial, path/symlink containment, exact server-issued step ids, bounded reads/discovery and artifact/frame/video IO, atomic video replacement, secret/reasoning redaction, no browser-supplied roots/artifact paths, no CORS, and no imports from Playground or module-private implementation files.
- Compatibility verification proves Control Plane can start from any directory, workspace APIs and Devices use only registered roots plus explicit platform selection, unsupported legacy workspaces remain safely unavailable, and no execution derives configuration or output from the process startup directory.
- Integration verification proves at least one available platform can start Explore and Strict runs, emit progress/evidence, switch evidence views through the API, cancel, reach a truthful terminal state, retrieve one step's Before/After artifacts, enumerate replay frames, upload a generated WebM, and seek its stored range response.

## Current Invariants

- Control Plane is independent from Playground and does not delegate to it.
- Control Plane composes shared execution authority; it never implements a second agent loop, strict runner, parser, lifecycle engine, capability table, evidence schema, recorder, or report generator.
- Control Plane transport never owns Provider/registry/config file formats, GitHub protocol behavior, token exchange, or model invocation. It delegates persistence/settings rules to `config` and provider protocols to `providers`.
- Provider Config and workspace APIs require a loopback bind and peer, reject cross-origin writes, disable caching, and do not enable CORS. The complete Azure key and platform env values are returned only through their documented trusted-local selected-platform detail surface; GitHub tokens are never returned.
- Workspace list and summary results preserve registry/canonical platform order and never expose env values. Platform detail/add/update resolve by registry identity on every request; browser-supplied roots are never trusted.
- Workspace name/root and persisted platform identity/config path are immutable. Add creates only an absent platform; update replaces only one platform's complete target/env content after its exact revision comparison; no operation deletes a platform.
- Workspace browsing exposes only bounded read-only UTF-8 content under `cases/` and `knowledge/`; `.fsq`, path escapes, symlink escapes, writes, and raw workspace access are forbidden.
- Exactly one unsaved GitHub provider transaction may exist at a time. Its state is independent of the one-active-run state, its credentials remain only in memory, and only explicit save of one server-offered model changes Provider configuration.
- Each Devices run request names a registered workspace and explicit configured platform; exact platform settings and roots are reloaded and frozen per run. Later browser selection or platform configuration changes do not mutate active Devices state.
- Exactly one task may be active across preparation, execution, and finalization.
- Run-start validation is authoritative even when discovery/readiness data was previously returned to a client.
- Provider readiness blocks Explore and Strict cases containing `assertWithAI`, but not provider-free Strict cases.
- Automatic live evidence uses `screenshot` and normalized `ui_snapshot`; UI labels do not change artifact semantics.
- Per-step comparison and replay use persisted artifact metadata without changing automatic capture policy or inventing evidence.
- Control Plane stores browser-generated replay videos but does not generate or transcode media in Python.
- Browser-visible events and errors are safe projections, not raw internal objects.
- Control Plane never derives workspace configuration or output from its startup directory. Workspace operations and Devices use explicit registered roots and do not require the server to start inside a workspace.
- Generated frontend assets are build artifacts, not source files.
