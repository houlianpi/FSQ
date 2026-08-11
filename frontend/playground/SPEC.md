# Module: frontend/playground

## Purpose

Own the authored browser application for the local FSQ-Agent Playground. The application presents runtime status, platform session setup where applicable, dynamic and strict execution controls, YAML views and lifecycle editing, progress, screenshots, replay video, reports, existing-run loading, and completed-step artifacts.

This module owns browser-local state, rendering, interaction, and browser-side replay generation. It consumes the HTTP contracts owned by `fsq_agent/playground/SPEC.md` and does not own Python execution, filesystem safety, route semantics, production static serving, or wheel packaging.

## Dependencies

- Parent workspace: Uses the npm, Vite, lock-file, and generated-asset contracts in `frontend/SPEC.md`.
- Python Playground API: Consumes the documented JSON, Server-Sent Events, screenshot, replay, report, YAML, and step-artifact endpoints without importing Python modules.
- `ts-ebml`: Imported as an ES module for browser-side seekable WebM generation.
- Browser platform APIs: Uses `fetch`, `EventSource`, DOM events, media elements, local storage, blobs, Canvas 2D with `captureStream`, `MediaRecorder`, `Image`, and `FileReader`.

## Public Interface

- Source entry: `index.html` loads `playground.js` as an ES module and `playground.css` as the authored stylesheet.
- Run modes: Goal, YAML, and Strict YAML preserve their corresponding server execution semantics.
- Workspace views: Source YAML, Generated YAML, Progress, Preview, and Report expose mode-appropriate state without changing execution semantics.
- Session controls: Android session setup is visible only when the active platform requires it.
- Existing-run loading: Goal mode can load one server-validated completed run and reuse the normal Progress, Report, replay, generated-YAML, and step-artifact surfaces.
- Input lifecycle editing: Source YAML exposes case-level `onCaseStart` and `onCaseComplete` action drafts while metadata and case steps remain read-only.
- Artifact navigation: Completed Strict Input and Generated YAML step cards can select step artifacts in Preview; selecting the case title returns to replay preview.

The browser consumes endpoint contracts from `fsq_agent/playground/SPEC.md`. Endpoint validation, response safety, execution ordering, path resolution, and persistence semantics remain owned by that Python module.

## Data And State Flow

- A centralized browser state tracks the active request, run mode, per-mode view snapshots, progress sequence, selected artifacts, lifecycle drafts, replay generation, finalization, and loaded-run state.
- Each run mode preserves its own YAML content and active view, Progress history, active Preview/Report tab, report content, replay state, and step-artifact preview when the user switches modes. Transient YAML-region and Progress-item selection styling is cleared when a mode is restored.
- Live progress prefers Server-Sent Events and falls back to sequence-based polling; events append without rebuilding prior history.
- Execution completion resolves the run id, report, generated YAML, replay frames/video, and step-artifact availability independently so one unavailable surface does not invalidate the others.
- Lifecycle edits remain browser-local drafts until Save sends structured hooks with the source revision. Discard restores the last server snapshot.
- Browser replay generation converts persisted screenshot frames to WebM, uploads the result through the server contract, and then uses the stored range-capable video for playback and seeking.

## Internal Structure

- `index.html`: Semantic application shell, controls, tabs, panels, media surfaces, accessible names, and the browser entry declaration.
- `playground.js`: Current application controller, API client, centralized state, rendering, execution/progress coordination, YAML presentation, artifact views, panel resizing, replay generation, and event wiring.
- `lifecycle-editor-model.js`: Pure clone, add, update, delete, reorder, and validation operations for lifecycle action drafts.
- `playground.css`: Workspace layout, responsive behavior, visual states, focus treatment, artifact comparison, YAML presentation, and editor styling.

## Frontend Architecture

- Architecture level: Legacy stateful single-page application, documented as an exception to the normalized React application levels.
- Runtime boundary: Browser-only authored source compiled by Vite.
- State boundary: `playground.js` owns centralized mutable application and per-mode state; `lifecycle-editor-model.js` owns pure lifecycle draft operations.
- Integration boundary: A shared browser API helper and `EventSource` calls consume only the Python Playground transport surface.
- Dependency direction: `playground.js` may import `lifecycle-editor-model.js` and `ts-ebml`; authored frontend source does not import generated assets or Python modules.
- Current framework: Vanilla JavaScript, HTML, and CSS. React and TypeScript/TSX are not current dependencies or source formats for this module.

## Error Handling

- Failed JSON requests surface the server's concise `error` value when present and otherwise show the HTTP status.
- Status, YAML, load-run, report, replay, and artifact failures stay local to their relevant surface when the rest of the completed run remains usable.
- Starting execution or changing/reloading the YAML path while lifecycle drafts are dirty requires Save or Discard; Clear discards the draft.
- Client lifecycle validation appears when Save is attempted. Empty action values and unsupported action types are rejected before the request.
- Lifecycle revision conflicts require the source to be reloaded and do not silently overwrite disk changes.
- Controls that can conflict with execution, completion/replay finalization, or an active save are disabled and guarded in event handlers.
- A run with no persisted progress, generated YAML, replay, report, or artifacts presents a concise empty or unavailable state rather than synthetic content.

## Verification Scope

- Verification covers mode switching, per-mode state preservation, execution and cancellation controls, SSE-to-polling progress behavior, lifecycle draft editing, existing-run loading, report and YAML presentation, replay generation/playback, and step-artifact navigation.
- Browser-source verification covers labeled native controls, keyboard-operated main workspace panel resizing and form submission, main-control focus treatment, and non-overlapping narrow-viewport behavior. It does not represent pointer-only artifact navigation or artifact-region resizers as keyboard-operable.
- Integration verification covers the documented JSON and SSE endpoints, binary replay upload/playback, HTTP range seeking, safe generated-YAML rendering, and the distinction between dynamic raw YAML and strict execution.
- Build verification uses the parent workspace's locked install and Vite build and confirms no committed vendor bundle or global EBML dependency is required.

## Current Invariants

### Progress And Workspace State

- The desktop UI uses a persisted resizable two-column workspace: mode-specific YAML/Progress views on the left and Preview/Report on the right. Starting execution clears the Preview surface but preserves the active Preview/Report tab until later artifact or replay navigation selects Preview; progress continues independently.
- Left-side tab availability and defaults follow run mode: Goal exposes Progress and Generated YAML, YAML exposes Progress, Source YAML, and Generated YAML, and Strict YAML exposes Source YAML and Progress. Each mode preserves its own view state, and generated recording content does not force tab selection.
- Strict execution uses server-provided current-step metadata for Source YAML highlighting without synthesizing tool-call events from core lifecycle events. Dynamic YAML does not mutate Input step state. Run-mode and artifact navigation changes are blocked while execution or replay finalization is active.
- Generated YAML and loaded-run YAML remain read-only structured presentations and do not render lifecycle editor sections. Ordinary command cards render under a `Case steps` heading. Live Source YAML renders case-level `onCaseStart` before Case steps and `onCaseComplete` after them. Only lifecycle action rows are editable; metadata and Case steps remain read-only.
- Input lifecycle drafts contain flat ordered `Before case` and `After case` action lists. `runCase` and `runShell` may repeat. Save and Discard are document-level controls; Save validates dirty drafts when invoked, and Discard restores the last server snapshot.
- Saving lifecycle drafts sends structured hook data plus the loaded source revision. Empty lifecycle sections remove their keys. Unedited files are never rewritten by the browser.
- Load Run expands an inline run-directory form in Goal mode. A successful load creates a completed-run view without an active request and independently loads persisted Progress, Report, replay, Generated YAML, and step-artifact availability through existing endpoints.
- Failed existing-run validation preserves the displayed result and reports the error in the inline form. Cancel preserves the result and collapses the form. Clear removes loaded-run state and restores the empty workspace.

### Preview And Artifacts

- Completed runs use persisted screenshots as replay-video input and show available replay video in Preview with native playback and seeking controls. Replay generation is automatic rather than a separate user command.
- Completed Strict Source YAML and Generated YAML step cards open their artifacts in Preview; dynamic Source YAML cards do not.
- Screenshots precede structured artifacts, absent artifact kinds do not create empty regions, and selecting the case title restores the completed replay-video view.
- Before/After screenshots default to a centered, complete side-by-side comparison on a neutral backdrop. Screenshot and UI snapshot regions resize independently and use scrolling for overflow.
- Before/after normalized `ui_snapshot` artifacts may render as a read-only full-content diff with line-level and paired inline change highlighting. Explicit Android `uiTree` and Web/desktop `uiSnapshot` artifacts remain supported.
- The named main workspace panel separator supports keyboard resizing. Artifact-region height resizers and artifact selection from Progress or structured YAML are current pointer-only legacy interactions.
- Lifecycle editing uses compact, unnested action rows with an action menu, single-line value, and icon controls with tooltips and accessible labels. Controls remain usable without overlap in the resizable desktop layout and narrow viewport.

### Ownership And Distribution

- Authored browser source and browser dependencies are owned by the frontend workspace; generated bundles are untracked package data.
- The Python Playground server owns all endpoint semantics and production static serving. Browser code treats server responses as transport contracts and does not reproduce server validation or filesystem policy.
- The module remains vanilla JavaScript until a confirmed module SPEC changes its framework and source-language contract.