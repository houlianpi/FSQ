# Frontend Entry: control-plane

## Purpose

Provide the production FSQ Control Plane browser entry. The entry owns a reusable application shell and left sidebar, the Devices page for local execution, and the Config page for managing the single active local model provider, GitHub device authentication, and saved-provider connection testing.

The entry does not own backend validation, Provider persistence/auth protocol, target/case truth, execution semantics, persisted-run browsing, YAML editing, or production implementations of Overview, Workspace, Runs, or Settings.

## Dependencies

- React and React DOM provide the component runtime.
- TypeScript is the authored language and type-check boundary.
- Vite and the root Vite React plugin compile the entry within the repository multi-page build.
- Vitest, Testing Library, and a DOM test environment verify focused state and component behavior.
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

The timeline preserves every server event in chronological order and groups only contiguous events with the same phase; a missing phase is presented as Run, and a repeated phase separated by another phase forms a new group. The latest/current phase defaults expanded and older phases default collapsed while explicit user disclosure choices for historical groups are preserved. Group summaries are derived presentation and do not replace or fabricate events.

Long safe event messages default to a bounded preview and expose per-message native expand/collapse controls. Timeline history auto-follows appended events only while its scroll position remains near the bottom. User scrolling upward pauses following, preserves the reading position, counts appended unseen events, and exposes Jump to latest; returning to the bottom or activating that control resumes following without moving keyboard focus.

The frontend does not fabricate waiting/completed timeline steps. Live updates do not steal focus.

Terminal states are success, failed, inconclusive, cancelled, and error. The truthful result summary and New run action remain visible outside the bounded timeline history. New run returns to the composer, preserves the selected platform when still valid, and focuses the primary mode input. Terminal transitions focus the result heading through deliberate focus management without forcing the timeline or Logs scroll position.

### Live evidence

The right panel exposes semantic Screen, UI Tree, and Logs tabs:

- Screen loads the latest real screenshot only when its revision changes, preserves natural aspect ratio, and does not fabricate application content. Android may use device-proportioned presentation; other platforms use a neutral canvas.
- UI Tree loads the latest normalized `ui_snapshot` only when its revision changes and displays read-only whitespace-preserving text with scrolling.
- Logs render structured time, level, phase, tool, status, and safe message rows rather than raw JSON. The table header remains sticky in the bounded Logs scroll region. Long messages use per-row native disclosure. Logs independently auto-follow near-bottom appends, pause and count unseen rows while the user reads history, and expose Jump to latest to resume.

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
- `src/features/devices/components/RunTimeline.tsx`: source, task state, contiguous phase grouping, timeline and message disclosure, timeline scroll following, result, cancel, and new-run actions.
- `src/features/devices/components/LiveEvidencePanel.tsx`: evidence tab composition.
- `src/features/devices/components/ScreenView.tsx`, `UiSnapshotView.tsx`, and `RunLogsView.tsx`: evidence-kind presentation; Logs owns structured-row message disclosure, sticky-table semantics, and log scroll following.
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

`useDeviceWorkspace` owns selected platform/target/mode/goal/case, discovery request state, active request snapshot, and selected evidence tab. Start eligibility, connection status, validated summary, and control locks are derived values. Phase/message disclosure, scroll positions, follow state, and unseen counts are local transient state owned by their timeline or Logs presentation component and are not workspace state. `useRunStream` owns transport/reconnect state but not run truth.

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

Platform changes cancel stale requests. Target/case disappearance at run start is shown as server validation failure and triggers relevant refresh guidance. Stream disconnection is shown as reconnecting without changing task outcome. Screen/UI-snapshot failures stay scoped to their tabs. A restarted backend reports that the prior live session ended rather than presenting a stale running state.

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
- Phase and message disclosure plus Jump to latest use native keyboard-operable buttons with visible focus, accessible names, `aria-expanded`/`aria-controls` where applicable, and unseen-event text that does not rely on color.
- Motion respects `prefers-reduced-motion`; functionality does not depend on animation.
- Screenshot alternative text identifies platform/target and evidence state.

## Verification Scope

- A clean lock-file install, TypeScript check, focused frontend tests, and Vite build validate the entry.
- Shell tests prove one centralized sidebar can render Devices and Config without feature imports; cover active/unavailable semantics, keyboard order, `aria-current`, narrow drawer, page selection, and focus restoration.
- Devices tests cover stale-request protection, derived start eligibility, Explore/Strict payloads, active locks, contiguous timeline phase grouping/disclosure, long timeline/log message disclosure, independent near-bottom auto-follow/pause/unseen/resume behavior, timeline/cancel/terminal/new-run behavior, stream resume/fallback, evidence states, sticky Logs structure, tabs, accessible names, live announcements, and focus behavior.
- Config tests cover malformed-response rejection, loading/empty/configured/unavailable states, complete Azure save and key visibility, dirty-state discard behavior, provider replacement preservation, device-flow request/poll/success/failure/retry/cancel cleanup, saved-only Test connection eligibility/results, dialog keyboard/focus behavior, and secret-safe presentation.
- Browser verification covers desktop viewport containment and independent panel scrolling at 1440×900 and 1280×720, narrow stacked/page-scrolling behavior around 390px, keyboard-only disclosure and Jump to latest, long-content wrapping, sticky Logs headers, all four platform unavailable/readiness presentations, and at least one available platform's Explore/Strict start, progress, evidence, cancellation, and terminal behavior. Layout changes require reviewed desktop and narrow screenshots plus a clean browser console.
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
