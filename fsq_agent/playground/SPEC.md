# Module: playground

## Purpose

Serve the Python runtime boundary for the local, single-user FSQ-Agent Playground after CLI has resolved one explicit registered workspace and configured platform. The module owns the HTTP API, server-side session and task state, execution adaptation, safe platform-scoped YAML and run-artifact access, replay persistence, production static serving, and package integration.

The authored browser application and browser-local interaction state are owned by `frontend/playground/SPEC.md`. This Python module is an entry-layer convenience surface that reuses existing FSQ-Agent execution, configuration, platform harness/tool provider, event, report, and recording contracts rather than implementing a separate agent loop or platform runner.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, `RunEvent`, report artifacts, and shared configuration/error models.
- `config`: Receives validated workspace-platform startup settings, refreshes only the user-provider portion at each complete execution boundary, and applies the same runtime/provider/strict validation policy used by CLI entry points.
- `providers`: Builds the provider-backed AI assertion evaluator used by configured dynamic and strict execution.
- `agent`: Runs dynamic goal/raw-reference tasks through `FsqAgent.run` and receives live events through an event sink.
- `fsq`: Loads strict FSQ YAML cases and converts them into executable steps for strict mode.
- `core`: Uses shared Android device discovery, active platform harnesses, platform CommonTool providers, and driver capabilities for session metadata, screenshot capture, and strict-core step execution.
- `report`: Resolves generated report paths for completed runs.
- Package-private entry-layer helpers: `fsq_agent._capability_bootstrap` builds the active capability registry, `fsq_agent._strict_lifecycle` collects and runs shared strict lifecycle cases, and `fsq_agent._strict_case_recording` is consumed through the Playground recording adapter.
- External dependencies: Pydantic supplies validation errors at the execution boundary. PyYAML is used only by playground HTTP display endpoints to parse YAML into a safe presentation model. `ruamel.yaml` is used only for round-trip mutation of editable Input YAML lifecycle metadata. Presentation parsing and round-trip mutation must not replace `fsq` strict case loading, lifecycle validation, or executable-step conversion. Generated browser assets are supplied by the frontend workspace at the package/static-serving boundary; Python runtime code does not depend on Node.js or authored frontend modules.
The module must not be imported by `models`, `config`, `providers`, `tools`, `observation`, `knowledge`, `skills`, `fsq`, `core`, `agent`, or `report`. `cli` may import `playground` to expose the public command.

The playground module must not import `capabilities` or decorator internals. It consumes public execution APIs, registry-backed strict adapters, and normalized run events in the same way as CLI entry paths.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `PlaygroundServer`: Local HTTP server wrapper.
- `PlaygroundServerOptions`: Host, port, open-browser flag, and optional static path overrides for tests.
- `run_playground(settings: Settings, options: PlaygroundServerOptions) -> None`: Blocking entry helper used by the CLI command after explicit workspace/platform resolution. It does not discover or select a workspace or platform.

Initial HTTP API:

| Endpoint | Behavior |
|---|---|
| `GET /status` | Return server health, selected session summary, and busy flag. |
| `GET /session` | Return current Android session state, or a structured unavailable response when the active platform is not Android. |
| `GET /session/setup` | Return Android setup schema plus discovered ADB targets, or a structured unavailable response when the active platform is not Android. |
| `POST /session/auto` | Automatically select/create an Android session only when device discovery has one unambiguous online target; unavailable for non-Android platforms. |
| `POST /session` | Select/create one Android session by device id when no task is running; unavailable for non-Android platforms. |
| `DELETE /session` | Clear active session metadata when no task is running; unavailable for non-Android platforms. |
| `GET /runtime-info` | Return platform/runtime metadata, preview capability, Android app id presence and selected device id when applicable, Web backend/channel/browser-executable-configured/headless/base URL presence when applicable, macOS backend/Appium-server-configured/bundle-id-presence/app-path-presence when applicable, and last run summary. Android runtime info has no configured/default serial member. |
| `GET /yaml/input?path=...` | Resolve an input case YAML path inside `settings.cases.dir`, enforce containment and a conservative display size limit, read UTF-8 text, validate lifecycle metadata through existing FSQ case models, and return safe metadata, ordered `onCaseStart`/`onCaseComplete` presentation data, source revision, editability, and styled command-display data without executing hooks or commands. Raw YAML text may be returned only as copy-source data and must not be the primary visual presentation. |
| `PUT /yaml/input/lifecycle` | Update only case-level `onCaseStart` and `onCaseComplete` metadata for one safely resolved live Input YAML file. The request supplies the input path, the revision returned by `GET /yaml/input`, and structured ordered hook/action data. The endpoint validates hooks through shared FSQ models, round-trip updates only the first YAML document, validates the complete temporary case through `FsqCaseLoader`, atomically replaces the source, and returns the refreshed Input YAML response. Empty hook lists remove their lifecycle keys. |
| `GET /yaml/recorded/{request_or_run_id}` | Resolve a playground request id to its run id when possible or treat the value as a run id, read run-local `recording.json` metadata and `recorded.fsq.yaml` content only from inside `settings.output.runs_dir / run_id`, parse generated YAML only into a presentation model, and return styled-display data or recording status/warnings/errors. Each recorded display step exposes a `displayIndex` for presentation and an `artifactStepId` for querying step artifacts. Artifact step ids are derived by ordered alignment of each authored YAML action alias with persisted successful replay-event aliases; historical successful platform events without replay metadata use `fsq_action_name` as the compatibility alias. Extra events do not shift later matches, and an unmatched step has a null `artifactStepId`. Raw YAML text may be returned only as copy-source data and must not be the primary visual presentation. |
| `POST /runs/load` | Resolve a user-supplied run id, runs-root-relative directory, or runs-root-contained absolute directory to one existing direct child of `settings.output.runs_dir`; reject files, the runs root, escapes, missing directories, and unrecognized directories; and return the normalized run id plus report, recorded-YAML, replay, and step-artifact availability metadata without aggregating artifact content. |
| `GET /runs/{run_id}/progress` | Resolve one direct-child run id under `settings.output.runs_dir` and return valid persisted `RunEvent` dictionaries from its run-local `events.jsonl` in file order for the same Progress presentation used during live execution. Invalid JSON and non-object lines are skipped, missing or non-positive sequences are assigned monotonically, and a missing event log returns an empty event list. |
| `POST /execute` | Start one dynamic goal, raw YAML-reference, or strict YAML execution and return a request id immediately. |
| `POST /cancel/{request_id}` | Request cooperative cancellation for the currently running task and return the updated task state. |
| `GET /task-progress/{request_id}` | Return progress and final result metadata for one request id. Without query parameters it returns accumulated events for compatibility; with `after_sequence` it returns only events whose sequence is greater than the supplied value so browser polling can append new progress without re-rendering history. |
| `GET /task-stream/{request_id}` | Server-Sent Events stream of the same progress payloads. Emits a `data:` event whenever new progress is available and closes once the task leaves `running`. Honors `after_sequence` to resume. Polling `/task-progress` remains the fallback. |
| `GET /screenshot` | Return an active-platform base64 screenshot and timestamp when available, or a structured unavailable/error response. |
| `GET /replay/{request_or_run_id}` | Return persisted timestamped screenshot frames for one playground request id or run id, including the frame index, source path when available, and base64 screenshot bytes used by browser replay-video generation. A known request/run with no captured frames returns `200` with `available: false` and an empty frame list; an unknown id returns `404`. |
| `GET /replay-video/{request_or_run_id}` | Return metadata for a stored run-local replay video when available. |
| `POST /replay-video/{request_or_run_id}` | Store a browser-generated run-local replay video. |
| `GET /replay-video-file/{request_or_run_id}` | Return the generated replay video bytes for browser playback. Honors HTTP `Range` requests (responds `206 Partial Content` with `Content-Range` and `Accept-Ranges: bytes`) so the browser can seek inside the WebM. |
| `GET /step-artifacts/{request_or_run_id}/{step_id_or_index}` | Resolve one completed-run step and return safe run-local artifacts for that step. A step-id selector resolves strictly against artifact and event step ids; a numeric selector resolves against evidence step indices. Strict YAML uses evidence step ids; dynamic raw-YAML may best-effort use runner metadata. The endpoint returns screenshot and supported text artifacts, or a structured no-artifacts response. |
| `GET /reports/{run_id}` | Resolve a stored Markdown or JSON report for one run id and return safe metadata or content. |

`POST /execute` accepts exactly one of `goal`, `caseYamlPath`, or `strictCaseYamlPath`. `goal` constructs a dynamic `Task` equivalent to CLI `--goal`. Case paths must identify exact lowercase `.fsq.yaml` files contained below the selected platform's resolved `settings.cases.dir`; the same boundary applies to Input YAML display/edit and strict lifecycle `runCase` dependencies. Dynamic case input is read as complete UTF-8 raw reference text and is not parsed into strict steps. Strict case input executes through the shared lifecycle service and active platform harness. Lifecycle and main steps share one report and evidence manifest. Playground dynamic execution attempts post-run recording with `allow_failure=True`; strict YAML execution does not record again.

At the beginning of every accepted `/execute`, Playground copies its startup settings and refreshes only the user-provider snapshot before validating or constructing provider-dependent runtime objects. The server's selected workspace/platform identity, platform-config-derived target/secrets, session metadata, cases/knowledge/runs roots, and all other runtime policy remain unchanged for its lifetime. The refreshed snapshot is frozen for that complete execution; Provider changes do not alter a preparing/running/finalizing task.

Lifecycle `runCase` uses strict path resolution and recursion detection, and repeated actions preserve authored order. Before-hook failure skips the remaining before/main work as appropriate, while after hooks still execute. Windows `runShell` uses PowerShell; other platforms use the local system shell. Playground cancellation applies throughout lifecycle execution.

`PUT /yaml/input/lifecycle` is a source-editing operation, not an execution path. Each lifecycle field is represented as one ordered list of `runCase`/`runShell` actions; action types may repeat. Playground validates each row through shared FSQ action/hook models and serializes each row as one single-action YAML list item. It must not resolve `runCase` paths, run shell commands, adapt command steps, or execute lifecycle hooks. The server rejects saves while a task is running. The revision is a SHA-256 digest of the exact UTF-8 source bytes returned by `GET /yaml/input`; a mismatch returns `409` without modifying the source.

## Platform Playground Blocks

Shared playground behavior:

- Runtime info reports the active platform and safe backend metadata.
- Dynamic and strict execution use the selected platform's private runtime secret store as CLI execution. Playground may expose configured names but never values. Platform target/secret changes require restart; saved Provider changes are captured by the next `/execute` without restart.
- `/execute`, progress polling, screenshots, replay frames/video, and report lookup route through the active platform execution path.
- Strict execution parses YAML through the active platform registry snapshot containing inherited CommonTools plus active PlatformTools. Authored command names resolve through canonical capability names and active `fsq_command` replay aliases.
- Strict execution always uses the shared lifecycle service, including cases without hooks. Lifecycle, child, and main steps share progress, evidence, report, preview, and replay behavior.
- Existing-run loading is platform-neutral, read-only, and reuses the same report, recorded-YAML, replay, and step-artifact endpoints used after a live completed run.

Android playground behavior:

- Android session/setup endpoints project the public `core` Android discovery result into Playground targets and selected device state. They have no configured serial source and mark a discovery default only when exactly one online device is selectable.
- Android screenshot preview uses the Android harness/driver screenshot path.

Web playground behavior:

- Android session/setup endpoints return structured unavailable responses when Web is active.
- Web runtime info reports backend, channel, browser executable configured state, headless mode, and base URL presence.
- Web dynamic and strict execution construct the active harness through `HarnessFactory` and the config-selected Web backend driver without launching a browser; `startBrowser` and `closeBrowser` remain explicit task/FSQ capabilities and are not injected by playground routes.
- Web screenshot preview uses the active Web harness/driver screenshot path when a page is started and returns a structured unavailable/error response before `startBrowser` or after `closeBrowser`.

Windows playground behavior:

- Android session/setup endpoints return structured unavailable responses when Windows is active.
- Windows runtime info reports backend, pywinauto backend kind, app path configured state, window title regex presence, launch-args count, busy state, and last-run summary.
- Windows dynamic and strict execution construct the active harness through `HarnessFactory` and the config-selected Windows backend driver without launching the app during route setup, registry bootstrap, or YAML parsing; `launchApp` and `killApp` remain explicit task/FSQ capabilities and are not injected by playground routes.
- Windows strict execution parses replay aliases such as `launchApp`, `clickOn`, `typeText`, `pressKey`, `uiSnapshot`, `assertVisible`, and `assertWithAI` through the Windows registry snapshot.
- Windows screenshot preview uses the active Windows harness/driver screenshot path when a pywinauto window is available and returns a structured unavailable/error response before `launchApp` or after app cleanup.

macOS playground behavior:

- Android session/setup endpoints return structured unavailable responses when macOS is active.
- macOS runtime info reports backend, Appium server configured state, bundle id presence, app path presence, busy state, and last-run summary.
- macOS dynamic and strict execution construct the active harness through `HarnessFactory` and the config-selected macOS backend driver without connecting to Appium or launching the app during route setup; `launchApp` and `killApp` remain explicit task/FSQ capabilities and are not injected by playground routes.
- macOS screenshot preview uses the active macOS harness/driver screenshot path when a Mac2 session exists and returns a structured unavailable/error response before `launchApp` or after session cleanup.
- macOS strict execution parses replay aliases such as `clickOn`, `typeText`, `uiSnapshot`, `assertVisible`, `assertElementsOrder`, and `assertWithAI` through the macOS registry snapshot.

## Internal Structure

- `__init__.py`: Public exports only.
- `_server.py`: Local HTTP server, JSON route dispatch, static serving, lifecycle, safe Input YAML and existing-run path resolution, input presentation shaping, existing-run availability inspection, run-local replay/video/report/artifact resolution, step-artifact response shaping, and dynamic recording option propagation.
- `_yaml_lifecycle.py`: Private Input YAML lifecycle editing service. It validates structured hooks through public FSQ models, computes revisions, performs `ruamel.yaml` round-trip first-document mutation, validates temporary complete cases through `FsqCaseLoader`, preserves unrelated documents and formatting where supported, and atomically replaces source files.
- `_state.py`: In-memory session/task state, one-task lock, progress event buffering with optional sequence-window projection, final result summaries, and request id generation.
- `_android.py`: Playground target/error projection over shared `core` Android discovery, setup schema generation, Android session metadata, and screenshot helper boundaries.
- `_recording.py`: Playground-owned dynamic post-run recording adapter around package-private `fsq_agent._strict_case_recording`, including recording failure normalization.
- `_execution.py`: Provider-only settings refresh at the complete-task boundary, dynamic goal/raw-case execution adapter around `FsqAgent.run`, strict YAML execution adapter around core runner contracts, platform-dispatching harness/backend construction, configured post-action delay settings, event capture, result/report shaping, recording, and error normalization.
- `static/`: Untracked Vite-generated production assets included as Python package data and served by the Playground HTTP server. Authored source ownership is defined by `frontend/playground/SPEC.md`.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: `PlaygroundServer`, `PlaygroundServerOptions`, `run_playground`, and the local HTTP endpoints listed in this SPEC.
- Internal modules: `_server.py`, `_state.py`, `_android.py`, `_recording.py`, `_execution.py`, `_yaml_lifecycle.py`, and generated package assets under `static`.
- Domain boundaries: playground owns HTTP behavior, Input YAML lifecycle editing, safe run-artifact lookup, replay persistence, execution adaptation, and task/session state. Shared models and `fsq` own lifecycle syntax and case validation; the package-private shared strict lifecycle service owns strict lifecycle execution. The frontend Playground module owns browser-local rendering, view state, interaction, and replay generation.
- Boundary models: JSON request and response payloads returned by `_server.py`, ordered `FsqCaseHook`/`FsqCaseHookAction` values consumed for lifecycle validation, shared `Settings`, `Task`, `TaskResult`, `RunEvent`, report artifacts, and session/task progress dictionaries.
- Dependency direction: playground may import public APIs from `models`, `config`, `providers`, `agent`, `fsq`, `core`, and `report`, plus package-private entry-layer composition from `fsq_agent._capability_bootstrap`, `fsq_agent._strict_lifecycle`, and `fsq_agent._strict_case_recording`; those modules must not import playground. Playground must not import CLI-private modules, `capabilities`, decorator internals, or authored frontend source. Python runtime code consumes generated assets only at the packaging and static-serving boundary.
- Rationale: playground coordinates HTTP transport, runtime state, execution adapters, filesystem-safe artifact access, replay persistence, reports, and recording summaries, so Level 3 remains appropriate. Browser-local application behavior is a separate frontend ownership boundary and does not require another Python layer.

## Error Handling

The playground returns JSON errors for API failures and does not expose tracebacks by default. Missing goals, missing case YAML paths, unreadable YAML references, ambiguous input bodies, Android-only endpoint use while a non-Android platform is active, ADB discovery errors, missing selected Android device, Web screenshot/runtime construction failures, macOS Appium/runtime construction failures, report resolution failures, and screenshot capture failures must produce concise structured errors. Recording failures must not change the dynamic run status.

Playground startup requires the generated static root and production entry. When either is absent in a source checkout, startup fails before binding the HTTP server with a concise instruction to run `npm ci` and `npm run build`. Installed wheels contain the generated assets and do not require Node.js at runtime.

YAML display endpoints must return concise structured errors for missing paths, missing files, directory paths, non-UTF-8 reads, display size-limit failures, request ids that cannot resolve to runs, missing run directories, missing `recording.json`, invalid recording metadata, and recorded-case paths that escape the run directory. A skipped or failed recording must be displayed as recording metadata with warnings/errors when available rather than treated as a dynamic run failure. Recorded YAML and loaded-run YAML remain read-only.

Input YAML lifecycle saves must not expose tracebacks or partially update source files. Malformed request data, invalid shared hook models, unsupported YAML document shapes, invalid complete FSQ cases, and serialization failures return `400`. Missing files return `404`. Busy/finalizing state and source revision conflicts return `409`; revision conflicts state that the file changed on disk and require reload. Existing or resulting files above the display/edit size limit return `413`. Atomic-write failures return `500`. The service writes a UTF-8 temporary file in the source directory, validates it through `FsqCaseLoader`, flushes it, and uses `os.replace`; every failure before replacement leaves the source unchanged and cleans up the temporary file.

Existing-run loading must trim and validate the submitted `path`, resolve relative values under the resolved `settings.output.runs_dir`, and allow absolute values only when they resolve to an existing direct child directory of that root. It must reject the runs root itself, nested descendants, files, path or symlink escapes, missing directories, and directories without a recognized run marker. Recognized markers are `report.md`, `report.json`, `core-report.md`, `core-report.json`, `evidence-manifest.json`, `events.jsonl`, `recording.json`, `recorded.fsq.yaml`, `playground-replay/replay-manifest.json`, or `playground-replay/replay.webm`. Missing input, invalid directory shape, escapes, and unrecognized directories return structured `400` errors; a missing directory returns `404`.

The successful existing-run response returns `available: true`, the direct-child directory name as `runId`, and an `availability` object. `report` is true when any supported report file is present. `recordedYaml` is true when `recording.json` or `recorded.fsq.yaml` is present. `replay` is true when a stored replay manifest/video exists or screenshot replay sources are discoverable from evidence/events metadata. `stepArtifacts` is true when `evidence-manifest.json` or `events.jsonl` is present. These flags report discoverability, not content validity; malformed content is handled independently by its dedicated endpoint and UI surface. The load endpoint must not return report, YAML, screenshot, observation, or video content and must not mutate the run.

Existing-run Progress retrieval must accept only a non-empty direct-child run id, read only `events.jsonl` under that validated run directory, preserve valid event dictionaries and file order, and assign monotonically increasing display sequences only when a sequence is missing, non-integer, or non-positive. Invalid JSON and non-object lines are skipped. A missing event log returns `200` with the run id and an empty `events` list; unsafe or missing run ids return structured errors. The endpoint must not synthesize historical tool calls from reports, evidence manifests, or recording metadata.

Step artifact endpoints are read-only and must read only under the resolved run directory. They must return concise structured errors for unsafe paths, invalid step identifiers, and unsupported artifact content. Event `artifact_refs` are authoritative when present; the legacy singular `artifact_path` is a fallback only and must not add a duplicate screenshot with missing phase metadata when the same path already exists in `artifact_refs`. A text artifact exceeding the display size limit must return an error on that artifact without suppressing other step artifacts such as screenshots. Missing files or no matching artifacts must not imply run failure.

## Verification Scope

- Verification covers playground state/session behavior, runtime info, dynamic and strict execution adapters, strict lifecycle execution, Input YAML lifecycle display/save behavior, progress delivery, cancellation, report lookup, recorded YAML display, existing-run loading, replay/video endpoints, and step-artifact preview.
- Boundary verification ensures the server accepts an already resolved explicit workspace/platform context; all case/lifecycle paths remain in that platform's cases root; all run and artifact endpoints remain in that platform's run root and stay read-only where specified; YAML lifecycle saves are atomic and revision-checked; unsafe paths are rejected; secret redaction is preserved; and dynamic raw YAML display remains separate from strict YAML execution.
- Frontend integration verification ensures Python static serving resolves the generated assets, missing generated output fails with the documented build instruction, API/SSE/binary/range contracts remain consumable by the browser application, and a built wheel runs the Playground without Node.js. Frontend source and build verification are owned by `frontend/SPEC.md` and `frontend/playground/SPEC.md`.

## Current Invariants

### Execution and Ownership

- Goal, YAML, and Strict YAML preserve the corresponding CLI execution semantics: dynamic goal task construction, non-strict raw UTF-8 YAML reference material, and registry-backed deterministic strict execution with core evidence reporting.
- Each `/execute` captures the latest complete Provider snapshot while preserving startup workspace/platform/config/session/path policy. Active tasks never change Provider in place, and Playground never infers or switches platform.
- Capability declaration and discovery remain bootstrap concerns. Playground consumes validated registry metadata, public execution APIs, and normalized results rather than decorator internals or platform action catalogs.
- Completed dynamic runs use post-run recording with `allow_failure=True`; recording failure does not change execution status.
- Authored browser source and npm dependencies are owned by `frontend/SPEC.md` and `frontend/playground/SPEC.md`. The Python package owns production serving of generated assets; generated bundles are package data rather than authored or tracked source.
