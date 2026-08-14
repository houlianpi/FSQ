# Module: config

## Purpose

Load, persist, merge, normalize, and validate versioned workspace configuration, the user-level active Provider plus workspace registry, repository platform presets, retained system settings, private workspace runtime-secret values, and the effective runtime settings used by dynamic, strict, Playground, and Control Plane entry surfaces. Config owns workspace creation/update transactions and path validation; it does not execute runs or expose workspace files over HTTP.

## Dependencies

- `models`: Uses runtime settings models plus `WorkspaceConfig`, platform workspace target models, `WorkspaceRegistryEntry`, `WorkspaceSettings`, and `ConfigurationError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `Settings`: Runtime aggregate combining preset policy, workspace target and resolved paths, retained system settings, private workspace runtime-secret values, reusable repository skills, and the latest Provider snapshot.
- `UserProviderConfig`: Validated presentation/runtime snapshot for the single active `azure_openai` or `github_copilot` provider, or the explicit unconfigured state. The persisted user document is version 2 and also carries the workspace registry; Provider APIs preserve registry entries on every write.
- `WorkspaceConfig`, platform workspace target models, and `WorkspaceRegistryEntry`: Re-exported shared boundary models used by trusted entry surfaces.
- `PLATFORM_CONFIG_PATHS`: Mapping from supported platform ids (`android`, `web`, `windows`, `macos`) to committed repository preset paths (`config.android.yaml`, `config.web.yaml`, `config.windows.yaml`, `config.macos.yaml`).
- `resolve_platform_config_path(platform: str) -> Path`: Validates a platform id and returns the corresponding committed platform preset path. Unsupported platform ids or missing preset files raise `ConfigurationError` with the platform and expected path.
- `load_workspace_settings(workspace: str | Path | None = None, user_config_root: str | Path | None = None) -> Settings`: Validates the current or explicit workspace `.fsq/config.yaml`, selects its immutable platform preset, resolves repository-owned resources, overlays workspace target/paths/private secrets, applies only retained system settings, overlays the latest Provider, and validates final paths without initializing the workspace.
- `load_platform_settings(platform: str, workspace: str | Path | None = None, user_config_root: str | Path | None = None) -> Settings`: Legacy platform-preset loader retained only for existing Control Plane Devices behavior and focused tests. It preserves the existing startup-directory `.fsq-agent-workspace` path policy and is not used by workspace-aware CLI or workspace APIs.
- `load_settings(path: str | Path | None = None, workspace: str | Path | None = None, user_config_root: str | Path | None = None) -> Settings`: Lower-level loader for tests and internal callers. It loads `.env` values without overriding existing non-provider process values, loads YAML from the provided path or developer default search locations, overlays the latest user-provider snapshot, and resolves runtime paths. Developer default discovery may use `config.yaml` or `config.yml`; it must not use `config.example.yaml`.
- `load_user_provider_config(user_config_root: str | Path | None = None) -> UserProviderConfig`: Loads or upgrades the versioned user document, validates Provider metadata plus credentials, preserves the workspace registry, and returns the explicit unconfigured or complete Provider snapshot. The default root is `Path.home() / ".fsq"`; tests pass a temporary root.
- `list_workspace_registry(user_config_root: str | Path | None = None) -> list[WorkspaceRegistryEntry]`: Returns registry entries in persisted order without loading secret values.
- `load_registered_workspace(name: str, user_config_root: str | Path | None = None) -> WorkspaceConfig`: Resolves one case-insensitive registry name, validates that its config still matches the registry, and returns current workspace truth or a safe configuration error.
- `create_workspace(*, parent_path: Path, config: WorkspaceConfig, user_config_root: str | Path | None = None) -> WorkspaceConfig`: Validates the complete candidate, creates only the required layout and empty `knowledge/project.md`, atomically commits workspace config, then atomically appends the registry entry while preserving Provider state. Ordinary failures roll back request-created files without deleting user-owned parent content.
- `update_workspace(*, name: str, target: object, env: Mapping[str, str], expected_revision: str, user_config_root: str | Path | None = None) -> WorkspaceConfig`: Reloads registered workspace truth, rejects identity changes and stale revisions, validates the complete replacement, and atomically replaces only `.fsq/config.yaml`.
- `save_azure_openai_provider(*, base_url: str, model: str, api_key: str, user_config_root: str | Path | None = None) -> UserProviderConfig`: Validates and normalizes a complete Azure candidate, atomically writes Azure credentials and metadata, then removes both GitHub token files only after activation succeeds.
- `activate_github_copilot_provider(*, model: str, github_token: Mapping[str, object], provider_token: Mapping[str, object], user_config_root: str | Path | None = None) -> UserProviderConfig`: Validates a completely authenticated GitHub candidate, atomically writes both token files and metadata, then removes Azure credentials only after activation succeeds.
- `refresh_provider_settings(settings: Settings, user_config_root: str | Path | None = None) -> Settings`: Returns a settings copy whose provider fields come from the latest user snapshot while preserving platform, target/session, workspace, cases, output, and all other runtime policy.
- `resolve_runtime_paths(settings: Settings, base_dir: Path | None = None) -> None`: Resolves and validates workspace cases/knowledge/run roots, repository preset skill resources, pre-plan knowledge, and prompt template paths without creating workspace identity files or missing project knowledge. Run writers may create a missing `cases/` only at their write boundary.
- `validate_provider_settings(settings: Settings) -> None`: Validates only the selected model provider before dynamic LLM use or provider-backed AI assertion use. It rejects explicit unconfigured state, requires a non-empty model, and validates Azure endpoint/API-key values when selected without requiring platform harness values.
- `validate_runtime_settings(settings: Settings) -> None`: Validates user-provider readiness, Azure OpenAI base URL shape when selected, resolved model name, LLM harness/driver/platform tool settings, AgentTool policy, platform CommonTool policy, and local path constraints before a default LLM run starts.
- `validate_strict_core_settings(settings: Settings, requires_ai_assertion: bool = False) -> None`: Validates strict-core harness/driver settings not provided by a case file. It does not require provider credentials unless the caller knows the strict run contains an authored `assertWithAI` step or otherwise requires a provider-backed AI assertion evaluator. Runtime-secret text references are validated by entry/core code after the case is parsed because referenced names come from case commands, not from static settings alone.

Repository-owned platform YAML presets contain stable, shareable runtime shape: active platform, backend selection, OpenAI Agents SDK turn limit, execution post-action delay defaults, lifecycle policy, harness policy, and reusable skill definitions. They do not define workspace, cases/output, project knowledge, target, or runtime-secret values. `config.example.yaml` is a reference sample only.

Environment variables and `.env` contribute only `FSQ_ANDROID_SERIAL`, `FSQ_WINDOWS_BACKEND_KIND`, and `FSQ_MACOS_APPIUM_SERVER_URL`. Process environment takes precedence over `.env` for those names. Migrated application target variables and runtime-secret values are not configuration sources or compatibility fallbacks. Provider variables remain unsupported.

Optional top-level `caseLifecycle` is a strict execution policy block loaded as configuration only. Config validates hook shape with the same hook model used by FSQ case metadata; CLI strict execution owns hook path resolution, shell execution, recursion detection, lifecycle ordering, and failure semantics.

Provider metadata and the workspace registry are read only from `~/.fsq/config.yaml`, and Provider credentials are read only from `~/.fsq/auth`. Missing user state is initialized as version 2 with `provider: null` and an empty workspace registry; there is no Provider fallback.

## Platform Configuration Blocks

Shared configuration rules:

- Workspace `platform` selects exactly one committed preset and matching `harness.<platform>` settings block for dynamic, strict, and Playground execution.
- Repository presets own stable platform/backend, turn-limit, timeout, snapshot, browser policy, lifecycle, delay, and reusable skill settings. Workspace config owns target identity, private runtime secrets, and workspace paths.
- `agent_context.knowledge.root_dir` resolves to workspace `knowledge/`. Preset-configured reusable skill paths remain repository-relative and do not move under that workspace root. Optional pre-plan page knowledge uses the workspace knowledge root.
- Validation rejects unsupported platform/backend combinations, mismatched workspace target variants, unsafe roots, and invalid local target files before external actions.
- Workspace names are trimmed bounded single-directory names; empty names, dot segments, path separators, control characters, host-invalid forms, and applicable Windows reserved device names are invalid. Registry names are case-insensitively unique, while normalized config paths use host path-case semantics.
- Workspace `env` accepts only valid environment-variable names mapped to non-empty strings. Duplicate YAML keys, blank/invalid names, non-string values, and blank values fail without exposing values.
- `caseLifecycle` remains preset-owned policy; config validates shape and strict entry layers own execution.
- The user document owns Provider metadata and ordered workspace registry entries. `.env` and process environment own only the retained system settings.

Provider configuration:

- The default root is `Path.home() / ".fsq"`, containing version-2 `config.yaml` and `auth/`. Missing state is created as `version: 2`, `provider: null`, and `workspaces: []`; valid version-1 Provider state is upgraded atomically when the combined model is needed.
- Configured YAML uses exactly one provider shape: `{type: azure_openai, model, base_url}` or `{type: github_copilot, model}`. Both require a non-empty model; Azure base URLs normalize to `/openai/v1/`.
- Azure credentials are complete JSON in `auth/azure-openai.json`. GitHub OAuth and provider-token JSON retain their existing formats in `auth/github-copilot-token.json` and `auth/github-copilot-provider-token.json`.
- Every changed file uses a same-directory temporary file, flush, `fsync`, and `os.replace`. Workspace config permissions are restricted to the current user on POSIX where supported and hardened best-effort on Windows. Writes serialize within one process; cross-process transactions and conflict detection are unsupported.
- Provider activation and workspace registry operations use the same write lock and always preserve the complete counterpart state.
- Replacement validates and commits the candidate before deleting old-provider credentials. Failed saves and incomplete GitHub authentication preserve the previous active provider.
- Provider metadata and credentials are never recovered from `.env`, process environment, platform YAML, or the managed workspace.
- Provider-only validation must not require platform harness local settings.

Android configuration:

- `harness.android.backend` supports `uiautomator2` in the first Android backend.
- Workspace target `app_id` is required. `FSQ_ANDROID_SERIAL` remains the optional system device selector.
- Strict Android runs may fall back to FSQ case `appId` metadata where the CLI/playground strict entry permits it.

Web configuration:

- `harness.web.backend` supports `playwright` in the first Web backend.
- `harness.web.channel` selects the local browser channel. The supported channel is `chrome`.
- Workspace target `browser_executable_path` is required and must point to an existing executable compatible with the preset channel.
- `harness.web.headless`, optional `harness.web.base_url`, and optional viewport fields are YAML-owned runtime shape.
- Missing Playwright packages are reported during Web runtime construction with actionable setup guidance, not during registry bootstrap. Missing, nonexistent, non-file, non-executable, or channel-mismatched Web browser executable paths are reported by configuration validation before external actions begin.

Windows configuration:

- `harness.windows.backend` supports `pywinauto` in the first Windows backend.
- Workspace target `app_path` is required; optional `window_title_re` and command-line-string `launch_args` are workspace-owned.
- `FSQ_WINDOWS_BACKEND_KIND` optionally selects pywinauto's UI automation backend, with `uia` as the default and `win32` also supported. This is a pywinauto adapter mode, not a second FSQ Windows backend.
- Per-step `launchApp.extra_args` append after parsed workspace launch arguments.
- Missing pywinauto packages are reported during Windows runtime construction. Invalid backend kind, launch arguments, and application paths fail configuration before external actions.

macOS configuration:

- `harness.macos.backend` supports `appium_mac2` in the first macOS backend.
- `harness.macos.page_source_max_depth`, `harness.macos.action_timeout_seconds`, and `harness.macos.new_command_timeout_seconds` are YAML-owned stable defaults. The action timeout and Appium command-idle timeout are independent settings.
- `FSQ_MACOS_APPIUM_SERVER_URL` supplies the operator's Appium endpoint. The code may use `http://127.0.0.1:4723` only when the implementation treats it as a stable default and reports whether the endpoint was explicitly configured.
- Workspace target supplies optional `bundle_id` and `app_path`, with at least one required; a supplied app path must identify an existing application bundle or executable.
- Missing Appium Python packages are reported during macOS runtime construction with actionable setup guidance, not during registry bootstrap. Missing or unusable Appium server URL, bundle id, app path, or path existence issues are reported by configuration validation before external actions begin.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: Workspace/preset composition, retained environment overlays, Provider merge, and runtime validation.
- `_user_provider.py`: User-root layout, versioned Provider/registry records, v1-to-v2 upgrade, credential loading, shared atomic writes, Provider activation, workspace registration, and Provider-only refresh.
- `_workspace.py`: Strict workspace YAML loading, revisions, target validation, creation/update transactions, registry truth checks, and rollback.
- `_settings.py`: `Settings` aggregate model.
- `_paths.py`: Workspace config/root validation, containment, and side-effect-free runtime path resolution helpers.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 2 Simple Package.
- Public API: runtime/workspace models, workspace and legacy Devices loaders, Provider load/save/activation/refresh, workspace registry/create/update operations, path resolution, and validation functions exported from `__init__.py`.
- Internal modules: `_loader.py`, `_user_provider.py`, `_workspace.py`, `_settings.py`, and `_paths.py` are private implementation files.
- Domain boundaries: config owns Provider/registry/workspace filesystem persistence, configuration composition, revisions, atomic writes, rollback, path containment, and validation. It does not own provider clients, authentication protocols, HTTP transport, file-browser projection, or task orchestration.
- Boundary models: shared workspace/target/registry models come from `models`; `Settings` and `UserProviderConfig` are config runtime boundaries; project exceptions come from `models`.
- Dependency direction: config depends on `models` and configuration/filesystem libraries. `providers` and entry layers may depend on config public APIs; config must not import them.
- Rationale: a small versioned local store and deterministic merge/validation operations need focused private helpers, not service/repository layers.

## Error Handling

Invalid or missing configuration raises `ConfigurationError` from `models`. YAML duplicate keys, unsupported versions, schema extras, identity/root mismatches, malformed user state, invalid target paths, invalid runtime-secret entries, stale revisions, registry conflicts, containment failures, and atomic-write failures are reported with actionable safe context and no secret values. A malformed workspace or user document never degrades to unconfigured/default state. Workspace creation rejects non-empty final roots, legacy markers, and existing `.fsq` state without merge or overwrite. Provider-only validation remains independent from workspace target readiness. Backend packages are imported only at runtime construction, and config validation never connects to a device, browser, application, or Appium server.

## Current Invariants

- Runtime configuration has four ownership layers: repository presets own stable policy, workspace config owns application target/paths/private runtime secrets, retained system environment owns three shared machine settings, and the user document owns Provider metadata plus the workspace registry.
- Public settings loads capture the latest complete user-provider snapshot. Long-lived entry surfaces may refresh only that snapshot at a documented complete-task boundary; an already constructed task/provider lifecycle is not mutated.
- `caseLifecycle` remains an optional platform-YAML strict lifecycle policy. Config validates its shared FSQ hook shape; entry-layer strict execution owns path resolution, shell execution, recursion detection, ordering, and failure semantics.
- There is no default provider. `openai_agents.provider` is `None` for explicit unconfigured state and otherwise stores the active user-provider type. Both providers use the configured non-empty model; no fixed GitHub model is injected.
- Azure metadata and plaintext API key live only under `~/.fsq`; the endpoint normalizes to the OpenAI-compatible Responses base URL form. GitHub OAuth and provider-token files live under the same user auth root and retain their existing expiration formats.
- Provider API keys and tokens are never stored in workspace config, platform YAML, or `.env`. Workspace `env` keys form the runtime-secret allowlist; values remain private and non-serialized in effective settings.
- Android app id comes from the workspace target. `FSQ_ANDROID_SERIAL` optionally selects the Android device serial; an empty value means no serial override.
- `openai_agents.provider` stores the effective user-provider type or `None`. Config owns persistence and snapshot resolution; provider construction, GitHub device flow, token exchange, and live connection testing belong to `providers`.
- Tracing is enabled by default through `openai_agents.tracing_enabled: true`, and the CLI may override that setting for one run. The runtime enables OpenAI Agents SDK trace export only when `OPENAI_API_KEY` is present for the SDK exporter; otherwise it disables SDK tracing for the run so GitHub Copilot and Azure OpenAI executions do not repeatedly log missing OpenAI trace-export-key warnings. Sensitive tracing is fixed off; `trace_include_sensitive_data` is not a YAML or CLI option.
- OpenAI Agents SDK run length is YAML-owned through `openai_agents.max_turns` in committed platform presets. Android and Windows presets default to 100 turns; Web and macOS presets default to 50 turns. Lower-level custom config loading may still rely on the model fallback when the field is omitted.
- Context trimming and AgentTool local output artifact policy are internal defaults, not part of the default YAML surface. The defaults keep recent moderate AgentTool and platform capability outputs inline, write complete large helper outputs to per-run artifacts, and trim older large SDK tool outputs before model calls.
- `shell`, `cli_tools`, platform-YAML provider endpoint/key/model fields, YAML Android app id/serial fields, sensitive tracing, workspace marker/autoinit settings, and one-option output policy switches are not accepted external platform YAML configuration keys.
- Workspace-aware CLI commands validate the current directory `.fsq/config.yaml` without initializing anything. The legacy marker path remains available only through `load_platform_settings` for Control Plane Devices.
- `cases.dir`, `output.root_dir`, and `output.runs_dir` resolve to `<workspace>/cases`; `agent_context.knowledge.root_dir` resolves to `<workspace>/knowledge`.
- Reusable skills remain preset-owned repository resources. Optional project/page knowledge resolves under workspace `knowledge/` and is loaded only when non-blank content exists.
- `openai_agents.prompt` owns prompt template customization and scalar prompt variables. `prompt.agent_template_path` and `prompt.task_template_path` may point to files resolved relative to the configuration file directory; when template paths are omitted, package default templates are used. Static prompt text, headings, loops, and task formatting live in templates. `prompt.variables` provides operator-controlled scalar model data injected into templates. `prompt.custom_instructions` and `prompt.custom_instructions_path` are not supported configuration keys; project-specific guidance belongs in `knowledge/project.md`, and reusable execution guidance belongs in configured skills.
- `harness.platform` selects the platform harness used by goal-driven task execution and strict-core execution. Supported platforms are `android`, `web`, `windows`, and `macos`.
- `harness.android.backend` selects the Android backend. The supported backend is `uiautomator2`.
- `harness.web.backend` selects Playwright and the preset selects channel/headless/base-URL policy; the workspace target supplies the browser executable path.
- `execution.post_action_delay_seconds` controls runner-owned post-action stabilization delay defaults. `platform` defaults to `1.0` seconds and applies to PlatformTool capabilities when capability metadata does not override it. `common` defaults to `0.0` seconds and applies to inherited CommonTool capabilities when capability metadata does not override it. Values must be non-negative, and this pacing is execution timing only: it must not add `waitMs` commands, mutate parsed FSQ commands, record generated strict replay waits, or create synthetic evidence steps.
- Android workspace target supplies app id; strict case metadata may override it where already allowed. Android serial remains environment-backed.
- Playwright package installation is operator-managed through the `web` extra. Configuration validates the workspace browser executable against preset channel policy before external actions.
- pywinauto package installation is operator-managed through the `windows` extra. Workspace target owns app path/window matcher/launch args, while `FSQ_WINDOWS_BACKEND_KIND` owns adapter mode.
- Appium Mac2 package installation is operator-managed through the `macos` extra. Workspace target owns bundle id/app path, while `FSQ_MACOS_APPIUM_SERVER_URL` owns the server endpoint.
- Strict-core execution remains deterministic except for explicitly authored `assertWithAI` assertion steps. When a strict run contains `assertWithAI`, entry-layer code may request provider validation and inject a provider-backed evaluator into the active harness/backend support. Missing provider readiness for such a step is a configuration failure. No AI recovery, locator fallback, or testcase mutation is enabled by this setting.
- Runtime-secret text references are validated against workspace `env` keys and resolved from the private settings mapping. Missing names/values fail at use time; concrete values never enter global environment, serialized settings, generated YAML, events, manifests, or reports.
- Dynamic LLM final verification is not configurable through settings. The runtime verifies the single pre-plan-derived `verification_goal`; `verification.mode` is obsolete and must not be accepted.
- Non-interactive execution is the default. Any human-in-the-loop SDK feature must be disabled or backed by deterministic programmatic approval.
- Config resolution performs no workspace creation. Run entry code may recreate a missing `cases/` immediately before writing one direct-child run directory; every run artifact remains under that directory.
- Workspace creation may best-effort mark `.fsq` hidden on Windows, but workspace validity never depends on that attribute.
- Platform action schemas are not configured through external tool servers. They are declared by decorated capability hosts, validated in the capability registry, and adapted by the agent runtime into SDK `FunctionTool` objects.
- Top-level `skills`, top-level `knowledge_dir`, and top-level `pre_plan` YAML keys are not accepted external configuration keys. Agent context is expressed through `agent_context.knowledge` so the relationship between the knowledge root, skill files, and pre-plan page knowledge remains explicit.