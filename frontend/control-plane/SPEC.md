# Frontend Entry: control-plane

## Purpose

Provide the production FSQ Control Plane browser entry. The entry owns a reusable application shell and left sidebar, the Devices page for local execution, and the Config page for managing the single active local model provider, GitHub device authentication, and saved-provider connection testing.

The entry does not own backend validation, Provider persistence/auth protocol, target/case truth, execution semantics, persisted-run browsing, YAML editing, or production implementations of Overview, Workspace, Runs, or Settings.

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

Devices and Config are available. Devices is initially active. Pages without production implementations are visibly and programmatically unavailable and do not render prototype content or clickable no-op destinations. Active navigation uses `aria-current="page"`.

The sidebar is persistent on desktop. At narrow widths the shell owns one accessible collapsed/drawer presentation, keyboard containment while open, close behavior, and focus restoration. Feature pages do not define global navigation breakpoints.

### Config

Config uses the shared shell and title bar with page title `Config`. Entry loads the local Config API and distinguishes loading, unconfigured, configured Azure, configured GitHub, unavailable, and error states. Unconfigured state has one `Add configuration` action. Configured state has `Change provider`; the application never presents retained profiles or a Switch provider action.

Add/Change opens an accessible provider-choice dialog for Azure GPT and GitHub Copilot GPT. Selecting Azure closes the dialog and shows `Azure GPT configuration` in the main outlet. Selecting GitHub advances the same dialog to a required Model name step and then device authentication. Choosing the current provider is allowed as a replacement flow. The previous provider remains active until the replacement completes.

The Azure form contains required Base URL, Model name, and API key fields. Model guidance recommends GPT 5 or later without restricting other non-empty names. API key is populated from the trusted local response, masked by default, and has an eye-icon control with accessible show/hide labels and tooltip. Save submits the complete form and disables competing controls while pending. Cancel returns to the unchanged empty/configured presentation. Dirty state is derived from normalized loaded and draft values; navigating to Devices, starting Change provider, or cancelling while dirty requests discard confirmation. Browser refresh discards the draft.

GitHub authentication requests a device flow only after a non-empty Model name. Waiting state displays the verification URI as a new-tab link, user code with a copy control, expiration, status, and Cancel. The feature polls at bounded server-provided intervals and clears polling/timers on close, cancellation, terminal state, navigation, or unmount. Success closes the dialog, refreshes Config, restores focus, and displays authenticated provider/model state. Failure, denial, and expiration retain a safe error with Retry. Cancellation preserves the previous provider.

After a provider is persisted, the bottom action area contains `Test connection`. It tests only saved configuration and is enabled only when no Azure edits are unsaved and no save, device-flow transition, or test is pending. Success and failure use a result dialog; success shows provider, model, and elapsed duration, while failure shows the backend message/action. Dismissal returns to the unchanged page.

Config API unavailable state explains that editable configuration requires a loopback-bound and loopback-accessed Control Plane and does not expose editable values. Long endpoints, models, codes, and errors wrap without horizontal overflow.

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

- Shows selectable cases returned by Control Plane case discovery through a collapsed case selector entry. The entry displays `Select a yaml` when no case is selected and displays the selected case path after selection. Case discovery does not automatically select the first YAML case; `casePath` is set only when the user selects a YAML file from the tree.
- Activating the selector's disclosure opens a file-tree panel built from each case path relative to `cases.dir`. The file tree displays folders and `.yaml` case files, lets folders expand and collapse, and selects a case when the user activates a file row. Selecting a file closes the panel. Non-selectable discovered cases are not shown in the tree; their count is reported separately.
- Shows selected case declared platform, command count, `requiresAiAssertion`, and `validated` state. The selected case path is shown in the selector entry, not duplicated in the summary cards.
- Never labels machine validation as human review.
- Requires workspace, strict, target, and source readiness. It additionally requires provider readiness when the selected case has `requiresAiAssertion=true`.
- When case discovery returns no selectable cases, shows the empty case-source state and keeps start disabled without changing workspace or strict-runner readiness.
- During and after a strict run, the operation panel shows the authored case action rows from the run source with their execution state derived from Control Plane strict step result projection for the same `stepId`. Each authored action row preserves the authored action name, canonical action name, and step kind, and displays the truthful final status, duration when available, and safe message when the backend supplies one. Low-level server event statuses such as `step_finish`, `phase_finish`, `harness_call_finish`, and finalize progress never override a final action result. Rows without emitted execution results remain pending/running while the run is active and display `skipped` after the run reaches a terminal state.

The start action is derived from authoritative visible readiness, target, input, case, busy, and request states. The frontend still treats run-start server validation as authoritative and displays structured server errors.

### Active and terminal runs

Starting a run replaces the composer with:

- Source summary.
- Current task-state badge.
- For Explore, a safe live timeline derived from server events.
- For Strict Replay, the loaded YAML command step list from the selected case source with execution results derived from server events.
- Cancel while cancellation remains available.

The source summary displays only source identity and source text. For Explore, source text is the natural-language goal. For Strict Replay, source text is the selected YAML script content returned in the run snapshot, with the case path used only as fallback when source text is unavailable. It does not duplicate the run status badge already shown in the operation card header. Long source text defaults to a single-line ellipsis view with an arrow disclosure for expanding and collapsing the complete source without breaking the source card layout. The disclosure appears on the source content line at the far right of the source text, not on the Run source title line and not vertically centered in the whole card.

On desktop, the run workspace is bounded to the viewport below the title bar. The operation column is narrower than the evidence column so Live evidence receives more horizontal space, while preserving responsive fallback without horizontal overflow. The operation and evidence cards keep their headers and outer status/action regions visible while timeline history and the active evidence surface scroll independently. Appended run events do not increase document height.

Explore timeline preserves every server event in sequence order as one flat list of event cards. It does not add phase group containers, phase headers, group summaries, or group-level disclosure controls. Timeline cards preserve their own label and safe message without replacing or fabricating events, and they do not show timestamps. Timeline cards show a status badge only when the server event includes a status; events without status do not display a fallback status badge. Selectable terminal Action cards preserve label, safe message, and server-provided status.

Strict Replay does not render low-level server events in the left operation body. It renders only the selected YAML command steps in authored command order as action-result rows. Each Strict Replay step row shows the one-based command index, authored action name when available, canonical action name, step kind, final status, duration when available, and safe message when supplied for that `stepId`. The final row status is the backend strict step result status, not the latest low-level event status; terminal authored actions with no final result display `skipped`. Internal strict execution events such as step start, phase start/finish, harness call start/finish, artifact captured, and other per-phase progress remain available in Logs and do not render as separate left-body cards.

Safe event messages default to one visual line with ellipsis. A message that overflows that line exposes one icon-only down-arrow control at the right edge; activation expands the complete message and changes the control to an up arrow, and a second activation collapses it. The control is a native button with an accessible Expand/Collapse message name and explicit expanded state.

Timeline history auto-follows appended events only while an active run remains near the bottom. During `preparing`, `running`, or `finalizing`, user scrolling upward pauses following, preserves the reading position, counts appended unseen events, and exposes Jump to latest. Activating Jump to latest synchronously sets the corresponding scroll region to its actual maximum scroll position, verifies bottom-follow state from the resulting geometry, clears the unseen count, removes the control, and transfers keyboard focus to that scroll region rather than leaving focus on a removed element. Returning to the bottom through ordinary scrolling also resumes following. Terminal runs never display Jump to latest regardless of preserved scroll position or focus. Run connection/update state is not rendered as a separate row beneath the source summary; timeline rows keep a small stable gap below the source summary. The timeline scroll region shows its vertical scrollbar from initial render without horizontal scrolling, so timeline cards remain visually centered and do not shift when scrolling becomes necessary.

The frontend does not fabricate waiting/completed timeline steps. Live updates do not steal focus.

Terminal states are success, failed, inconclusive, cancelled, and error. Terminal runs do not render a separate result summary card below the timeline. A completed-run action row remains visible outside the bounded timeline history with a disabled `Save yaml` placeholder beside `New run`. New run returns to the composer, preserves the selected platform when still valid, and focuses the primary mode input. Terminal transitions do not force timeline or Logs scroll position.

After an Explore run becomes terminal, timeline events that identify an execution step are selectable Action cards. Selecting one step highlights every timeline row representing that step and makes the right-side Screen and UI Tree tabs inspect that step without changing the active evidence tab. Selecting the same step again or activating Show run replay clears the selection. Action selection is unavailable while execution or finalization is active and events without a step id remain non-selectable.

After a strict run becomes terminal, authored action rows that have a `stepId` are selectable Action rows even when the backend emitted multiple lower-level events for that step. Selecting one authored action row selects its `stepId`, highlights the matching action row, and makes the right-side Screen and UI Tree tabs inspect that step. The server-event stream remains available as the Logs event source instead of rendering as separate cards beneath the strict action rows.

While a run is active, current action highlighting applies to every row that can be identified as current. Rows whose `stepId` matches `activeStep.stepId` use the active highlight first. When no rendered row can be matched by `activeStep.stepId`, the latest `running` timeline row is highlighted; if no row is explicitly running, the latest timeline row is highlighted. Terminal runs do not show active highlighting; they show only selected-Action highlighting when a user selects an Action.

### Live evidence

The right panel exposes semantic Screen, UI Tree, and Logs tabs:

- Screen shows the latest real screenshot while a run is active. After completion with no selected Action, it automatically resolves or generates the persisted run replay and displays the stored seekable WebM with native playback controls. With an Action selected, it displays that step's available Before and After screenshots as a centered side-by-side comparison in capture order; one-sided evidence is shown without an empty fabricated counterpart. Selected Action screenshots are displayed as the original captured image content without additional image rounding, visible card border, surrounding frame, or device-frame styling. Selected Action screenshot media uses nearly the same visible sizing envelope as the run replay video: it should grow to use the available evidence-surface height and width, especially for Android portrait captures, while preserving readable Before/After labels, comparison order, `object-fit: contain`, and internal scrolling instead of page-level clipping. The presentation maximizes the screenshot image itself and leaves original screenshot pixels unchanged.
- Screen evidence surfaces use a subtle grid workbench background behind screenshot, selected-Action screenshot, replay-video, and replay-generation states. Screenshot and replay-video media use the same visual sizing envelope and are constrained to the visible evidence surface with `object-fit: contain` behavior so desktop and narrow viewports can inspect the whole media without page-level clipping; overflow stays inside the evidence surface when the available viewport is smaller than the media.
- UI Tree loads the latest normalized `ui_snapshot` while a run is active. With a terminal Action selected, it displays the available Before and After normalized snapshots as a read-only full-content diff with line-level and paired inline change highlighting; one-sided evidence remains readable and is not treated as a failed run. When a UI snapshot contains XML, the UI Tree view parses it into a readable structured tree that preserves useful element names, text-like attributes, state, and geometry signals, and falls back to raw text when XML parsing fails.
- Logs render structured time, level, phase, tool, status, and safe message rows rather than raw JSON. The message column is width-bounded and defaults to a single-line ellipsis view that cannot widen the table; activating the message disclosure shows the complete message. The message column starts narrower than before and can be resized horizontally through a drag handle in the Logs header, with the width stored only in component state. Each log row exposes a native disclosure control that expands a complete pretty-printed safe JSON view of the event fields returned by the backend, including optional fields such as `sequence`, `stepId`, `label`, `durationMs`, `payload`, `toolCallId`, `toolArguments`, and `toolOutputPreview` when present. The Details JSON region never widens the table; it has its own horizontal scroll for long fields. The table header remains sticky in the bounded Logs scroll region. Logs do not expose Jump to latest; users inspect history through the Logs scroll region.

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
- `src/features/devices/components/OperationComposer.tsx`: Explore/Strict source input, including the Strict Replay case selector entry and file-tree panel.
- `src/features/devices/components/PreflightStatus.tsx`: readiness presentation.
- `src/features/devices/components/RunTimeline.tsx`: source, task state, Explore flat chronological event presentation, Strict Replay authored-action execution summary, one-line message disclosure, terminal Action selection, timeline scroll following, result, cancel, and new-run actions.
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

Current Config ownership:

- `src/features/config/ConfigPage.tsx`: Config feature composition and loaded/empty/configured presentation.
- `src/features/config/components/`: Provider choice, Azure form, GitHub device flow, and connection-result dialogs.
- `src/features/config/hooks/useProviderConfig.ts`: Config loading, complete Azure save, GitHub polling/cancellation, saved-provider test, and stale-request cleanup.
- `src/styles/config.css`: Config feature layout and responsive presentation without overriding shell structure.

`ControlPlaneShell` has a router-neutral page outlet and active-page callback contract and does not import Devices or Config internals. `ControlPlaneApp` owns local `devices | config` selection and supplies the active page to the shell. Durable URLs and a client router are not required.

`useDeviceWorkspace` owns selected platform/target/mode/goal/case, discovery request state, active request snapshot, selected evidence tab, and terminal selected-step id. Start eligibility, connection status, validated summary, and control locks are derived values. Message disclosure, scroll positions, follow state, unseen counts, loaded step artifacts, replay generation, and media resources are local transient state owned by their timeline, evidence, replay, or Logs presentation component and are not run truth. `useRunStream` owns transport/reconnect state but not run truth.

Effects synchronize fetch, stream, image, and focus boundaries. Render-derived values and event-handler work are not stored or synchronized through effects. Request cancellation and generation checks prevent stale platform responses.

Config server state, pending request state, and the Azure draft are local to the Config feature. Dialog focus, key visibility, copy feedback, and result disclosure are transient component state. Dirty state and Test connection eligibility are derived. Config state is independent from Devices run state; changing Provider does not mutate an active run.

## Frontend Architecture

- Architecture level: Level 2 Component Application.
- Runtime boundary: React/TypeScript in the browser, consuming only `/api/control-plane/*`.
- State boundary: the application owns active page; Devices and Config each own their server/request/interaction state; dialogs own transient focus/disclosure state.
- Integration boundary: `src/api/controlPlaneClient.ts` owns fetch/EventSource details and runtime response validation; `src/api/types.ts` owns transport types.
- Dependency direction: feature components depend on shell props and API adapters; shell and API adapters do not import feature internals; frontend never imports Python implementation.
- Current framework and language: React 19 with TypeScript/TSX and CSS in the existing Vite entry.

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

Empty states direct the user to add a Provider, select/configure a platform, connect a target, provide a goal, or add a valid case. Missing evidence is not represented by a blank success panel. Config save/auth/test failures remain scoped to Config and never fabricate a configured state.

## Accessibility And Responsive Behavior

- The visual system follows the Control Plane UX: warm off-white workbench, clean surfaces, subtle borders, deep rose primary accent, persistent product navigation, and fixed context bar.
- The distinguishing layout is the operation timeline beside live evidence; generic dashboard metrics, decorative numbering, unrelated gradients, and ambient motion are absent.
- Desktop uses a sidebar plus a viewport-bounded two-column Devices workbench whose timeline and evidence bodies scroll independently. Narrow layouts use the shell-owned sidebar drawer, normal page scrolling, a stacked workbench, bounded panel-body maximum heights, and a wrapped toolbar without clipping or touch scroll traps.
- Native controls and semantic headings/landmarks precede ARIA recreation.
- Navigation, tabs, mode controls, selects, textarea, start/cancel/new-run, and sidebar drawer are keyboard operable with visible `:focus-visible`.
- Status is communicated by text/icon as well as color. A restrained live region announces connection, start, cancellation, and terminal results.
- Tab behavior uses standard selected/tab-panel relationships. Icon-only controls have accessible names.
- Live updates preserve focus. Drawer/result/new-run focus transitions are explicit.
- Config choice/auth/result dialogs have labelled dialog semantics, contained Tab order, Escape cancellation where cancellation is allowed, logical initial focus, and focus restoration. Copy-code and key-visibility icon controls have accessible names and tooltips.
- Message disclosure, Action selection, Show run replay, and Jump to latest use native keyboard-operable buttons with visible focus, accessible names, `aria-expanded`/`aria-pressed`/`aria-controls` where applicable, and unseen-event text that does not rely on color. Immediate Jump removal transfers focus to the labelled scroll region.
- Motion respects `prefers-reduced-motion`; functionality does not depend on animation.
- Screenshot alternative text identifies platform/target and evidence state.

## Verification Scope

- A clean lock-file install, TypeScript check, focused frontend tests, and Vite build validate the entry.
- Shell tests prove one centralized sidebar can render Devices and arbitrary page outlet content without Devices imports; cover active/unavailable semantics, keyboard order, `aria-current`, narrow drawer, and focus restoration.
- Devices tests cover stale-request protection, derived start eligibility, Explore/Strict payloads, Strict Replay case selector entry, file-tree panel selection, folder disclosure, active locks, Explore flat sequence-ordered timeline events, Strict Replay YAML command step action-result rows without low-level left-body event cards, one-line overflow disclosure, active-run-only Jump visibility, exact bottom scrolling, immediate Jump dismissal/focus transfer, terminal Action selection, selected-step artifact states, screenshot comparison, UI Tree diff, replay generation/reuse/error cleanup, range-video playback, timeline/cancel/terminal/new-run behavior, stream resume/fallback, sticky Logs structure, per-row full event disclosure, tabs, accessible names, live announcements, and focus behavior.
- Browser verification covers desktop viewport containment and independent panel scrolling at 1440×900 and 1280×720, narrow stacked/page-scrolling behavior around 390px, keyboard-only one-line disclosure, Action selection, Show run replay, and immediate Jump dismissal, Before/After comparison with original image edges, UI Tree diff including XML structured rendering, generated-video playback/seeking, constrained screenshot/replay media sharing the same sizing envelope with the Screen grid background visible, sticky Logs headers, all four platform unavailable/readiness presentations, and at least one available platform's Explore/Strict progress, evidence, cancellation, and terminal behavior. Layout changes require reviewed desktop and narrow screenshots plus a clean browser console.
- Config tests cover malformed-response rejection, loading/empty/configured/unavailable states, complete Azure save and key visibility, dirty-state discard behavior, provider replacement preservation, device-flow request/poll/success/failure/retry/cancel cleanup, saved-only Test connection eligibility/results, dialog keyboard/focus behavior, and secret-safe presentation.
- Build/package verification proves both Vite entries are generated, existing Playground remains functional, and an isolated wheel starts Control Plane without Node.js.

## Current Invariants

- The shell/sidebar is application-level reusable code; Devices does not own or duplicate it.
- Devices and Config are the only available pages; Config is the sole browser provider-configuration workflow.
- Unimplemented navigation destinations are truthfully unavailable.
- Backend responses are the source of truth for readiness, targets, cases, timeline, task status, and evidence revisions.
- Config stores no provider profile list and never treats an Azure draft as saved provider truth. Test connection is disabled while that draft differs from the loaded provider.
- GitHub token values never enter frontend types or state. The complete Azure key is accepted only from the loopback Config response and is masked by default.
- State stores minimum ground truth and derives display values.
- Platform request generations prevent stale responses from changing the selected context.
- No large evidence bytes are carried in SSE.
- Existing Playground source and behavior remain independent.
