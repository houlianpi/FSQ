# Module: cli

## Purpose

Provide the public `fsq` command-line adapter for people, CI systems, and Coding Agents. CLI parses arguments, selects human or machine presentation, invokes resource-grouped Application operations, renders results/events, and maps errors to process exit codes. It does not independently orchestrate Agent, Core, FSQ, Report, Driver, Provider, or Environment behavior.

## Dependencies

- `application`: The only boundary used for CLI business operations and their Request, Result, Event, and Error contracts.
- `control_plane`: Public server startup boundary for `fsq ui`; business operations behind that server still use Application.
- `models`: Shared primitive/domain values only where required by Application contracts.

CLI must not directly compose `agent`, `fsq`, `core`, `report`, concrete drivers, or provider implementations. Lower modules must not import CLI.

## Public Interface

`__init__.py` exports `main`. The primary executable is `fsq`. The public command tree is:

```text
fsq
├── init
├── doctor
├── case
│   ├── create
│   └── test
├── ui
├── providers
│   ├── list
│   ├── configure NAME
│   └── status [NAME]
├── runs
│   ├── list
│   ├── show RUN_ID
│   └── logs RUN_ID
└── environments
    ├── list
    └── doctor NAME
```

Core Case forms are:

```bash
fsq case create --platform web --goal "Verify product search"
fsq case test --platform web tests/search.fsq.yaml
fsq case test --platform web tests/search.fsq.yaml --suggest
```

Workspace initialization uses the current directory as the workspace root and derives its default workspace name from that directory's final path component:

```bash
fsq init --platform web --browser-channel chrome
fsq init --platform web --browser-channel msedge-canary --browser-executable-path /path/to/edge-canary --install-driver
fsq init --platform android --app-id com.example.app
fsq init --platform windows --app-path /path/to/application
fsq init --platform macos --bundle-id com.example.app
```

`init` accepts the same complete platform target shapes as Control Plane: Android requires `--app-id`; Web requires `--browser-channel` while `--browser-executable-path` is optional; Windows requires `--app-path` and accepts `--window-title-re` and `--launch-args`; macOS requires at least one of `--bundle-id` and `--app-path`. Target options for another platform are rejected. When the Web path is omitted, Application discovers an executable compatible with the exact selected channel on the current host. One unambiguous compatible candidate is selected; no candidate or multiple distinct candidates fail before workspace mutation with safe guidance to install the channel or pass an explicit path. An explicit path is normalized and validated against the channel through the same shared operation.

`init` always checks selected-platform Driver readiness before workspace mutation. `--install-driver` authorizes Application to invoke the platform-owned supported installer only when readiness is missing, and then requires a successful bounded recheck. Without the flag, readiness failure is read-only and returns the exact safe install action. Unsupported automatic installation fails with an explicit manual action; it never reports success or falls through to workspace writes. Driver installation is limited to FSQ-owned platform runtime prerequisites and must not install or modify the application under test, create emulators/VMs, connect to a device, start Appium, authenticate, or install system package managers.

`--name` may override the derived name but does not change the root. `--env NAME=VALUE` may be repeated and supplies the complete private environment mapping. `--update-existing` permits replacement of a differing existing platform target/environment; without it, equal configuration is unchanged and differing configuration is a conflict. `--provider` is not part of workspace initialization; Provider configuration remains under `providers configure` or Control Plane Config. Public option spelling uses hyphens, including `--install-driver`; underscore aliases are not accepted.

- `case create` accepts a natural-language Goal, performs AI-participating testing, and may produce a Run-local candidate `*.fsq.yaml` Case.
- `case test` executes an existing FSQ Case as authored. The source Case is immutable.
- `case test --suggest` permits AI analysis and Run-local suggestions or a candidate Case while preserving original execution facts and never overwriting the source Case.
- `runs` is not a complete supported multi-platform contract in this specification. Its platform-selection, aggregation, and complete query behavior require a separate confirmed specification before being treated as complete.
- `providers` exposes safe provider inventory, configuration, and readiness.
- `environments` exposes Environment inventory and diagnostics. Mutation is not public in this phase.
- `doctor` performs workspace-level diagnostics; `ui` starts the Control Plane adapter.

The first phase does not expose extension management, public capability/action discovery, Environment mutation, Run mutation, a daemon, async queues, sharding, or workers. `test`, `replay`, and `run` are not public top-level execution commands and are not retained as silent aliases.

## Workspace Rule

The exact current directory is the CLI workspace root. A valid CLI workspace is registered in the user workspace registry at that exact normalized root and contains at least one valid `.fsq/config/config.<platform>.yaml`; `.fsq-agent-workspace` markers are neither created nor accepted. Commands do not search parent directories, auto-initialize, or accept an alternate workspace flag. Commands requiring only workspace context validate the exact registered root; platform-specific commands additionally require the selected platform config. Failure uses Application error code `workspace.not_initialized` and tells a human to run `fsq init` in the intended root or change to an initialized Workspace. Control Plane continues to list all registered workspaces and does not derive selection or execution paths from the CLI process startup directory.

`fsq init` is the only CLI command that may establish this precondition. It validates all input, resolves the complete target, and completes Driver readiness before workspace mutation; it then initializes or updates exactly one platform at the current root through the shared Application and Config workspace operation, and reports success only after workspace files and registry truth are committed. It safely adopts an existing non-empty project directory only when `.fsq` and legacy workspace markers are absent; it preserves unrelated project files. It creates `.fsq/config/config.<platform>.yaml`, `.fsq/runs/<platform>/`, `cases/<platform>/`, `knowledge/<platform>/project.md`, and the user registry entry. Repetition is idempotent. A partially initialized, unregistered, mismatched, invalid, or Driver-unready workspace fails with safe repair guidance rather than being treated as ready.

## Global Machine Contract

- `--output human|json|jsonl` selects presentation and defaults to `human`.
- `--non-interactive` forbids prompts and implicit interactive authentication.
- Human output may be styled; JSON emits one complete operation envelope; JSONL emits one object per event followed by one terminal result or error object.
- Machine output is stdout-only. Diagnostics that cannot be represented as protocol records use stderr. Secrets and hidden reasoning are never emitted.
- Exit categories are `0` success, `1` test/case failure, `2` usage or validation error, `3` workspace/configuration error, `4` provider/environment unavailable, `5` internal/infrastructure error, and `130` interruption.

## Compatibility

The executable and command hierarchy change explicitly to `fsq`. Legacy `fsq-agent run`, `run --strict`, `report`, and raw dynamic `--case-yaml` forms are not silently forwarded. Compatibility messaging may identify the corresponding new command. Case discovery treats `*.fsq.yaml` as canonical and may accept `*.codex.yaml` for one deprecation cycle with a machine-visible warning. `*.intent.yaml` and `fsq.test-intent/v1` are unsupported.

## Python Architecture

- Architecture level: Level 3 transport adapter.
- Public API: `main`.
- CLI owns Click declarations, argument decoding, terminal/JSON/JSONL rendering, prompt policy, and exit-code mapping.
- Application owns shared request validation, orchestration, operation events, results, and stable errors.
- Dependency direction: CLI to Application; never Application to CLI.

## Error Handling

CLI maps stable Application Errors to the documented exit categories and presentation protocol. Malformed command syntax and unsupported legacy options fail before invoking Application. Interrupted operations exit `130`. Unexpected exceptions are normalized as internal errors with only the exception type retained as safe diagnostic detail. Human internal-error output includes that safe exception type; machine-mode errors include it in the structured error details. Neither form includes the exception message, traceback, arguments, secrets, hidden reasoning, or unrestricted backend values. Machine-mode errors remain valid JSON or JSONL.

## Verification Scope

Verification covers command/option parsing, platform-target exclusivity, required Web channel and optional executable path, unambiguous shared Web discovery and explicit-path validation, read-only Driver readiness, authorized install/recheck and unsupported-install failure, no workspace mutation before readiness, current-directory name derivation/override, existing-project adoption, idempotent initialization/update/conflict behavior, registry and directory creation, workspace precondition presentation, Application request mapping, human/JSON/JSONL rendering, non-interactive behavior, exit-code mapping, safe unexpected-exception diagnostics, `ui` startup through the current public Control Plane server options without startup-directory workspace selection, legacy rejection/migration guidance, and absence of direct domain/runtime orchestration.

## Current Invariants

- CLI is a transport adapter over Application.
- Existing Case source files are never overwritten by `case test` or `--suggest`.
- Machine output is stable, structured, and safe for Coding Agents.
- Public command names and hierarchy match this specification exactly.
