# Module: playground

## Purpose

Serve a local, single-user FSQ-Agent playground. The playground owns the Python HTTP API and static browser UI for runtime status, session setup, dynamic or strict execution, loading existing run results, progress streaming, YAML display, screenshots, replay video, reports, and completed-run step artifact preview.

The playground is an entry-layer convenience surface. It reuses existing FSQ-Agent execution, configuration, platform harness/tool provider, event, report, and recording contracts rather than implementing a separate agent loop or platform runner.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, `RunEvent`, report artifacts, and shared configuration/error models.
- `config`: Loads settings and applies the same runtime/provider/strict validation policy used by CLI entry points.
- `agent`: Runs dynamic goal/raw-reference tasks through `FsqAgent.run` and receives live events through an event sink.
- `fsq`: Loads strict FSQ YAML cases and converts them into executable steps for strict mode.
- `core`: Uses active platform harnesses, platform CommonTool providers, and driver capabilities for session metadata, screenshot capture, and strict-core step execution.
- `report`: Resolves generated report paths for completed runs.
- External dependencies: PyYAML is used only by playground HTTP display endpoints to parse YAML into a safe presentation model. `ruamel.yaml` is used only for round-trip mutation of editable Input YAML lifecycle metadata. Presentation parsing and round-trip mutation must not replace `fsq` strict case loading, lifecycle validation, or executable-step conversion.
The module must not be imported by `models`, `config`, `providers`, `tools`, `observation`, `knowledge`, `skills`, `fsq`, `core`, `agent`, or `report`. `cli` may import `playground` to expose the public command.

The playground module must not import `capabilities` or decorator internals. It consumes public execution APIs, registry-backed strict adapters, and normalized run events in the same way as CLI entry paths.

## Public Interface

Target `__init__.py` exports via `__all__`:

- `PlaygroundServer`: Local HTTP server wrapper.
- `PlaygroundServerOptions`: Host, port, open-browser flag, and optional static path overrides for tests.
- `run_playground(settings: Settings, options: PlaygroundServerOptions) -> None`: Blocking entry helper used by the CLI command.

Initial HTTP API:

| Endpoint | Behavior |
|---|---|
| `GET /status` | Return server health, selected session summary, and busy flag. |
| `GET /session` | Return current Android session state, or a structured unavailable response when the active platform is not Android. |
| `GET /session/setup` | Return Android setup schema plus discovered ADB targets, or a structured unavailable response when the active platform is not Android. |
| `POST /session/auto` | Automatically select/create an Android session when configuration or device discovery has one unambiguous online target; unavailable for non-Android platforms. |
| `POST /session` | Select/create one Android session by device id when no task is running; unavailable for non-Android platforms. |
| `DELETE /session` | Clear active session metadata when no task is running; unavailable for non-Android platforms. |
| `GET /runtime-info` | Return platform/runtime metadata, preview capability, Android app id presence and selected device id when applicable, Web backend/channel/browser-executable-configured/headless/base URL presence when applicable, macOS backend/Appium-server-configured/bundle-id-presence/app-path-presence when applicable, and last run summary. |
| `GET /yaml/input?path=...` | Resolve an input case YAML path using the same candidate order as execution (`settings.cases.dir`, then current working directory for relative paths; the absolute path directly for absolute paths), enforce a conservative display size limit, read UTF-8 text, validate lifecycle metadata through existing FSQ case models, and return safe metadata, ordered `onCaseStart`/`onCaseComplete` presentation data, source revision, editability, and styled command-display data without executing hooks or commands. Raw YAML text may be returned only as copy-source data and must not be the primary visual presentation. |
| `PUT /yaml/input/lifecycle` | Update only case-level `onCaseStart` and `onCaseComplete` metadata for one safely resolved live Input YAML file. The request supplies the input path, the revision returned by `GET /yaml/input`, and structured ordered hook/action data. The endpoint validates hooks through shared FSQ models, round-trip updates only the first YAML document, validates the complete temporary case through `FsqCaseLoader`, atomically replaces the source, and returns the refreshed Input YAML response. Empty hook lists remove their lifecycle keys. |
| `GET /yaml/recorded/{request_or_run_id}` | Resolve a playground request id to its run id when possible or treat the value as a run id, read run-local `recording.json` metadata and `recorded.codex.yaml` content only from inside `settings.output.runs_dir / run_id`, parse generated YAML only into a presentation model, and return styled-display data or recording status/warnings/errors. Each recorded display step exposes a `displayIndex` for presentation and an `artifactStepId` for querying step artifacts. Artifact step ids are derived by ordered alignment of each authored YAML action alias with persisted successful replay-event aliases; historical successful platform events without replay metadata use `fsq_action_name` as the compatibility alias. Extra events do not shift later matches, and an unmatched step has a null `artifactStepId`. Raw YAML text may be returned only as copy-source data and must not be the primary visual presentation. |
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

`POST /execute` accepts exactly one of `goal`, `caseYamlPath`, or `strictCaseYamlPath`. `goal` constructs a dynamic `Task` equivalent to CLI `--goal`. `caseYamlPath` resolves against `settings.cases.dir` first, then the current working directory, reads the complete UTF-8 file as raw text, and constructs a dynamic raw-case reference task equivalent to CLI non-strict `--case-yaml`; it must not parse YAML into strict executable steps. `strictCaseYamlPath` resolves the same way and executes the complete strict lifecycle through the shared strict lifecycle service and active platform harness. Lifecycle order is config before hooks, case before hooks, main commands, case after hooks, then config after hooks. Lifecycle and main steps share one report and evidence manifest. Playground dynamic execution should attempt post-run recording with `allow_failure=True`, matching CLI `--record --record-on-failure`; strict YAML execution does not record again.

Lifecycle `runCase` uses strict path resolution and recursion detection, and repeated actions preserve authored order. Before-hook failure skips the remaining before/main work as appropriate, while after hooks still execute. Windows `runShell` uses PowerShell; other platforms use the local system shell. Playground cancellation applies throughout lifecycle execution.

`PUT /yaml/input/lifecycle` is a source-editing operation, not an execution path. Each lifecycle field is represented as one ordered list of `runCase`/`runShell` actions; action types may repeat. Playground validates each row through shared FSQ action/hook models and serializes each row as one single-action YAML list item. It must not resolve `runCase` paths, run shell commands, adapt command steps, or execute lifecycle hooks. The server rejects saves while a task is running. The browser disables and blocks saves while a task, completion/replay finalization, or another save is active because replay finalization is browser-local state. The revision is a SHA-256 digest of the exact UTF-8 source bytes returned by `GET /yaml/input`; a mismatch returns `409` without modifying the source.

## Platform Playground Blocks

Shared playground behavior:

- Runtime info reports the active platform and safe backend metadata.
- `/execute`, progress polling, screenshots, replay frames/video, and report lookup route through the active platform execution path.
- Strict execution parses YAML through the active platform registry snapshot containing inherited CommonTools plus active PlatformTools. Authored command names resolve through canonical capability names and active `fsq_command` replay aliases.
- Strict execution always uses the shared lifecycle service, including cases without hooks. Lifecycle, child, and main steps share progress, evidence, report, preview, and replay behavior.
- Existing-run loading is platform-neutral, read-only, and reuses the same report, recorded-YAML, replay, and step-artifact endpoints used after a live completed run.

Android playground behavior:

- Android session/setup endpoints expose ADB discovery and selected device state.
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

Future platform playground behavior:

- New platforms must add endpoint availability rules and preview behavior before being exposed in the playground.

## Internal Structure

- `__init__.py`: Public exports only.
- `_server.py`: Local HTTP server, JSON route dispatch, static serving, lifecycle, safe Input YAML and existing-run path resolution, input presentation shaping, existing-run availability inspection, run-local replay/video/report/artifact resolution, step-artifact response shaping, and dynamic recording option propagation.
- `_yaml_lifecycle.py`: Private Input YAML lifecycle editing service. It validates structured hooks through public FSQ models, computes revisions, performs `ruamel.yaml` round-trip first-document mutation, validates temporary complete cases through `FsqCaseLoader`, preserves unrelated documents and formatting where supported, and atomically replaces source files.
- `_state.py`: In-memory session/task state, one-task lock, progress event buffering with optional sequence-window projection, final result summaries, and request id generation.
- `_android.py`: ADB discovery, setup schema generation, Android session metadata, and screenshot helper boundaries.
- `_recording.py`: Playground-owned dynamic post-run recording adapter around the existing strict case recorder, including recording failure normalization.
- `_execution.py`: Dynamic goal/raw-case execution adapter around `FsqAgent.run`, strict YAML execution adapter around core runner contracts, platform-dispatching harness/backend construction, configured post-action delay settings, event capture, result/report shaping, recording, and error normalization.
- `static/`: Package-owned browser assets.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: `PlaygroundServer`, `PlaygroundServerOptions`, `run_playground`, and the local HTTP endpoints listed in this SPEC.
- Internal modules: `_server.py`, `_state.py`, `_android.py`, `_recording.py`, `_execution.py`, `_yaml_lifecycle.py`, and package-owned static browser assets.
- Domain boundaries: playground owns HTTP/UI behavior, Input YAML lifecycle editing, run-artifact display, execution adaptation, and task/session state. Shared models and `fsq` own lifecycle syntax and case validation; the package-private shared strict lifecycle service owns strict lifecycle execution. Existing-run and step-artifact lookup remain read-only presentation concerns.
- Boundary models: JSON request and response payloads returned by `_server.py`, ordered `FsqCaseHook`/`FsqCaseHookAction` values consumed for lifecycle validation, shared `Settings`, `Task`, `TaskResult`, `RunEvent`, report artifacts, and session/task progress dictionaries.
- Dependency direction: playground may import public APIs from `models`, `config`, `agent`, `fsq`, `core`, and `report`; those modules must not import playground. Playground must not import `capabilities` or decorator internals.
- Rationale: playground coordinates a browser UI, HTTP transport, runtime state, execution adapters, screenshots/replay artifacts, reports, and recording summaries, so Level 3 remains appropriate. YAML display is a presentation and safe artifact-resolution concern inside the existing module and does not justify a new package or stronger architecture.

## Error Handling

The playground returns JSON errors for API failures and does not expose tracebacks by default. Missing goals, missing case YAML paths, unreadable YAML references, ambiguous input bodies, Android-only endpoint use while a non-Android platform is active, ADB discovery errors, missing selected Android device, Web screenshot/runtime construction failures, macOS Appium/runtime construction failures, report resolution failures, and screenshot capture failures must produce concise structured errors. Recording failures must not change the dynamic run status.

YAML display endpoints must return concise structured errors for missing paths, missing files, directory paths, non-UTF-8 reads, display size-limit failures, request ids that cannot resolve to runs, missing run directories, missing `recording.json`, invalid recording metadata, and recorded-case paths that escape the run directory. A skipped or failed recording must be displayed as recording metadata with warnings/errors when available rather than treated as a dynamic run failure. Recorded YAML and loaded-run YAML remain read-only.

Input YAML lifecycle saves must not expose tracebacks or partially update source files. Malformed request data, invalid shared hook models, unsupported YAML document shapes, invalid complete FSQ cases, and serialization failures return `400`. Missing files return `404`. Busy/finalizing state and source revision conflicts return `409`; revision conflicts state that the file changed on disk and require reload. Existing or resulting files above the display/edit size limit return `413`. Atomic-write failures return `500`. The service writes a UTF-8 temporary file in the source directory, validates it through `FsqCaseLoader`, flushes it, and uses `os.replace`; every failure before replacement leaves the source unchanged and cleans up the temporary file.

Existing-run loading must trim and validate the submitted `path`, resolve relative values under the resolved `settings.output.runs_dir`, and allow absolute values only when they resolve to an existing direct child directory of that root. It must reject the runs root itself, nested descendants, files, path or symlink escapes, missing directories, and directories without a recognized run marker. Recognized markers are `report.md`, `report.json`, `core-report.md`, `core-report.json`, `evidence-manifest.json`, `events.jsonl`, `recording.json`, `recorded.codex.yaml`, `playground-replay/replay-manifest.json`, or `playground-replay/replay.webm`. Missing input, invalid directory shape, escapes, and unrecognized directories return structured `400` errors; a missing directory returns `404`.

The successful existing-run response returns `available: true`, the direct-child directory name as `runId`, and an `availability` object. `report` is true when any supported report file is present. `recordedYaml` is true when `recording.json` or `recorded.codex.yaml` is present. `replay` is true when a stored replay manifest/video exists or screenshot replay sources are discoverable from evidence/events metadata. `stepArtifacts` is true when `evidence-manifest.json` or `events.jsonl` is present. These flags report discoverability, not content validity; malformed content is handled independently by its dedicated endpoint and UI surface. The load endpoint must not return report, YAML, screenshot, observation, or video content and must not mutate the run.

Existing-run Progress retrieval must accept only a non-empty direct-child run id, read only `events.jsonl` under that validated run directory, preserve valid event dictionaries and file order, and assign monotonically increasing display sequences only when a sequence is missing, non-integer, or non-positive. Invalid JSON and non-object lines are skipped. A missing event log returns `200` with the run id and an empty `events` list; unsafe or missing run ids return structured errors. The endpoint must not synthesize historical tool calls from reports, evidence manifests, or recording metadata.

Step artifact endpoints are read-only and must read only under the resolved run directory. They must return concise structured errors for unsafe paths, invalid step identifiers, and unsupported artifact content. Event `artifact_refs` are authoritative when present; the legacy singular `artifact_path` is a fallback only and must not add a duplicate screenshot with missing phase metadata when the same path already exists in `artifact_refs`. A text artifact exceeding the display size limit must return an error on that artifact without suppressing other step artifacts such as screenshots. Missing files or no matching artifacts must not imply run failure.

## Testing Contract

- Unit tests cover playground state/session behavior, report lookup, replay/replay-video endpoints, task progress streaming and filtering, cancellation, runtime info, platform-specific setup availability, and strict/dynamic execution adapters.
- Strict lifecycle tests cover ordering, repeated actions, child cases and recursion, failure policy, shell execution, cancellation, unified evidence/progress/preview, and cases without hooks. Existing CLI lifecycle tests remain unchanged and must continue to pass.
- YAML display tests must cover `GET /yaml/input` success with structured metadata, ordered lifecycle, revision/editability, and command-step display data; omitted lifecycle fields; combined hook action order; missing file; directory path; display size-limit behavior; UTF-8 read failures when practical; malformed YAML presentation errors; and path resolution order.
- Input YAML lifecycle save tests must cover adding, editing, deleting, and reordering flat action rows; repeated action types; flattening existing combined mappings in authored order; deleting empty lifecycle keys; preserving the command document and representative comments/key order/quotes/document separators; shared action/hook-model rejection; complete temporary-case validation; stale revision and busy-state rejection; the same cases-dir/current-working-directory/absolute path resolution policy as `GET /yaml/input`; missing/directory/oversized inputs; serialization and atomic-write failure preservation; temporary-file cleanup; and refreshed response/revision generation.
- Recorded YAML tests must cover `GET /yaml/recorded/{request_or_run_id}` with generated content, skipped recording metadata, failed recording metadata, missing run id, path safety for recorded-case paths, and recorded steps exposing `displayIndex` and `artifactStepId`, including ordered alias alignment when persisted events contain extra observation calls, compatibility with historical recorded YAML that contains observation commands, and historical successful platform events with `fsq_action_name` but no replay metadata.
- Existing-run tests must cover `POST /runs/load` with a run id, relative directory, and runs-root-contained absolute directory; complete and partial availability; and rejection of empty input, the runs root, nested directories, files, traversal or symlink escapes where practical, missing directories, and unrecognized directories.
- Existing-run Progress tests must cover event file order, preserving valid sequences, assigning missing or invalid sequences, malformed/non-object line skipping, a missing event log, and unsafe or missing run ids.
- Step artifact tests must cover `GET /step-artifacts/{request_or_run_id}/{step_id_or_index}` success, no-artifacts response, missing run id, path safety, missing files, per-artifact text display size-limit behavior that preserves screenshots, resolving a step by its artifact step id, and suppressing a duplicate legacy `artifact_path` when the same screenshot already exists in phased `artifact_refs`.
- Static UI integration tests must cover YAML section placement, run-mode path input behavior, Input/Recorded tab behavior, structured YAML rendering, ordered Before case/After case lifecycle sections, Save/Discard wiring, client-validation wiring, execution/path-change dirty guards, editing controls hidden for Recorded/loaded-run YAML, recorded YAML loading, strict-run no-recorded-YAML behavior, and the existing-run heading control, inline form, Enter/Cancel behavior, disabled state, local errors, failed-load preservation, and Clear reset. Executable Node tests for the dependency-free lifecycle draft model must cover hook/action add, edit, delete, reorder, validation, and snapshot restoration used by Discard. HTTP integration tests cover successful Save and stale-save draft-preserving error responses. Browser verification through the available VS Code Playwright tooling must cover rendered lifecycle sections, draft Add/Edit/Discard state transitions, Save enablement, and no overlap or horizontal overflow at desktop and narrow viewports; the project does not add a browser binary dependency to its core dev test environment for this cycle.
- Static step-artifact UI tests must cover completed-run step-card artifact preview, running Preview remaining unchanged, screenshot and structured-artifact rendering, missing artifact kinds not rendering empty regions, Clear/new execution reset, and case title clicks showing completed-run replay video only after execution.
- Verification command: `python -m pytest tests/test_playground.py`.

## Design Decisions

### Execution and Ownership

- Goal, YAML, and Strict YAML preserve the corresponding CLI execution semantics: dynamic goal task construction, non-strict raw UTF-8 YAML reference material, and registry-backed deterministic strict execution with core evidence reporting.
- Capability declaration and discovery remain bootstrap concerns. Playground consumes validated registry metadata, public execution APIs, and normalized results rather than decorator internals or platform action catalogs.
- Completed dynamic runs use post-run recording with `allow_failure=True`; recording failure does not change execution status.

### Progress and Workspace State

- Progress delivery is incremental. Server-Sent Events are preferred, sequence-based polling is the fallback, and the browser appends new events without rebuilding existing history. Cancellation status is delivered through the same progress channel.
- The desktop UI uses a persisted resizable two-column workspace: mode-specific YAML/Progress views on the left and Preview/Report on the right. Execution starts in Preview while progress continues independently.
- Left-side tab availability and defaults follow run mode: Goal exposes Progress and Recorded, YAML exposes Progress, Input, and Recorded, and Strict YAML exposes Input and Progress. Each mode preserves its own view state, and generated recording content does not force tab selection.
- Strict execution exposes current-step metadata for Input YAML highlighting without synthesizing tool-call events from core step lifecycle events. Dynamic YAML does not mutate Input step state. Run-mode and artifact navigation changes are blocked while execution or replay finalization is active.
- Recorded YAML and loaded-run YAML remain read-only structured presentations and do not render lifecycle editor sections in this cycle. Ordinary command cards render under a `Case steps` heading. Live Input YAML renders case-level `onCaseStart` before Case steps and `onCaseComplete` after them. Only lifecycle action rows are editable; metadata and Case steps remain read-only. Loading and save errors appear once in the YAML status surface rather than inside viewer content.
- Input lifecycle edits are browser-local drafts. `Before case` and `After case` each contain one flat ordered action list. Users can add, edit, delete, and reorder action rows; `runCase` and `runShell` may each appear multiple times. Save and Discard are document-level controls; Save is enabled for dirty drafts and performs client validation when clicked, showing validation errors only then. During execution, completion/replay finalization, or an active save, all lifecycle action menus, value inputs, add/delete/reorder controls, Save, and Discard are disabled. Discard restores the last server snapshot. Starting execution or changing/reloading the YAML path while dirty requires Save or Discard; Clear discards the draft.
- Saving lifecycle drafts sends structured hook data plus the loaded source revision. Empty lifecycle sections remove their keys. Existing lifecycle key position is preserved where practical; newly inserted lifecycle keys are ordered `onCaseStart` before `onCaseComplete` around the case metadata boundary. Single-mapping lifecycle shorthand may normalize to list form after an edit. Unedited files are never rewritten.
- The `YAML` heading exposes a `Load Run` workspace command that expands an inline run-directory input with Load and Cancel commands. Enter submits the form. The control is disabled during active execution or completion/replay finalization, does not add or change an execution mode, and only replaces the displayed completed-run state after server validation succeeds.
- A loaded existing run is a completed-run state without an active request. The browser sets its normalized Run ID, retrieves persisted Progress events, and renders every event through the same `eventLabel`, `eventDetails`, `eventStatus`, sequence, selection, and detail presentation used by live Progress. It defaults the right side to Preview and independently loads each discoverable Report, replay, Recorded YAML, and step-artifact surface through existing content endpoints. Recorded YAML loading for an existing run is not suppressed by the currently selected execution form mode. A run without persisted Progress events shows a concise empty state rather than a synthetic summary. Missing or malformed individual surfaces show local unavailable/error states without invalidating the loaded run or other surfaces.
- Failed existing-run validation preserves the currently displayed result and reports the error in the inline load form. Cancel preserves the displayed result and collapses the form. Clear removes the loaded-run state, resets and collapses the form, and restores the empty workspace; starting a new execution replaces the loaded completed-run presentation through the existing run-start reset behavior.

### Preview and Artifacts

- Completed runs use persisted screenshots as replay-video input and show available replay video in Preview with native playback and seeking controls. Replay remains automatic rather than a separate manual action, and stored video supports HTTP range requests.
- Completed Strict Input and Recorded step cards open their artifacts in Preview; dynamic Input cards do not. Screenshots precede structured artifacts, absent artifact kinds do not create empty regions, and selecting the case title returns to the completed replay-video view.
- Before/After screenshots default to a centered, complete side-by-side comparison on a neutral backdrop. Screenshot and UI Tree regions resize independently from their boundaries; resizing is continuous, preserves horizontal comparison, and uses scrolling for overflow.
- Before/after automatic platform observations render as normalized `ui_snapshot` artifacts and may render as a read-only full-content diff with line-level added/removed highlighting and inline highlighting for paired changed lines. Explicit observation command outputs such as Android `uiTree`, Web `pageSnapshot`, and desktop `uiSnapshot` remain supported when they appear as step artifacts.
- Input lifecycle sections use compact un-nested editing surfaces between case metadata and ordinary commands. Action type uses a menu, action value uses a single-line input, and add/delete/reorder controls use familiar icons with tooltips and accessible labels. Controls must remain usable without overlap in the resizable desktop layout and narrow viewport.
