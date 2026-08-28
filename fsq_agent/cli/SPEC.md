# Module: cli compatibility entry

## Purpose

Preserve existing `fsq_agent.cli:main` as a public compatibility export for the canonical `adapters.cli` command while installed `fsq` and `fsq-agent` scripts target `fsq_agent.adapters.cli:main` directly. Canonical CLI modules parse arguments, select presentation, invoke Application operations, render results/events, and map exit codes. Old `fsq_agent.cli._*` private module paths are unsupported and absent.

## Dependencies

- `application`: The boundary used for CLI business operations and their Request, Result, Event, and Error contracts. Application Case operations delegate complete run orchestration to Execution.
- `control_plane`: Public server startup boundary for `fsq ui`; business operations behind that server still use Application.
- `models`: Shared primitive/domain values only where required by Application contracts.

CLI must not directly compose `agent`, `execution`, `fsq`, `core`, `report`, concrete drivers, or provider implementations. Lower modules must not import CLI.

## Public Interface

`__init__.py` exports the canonical `adapters.cli.main` object. The primary executable remains `fsq`. The public command tree is:

```text
fsq
├── init
├── doctor
├── case
│   ├── create
│   └── test
├── ui
├── providers
│   ├── configure NAME
│   └── status
├── runs
│   ├── list
│   ├── show RUN_ID
│   └── logs RUN_ID
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
fsq init --platform web --browser-channel msedge-canary --browser-executable-path /path/to/edge-canary
fsq init --platform android --app-id com.example.app
fsq init --platform windows --app-path /path/to/application
fsq init --platform macos --bundle-id com.example.app
```

`init` accepts the same complete platform target shapes as Control Plane: Android requires `--app-id`; Web requires `--browser-channel` while `--browser-executable-path` is optional; Windows requires `--app-path` and accepts `--window-title-re` and `--launch-args`; macOS requires at least one of `--bundle-id` and `--app-path`. Target options for another platform are rejected. When the Web path is omitted, Application discovers an executable compatible with the exact selected channel on the current host. One unambiguous compatible candidate is selected; no candidate or multiple distinct candidates fail before workspace mutation with safe guidance to install the channel or pass an explicit path. An explicit path is normalized and validated against the channel through the same shared operation.

`init` always checks selected-platform runtime readiness before workspace mutation. Readiness checks are read-only. A missing Python platform dependency reports that the installed `fsq-agent` distribution is incomplete and must be reinstalled or repaired; a missing host service, browser/application target, device prerequisite, or other system dependency reports a safe external provisioning action. `init` does not expose `--install-driver` or any runtime-install option and never invokes Python or system package managers, installs or modifies the application under test, creates emulators/VMs, connects to a device, starts Appium, or authenticates.

`--name` may override the derived name but does not change the root. `--env NAME=VALUE` may be repeated and supplies the complete private environment mapping. `--update-existing` permits replacement of a differing existing platform target/environment; without it, equal configuration is unchanged and differing configuration is a conflict. `--provider` is not part of workspace initialization; Provider configuration remains under `providers configure` or Control Plane Config. Public option spelling uses hyphens; underscore aliases are not accepted.

- `case create` accepts a natural-language Goal, performs AI-participating testing, and may produce a Run-local candidate `*.fsq.yaml` Case.
- `case test` executes an existing FSQ Case as authored. The source Case is immutable.
- `case test --suggest` executes the authored Case exactly once, then permits read-only AI analysis of the parsed Case and bounded persisted execution facts. It may return Run-local suggestions or a candidate Case while preserving the completed execution result and never overwriting the source Case or configured Case directory.
- When suggestion analysis produces an artifact, Human output displays each Run-local suggestion or candidate Case path and states that the source Case was not modified. JSON and JSONL terminal results expose the same paths through `suggestion_path` and `candidate_case_path`; absent artifacts remain `null`.
- `runs` is not a complete supported multi-platform contract in this specification. Its platform-selection, aggregation, and complete query behavior require a separate confirmed specification before being treated as complete.
- `providers` exposes only user-level active-Provider configuration and readiness. Provider inventory is not a public CLI capability in the first release.
- `doctor` performs read-only Workspace diagnostics across every identifiable configured platform and reports fixed component checks plus readiness for `case test`, `case test --suggest`, and `case create`; `ui` starts the Control Plane adapter.

The CLI does not expose Environment inventory, Environment diagnostics, extension management, public capability/action discovery, Environment mutation, Run mutation, a daemon, async queues, sharding, or workers. Environment readiness remains an internal/public Python module capability consumed by Workspace initialization and `fsq doctor`. `environments`, `test`, `replay`, and `run` are not public top-level commands and are not retained as silent aliases.

## Workspace Rule

The exact current directory is the CLI workspace root. A valid CLI workspace is registered in the user workspace registry at that exact normalized root and contains at least one valid `.fsq/config/config.<platform>.yaml`; `.fsq-agent-workspace` markers are neither created nor accepted. Commands do not search parent directories, auto-initialize, or accept an alternate workspace flag. Commands requiring only workspace context validate the exact registered root; platform-specific commands additionally require the selected platform config. Failure uses Application error code `workspace.not_initialized` and tells a human to run `fsq init` in the intended root or change to an initialized Workspace. Control Plane continues to list all registered workspaces and does not derive selection or execution paths from the CLI process startup directory.

`fsq init` is the only CLI command that may establish this precondition. It validates all input, resolves the complete target, and completes Driver readiness before workspace mutation; it then initializes or updates exactly one platform at the current root through the shared Application and Config workspace operation, and reports success only after workspace files and registry truth are committed. It safely adopts an existing non-empty project directory only when `.fsq` and legacy workspace markers are absent; it preserves unrelated project files. It creates `.fsq/config/config.<platform>.yaml`, `.fsq/runs/<platform>/`, `cases/<platform>/`, `knowledge/<platform>/project.md`, and the user registry entry. Repetition is idempotent. A partially initialized, unregistered, mismatched, invalid, or Driver-unready workspace fails with safe repair guidance rather than being treated as ready.

`providers configure` and `providers status` are user-level commands and are exempt from the Workspace precondition. They operate on the same active Provider under `~/.fsq` as Control Plane Config and never read or write a Workspace `.env` or platform configuration.

## Provider Commands

The supported configuration forms are:

```bash
fsq providers configure github_copilot [--model MODEL]
fsq providers configure azure_openai [--base-url URL] [--model MODEL] [--api-key KEY]
fsq providers status
```

In Human interactive mode, GitHub Copilot configuration requests a device code, displays only its verification URL and user code, waits with the Provider-owned polling policy, discovers eligible models, and asks the user to select one when `--model` did not select an offered model. It atomically activates the completed authorization and selected model only after all steps succeed. Because the device flow requires an observable user action before a terminal result exists, it is rejected under `--non-interactive`, JSON, and JSONL in the first release with guidance to use Human interactive mode. An explicitly requested model must be present in the discovered eligible model set.

Azure OpenAI configuration requires base URL, model/deployment name, and API key. Human interactive mode securely prompts for omitted values and hides the API key. JSON, JSONL, and `--non-interactive` never prompt and require all three options. Configuration validates and atomically saves the complete candidate through the shared user Config API. No output or error includes the API key. A failed GitHub or Azure replacement leaves the previously active Provider and its credentials usable.

`providers status` loads the real active user Provider and model, checks local authentication and non-interactive readiness through Application, and never starts device login or sends model inference. It returns one result with `status` (`ready` or `unavailable`), `configured`, `provider`, `model`, `authenticated`, a safe `message`, and a safe repair `action` when needed. Human, JSON, and JSONL expose equivalent facts; JSONL emits one terminal record and no synthetic event. Ready exits `0`; a completed unconfigured, unauthenticated, or otherwise unavailable result exits `4`. Invalid user configuration is a configuration error, and unrecoverable orchestration failure is an internal error. Output never includes tokens, API keys, authorization data, raw backend responses, exception messages, or tracebacks.

## Global Machine Contract

- `--output human|json|jsonl` selects presentation and defaults to `human`.
- `--non-interactive` forbids prompts and implicit interactive authentication.
- Human output may be styled; JSON emits one complete operation envelope; JSONL emits one object per event followed by one terminal result or error object.
- Machine output is stdout-only. Diagnostics that cannot be represented as protocol records use stderr. Secrets and hidden reasoning are never emitted.
- Exit categories are `0` success, `1` test/case failure, `2` usage or validation error, `3` workspace/configuration error, `4` provider/environment unavailable, `5` internal/infrastructure error, and `130` interruption.

`doctor` has no platform option and checks configured platforms in Android, Web, Windows, macOS order. Its Human output shows Workspace and platform status, fixed checks, the three command verdicts, reasons/actions for non-ready items, and ordered deduplicated actions. JSON and JSONL each emit exactly one terminal result record; JSONL emits no synthetic event. Doctor exits `0` for `ready` or `partial`, `4` for a completed `unavailable` result, `3` when Workspace registry/root/config inventory is not trustworthy, `5` for unrecoverable internal orchestration failure, and `130` for interruption.

Doctor is read-only: it does not install, mutate configuration, authenticate interactively, send model inference, launch applications/browsers, or create external sessions. Provider readiness may perform only its supported non-interactive cached-token refresh. Human color never carries unique information, and all output obeys the global secret and safe-error contract.

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

Verification covers command/option parsing; absence and rejection of public `environments` and `providers list`; rejection of `--install-driver`; platform-target exclusivity; required Web channel and optional executable path; unambiguous shared Web discovery and explicit-path validation; read-only runtime readiness; incomplete-distribution and external-prerequisite guidance; no workspace mutation before readiness; current-directory name derivation/override; existing-project adoption; idempotent initialization/update/conflict behavior; registry and directory creation; workspace precondition presentation; Provider commands outside a Workspace; shared CLI/Control Plane user configuration in both directions; complete Azure interactive and non-interactive configuration; GitHub device flow, model discovery/selection, cancellation, and machine/non-interactive rejection; atomic Provider replacement failure preservation; real safe Provider status; Human/JSON/JSONL rendering and exit codes; Doctor platform ordering, command dependency/status aggregation, component error isolation, and no-side-effect boundary; Application request mapping; safe unexpected-exception diagnostics; `ui` startup through the current public Control Plane server options without startup-directory workspace selection; legacy rejection/migration guidance; and absence of direct domain/runtime orchestration.

## Current Invariants

- CLI is a transport adapter over Application.
- Existing Case source files are never overwritten by `case test` or `--suggest`.
- Machine output is stable, structured, and safe for Coding Agents.
- Public command names and hierarchy match this specification exactly.
