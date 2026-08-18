# Module: cli

## Purpose

Provide the public command line surface for fsq-agent: resolve and validate a required registered workspace name plus explicit configured platform independently of the process current directory, bootstrap a lightweight active-platform capability registry, run either dynamic LLM goal/reference execution or strict-core YAML execution with optional case lifecycle hook orchestration and explicit provider-backed `assertWithAI`, optionally record dynamic LLM runs into strict-replay FSQ YAML artifacts from capability replay metadata, print platform-scoped workspace reports, start the workspace-platform browser Playground, and start the directory-independent local Control Plane.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, FSQ case and lifecycle hook models, capability registry snapshots, replay policy metadata, strict replay refs, wait parameter models, report artifacts, and shared exceptions.
- `config`: Resolves registered workspace identity, loads the explicitly selected platform overlay and matching preset, then validates provider-only, LLM runtime, or strict-core readiness without creating workspace identity or config files.
- `providers`: Builds shared provider sessions and AI assertion evaluators for dynamic runs and strict runs that contain explicit `assertWithAI` steps.
- `core`: Composes capability registry bootstrap, deterministic `ExecutableStep` execution through `StepRunner`/`StepSequenceRunner`, runner events, and evidence manifest writing at the entry boundary.
- `fsq`: Owns the exact `.fsq.yaml` suffix contract, loads FSQ cases, and converts parsed cases into canonical strict-core executable steps using a registry snapshot.
- `agent`: Runs dynamic LLM goal/reference task workflows and persists recordable safe event metadata.
- `playground`: Starts the local browser playground server from loaded settings and CLI host/port/browser options.
- `control_plane`: Starts the local Control Plane server from CLI host/port/browser options. Workspace management and Devices selection come from browser state and the user registry, not CLI-selected workspace or platform options.
- `report`: Generates strict-core reports and resolves stored LLM or strict-core reports by run id.
- `tools`: Provides dynamic-only AgentTool hosts for default LLM execution.

The CLI module composes strict registry bootstrap from public `core` platform tool APIs and dynamic execution from `agent`/`tools` APIs. It must not import `capabilities` or decorator internals directly; declaration discovery happens inside the owning capability host modules.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `main`: CLI entry point for package scripts.

Current commands:

- `fsq-agent [--output human|json|jsonl] init --name NAME [--parent PATH] --platform android|web|windows|macos [platform target options] [--env NAME=VALUE ...] [--update-existing]`: Initialize exactly one platform through Config at `<parent>/<name>`. Parent defaults to the process current directory. Android requires `--app-id`; Web requires `--browser-executable-path`; Windows requires `--app-path` and accepts optional `--window-title-re` and `--launch-args`; macOS accepts `--bundle-id` and `--app-path` with at least one required. Repeated env options form the complete private env mapping. A first call creates and registers the workspace, a missing platform is added, an equal platform returns unchanged, and a differing platform requires `--update-existing` for the same revision-protected target/env replacement used by Control Plane.
- `fsq-agent run --workspace NAME --platform PLATFORM --goal TEXT [--android-serial SERIAL] --tracing/--no-tracing --stream/--no-stream --stream-format concise|jsonl --record --record-on-failure`: Resolve and validate the required registered workspace name and explicit configured platform, then run one dynamic LLM task from a natural-language goal. CLI task construction sets planning reference kind `goal` and normalized goal text; pre-planning derives ordered key actions and `verification_goal` before external UI actions. Streaming defaults to concise. A tracing override applies after settings load and before runtime validation. `--record` writes a run-local strict-replay artifact after a successful run; `--record-on-failure` additionally permits draft recording for failed or inconclusive runs and requires `--record`.
- `fsq-agent run --workspace NAME --platform PLATFORM --case-yaml PATH [--android-serial SERIAL] --tracing/--no-tracing --stream/--no-stream --stream-format concise|jsonl --record --record-on-failure`: Resolve the exact lowercase `.fsq.yaml` file inside the selected platform's `cases/<platform>/` root, read complete UTF-8 text, and run one dynamic LLM task using a `raw_case` planning-reference envelope containing the contained source path and content. The CLI does not parse this YAML for execution or derive verifier requirements. Pre-plan derives ordered key actions and `verification_goal`; optional recording uses only persisted run events.
- `fsq-agent run --workspace NAME --platform PLATFORM --case-dir PATH [--android-serial SERIAL] --tracing/--no-tracing --stream/--no-stream --stream-format concise|jsonl --record --record-on-failure`: Resolve a contained directory inside the selected platform's cases root, recursively discover exact `*.fsq.yaml` files, sort them, and run one independent dynamic `raw_case` task per file serially. Execution and per-run recording attempts continue after failures and produce an operational summary.
- `fsq-agent run --workspace NAME --platform PLATFORM --strict --case-yaml PATH [--android-serial SERIAL] --tracing/--no-tracing`: Resolve one contained `.fsq.yaml` case, load the selected workspace-platform settings, construct the active harness/driver/tool provider without external connection during bootstrap, validate the active registry, load case/config lifecycle hooks, and preflight platform-private runtime-secret references without serializing private values. Strict phases remain config `onCaseStart`, case `onCaseStart`, main commands when before hooks pass, case `onCaseComplete`, and config `onCaseComplete`. Hook `runCase` dependencies resolve under the same selected platform cases containment boundary, including traversal and symlink checks; `runShell` remains an operator-authored local command. Canonical commands execute through `StepSequenceRunner`/`StepRunner` with centralized delay and evidence policy. Each run writes evidence and strict reports inside its unique direct `.fsq/runs/<platform>/<run-id>/` directory and snapshots the source case there for provenance without mutating authored content. Recovery, testcase mutation, and strict recording are disabled. An explicitly authored `assertWithAI` may inject a provider-backed evaluator after provider validation.
- `fsq-agent run --workspace NAME --platform PLATFORM --strict --case-dir PATH [--android-serial SERIAL] --tracing/--no-tracing`: Resolve a contained directory under the selected platform cases root and execute discovered cases serially through the same strict lifecycle. Hook `runCase` files are contained dependencies, not separate top-level results. Execution continues after failed top-level cases and exits nonzero when any case or dependency fails.
- `fsq-agent report --workspace NAME --platform PLATFORM --run-id ID --format markdown|json`: Resolve one LLM `report.md/json` or strict `core-report.md/json` from a unique direct child of the selected platform run root; fail when the registered workspace or selected platform is unavailable or invalid, no report matches, or the run id is ambiguous.
- `fsq-agent playground --workspace NAME --platform PLATFORM --host HOST --port PORT --open-browser/--no-open-browser`: Load the same explicit workspace-platform settings as `run`, then start the local Playground with that selection frozen for the server lifetime. The command blocks, serves packaged Vite assets, optionally opens a browser, and delegates behavior to `playground`. Configuration, asset, and bind failures exit nonzero; installed wheels require no Node.js runtime.
- `fsq-agent control-plane --host HOST --port PORT --open-browser/--no-open-browser`: Start the local single-user Control Plane from any current directory without selecting a workspace or platform. Workspace management and Devices read the user registry and explicit workspace roots. The command blocks, serves the Vite-generated Control Plane entry, and optionally opens the browser. The default host is `127.0.0.1` and port is `8879`; `--platform`, `--config`, and `--workspace` are unsupported.

Public CLI commands do not expose `--config`; `init` does not expose `--provider`. The root `--output` option defaults to `human`. Init emits Human output or exactly one compact terminal JSON record for `json` and `jsonl`; those records contain stable operation/status/workspace/platform fields or a safe structured error and never contain target or env values. Non-init commands reject root `json` or `jsonl` output before settings loading, execution, or server startup because they do not define that machine-output protocol. `run`, `report`, and `playground` require both `--workspace NAME` and `--platform PLATFORM` and fail argument parsing before settings load or writes when either option is missing. `control-plane` accepts neither selection option because browser state manages the registry and execution context.

Init accepts exactly one platform per invocation. Target options for another platform, malformed or duplicate env assignments, blank env values, invalid targets, invalid names, invalid parents, registered-name/root mismatches, and differing existing platform data without `--update-existing` fail before an unauthorized workspace write. Env option values may be visible to the invoking shell or process inspection, so help text warns about command-line secret exposure; CLI output, errors, and logs never echo them. `--update-existing` permits only the complete target/env fields editable by Control Plane and does not permit workspace name, root, or platform identity changes or bypass Config revision checks.

Every `run` form accepts optional `--android-serial SERIAL`. With `--platform android`, CLI verifies an explicit serial is online or, when omitted, discovers exactly one online device and applies it only to the run-specific settings copy. Zero devices, multiple devices without an explicit serial, an offline/unknown explicit serial, or use with a non-Android selected platform fail before agent, case, hook, harness, or driver execution. Directory runs freeze one selected Android serial for the complete command.

`--goal`, `--case-yaml`, and `--case-dir` are mutually exclusive. `--strict --goal` is invalid because strict-core execution requires authored YAML steps. `--strict --record` and `--strict --record-on-failure` are invalid because recording is a dynamic-run post-processing workflow. `--record-on-failure` without `--record` is invalid. Every case-oriented `--case-yaml` input requires the exact lowercase `.fsq.yaml` suffix. Absolute and relative case inputs resolve against the selected platform's `cases.dir` and are accepted only when the resolved target remains contained; there is no current-working-directory fallback outside that root. Strict hook `runCase` paths from config-level or case-level hooks use the same suffix, containment, traversal, and symlink policy.

Dynamic recording writes the following run-local files when attempted:

```text
<runs_dir>/<run-id>/
    recorded.fsq.yaml
    recording.json
```

`recorded.fsq.yaml` contains two YAML documents: generated FSQ metadata followed by recorded commands. Generated metadata must include `tags` identifying the case as recorded and `properties.recording` with source run id, source task id, source status, `draft`, required runtime secret names, and warnings. `recording.json` contains recording status, command count, recorded case path when present, required runtime secret names, warnings, skipped tool calls, validation status, and errors when recording fails. Neither file may contain secret values.

The recording helper reconstructs logical replay entries from the dynamic run's `events.jsonl` by consuming structured capability metadata emitted by `StepRunner` for CommonTool and PlatformTool calls. A completed event with `replay.kind == "fsq_command"` and `step_kind != "observation"` appends `{replay.alias: safe_replay_params}` to generated strict YAML when the status indicates success and params validate, falling back to the started event's JSON arguments only when no safe replay params are present. Observation PlatformTools such as `uiTree`, `uiSnapshot`, and `takeScreenshot` are diagnostic/current-state observations and are skipped by dynamic recording even when they remain valid authored strict YAML commands. Capabilities with no `fsq_command` replay policy are diagnostics and are not replayed. The recorder requires replay metadata rather than using `fsq_action_name` or tool names as replayability fallback. AgentTool events are dynamic-only diagnostics and are ignored by recording. Runtime-secret text inputs record as text-entry commands with `text: ENV_NAME` and `textType: runtimeSecret`; `get_runtime_secret` is not a replay dependency. `wait_ms` records as `waitMs` through its replay alias. The recorder must not decide replay behavior by checking tool names, `fsq_action_name`, or schema strictness metadata.

Strict runtime-secret text validation is an entry/core responsibility. Before passing steps to `StepSequenceRunner`, CLI may preflight each referenced name against the active workspace runtime-secret names and verify that its private workspace value is present. The shared runtime secret resolver reads that already-loaded private value only in memory before driver invocation; it does not rediscover from or mutate global environment state, and values are redacted from persisted events, manifests, reports, and logging.

Internal deterministic-core composition helper:

```python
bundle = run_fsq_core_case(
    case_path=Path("case.fsq.yaml"),
    registry=registry,
    harness=harness,
    output_dir=Path("runs/run-1"),
    run_id="run-1",
    post_action_delay_seconds=settings.execution.post_action_delay_seconds,
)
```

This helper is not a public CLI command. It exists to give `run --strict` and tests a single entry-layer path for running one FSQ case through the deterministic core. It should receive or build a lightweight active-platform capability registry, load the FSQ case, convert commands to canonical `ExecutableStep` records with a registry snapshot, resolve strict replay refs in memory, run them through `StepSequenceRunner` and `StepRunner` with caller-supplied harness/backend bindings and post-action delay settings, rely on `StepRunner` for centralized driver step-kind evidence and delay policy, write `evidence-manifest.json`, and return an `EvidenceBundle` whose `manifest_path` points to the written manifest.

Lifecycle orchestration wraps this deterministic command execution path for strict public runs. The lifecycle layer loads config-level and case-level hook metadata, resolves hook `runCase` paths, detects recursive hook chains across both hook origins, executes `runShell` commands, annotates hook case steps with lifecycle phase and hook origin metadata, and then delegates canonical FSQ command steps to the same `StepRunner`/`StepSequenceRunner` path. On Windows, `runShell` executes through non-interactive Windows PowerShell; on other platforms it uses the local system shell. The deterministic command execution helper must not parse or execute lifecycle hooks by itself.

The helper must not construct real platform drivers, choose backend settings, or add retry/report policy.

Internal strict deterministic-core entry:

```python
artifact = run_strict_fsq_core_case(
    case_path=Path("case.fsq.yaml"),
    registry=registry,
    harness=harness,
    output_dir=Path("runs/run-1"),
    run_id="run-1",
    post_action_delay_seconds=settings.execution.post_action_delay_seconds,
)
```

This strict entry executes the case lifecycle exactly as authored with the supplied registry and harness/backend bindings, writes `evidence-manifest.json`, generates `core-report.md` and `core-report.json`, and returns the generated Markdown `ReportArtifact`. It must not enable locator fallback, AI recovery, testcase mutation, platform-driver construction, OpenAI provider validation, or AI assertion evaluator construction. If AI assertion is needed, the caller must provide a harness/backend binding that already has an evaluator injected. Strict results remain auditable because recovery execution is not part of this entry.

Strict replay post-action stabilization is owned by `StepRunner` and configured through `execution.post_action_delay_seconds` plus capability metadata overrides. CLI strict execution passes those settings into the deterministic-core helper, which passes them to `StepRunner`. The delay is execution timing only; it should not modify parsed FSQ commands, add `waitMs` records to reports, or create synthetic evidence steps. Strict replay evidence capture is also owned by `StepRunner`: `action` steps capture before and after, `assertion` steps capture before only, `setup` steps capture after only, and `teardown` steps capture before only, always writing `screenshot` plus normalized `ui_snapshot` artifacts. CommonTool actions such as `wait_ms` receive automatic evidence capture; observation/diagnostic steps do not.

## Platform CLI Blocks

Shared CLI rules:

- `run` and Playground startup validate that `settings.harness.platform` matches the explicit configured platform and use it for readiness validation, registry bootstrap, strict harness/platform tool construction, and platform-specific error messages. `init` constructs the selected platform's existing target/config boundary models and calls Config initialization without loading runtime settings or Provider readiness.
- `run`, `report`, and `playground` require a workspace registry name plus explicit platform, resolve the name case-insensitively, validate the registered root and exact platform config identity, and load settings from that pair. They do not inspect `Path.cwd()` for workspace identity and have no implicit current-directory fallback. Provider configuration and interactive authentication belong to Control Plane Config.
- Strict replay parses cases and hook case dependencies against the active platform registry snapshot containing inherited CommonTools plus active PlatformTools.
- Dynamic recording remains capability metadata-driven and must not infer platform semantics or replayability from command names, `fsq_action_name`, or schema strictness metadata.
- Dynamic recording records by-design observation skips such as Android `uiTree`/`ui_snapshot`, Web/desktop `uiSnapshot`/`ui_snapshot`, and screenshot/snapshot tools in `recording.json` audit data without adding generated case warnings.

Android CLI behavior:

- Android dynamic and strict runs require Android app id from the active workspace target. CLI consumes the public `core` Android discovery service and owns direct-run selection policy plus transient serial assignment; configuration, workspace targets, and case metadata never supply a serial.
- Android strict runs build the active harness through `HarnessFactory`; `DriverFactory` selects the configured Android backend driver, and strict execution captures automatic `screenshot`/`ui_snapshot` evidence through the centralized driver step-kind policy. Explicit `uiTree` commands remain valid authored observations.

Web CLI behavior:

- Web strict runs do not require Android app id or serial.
- Web strict runs build the active harness through `HarnessFactory` and the config-selected Web backend driver without launching a browser. Authored `startBrowser` starts or reuses the browser/page; authored `closeBrowser` closes it. CLI must not inject either command, and `navigateTo` must not be treated as startup.
- Web strict runs capture automatic `screenshot`/`ui_snapshot` evidence through the centralized driver step-kind policy when the active Web driver has a started page. Explicit `uiSnapshot` commands remain valid authored observations.
- Web strict navigation must use fully qualified URLs or the configured Web base URL policy.

Windows CLI behavior:

- Windows strict runs do not require Android app id or serial, Web browser executable settings, or macOS Appium settings.
- Windows strict runs validate `harness.windows.backend == "pywinauto"`, the preset-owned pywinauto adapter setting, and the workspace-owned app path/window-title/launch arguments before external UI actions begin.
- Windows strict runs build the active harness through `HarnessFactory` and the config-selected Windows backend driver without launching the app during registry bootstrap or YAML parsing. Authored `launchApp` starts the configured application and authored `killApp` terminates it; CLI must not inject either command.
- Windows strict runs pass normalized settings values for app path, pywinauto backend kind, optional window title regex, and configured launch arguments into the config-selected Windows backend driver.
- Windows strict runs capture automatic `screenshot`/`ui_snapshot` evidence through the centralized driver step-kind policy and use `uiSnapshot` for explicit observation commands.

macOS CLI behavior:

- macOS strict runs do not require Android app id or serial and do not require Web browser executable settings.
- macOS strict runs validate `harness.macos.backend == "appium_mac2"`, the preset-owned Appium server setting, and the workspace-owned bundle-id/app-path target before external UI actions begin.
- macOS strict runs build the active harness through `HarnessFactory` and the config-selected macOS backend driver without connecting to Appium or launching the app during registry bootstrap or YAML parsing. Authored `launchApp` creates or reuses the Mac2 session and target app, and authored `killApp` terminates or closes it according to the driver contract. CLI must not inject either command.
- macOS strict runs capture automatic `screenshot`/`ui_snapshot` evidence through the centralized driver step-kind policy and use `uiSnapshot` for explicit observation commands.
- macOS strict runs support deterministic desktop assertions including `assertVisible` and `assertElementsOrder`; wrong element order is an assertion failure, while missing required elements are target-resolution failures.

Internal dynamic recording helper:

```python
recording = record_dynamic_run_as_strict_case(
    run_dir=Path("runs/run-1"),
    task=task,
    result=result,
    settings=settings,
    allow_failure=False,
)
```

This helper is not a public CLI command. It reads a completed dynamic run directory, writes `recorded.fsq.yaml` and `recording.json` when eligible and replayable, validates generated YAML through `fsq`, and returns an internal recording summary used for CLI output and directory-run summaries. It must not call provider APIs, execute platform actions, mutate source case files, or reveal secret values.

## Internal Structure

- `__init__.py`: Public exports only.
- `__main__.py`: Package entry point for `python -m fsq_agent.cli` and VS Code launch configurations.
- `_main.py`: Click command group and command handlers.
- `_android_devices.py`: Deterministic direct-run Android selection and CLI error mapping over the public `core` Android discovery service.
- `_task_loader.py`: Raw goal-source loading for LLM runs and path discovery/resolution for both run modes.
- `_capability_bootstrap.py`: Internal CLI wrapper around the package-private capability bootstrap helper used to construct lightweight platform capability definitions, build the capability registry, and identify provider-required capabilities and executable steps from registry metadata for dynamic and strict entry paths.
- `_core_execution.py`: Internal composition helper for deterministic FSQ case execution through `core` with a caller-supplied registry and harness/backend binding.
- `_case_lifecycle.py`: Internal strict lifecycle orchestration for config-level and case-level `onCaseStart`/`onCaseComplete`, hook `runCase` path resolution, recursion detection, shell hook execution, hook phase/origin metadata annotation, and aggregation of lifecycle status before report generation.
- Package-private `fsq_agent._strict_case_recording`: Shared post-run recorder used by CLI, Playground, and Control Plane to convert dynamic run capability events into run-local `recorded.fsq.yaml` and `recording.json` artifacts.
- `_strict_replay.py`: Internal strict-entry helper that preflights workspace runtime-secret names when needed before deterministic core execution. Final private-value resolution is owned by the shared execution resolver before driver invocation.
- `_formatting.py`: Logging-backed CLI rendering helpers for task results, concise phase-tagged live events, strict run summaries, and report paths. Concise live-event rendering is a human display concern only; it must not mutate `RunEvent` values or persisted run artifacts.
- `_logging.py`: CLI logging configuration.
- `playground` command handler in `_main.py`: Thin adapter that loads settings, maps host/port/browser flags into `PlaygroundServerOptions`, and calls `run_playground` without reimplementing playground routing or execution.
- `control-plane` command handler in `_main.py`: Thin adapter that maps host/port/browser flags into `ControlPlaneServerOptions` and calls `run_control_plane` without loading a workspace/platform or reimplementing browser-owned Control Plane selection.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 3 Layered Application.
- Public API: `main` exported from `__init__.py`.
- Internal modules: all CLI `_*.py` files are private command/helper implementation modules. Shared dynamic-run recording composition lives in package-private `fsq_agent._strict_case_recording` and is consumed only by CLI, Playground, and Control Plane entry layers.
- Domain boundaries: CLI owns argument validation, workspace-init target/config construction, registered-workspace selection for `run`/`report`/`playground`, settings loading, entry-mode orchestration, registry bootstrap, strict config/case lifecycle hook orchestration, strict replay secret resolution, dynamic recording, output rendering, and exit behavior. It does not own workspace filesystem transactions or registration policy, Provider configuration/authentication, capability implementation, StepRunner internals, FSQ parsing rules, provider runtime behavior, config parsing, or report rendering.
- Boundary models: workspace config/init results, tasks, results, settings, registry snapshots, executable steps, FSQ lifecycle hooks, replay refs, evidence bundles, and report artifacts come from `models`.
- Dependency direction: CLI may depend on entry/runtime modules (`config`, `providers`, `core`, `fsq`, `agent`, `playground`, `control_plane`, `report`, `tools`) but those modules must not import CLI. CLI imports only the public Control Plane API; Control Plane must not import CLI or Playground.
- Rationale: CLI coordinates multiple workflows and side-effect boundaries, so Level 3 is appropriate without adding repository or service-layer ceremony beyond focused helpers.

## Error Handling

CLI commands catch `FsqAgentError` subclasses from `models`, render concise user-facing messages, and exit nonzero. Unexpected exceptions are logged with trace details and summarized in the console.

Input validation failures, including unsupported commands/options, invalid Control Plane ports, missing workspace/platform selections, unregistered or unavailable workspaces, unsupported/unconfigured/unavailable platforms, invalid registered workspace or platform-config identity, missing or multiple run inputs, escaped/traversing/symlinked case inputs or hook dependencies, `--strict --goal`, invalid record flags, unreadable dynamic case files, invalid strict YAML, malformed lifecycle metadata, empty case directories, missing hook cases, recursive hook chains, invalid active platform targets, invalid Web navigation/base URL policy, invalid preset-owned platform settings, invalid Android serial selection, missing platform-private secret names/values, missing provider readiness for authored strict `assertWithAI`, unresolved reports, or missing generated frontend assets fail before external UI actions or writes begin for the affected command, case, hook, or server. Dynamic `--case-yaml` input does not fail merely because content is invalid YAML, because that path treats it as raw planning reference text.

Control Plane startup converts shared `FsqAgentError` failures and OS-level startup failures into concise CLI errors and nonzero exits. CLI must not expose secret values, hidden reasoning, or raw server internals.

Strict lifecycle failures during execution, including failed start hooks, failed hook cases, nonzero shell hook exit codes, shell launch failures, failed main commands, and failed complete hooks, must be reflected in the owning strict case result and report without enabling recovery. `onCaseComplete` hooks must still run after a start hook or main command failure when they are configured.

`init` maps Config initialization outcomes to `initialized`, `platform_added`, `unchanged`, or `updated` output. Input/configuration conflicts and filesystem failures exit nonzero and produce one safe terminal machine record when machine output is selected. It does not load Provider readiness, modify Provider state, parse `.env`, or start authentication. An unsupported `--provider` option fails argument parsing before side effects.

Recording failures happen after a dynamic run and must not change that dynamic run's status. The CLI should log and summarize recording errors, including no replayable commands, runtime-secret text references with missing names, unsupported replay commands, generated YAML validation failures, and existing `recorded.fsq.yaml` conflicts. Directory runs continue after per-case recording failures.

## Verification Scope

- Verification covers init argument/target/env validation, rejected `--provider`, Config delegation, controlled update behavior, Human and single-record machine output, non-init machine-output rejection, dynamic goal/raw-case task construction, strict-case execution entry behavior, strict lifecycle ordering/failure semantics, dynamic recording handoff, report lookup, live event formatting, and thin Playground/Control Plane server startup delegation.
- Boundary verification ensures `run`/`report`/`playground` require and resolve a valid registered workspace name plus explicit configured platform independently of the current directory; Android direct runs reject invalid, missing, or ambiguous device selection before execution; all case and lifecycle paths remain under that platform's cases root; all run artifacts remain under that platform's run root; init writes only through Config's registered workspace operations and never exposes private env values; Control Plane can start elsewhere; unsupported commands/options fail before side effects; and strict/dynamic execution delegates behavior to owning modules.

## Current Invariants

- CLI commands are thin adapters over module APIs, not a second orchestration layer.
- Capability decorators are not a CLI concern. CLI entry paths consume validated `CapabilityRegistry` instances, registry snapshots, harness/backend bindings, and normalized runner/event metadata.
- Strict provider requirement detection uses the shared package-private capability bootstrap contract: provider-required canonical capability names are derived by comparing the active platform registry with and without provider-backed capabilities, and case steps are checked through registry resolution. CLI must not hard-code provider gating by authored or canonical action name.
- The public command surface is limited to `init`, `run`, `report`, `playground`, and `control-plane`. Unsupported command names are not retained as compatibility aliases.
- `init` is a thin non-interactive adapter over Config initialization. It initializes one platform per invocation, defaults only its omitted parent to `Path.cwd()`, preserves explicit registry-based selection for every runtime command, and never introduces current-directory workspace discovery.
- Root `--output` is a presentation selector, not runtime configuration. Init supports Human and one-record JSON/JSONL terminal results; all other commands accept only Human until they define their own machine-output contracts.
- `run`, `report`, and `playground` require `--workspace NAME --platform PLATFORM` and intentionally do not accept `--config` or `--env-file`. They resolve registered workspace identity plus exact `.fsq/config/config.<platform>.yaml`, never infer a sole configured platform, and never use `Path.cwd()` as a workspace fallback.
- A missing selection, unknown registry name, unavailable workspace, or unsupported/unconfigured/unavailable platform fails with create-or-repair guidance and no workspace or run writes.
- `run` applies `--tracing` or `--no-tracing` as a one-run override after `load_settings` returns and before LLM or provider-backed AI assertion validation. Sensitive tracing is never enabled by CLI.
- Android app id is workspace target truth. Android serial is transient run state; CLI exposes it only as `run --android-serial`, automatically selects only a sole online device when omitted, and never persists the selection.
- Streaming CLI output logs live `RunEvent` values from the agent. Concise format is the default human-readable stream and includes `HH:MM:SS LEVEL` log prefixes so operators can distinguish informational, warning, and error events. Human-readable event rendering must derive concise display phase labels from existing event type/title data, including pre-plan, startup, execution, verification, report, and run-level fallbacks; derive tool identity from existing event tool fields, matching started events, safe payload metadata, or safe output preview metadata; derive tool outcome from existing payload status, runner-result status, safe preview status, or event type; keep arguments compact, redacted, and faithful to the event value, including explicit `null` values; preserve meaningful safe reasoning-summary messages as concise model reason summaries; suppress generic reasoning-summary notices that contain no model-readable content; summarize structured SDK agent messages; and suppress verbose `tool_output_preview` JSON unless it is short and no better summary exists. When verbose output is suppressed, the concise log should point to existing result, artifact, report, or run-output hints when available and must not invent new artifacts or files.
- Concise log cleanup is a presentation-only behavior. It must not change dynamic execution flow, `RunEvent` model fields, persisted `events.jsonl`, reports, recording manifests, generated strict YAML, tool artifacts, or intermediate run outputs. JSONL format emits one raw serialized event per log message for CI and log processors; the CLI formatter bypasses prefixes and human-readable compaction for those raw JSONL records so the stream remains machine-readable.
- Normal `run` is always dynamic LLM goal/reference execution. `--goal` supplies the user goal text. `--case-yaml` and `--case-dir` supply raw file content as reference material and must not use `FsqCaseLoader` or `FsqTaskAdapter`.
- Dynamic task construction separates planning references from final verification. `--goal` tasks use `planning_reference_kind="goal"` with the normalized goal text. Raw case tasks use `planning_reference_kind="raw_case"` with source path plus complete raw file content. The CLI does not derive final verifier requirements itself; pre-plan must summarize one `verification_goal` before external UI actions.
- Dynamic run recording is post-run evidence transformation, not task execution. It reads persisted normalized capability events after `FsqAgent.run` returns and writes only under that run directory.
- Recorded cases reflect actual successfully completed non-observation capabilities with `ReplayPolicy(kind="fsq_command")`. Runtime-secret inputs are recorded as text-entry command parameters, not as dependency replay capabilities. The recorder must skip observation step kinds, and must not invent setup, teardown, Web `startBrowser`/`closeBrowser`, assertions, locator fallback, recovery actions, or source YAML mutations. Missing assertions, observations, or lifecycle actions produce warnings when relevant.
- Runtime secrets in recorded cases are represented by workspace `env` names on text-entry commands using `textType: runtimeSecret`. Missing `textType` remains literal for YAML compatibility. Private workspace values are resolved only in memory during execution and are never written to generated YAML, event previews, manifests, reports, recording manifests, or logs.
- `run --strict` is strict-core execution. It parses FSQ YAML including lifecycle hook metadata, uses config-owned active platform settings including optional `caseLifecycle` hooks, and does not construct or invoke LLM components for planning, recovery, locator fallback, action repair, or final verification. Strict runs resolve platform aliases through the active registry and build the active harness through `HarnessFactory`, with `CommonPlatformTools` inherited by every platform and the concrete backend driver selected by config. CLI owns lifecycle hook orchestration around canonical command execution: config `onCaseStart`, case `onCaseStart`, main commands when before hooks pass, case `onCaseComplete`, and config `onCaseComplete` after before hooks have been attempted. Strict lifecycle execution should emit concise INFO logs for phase start and per-step/per-hook action completion, including phase (`before case`, `main case`, or `after case`), action label, status, and failure message when present. No extra CLI flag is required for these strict progress logs; existing logging configuration controls whether INFO logs are displayed. The sole provider-backed exception is an explicitly authored `assertWithAI` step, for which CLI may build and inject an AI assertion evaluator into the active harness/backend support before execution.
- Directory execution is intentionally serial because UI automation cases share external device and application state. Each case still creates independent run state so SDK sessions, harness context, AgentTool state, and platform CommonTool state do not leak across cases.
- `report` is a lookup/print command only; report generation happens during execution. It resolves either LLM reports or strict-core reports without exposing separate report commands.
- `playground` is a local developer convenience entry point. CLI owns only argument parsing, settings loading, and server startup; the `playground` module owns HTTP routes, production serving of generated browser assets, session state, execution adapters, screenshot preview, replay video handling, and report lookup. Frontend dependency resolution and compilation belong to the repository root npm/Vite project.
- `control-plane` is a directory-independent local product entry point for workspace management and execution. CLI owns only argument parsing and server startup; `control_plane` owns registry-backed workspace APIs plus workspace-aware Devices runtime. The command has no `--platform` or selected-workspace option.
- CLI logging never emits API key values; it may log the configured API key environment variable name and whether it is present.
