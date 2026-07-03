# Module: cli

## Purpose

Provide the public command line surface for fsq-agent: initialize/check runtime readiness, set up and check local LLM provider configuration, bootstrap lightweight platform-selected capability registries, run either dynamic LLM goal/reference execution or strict-core YAML execution for the active platform with optional explicit provider-backed `assertWithAI`, optionally record dynamic LLM runs into strict-replay FSQ YAML artifacts from capability replay metadata, print stored reports from prior runs, and start the local browser playground.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, FSQ case models, capability registry snapshots, replay policy metadata, strict replay refs, wait parameter models, report artifacts, and shared exceptions.
- `config`: Loads settings and validates provider-only, LLM runtime, or strict-core readiness.
- `providers`: Builds shared provider sessions, performs provider setup/auth readiness checks, and builds AI assertion evaluators for dynamic runs and strict runs that contain explicit `assertWithAI` steps.
- `core`: Composes capability registry bootstrap, deterministic `ExecutableStep` execution through `StepRunner`/`StepSequenceRunner`, runner events, and evidence manifest writing at the entry boundary.
- `fsq`: Loads `.codex.yaml` FSQ cases and converts parsed cases into canonical strict-core executable steps using a registry snapshot.
- `agent`: Runs dynamic LLM goal/reference task workflows and persists recordable safe event metadata.
- `playground`: Starts the local browser playground server from loaded settings and CLI host/port/browser options.
- `report`: Generates strict-core reports and resolves stored LLM or strict-core reports by run id.
- `tools`: Provides dynamic-only AgentTool hosts for default LLM execution.

The CLI module composes strict registry bootstrap from public `core` platform tool APIs and dynamic execution from `agent`/`tools` APIs. It must not import `capabilities` or decorator internals directly; declaration discovery happens inside the owning capability host modules.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `main`: CLI entry point for package scripts.

Current commands:

- `fsq-agent init --platform android|web|windows|macos --workspace PATH`: Initialize or verify the fsq-agent workspace for one committed platform preset, validate static configuration, and print readiness for the default LLM run path, strict-core run path, and provider-backed AI assertion readiness. Static configuration or workspace failures exit nonzero. Mode-specific dependency gaps are reported as readiness failures so strict-only users are not forced to configure LLM credentials unless they execute cases containing `assertWithAI`.
- `fsq-agent setup llm --provider github_copilot|azure_openai --check-only`: Set up, update, or check only the local LLM provider environment. This command is platform-neutral and must not expose `--platform`, `--workspace`, `--env-file`, or `--config`. It uses the current working directory as the setup root, writes the current directory `.env` file in normal setup mode, and uses the current directory `.fsq-agent-workspace` as the managed workspace for provider setup state such as the GitHub Copilot token cache. `--provider` is required. Without `--check-only`, the command may create or update `.env`, may initialize `.fsq-agent-workspace`, may prompt interactively for Azure values, and may trigger GitHub Copilot device-code authentication. With `--check-only`, the command is read-only: it must not write `.env`, create or modify auth files, initialize a workspace, prompt for missing Azure values, or start Copilot device-code authentication. The command validates provider-local readiness only and must not validate Android/Web/Windows/macOS harness settings or send a live model request.
- `fsq-agent run --platform android|web|windows|macos --goal TEXT --workspace PATH --tracing/--no-tracing --stream/--no-stream --stream-format concise|jsonl --record --record-on-failure`: Run one dynamic LLM task from a natural-language goal using the committed config preset for the selected platform. This is the default run mode. CLI task construction must set the explicit planning reference kind to `goal` and the planning reference text to the normalized goal. Internal pre-planning produces both ordered execution key actions and the final `verification_goal` before external UI actions begin. Streaming is enabled by default for LLM run events, and `concise` is the default human-readable stream format. `--tracing` and `--no-tracing` optionally override `openai_agents.tracing_enabled` for this run after settings load and before runtime validation; when omitted, config/default tracing applies. SDK trace export still requires `OPENAI_API_KEY`, and the runtime disables SDK tracing for the run when that variable is absent or blank. `--record` optionally records a strict-replay `.codex.yaml` artifact under the completed run directory when the final status is `success`; `--record-on-failure` permits draft recording for `failed` or `inconclusive` runs and is valid only with `--record`.
- `fsq-agent run --platform android|web|windows|macos --case-yaml PATH --workspace PATH --tracing/--no-tracing --stream/--no-stream --stream-format concise|jsonl --record --record-on-failure`: In default mode, read the file as complete UTF-8 text and run one dynamic LLM task using that raw content as reference material. CLI task construction must set the explicit planning reference kind to `raw_case` and the planning reference text to a stable envelope containing the source path and complete raw file content. The CLI must not parse the input YAML for execution, normalize FSQ commands, extract key actions, derive local operation/assertion verifier requirements, or create a file-name-only final verification goal for this path. Pre-plan owns deriving ordered key actions and one `verification_goal` from the raw case reference before UI execution. If `--record` is enabled, post-run recording may parse only the persisted event log and write a generated `recorded.codex.yaml` under the run directory.
- `fsq-agent run --platform android|web|windows|macos --case-dir PATH --workspace PATH --tracing/--no-tracing --stream/--no-stream --stream-format concise|jsonl --record --record-on-failure`: In default mode, discover `*.codex.yaml` files recursively, sort them, read each file as complete UTF-8 text, and run one dynamic LLM task per file serially. Each task must receive its own `raw_case` planning reference containing that file's source path and complete raw content; pre-plan derives per-case key actions and `verification_goal`. Execution continues after failed cases and prints a final operational summary. When recording is enabled, each case run independently attempts to write `recorded.codex.yaml` and `recording.json`; recording failures do not stop later dynamic cases.
- `fsq-agent run --platform android|web|windows|macos --strict --case-yaml PATH --workspace PATH --tracing/--no-tracing`: Run one `.codex.yaml` FSQ case through the strict-core path. CLI loads settings from the committed config preset for the selected platform, constructs the selected platform harness, driver, and platform tool provider without connecting to a real Android device or launching a Playwright browser, builds and validates a `CapabilityRegistry` containing inherited CommonTools plus active PlatformTools, parses the case through `FsqExecutableStepAdapter(registry_snapshot)`, validates and resolves strict replay refs such as `{runtimeSecret: NAME}` in memory before external UI actions begin, and executes canonical steps through `StepSequenceRunner` with `StepRunner`, the configured active harness/platform provider, and `settings.execution.post_action_delay_seconds`. Post-action delay is applied by `StepRunner` after invoke and before finalize evidence; it must not inject `waitMs` commands or synthetic evidence steps. Capability-derived evidence policy is also applied by `StepRunner`, so strict replay receives the same `capture_evidence=True` screenshot plus active platform observation artifacts as dynamic execution without CLI-specific policy mapping. The run writes `evidence-manifest.json`, generates `core-report.md/json`, and prints generated paths. Locator fallback, action repair, recovery, testcase mutation, and strict-mode recording are not allowed. If the parsed case contains an explicitly authored `assertWithAI`/`assert_with_ai` capability, CLI applies any tracing override before provider validation, validates provider readiness, builds a provider-backed AI assertion evaluator through `providers`, and injects it into the active harness/backend support before execution.
- `fsq-agent run --platform android|web|windows|macos --strict --case-dir PATH --workspace PATH --tracing/--no-tracing`: Run discovered `*.codex.yaml` files serially through the same deterministic strict-core path. Execution continues after failed cases, writes a directory-run summary, and exits nonzero when any case fails.
- `fsq-agent report --platform android|web|windows|macos --run-id ID --format markdown|json --workspace PATH`: Print a stored report from the selected platform preset's configured runs directory. The command resolves either `report.md/json` for LLM runs or `core-report.md/json` for strict-core runs and fails when no matching report exists or when the run id is ambiguous.
- `fsq-agent playground --platform android|web|windows|macos --workspace PATH --host HOST --port PORT --open-browser/--no-open-browser`: Load the same platform-preset runtime settings used by other CLI commands and start the local single-user playground HTTP server. The command blocks until the server exits, serves the package-owned static browser UI, optionally opens the browser, and delegates runtime behavior to the `playground` module. Startup failures from configuration or server binding errors must render concise CLI errors and exit nonzero.

Public CLI commands do not expose `--config`; old `--config` invocations fail as unknown options.

`setup llm` writes only managed provider keys in the current directory `.env`: `FSQ_LLM_PROVIDER`, `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`, and `AZURE_OPENAI_API_KEY`. It must preserve unrelated `.env` lines and comments, replace existing assignments for managed keys, and append missing managed keys. Copilot setup writes only `FSQ_LLM_PROVIDER=github_copilot` and must not delete existing Azure variables. Azure setup writes `FSQ_LLM_PROVIDER=azure_openai` plus the fixed Azure variables. Existing process environment values take precedence over `.env`; when an effective process value differs from the `.env` value being written or checked, CLI output must warn that the process environment wins and validate against the effective value.

`setup llm --provider github_copilot` validates provider-only settings, ensures interactive Copilot auth readiness in normal setup mode through public `providers` APIs, and reports local setup readiness without sending a Responses API model request. If no valid cached GitHub OAuth token is available, normal setup mode runs the GitHub device-code flow and caches the token under `.fsq-agent-workspace/auth/github-copilot-token.json`. In `--check-only` mode, missing or expired cached Copilot auth is a readiness failure with a next-step message to run normal setup.

`setup llm --provider azure_openai` prompts for `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`, and `AZURE_OPENAI_API_KEY` in normal setup mode. Endpoint and model prompts may show existing non-secret defaults; API key input must be hidden and may keep an existing non-placeholder effective key without echoing it. Azure readiness validates endpoint normalization to the `/openai/v1/` form, model presence, API key presence, and placeholder-key rejection. It must state that this is local configuration readiness, not proof that the Azure deployment authorizes model calls.

`--goal`, `--case-yaml`, and `--case-dir` are mutually exclusive. `--strict --goal` is invalid because strict-core execution requires authored YAML steps. `--strict --record` and `--strict --record-on-failure` are invalid because recording is a dynamic-run post-processing workflow. `--record-on-failure` without `--record` is invalid. Relative case paths resolve against `cases.dir` first, then the current working directory.

Dynamic recording writes the following run-local files when attempted:

```text
<runs_dir>/<run-id>/
    recorded.codex.yaml
    recording.json
```

`recorded.codex.yaml` contains two YAML documents: generated FSQ metadata followed by recorded commands. Generated metadata must include `tags` identifying the case as recorded and `properties.recording` with source run id, source task id, source status, `draft`, required runtime secret names, and warnings. `recording.json` contains recording status, command count, recorded case path when present, required runtime secret names, warnings, skipped tool calls, validation status, and errors when recording fails. Neither file may contain secret values.

The recording helper reconstructs logical replay entries from the dynamic run's `events.jsonl` by consuming structured capability metadata emitted by `StepRunner` for CommonTool and PlatformTool calls. A completed event with `replay.kind == "fsq_command"` appends `{replay.alias: safe_replay_params}` to generated strict YAML when the status indicates success and params validate, falling back to the started event's JSON arguments only when no safe replay params are present. A completed event with `replay.kind == "dependency"` records dependency metadata without adding a strict step. Capabilities with no replay policy are diagnostics and are not replayed. AgentTool events are dynamic-only diagnostics and are ignored by recording. `get_runtime_secret` is recorded only as a runtime-secret name dependency that may replace redacted later arguments with `{runtimeSecret: NAME}`; `wait_ms` records as `waitMs` through its replay alias. The recorder must not decide replay behavior by checking tool names.

Strict replay reference resolution is an entry-layer responsibility. Before passing steps to `StepSequenceRunner`, CLI validates every referenced runtime secret name against `runtime_secrets.allowed_env_names`, verifies the corresponding environment value exists, substitutes secret values into step params only in memory, and redacts any resolved secret values from persisted events, manifests, reports, and logging.

Internal deterministic-core composition helper:

```python
bundle = run_fsq_core_case(
    case_path=Path("case.codex.yaml"),
    registry=registry,
    harness=harness,
    output_dir=Path("runs/run-1"),
    run_id="run-1",
    post_action_delay_seconds=settings.execution.post_action_delay_seconds,
)
```

This helper is not a public CLI command. It exists to give `run --strict` and tests a single entry-layer path for running one FSQ case through the deterministic core. It should receive or build a lightweight active-platform capability registry, load the FSQ case, convert commands to canonical `ExecutableStep` records with a registry snapshot, resolve strict replay refs in memory, run them through `StepSequenceRunner` and `StepRunner` with caller-supplied harness/backend bindings and post-action delay settings, rely on `StepRunner` for capability-derived evidence and delay policy, write `evidence-manifest.json`, and return an `EvidenceBundle` whose `manifest_path` points to the written manifest.

The helper must not construct real platform drivers, choose backend settings, or add retry/report policy. Those remain future entry-layer responsibilities after the core execution contract is stable.

Internal strict deterministic-core entry:

```python
artifact = run_strict_fsq_core_case(
    case_path=Path("case.codex.yaml"),
    registry=registry,
    harness=harness,
    output_dir=Path("runs/run-1"),
    run_id="run-1",
    post_action_delay_seconds=settings.execution.post_action_delay_seconds,
)
```

This strict entry executes the YAML exactly as authored with the supplied registry and harness/backend bindings, writes `evidence-manifest.json`, generates `core-report.md` and `core-report.json`, and returns the generated Markdown `ReportArtifact`. It must not enable locator fallback, AI recovery, testcase mutation, platform-driver construction, OpenAI provider validation, or AI assertion evaluator construction. If AI assertion is needed, the caller must provide a harness/backend binding that already has an evaluator injected. Recovery execution should use a separate future entry so strict results remain auditable.

Strict replay post-action stabilization is owned by `StepRunner` and configured through `execution.post_action_delay_seconds` plus capability metadata overrides. CLI strict execution passes those settings into the deterministic-core helper, which passes them to `StepRunner`. The delay is execution timing only; it should not modify parsed FSQ commands, add `waitMs` records to reports, or create synthetic evidence steps.

## Platform CLI Blocks

Shared CLI rules:

- `run`, `init`, and playground startup use `settings.harness.platform` to select readiness validation, registry bootstrap, strict harness/platform tool construction, and platform-specific error messages.
- `setup llm` is platform-neutral, uses current-directory setup paths, and validates only provider-local readiness.
- Strict replay parses cases against the active platform registry snapshot containing inherited CommonTools plus active PlatformTools.
- Dynamic recording remains capability metadata-driven and must not infer platform semantics from command names.

Android CLI behavior:

- Android strict runs require Android app id from environment or case metadata according to strict validation rules.
- Android strict runs build `AndroidHarness` with `UiAutomator2AndroidDriver` and capture `screenshot`/`ui_tree` evidence.

Web CLI behavior:

- Web strict runs do not require Android app id or serial.
- Web strict runs build `WebHarness` with `PlaywrightWebDriver` without launching a browser. Authored `startBrowser` starts or reuses the browser/page; authored `closeBrowser` closes it. CLI must not inject either command, and `navigateTo` must not be treated as startup.
- Web strict runs capture `screenshot`/`page_snapshot` evidence only when the active Web driver has a started page.
- Web strict navigation must use fully qualified URLs or the configured Web base URL policy.

Windows CLI behavior:

- Windows strict runs do not require Android app id or serial, Web browser executable settings, or macOS Appium settings.
- Windows strict runs validate `harness.windows.backend == "pywinauto"` plus environment-backed Windows app path and pywinauto adapter settings before external UI actions begin.
- Windows strict runs build `WindowsHarness` with `PywinautoWindowsDriver` without launching the app during registry bootstrap or YAML parsing. Authored `launchApp` starts the configured application and authored `killApp` terminates it; CLI must not inject either command.
- Windows strict runs pass normalized settings values for app path, pywinauto backend kind, optional window title regex, and configured launch arguments into `PywinautoWindowsDriver`.
- Windows strict runs capture `screenshot`/`ui_snapshot` evidence for capture-enabled PlatformTools and use `uiSnapshot` for explicit observation commands.

macOS CLI behavior:

- macOS strict runs do not require Android app id or serial and do not require Web browser executable settings.
- macOS strict runs validate `harness.macos.backend == "appium_mac2"` plus environment-backed Appium server and target app settings before external UI actions begin.
- macOS strict runs build `MacOSHarness` with `AppiumMac2Driver` without connecting to Appium or launching the app during registry bootstrap or YAML parsing. Authored `launchApp` creates or reuses the Mac2 session and target app, and authored `killApp` terminates or closes it according to the driver contract. CLI must not inject either command.
- macOS strict runs capture `screenshot`/`ui_snapshot` evidence for capture-enabled PlatformTools and use `uiSnapshot` for explicit observation commands.
- macOS strict runs support deterministic desktop assertions including `assertVisible` and `assertElementsOrder`; wrong element order is an assertion failure, while missing required elements are target-resolution failures.

Future platform CLI behavior:

- New platforms must add explicit readiness and strict construction rules before the CLI exposes them.

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

This helper is not a public CLI command. It reads a completed dynamic run directory, writes `recorded.codex.yaml` and `recording.json` when eligible and replayable, validates generated YAML through `fsq`, and returns an internal recording summary used for CLI output and directory-run summaries. It must not call provider APIs, execute platform actions, mutate source case files, or reveal secret values.

## Internal Structure

- `__init__.py`: Public exports only.
- `__main__.py`: Package entry point for `python -m fsq_agent.cli` and VS Code launch configurations.
- `_main.py`: Click command group and command handlers.
- `_llm_setup.py`: Internal provider setup orchestration for `setup llm`, including current-directory setup path selection, provider-only settings loading, provider readiness calls, prompt coordination, and non-secret status summaries.
- `_env_file.py`: Internal `.env` reader/upserter for managed provider keys that preserves unrelated lines and comments and reports process-environment precedence conflicts without exposing secret values.
- `_task_loader.py`: Raw goal-source loading for LLM runs and path discovery/resolution for both run modes.
- `_capability_bootstrap.py`: Internal CLI wrapper around the package-private capability bootstrap helper used to construct lightweight platform capability definitions, build the capability registry, validate it, and return active harness/backend construction data for dynamic and strict entry paths.
- `_core_execution.py`: Internal composition helper for deterministic FSQ case execution through `core` with a caller-supplied registry and harness/backend binding.
- `_strict_case_recording.py`: Internal post-run recorder that converts dynamic run capability events into run-local `recorded.codex.yaml` and `recording.json` artifacts.
- `_strict_replay.py`: Internal strict-entry helper that validates and resolves strict replay refs, including runtime-secret refs, before deterministic core execution.
- `_formatting.py`: Logging-backed CLI rendering helpers for task results, concise phase-tagged live events, strict run summaries, and report paths. Concise live-event rendering is a human display concern only; it must not mutate `RunEvent` values or persisted run artifacts.
- `_logging.py`: CLI logging configuration.
- `playground` command handler in `_main.py`: Thin adapter that loads settings, maps host/port/browser flags into `PlaygroundServerOptions`, and calls `run_playground` without reimplementing playground routing or execution.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 3 Layered Application.
- Public API: `main` exported from `__init__.py`.
- Internal modules: all `_*.py` files are private command/helper implementation modules.
- Domain boundaries: CLI owns argument validation, settings loading, provider setup orchestration, current-directory `.env` upsert behavior for setup-managed keys, entry-mode orchestration, registry bootstrap, strict replay secret resolution, dynamic recording, output rendering, and exit behavior. It does not own capability implementation, StepRunner internals, FSQ parsing rules, provider runtime behavior, provider authentication internals, or report rendering.
- Boundary models: tasks, results, settings, registry snapshots, executable steps, replay refs, evidence bundles, and report artifacts come from `models`.
- Dependency direction: CLI may depend on entry/runtime modules (`config`, `providers`, `core`, `fsq`, `agent`, `playground`, `report`, `tools`) but those modules must not import CLI.
- Rationale: CLI coordinates multiple workflows and side-effect boundaries, so Level 3 is appropriate without adding repository or service-layer ceremony beyond focused helpers.

## Error Handling

CLI commands catch `FsqAgentError` subclasses from `models`, render concise user-facing messages, and exit nonzero. Unexpected exceptions are logged with trace details and summarized in the console.

Input validation failures, including missing input source, multiple input sources, `--strict --goal`, invalid record flag combinations, unreadable dynamic case files, invalid strict YAML, empty case directories, missing strict Android app id from `FSQ_ANDROID_APP_ID` or FSQ case metadata when the active platform is Android, invalid Web navigation/base URL policy when the active platform is Web, invalid or missing Windows app path/pywinauto adapter settings when the active platform is Windows, invalid or missing macOS Appium/target settings when the active platform is macOS, missing strict replay secret allowlist/presence, missing provider readiness for authored strict `assertWithAI`, or unresolved reports must fail before external UI actions begin. Dynamic `--case-yaml` input must not fail merely because the file is invalid YAML, because that path does not parse YAML.

Provider setup failures, including invalid `--provider`, unsupported `FSQ_LLM_PROVIDER`, `.env` read/write errors, non-interactive terminals with missing required prompt values, Azure endpoint/model/API-key validation failures, placeholder Azure API keys, process-environment conflicts that make the effective provider invalid, missing or expired Copilot cached auth in `--check-only`, or Copilot auth/token exchange failures must fail with concise diagnostics and no secret values. `--check-only` failures must occur without writing files or starting interactive auth.

Recording failures happen after a dynamic run and must not change that dynamic run's status. The CLI should log and summarize recording errors, including no replayable commands, ambiguous secret binding, redacted values with no matching runtime secret, unsupported replay commands, generated YAML validation failures, and existing `recorded.codex.yaml` conflicts. Directory runs continue after per-case recording failures.

## Testing Contract

- Unit tests should cover CLI input validation, `setup llm` command registration and option validation, provider setup/check `.env` upserts, check-only no-write/no-auth behavior, process-environment precedence warnings, dynamic raw-case task construction, strict-case entry behavior, recording handoff behavior, report lookup, and live event formatting.
- Live event formatting tests should construct representative `RunEvent` values and verify that concise output renders clear phase labels for pre-plan, startup, execution, verification, and run-level events; tool-started lines include the tool name and compact redacted arguments, including explicit `null` values supplied by the event; tool-completed lines include derived status, tool identity correlated from matching started events when needed, duration, safe result hints, and artifact hints without dumping verbose JSON output; failed tool outcomes include failure category and error message; meaningful reasoning summaries remain visible as safe single-line model reason summaries while generic empty-summary notices are suppressed; structured SDK agent messages are summarized without raw SDK object representations; and `stream_format="jsonl"` still emits raw serialized event JSON without human-readable prefixes or display compaction.
- Focused verification for CLI setup changes should include `./.venv/bin/python -m pytest tests/test_cli.py` on POSIX or `./.venv/Scripts/python.exe -m pytest tests/test_cli.py` on Windows, plus any dedicated CLI formatting or provider setup test file added during implementation.

## Design Decisions

- CLI commands are thin adapters over module APIs, not a second orchestration layer.
- Capability decorators are not a CLI concern. CLI entry paths consume validated `CapabilityRegistry` instances, registry snapshots, harness/backend bindings, and normalized runner/event metadata.
- The public command surface is intentionally limited to `init`, `setup llm`, `run`, `report`, and `playground`. Deleted command names are not retained as compatibility aliases.
- `setup llm` is independent from `init` because it mutates local provider environment/auth state while `init` remains a platform-preset workspace/readiness check. The setup command intentionally does not accept `--platform`, `--workspace`, or `--env-file` in this cycle; it uses the current working directory `.env` and `.fsq-agent-workspace` so the manual setup target is explicit.
- CLI owns only `.env` file upsert mechanics and prompt coordination for provider setup. Provider selection normalization and validation belong to `config`; Copilot device-code authentication, token cache interpretation, Copilot token exchange, and Azure/Copilot client construction belong to `providers`.
- `run` applies `--tracing` or `--no-tracing` as a one-run override after `load_settings` returns and before LLM or provider-backed AI assertion validation. Sensitive tracing is never enabled by CLI.
- Android app id and serial are local environment-backed settings resolved by `config` from `FSQ_ANDROID_APP_ID` and `FSQ_ANDROID_SERIAL`; CLI does not expose app id or serial flags.
- Streaming CLI output logs live `RunEvent` values from the agent. Concise format is the default human-readable stream and includes `HH:MM:SS LEVEL` log prefixes so operators can distinguish informational, warning, and error events. Human-readable event rendering must derive concise display phase labels from existing event type/title data, including pre-plan, startup, execution, verification, report, and run-level fallbacks; derive tool identity from existing event tool fields, matching started events, safe payload metadata, or safe output preview metadata; derive tool outcome from existing payload status, runner-result status, safe preview status, or event type; keep arguments compact, redacted, and faithful to the event value, including explicit `null` values; preserve meaningful safe reasoning-summary messages as concise model reason summaries; suppress generic reasoning-summary notices that contain no model-readable content; summarize structured SDK agent messages; and suppress verbose `tool_output_preview` JSON unless it is short and no better summary exists. When verbose output is suppressed, the concise log should point to existing result, artifact, report, or run-output hints when available and must not invent new artifacts or files.
- Concise log cleanup is a presentation-only behavior. It must not change dynamic execution flow, `RunEvent` model fields, persisted `events.jsonl`, reports, recording manifests, generated strict YAML, tool artifacts, or intermediate run outputs. JSONL format emits one raw serialized event per log message for CI and log processors; the CLI formatter bypasses prefixes and human-readable compaction for those raw JSONL records so the stream remains machine-readable.
- Normal `run` is always dynamic LLM goal/reference execution. `--goal` supplies the user goal text. `--case-yaml` and `--case-dir` supply raw file content as reference material and must not use `FsqCaseLoader` or `FsqTaskAdapter`.
- Dynamic task construction separates planning references from final verification. `--goal` tasks use `planning_reference_kind="goal"` with the normalized goal text. Raw case tasks use `planning_reference_kind="raw_case"` with source path plus complete raw file content. The CLI does not derive final verifier requirements itself; pre-plan must summarize one `verification_goal` before external UI actions.
- Dynamic run recording is post-run evidence transformation, not task execution. It reads persisted normalized capability events after `FsqAgent.run` returns and writes only under that run directory.
- Recorded cases reflect actual successfully completed capabilities with `ReplayPolicy(kind="fsq_command")` plus supported dependency capabilities with `ReplayPolicy(kind="dependency")`. The recorder must not invent setup, teardown, Web `startBrowser`/`closeBrowser`, assertions, locator fallback, recovery actions, or source YAML mutations. Missing assertions or lifecycle actions produce warnings.
- Runtime secrets in recorded cases are represented by environment variable names through `runtimeSecret` refs. Secret values are resolved only in memory during strict replay and are never written to generated YAML, event previews, manifests, reports, recording manifests, or logs.
- `run --strict` is strict-core execution. It parses FSQ YAML, uses config-owned active platform settings, and does not construct or invoke LLM components for planning, recovery, locator fallback, action repair, or final verification. Android strict runs use Android aliases, `AndroidHarness`, `CommonPlatformTools`, and the selected Android backend driver; Web strict runs use Web aliases, `WebHarness`, `CommonPlatformTools`, and the selected Web backend driver; macOS strict runs use macOS aliases, `MacOSHarness`, `CommonPlatformTools`, and `AppiumMac2Driver`. The sole provider-backed exception is an explicitly authored `assertWithAI` step, for which CLI may build and inject an AI assertion evaluator into the active harness/backend support before execution.
- Directory execution is intentionally serial because UI automation cases share external device and application state. Each case still creates independent run state so SDK sessions, harness context, AgentTool state, and platform CommonTool state do not leak across cases.
- `report` is a lookup/print command only; report generation happens during execution. It resolves either LLM reports or strict-core reports without exposing separate report commands.
- `playground` is a local developer convenience entry point. CLI owns only argument parsing, settings loading, and server startup; the `playground` module owns HTTP routes, browser assets, session state, execution adapters, screenshot preview, replay video handling, and report lookup.
- CLI logging never emits API key values; it may log the configured API key environment variable name and whether it is present.
