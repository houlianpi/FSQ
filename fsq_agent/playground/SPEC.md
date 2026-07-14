# Module: playground

## Purpose

Serve a local, single-user FSQ-Agent playground. The playground owns the Python HTTP API and static browser UI for runtime status, session setup, dynamic or strict execution, progress streaming, YAML display, screenshots, replay video, reports, and completed-run step artifact preview.

The playground is an entry-layer convenience surface. It reuses existing FSQ-Agent execution, configuration, platform harness/tool provider, event, report, and recording contracts rather than implementing a separate agent loop or platform runner.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, `RunEvent`, report artifacts, and shared configuration/error models.
- `config`: Loads settings and applies the same runtime/provider/strict validation policy used by CLI entry points.
- `agent`: Runs dynamic goal/raw-reference tasks through `FsqAgent.run` and receives live events through an event sink.
- `fsq`: Loads strict FSQ YAML cases and converts them into executable steps for strict mode.
- `core`: Uses active platform harnesses, platform CommonTool providers, and driver capabilities for session metadata, screenshot capture, and strict-core step execution.
- `report`: Resolves generated report paths for completed runs.
- External dependency: PyYAML is used only by playground HTTP display endpoints to parse YAML into a safe presentation model; this display parsing must not replace `fsq` strict case loading or executable-step conversion.
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
| `GET /yaml/input?path=...` | Resolve an input case YAML path using the same candidate order as execution (`settings.cases.dir`, then current working directory for relative paths; the absolute path directly for absolute paths), enforce a conservative display size limit, read UTF-8 text, parse it only into a presentation model, and return safe metadata plus styled-display data without executing, mutating, or parsing dynamic raw YAML as strict executable steps. Raw YAML text may be returned only as copy-source data and must not be the primary visual presentation. |
| `GET /yaml/recorded/{request_or_run_id}` | Resolve a playground request id to its run id when possible or treat the value as a run id, read run-local `recording.json` metadata and `recorded.codex.yaml` content only from inside `settings.output.runs_dir / run_id`, parse generated YAML only into a presentation model, and return styled-display data or recording status/warnings/errors. Each recorded display step exposes a `displayIndex` for presentation and an `artifactStepId` for querying step artifacts, with `artifactStepId` null when it cannot be derived. Raw YAML text may be returned only as copy-source data and must not be the primary visual presentation. |
| `POST /execute` | Start one dynamic goal, raw YAML-reference, or strict YAML execution and return a request id immediately. |
| `POST /cancel/{request_id}` | Request cooperative cancellation for the currently running task and return the updated task state. |
| `GET /task-progress/{request_id}` | Return progress and final result metadata for one request id. Without query parameters it returns accumulated events for compatibility; with `after_sequence` it returns only events whose sequence is greater than the supplied value so browser polling can append new progress without re-rendering history. |
| `GET /task-stream/{request_id}` | Server-Sent Events stream of the same progress payloads. Emits a `data:` event whenever new progress is available and closes once the task leaves `running`. Honors `after_sequence` to resume. Polling `/task-progress` remains the fallback. |
| `GET /screenshot` | Return an active-platform base64 screenshot and timestamp when available, or a structured unavailable/error response. |
| `GET /replay/{request_or_run_id}` | Return persisted timestamped screenshot frames for one playground request id or run id, including the frame index, source path when available, and base64 screenshot bytes used by browser replay-video generation. |
| `GET /replay-video/{request_or_run_id}` | Return metadata for a stored run-local replay video when available. |
| `POST /replay-video/{request_or_run_id}` | Store a browser-generated run-local replay video. |
| `GET /replay-video-file/{request_or_run_id}` | Return the generated replay video bytes for browser playback. Honors HTTP `Range` requests (responds `206 Partial Content` with `Content-Range` and `Accept-Ranges: bytes`) so the browser can seek inside the WebM. |
| `GET /step-artifacts/{request_or_run_id}/{step_id_or_index}` | Resolve one completed-run step and return safe run-local artifacts for that step. A step-id selector resolves strictly against artifact and event step ids; a numeric selector resolves against evidence step indices. Strict YAML uses evidence step ids; dynamic raw-YAML may best-effort use runner metadata. The endpoint returns screenshot and supported text artifacts, or a structured no-artifacts response. |
| `GET /reports/{run_id}` | Resolve a stored Markdown or JSON report for one run id and return safe metadata or content. |

`POST /execute` accepts exactly one of `goal`, `caseYamlPath`, or `strictCaseYamlPath`. `goal` constructs a dynamic `Task` equivalent to CLI `--goal`. `caseYamlPath` resolves against `settings.cases.dir` first, then the current working directory, reads the complete UTF-8 file as raw text, and constructs a dynamic raw-case reference task equivalent to CLI non-strict `--case-yaml`; it must not parse YAML into strict executable steps. `strictCaseYamlPath` resolves the same way but parses the YAML through the platform-selected registry, resolves strict replay references, executes steps through the deterministic core runner and active platform harness/tool provider using `settings.execution.post_action_delay_seconds`, and writes `core-report.md/json` plus `evidence-manifest.json` with capability-derived evidence artifacts and post-action stabilization from `StepRunner`. Playground dynamic execution should attempt post-run recording with `allow_failure=True`, matching CLI `--record --record-on-failure`; strict YAML execution does not record again.

## Platform Playground Blocks

Shared playground behavior:

- Runtime info reports the active platform and safe backend metadata.
- `/execute`, progress polling, screenshots, replay frames/video, and report lookup route through the active platform execution path.
- Strict execution parses YAML through the active platform registry snapshot containing inherited CommonTools plus active PlatformTools. Authored command names resolve through canonical capability names and active `fsq_command` replay aliases.

Android playground behavior:

- Android session/setup endpoints expose ADB discovery and selected device state.
- Android screenshot preview uses the Android harness/driver screenshot path.

Web playground behavior:

- Android session/setup endpoints return structured unavailable responses when Web is active.
- Web runtime info reports backend, channel, browser executable configured state, headless mode, and base URL presence.
- Web dynamic and strict execution construct `WebHarness`/`PlaywrightWebDriver` without launching a browser; `startBrowser` and `closeBrowser` remain explicit task/FSQ capabilities and are not injected by playground routes.
- Web screenshot preview uses the active Web harness/driver screenshot path when a page is started and returns a structured unavailable/error response before `startBrowser` or after `closeBrowser`.

Windows playground behavior:

- Android session/setup endpoints return structured unavailable responses when Windows is active.
- Windows runtime info reports backend, pywinauto backend kind, app path configured state, window title regex presence, launch-args count, busy state, and last-run summary.
- Windows dynamic and strict execution construct `WindowsHarness`/`PywinautoWindowsDriver` without launching the app during route setup, registry bootstrap, or YAML parsing; `launchApp` and `killApp` remain explicit task/FSQ capabilities and are not injected by playground routes.
- Windows strict execution parses replay aliases such as `launchApp`, `clickOn`, `typeText`, `pressKey`, `uiSnapshot`, `assertVisible`, and `assertWithAI` through the Windows registry snapshot.
- Windows screenshot preview uses the active Windows harness/driver screenshot path when a pywinauto window is available and returns a structured unavailable/error response before `launchApp` or after app cleanup.

macOS playground behavior:

- Android session/setup endpoints return structured unavailable responses when macOS is active.
- macOS runtime info reports backend, Appium server configured state, bundle id presence, app path presence, busy state, and last-run summary.
- macOS dynamic and strict execution construct `MacOSHarness`/`AppiumMac2Driver` without connecting to Appium or launching the app during route setup; `launchApp` and `killApp` remain explicit task/FSQ capabilities and are not injected by playground routes.
- macOS screenshot preview uses the active macOS harness/driver screenshot path when a Mac2 session exists and returns a structured unavailable/error response before `launchApp` or after session cleanup.
- macOS strict execution parses replay aliases such as `clickOn`, `typeText`, `uiSnapshot`, `assertVisible`, `assertElementsOrder`, and `assertWithAI` through the macOS registry snapshot.

Future platform playground behavior:

- New platforms must add endpoint availability rules and preview behavior before being exposed in the playground.

## Internal Structure

- `__init__.py`: Public exports only.
- `_server.py`: Local HTTP server, JSON route dispatch, static serving, lifecycle, safe path handling, run-local replay/video/report/artifact resolution, step-artifact response shaping, and dynamic recording option propagation.
- `_state.py`: In-memory session/task state, one-task lock, progress event buffering with optional sequence-window projection, final result summaries, and request id generation.
- `_android.py`: ADB discovery, setup schema generation, Android session metadata, and screenshot helper boundaries.
- `_recording.py`: Playground-owned dynamic post-run recording adapter around the existing strict case recorder, including recording failure normalization.
- `_execution.py`: Dynamic goal/raw-case execution adapter around `FsqAgent.run`, strict YAML execution adapter around core runner contracts, platform-dispatching harness/backend construction, configured post-action delay settings, event capture, result/report shaping, recording, and error normalization.
- `static/`: Package-owned browser assets.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: `PlaygroundServer`, `PlaygroundServerOptions`, `run_playground`, and the local HTTP endpoints listed in this SPEC.
- Internal modules: `_server.py`, `_state.py`, `_android.py`, `_recording.py`, `_execution.py`, and package-owned static browser assets.
- Domain boundaries: playground owns entry-layer HTTP routing, static UI behavior, safe run-artifact display, active-platform execution orchestration, and in-memory task/session state. Step-artifact lookup is a read-only run-local presentation concern in playground; execution semantics, FSQ parsing, capability metadata, report generation, provider behavior, and dynamic recording semantics remain owned by their existing modules.
- Boundary models: JSON request and response payloads returned by `_server.py`, shared `Settings`, `Task`, `TaskResult`, `RunEvent`, report artifacts, and session/task progress dictionaries.
- Dependency direction: playground may import public APIs from `models`, `config`, `agent`, `fsq`, `core`, and `report`; those modules must not import playground. Playground must not import `capabilities` or decorator internals.
- Rationale: playground coordinates a browser UI, HTTP transport, runtime state, execution adapters, screenshots/replay artifacts, reports, and recording summaries, so Level 3 remains appropriate. YAML display is a presentation and safe artifact-resolution concern inside the existing module and does not justify a new package or stronger architecture.

## Error Handling

The playground returns JSON errors for API failures and does not expose tracebacks by default. Missing goals, missing case YAML paths, unreadable YAML references, ambiguous input bodies, Android-only endpoint use while a non-Android platform is active, ADB discovery errors, missing selected Android device, Web screenshot/runtime construction failures, macOS Appium/runtime construction failures, report resolution failures, and screenshot capture failures must produce concise structured errors. Recording failures must not change the dynamic run status.

YAML display endpoints are read-only and must return concise structured errors for missing paths, missing files, directory paths, non-UTF-8 reads, display size-limit failures, request ids that cannot resolve to runs, missing run directories, missing `recording.json`, invalid recording metadata, and recorded-case paths that escape the run directory. A skipped or failed recording must be displayed as recording metadata with warnings/errors when available rather than treated as a dynamic run failure.

Step artifact endpoints are read-only, must read only under the resolved run directory, and must return concise structured errors for unsafe paths, invalid step identifiers, unsupported artifact content, and text display size-limit failures. Missing files or no matching artifacts must not imply run failure.

## Testing Contract

- Unit tests cover playground state/session behavior, report lookup, replay/replay-video endpoints, task progress streaming and filtering, cancellation, runtime info, platform-specific setup availability, and strict/dynamic execution adapters.
- YAML display tests must cover `GET /yaml/input` success with structured metadata/steps display data, missing file, directory path, display size-limit behavior, UTF-8 read failures when practical, malformed YAML presentation errors, and path resolution order.
- Recorded YAML tests must cover `GET /yaml/recorded/{request_or_run_id}` with generated content, skipped recording metadata, failed recording metadata, missing run id, path safety for recorded-case paths, and recorded steps exposing `displayIndex` and `artifactStepId`.
- Step artifact tests must cover `GET /step-artifacts/{request_or_run_id}/{step_id_or_index}` success, no-artifacts response, missing run id, path safety, missing files, text display size-limit behavior, and resolving a step by its artifact step id.
- Static UI tests must cover YAML section placement, run-mode path input behavior, Input/Recorded tab behavior, structured YAML rendering, recorded YAML loading, and strict-run no-recorded-YAML behavior.
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
- Input and Recorded YAML are read-only structured presentations. Loading errors appear once in the YAML status surface rather than inside the viewer content.

### Preview and Artifacts

- Completed runs use persisted screenshots as replay-video input and show available replay video in Preview with native playback and seeking controls. Replay remains automatic rather than a separate manual action, and stored video supports HTTP range requests.
- Completed Strict Input and Recorded step cards open their artifacts in Preview; dynamic Input cards do not. Screenshots precede structured artifacts, absent artifact kinds do not create empty regions, and selecting the case title returns to the completed replay-video view.
- Before/After screenshots default to a centered, complete side-by-side comparison on a neutral backdrop. Screenshot and UI Tree regions resize independently from their boundaries; resizing is continuous, preserves horizontal comparison, and uses scrolling for overflow.
- Before/after platform observations (`ui_tree`, `page_snapshot`, or `ui_snapshot`) may render as a read-only full-content diff with line-level added/removed highlighting and inline highlighting for paired changed lines.
