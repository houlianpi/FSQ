# Frontend Entry: control-plane

## Purpose

Provide the production FSQ Control Plane browser entry. The entry owns a reusable application shell and left sidebar plus the Devices page used to select a local platform/target, inspect readiness, run Explore or Strict Replay, follow execution, and inspect current screenshot, UI snapshot, and safe logs.

The entry does not own backend validation, target/case truth, execution semantics, persisted-run browsing, YAML editing, or production implementations of Overview, Workspace, Runs, Config, or Settings.

## Dependencies

- React and React DOM provide the component runtime.
- TypeScript is the authored language and type-check boundary.
- Vite and the root Vite React plugin compile the entry within the repository multi-page build.
- Vitest, Testing Library, and a DOM test environment verify focused state and component behavior.
- `ts-ebml` and browser Canvas, `captureStream`, `MediaRecorder`, image, blob, and media APIs provide browser-side seekable WebM replay generation and playback.
- Browser built-ins provide fetch, `AbortController`, `EventSource`, image loading, and accessibility semantics.
- `/api/control-plane/*` is the only backend contract consumed by this entry.

The entry must not import Playground source, Python-generated static assets, backend implementation files, or another frontend entry's private code. It does not introduce Redux, React Query, a client router, Tailwind, CSS-in-JS, or a component framework.

## Public Behavior

### Application shell and sidebar

The entry renders one application-level `ControlPlaneShell` containing:

- FSQ/Control Plane identity.
- Centralized primary navigation metadata for Overview, Workspace, Devices, and Runs.
- Optional workspace navigation supplied through typed shell props.
- Bottom Config and Settings navigation.
- A fixed page title/context bar.
- A page outlet used by every Control Plane feature page.

`ControlPlaneSidebar` is independent of Devices. Feature pages provide active page identity, title-bar context/actions, and outlet content; they do not copy branding, navigation markup, workspace navigation, responsive collapse, or sidebar styles. Navigation metadata has typed ids, labels, icons, availability, and active state in one source.

Devices is available and active. Pages without production implementations are visibly and programmatically unavailable and do not render prototype content or clickable no-op destinations. Active navigation uses `aria-current="page"`.

The sidebar is persistent on desktop. At narrow widths the shell owns one accessible collapsed/drawer presentation, keyboard containment while open, close behavior, and focus restoration. Feature pages do not define global navigation breakpoints.

### Devices toolbar and discovery

The Devices title bar contains:

- Platform selection for Android, Web, Windows, and macOS.
- Platform-specific target selection labelled Device, Browser, or Application.
- Text-plus-icon connection/readiness status.
- Refresh.

While idle, changing platform aborts outstanding readiness/target/case requests, clears values tied to the prior platform, and loads new readiness, targets, and cases concurrently. A response applies only when its request generation still matches the selected platform. Refresh reloads the same data without creating a run.

During `preparing`, `running`, and `finalizing`, platform and target controls are locked to the run context.

### Explore and Strict Replay

The operation panel has Explore and Strict Replay modes.

Explore:

- Accepts one non-empty natural-language goal.
- Explains that FSQ plans, operates, captures evidence, and verifies.
- Requires workspace, provider, target, and source readiness.
- Does not depend on case discovery completion, case selection, or existence of the configured cases directory.

Strict Replay:

- Lists selectable cases returned by Control Plane case discovery.
- Shows case name/path, declared platform, command count, `requiresAiAssertion`, and `validated` state.
- Never labels machine validation as human review.
- Requires workspace, strict, target, and source readiness. It additionally requires provider readiness when the selected case has `requiresAiAssertion=true`.
- When case discovery returns no selectable cases, shows the empty case-source state and keeps start disabled without changing workspace or strict-runner readiness.

The start action is derived from authoritative visible readiness, target, input, case, busy, and request states. The frontend still treats run-start server validation as authoritative and displays structured server errors.

### Active and terminal runs

Starting a run replaces the composer with:

- Source summary.
- Current task-state badge.
- Safe live timeline derived from server events.
- Cancel while cancellation remains available.

On desktop, the run workspace is bounded to the viewport below the title bar. The operation and evidence cards keep their headers and outer status/action regions visible while timeline history and the active evidence surface scroll independently. Appended run events do not increase document height.

The timeline preserves every server event in sequence order as one flat list of event cards. It does not add phase group containers, phase headers, group summaries, or group-level disclosure controls. Each event card preserves its own label, safe message, status, and timestamp without replacing or fabricating events.

Safe event messages default to one visual line with ellipsis. A message that overflows that line exposes one icon-only down-arrow control at the right edge; activation expands the complete message and changes the control to an up arrow, and a second activation collapses it. The control is a native button with an accessible Expand/Collapse message name and explicit expanded state.

Timeline history auto-follows appended events only while an active run remains near the bottom. During `preparing`, `running`, or `finalizing`, user scrolling upward pauses following, preserves the reading position, counts appended unseen events, and exposes Jump to latest. Activating Jump to latest synchronously sets the corresponding scroll region to its actual maximum scroll position, verifies bottom-follow state from the resulting geometry, clears the unseen count, removes the control, and transfers keyboard focus to that scroll region rather than leaving focus on a removed element. Returning to the bottom through ordinary scrolling also resumes following. Terminal runs never display Jump to latest regardless of preserved scroll position or focus. Logs use the same active-run-only visibility, deterministic bottom scroll, immediate-dismiss, and focus-transfer behavior for their independent scroll region.

The frontend does not fabricate waiting/completed timeline steps. Live updates do not steal focus.

Terminal states are success, failed, inconclusive, cancelled, and error. The truthful result summary and New run action remain visible outside the bounded timeline history. New run returns to the composer, preserves the selected platform when still valid, and focuses the primary mode input. Terminal transitions focus the result heading through deliberate focus management without forcing the timeline or Logs scroll position.

After a run becomes terminal, timeline events that identify an execution step are selectable Action cards. Selecting one step highlights every timeline row representing that step and makes the right-side Screen and UI Tree tabs inspect that step without changing the active evidence tab. Selecting the same step again or activating Show run replay clears the selection. Action selection is unavailable while execution or finalization is active and events without a step id remain non-selectable.

### Live evidence

The right panel exposes semantic Screen, UI Tree, and Logs tabs:

- Screen shows the latest real screenshot while a run is active. After completion with no selected Action, it automatically resolves or generates the persisted run replay and displays the stored seekable WebM with native playback controls. With an Action selected, it displays that step's available Before and After screenshots as a centered side-by-side comparison in capture order; one-sided evidence is shown without an empty fabricated counterpart. Android comparisons may use device-proportioned cards; other platforms use a neutral canvas.
- Screen evidence surfaces use a subtle grid workbench background behind screenshot, selected-Action screenshot, replay-video, and replay-generation states. Screenshot and replay-video media are constrained to the visible evidence surface with `object-fit: contain` behavior so desktop and narrow viewports can inspect the whole media without page-level clipping; overflow stays inside the evidence surface when the available viewport is smaller than the media.
- UI Tree loads the latest normalized `ui_snapshot` while a run is active. With a terminal Action selected, it displays the available Before and After normalized snapshots as a read-only full-content diff with line-level and paired inline change highlighting; one-sided evidence remains readable and is not treated as a failed run. When a UI snapshot contains XML, the UI Tree view parses it into a readable structured tree that preserves useful element names, text-like attributes, state, and geometry signals, and falls back to raw text when XML parsing fails.
- Logs render structured time, level, phase, tool, status, and safe message rows rather than raw JSON. The table header remains sticky in the bounded Logs scroll region. Overflowing messages use the same one-line arrow disclosure as timeline messages. Logs independently auto-follow near-bottom appends, pause and count unseen rows while the user reads history, and expose Jump to latest to resume.

Replay generation is automatic after terminal completion. The browser requests persisted screenshot frames in chronological order, uses their timestamps to derive bounded display durations, renders them through Canvas and `MediaRecorder`, converts the result to a seekable WebM through `ts-ebml`, uploads it to the frozen run, and then plays only the stored range-capable video URL. An existing stored video is reused. Runs with no readable frames show an unavailable state; unsupported browser media APIs, frame failures, generation failures, upload failures, and playback failures stay local to Screen and never change the truthful run result. Object URLs, media streams, timers, and in-flight generation are cleaned up when the run, selection, or component changes.

Each tab distinguishes loading, not-yet-captured, unavailable, oversized, failed, and available states. Evidence-tab failures do not replace the run result.

The run stream resumes from the last accepted sequence. On stream failure, the client reconnects with bounded backoff and then falls back to run snapshots. A browser reload uses bootstrap to discover and resubscribe to a live in-memory request.

## Component And State Architecture

Current application/shell ownership:

- `src/main.tsx`: React root.
- `src/app/ControlPlaneApp.tsx`: application composition and available-page selection.
- `src/app/shell/ControlPlaneShell.tsx`: sidebar/title-bar/page-outlet geometry and narrow shell behavior.
- `src/app/shell/ControlPlaneSidebar.tsx`: reusable navigation presentation.
- `src/app/shell/navigation.ts`: typed centralized navigation metadata.
- `src/app/shell/shell.css`: shared shell/sidebar layout, responsive, and focus styles.

Current Devices ownership:

- `src/features/devices/DevicesPage.tsx`: feature composition.
- `src/features/devices/components/TargetToolbar.tsx`: platform/target/status/refresh controls supplied to the shell title bar.
- `src/features/devices/components/OperationComposer.tsx`: Explore/Strict source input.
- `src/features/devices/components/PreflightStatus.tsx`: readiness presentation.
- `src/features/devices/components/RunTimeline.tsx`: source, task state, flat chronological event presentation, one-line message disclosure, terminal Action selection, timeline scroll following, result, cancel, and new-run actions.
- `src/features/devices/components/LiveEvidencePanel.tsx`: evidence tab composition, selected-Action context, and run-replay restoration.
- `src/features/devices/components/ScreenView.tsx`, `UiSnapshotView.tsx`, and `RunLogsView.tsx`: current/selected-step evidence presentation; Logs owns structured-row message disclosure, sticky-table semantics, and log scroll following.
- `src/features/devices/components/ReplayVideoView.tsx`: terminal replay resolution, generation state, stored-video playback, and browser-resource cleanup.
- `src/features/devices/components/StepEvidenceView.tsx`: selected-step screenshot comparison and UI-snapshot diff presentation.
- `src/features/devices/replay/`: frame timing, Canvas/MediaRecorder capture, seekable WebM conversion, and diff helpers that remain independent from Playground source.
- `src/features/devices/hooks/useDeviceWorkspace.ts`: page state and discovery/run commands.
- `src/features/devices/hooks/useRunStream.ts`: sequence, SSE reconnect, and snapshot fallback.
- `src/api/controlPlaneClient.ts`: fetch/EventSource boundary, structured errors, cancellation, and response validation.
- `src/api/types.ts`: transport boundary types.
- `src/styles/`: entry tokens and Devices-specific styles that do not override shell structure.

`ControlPlaneShell` has a router-neutral page outlet and active-page callback contract and does not import Devices internals. No client routing dependency is required while Devices is the only available page.

`useDeviceWorkspace` owns selected platform/target/mode/goal/case, discovery request state, active request snapshot, selected evidence tab, and terminal selected-step id. Start eligibility, connection status, validated summary, and control locks are derived values. Message disclosure, scroll positions, follow state, unseen counts, loaded step artifacts, replay generation, and media resources are local transient state owned by their timeline, evidence, replay, or Logs presentation component and are not run truth. `useRunStream` owns transport/reconnect state but not run truth.

Effects synchronize fetch, stream, image, and focus boundaries. Render-derived values and event-handler work are not stored or synchronized through effects. Request cancellation and generation checks prevent stale platform responses.

## Build And Delivery

- Authored source lives under `frontend/control-plane`.
- `frontend/control-plane/index.html` is the Control Plane input in the root Vite MPA configuration.
- Development requests under `/api/control-plane` proxy to the local Control Plane Python server and preserve unbuffered SSE.
- Production output is generated under `fsq_agent/control_plane/static`, remains untracked, and is included in the Python wheel.
- Installed-wheel use serves the generated entry and API from one Python process and requires no Node.js/network access.
- Static route fallback is limited to the Control Plane entry and never falls back to Playground.
- The root package manifest and lock file own all frontend dependencies. No nested package project or second lock file exists.

## Error Handling

The API client recognizes structured `code`, `message`, `action`, and optional safe `details`. User-visible errors say what happened and what action is available. They do not display tracebacks, hidden reasoning, raw internal JSON, secret values, or unnecessary local paths.

Platform changes cancel stale requests. Target/case disappearance at run start is shown as server validation failure and triggers relevant refresh guidance. Stream disconnection is shown as reconnecting without changing task outcome. Screen/UI-snapshot, selected-step artifact, replay-frame, video-generation, upload, and playback failures stay scoped to their evidence surface. A restarted backend reports that the prior live session ended rather than presenting a stale running state.

Empty states direct the user to select/configure a platform, connect a target, provide a goal, or add a valid case. Missing evidence is not represented by a blank success panel.

## Accessibility And Responsive Behavior

- The visual system follows the Control Plane UX: warm off-white workbench, clean surfaces, subtle borders, deep rose primary accent, persistent product navigation, and fixed context bar.
- The distinguishing layout is the operation timeline beside live evidence; generic dashboard metrics, decorative numbering, unrelated gradients, and ambient motion are absent.
- Desktop uses a sidebar plus a viewport-bounded two-column Devices workbench whose timeline and evidence bodies scroll independently. Narrow layouts use the shell-owned sidebar drawer, normal page scrolling, a stacked workbench, bounded panel-body maximum heights, and a wrapped toolbar without clipping or touch scroll traps.
- Native controls and semantic headings/landmarks precede ARIA recreation.
- Navigation, tabs, mode controls, selects, textarea, start/cancel/new-run, and sidebar drawer are keyboard operable with visible `:focus-visible`.
- Status is communicated by text/icon as well as color. A restrained live region announces connection, start, cancellation, and terminal results.
- Tab behavior uses standard selected/tab-panel relationships. Icon-only controls have accessible names.
- Live updates preserve focus. Drawer/result/new-run focus transitions are explicit.
- Message disclosure, Action selection, Show run replay, and Jump to latest use native keyboard-operable buttons with visible focus, accessible names, `aria-expanded`/`aria-pressed` where applicable, and unseen-event text that does not rely on color. Immediate Jump removal transfers focus to the labelled scroll region.
- Motion respects `prefers-reduced-motion`; functionality does not depend on animation.
- Screenshot alternative text identifies platform/target and evidence state.

## Verification Scope

- A clean lock-file install, TypeScript check, focused frontend tests, and Vite build validate the entry.
- Shell tests prove one centralized sidebar can render Devices and arbitrary page outlet content without Devices imports; cover active/unavailable semantics, keyboard order, `aria-current`, narrow drawer, and focus restoration.
- Devices tests cover stale-request protection, derived start eligibility, Explore/Strict payloads, active locks, flat sequence-ordered timeline events, one-line overflow disclosure, active-run-only Jump visibility, exact bottom scrolling, immediate Jump dismissal/focus transfer, terminal Action selection, selected-step artifact states, screenshot comparison, UI Tree diff, replay generation/reuse/error cleanup, range-video playback, timeline/cancel/terminal/new-run behavior, stream resume/fallback, sticky Logs structure, tabs, accessible names, live announcements, and focus behavior.
- Browser verification covers desktop viewport containment and independent panel scrolling at 1440×900 and 1280×720, narrow stacked/page-scrolling behavior around 390px, keyboard-only one-line disclosure, Action selection, Show run replay, and immediate Jump dismissal, Before/After comparison, UI Tree diff including XML structured rendering, generated-video playback/seeking, constrained screenshot/replay media with the Screen grid background visible, sticky Logs headers, all four platform unavailable/readiness presentations, and at least one available platform's Explore/Strict progress, evidence, cancellation, and terminal behavior. Layout changes require reviewed desktop and narrow screenshots plus a clean browser console.
- Build/package verification proves both Vite entries are generated, existing Playground remains functional, and an isolated wheel starts Control Plane without Node.js.

## Current Invariants

- The shell/sidebar is application-level reusable code; Devices does not own or duplicate it.
- Unimplemented navigation destinations are truthfully unavailable.
- Backend responses are the source of truth for readiness, targets, cases, timeline, task status, and evidence revisions.
- State stores minimum ground truth and derives display values.
- Platform request generations prevent stale responses from changing the selected context.
- No large evidence bytes are carried in SSE.
- Existing Playground source and behavior remain independent.
