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

- `case create` accepts a natural-language Goal, performs AI-participating testing, and may produce a Run-local candidate `*.fsq.yaml` Case.
- `case test` executes an existing FSQ Case as authored. The source Case is immutable.
- `case test --suggest` permits AI analysis and Run-local suggestions or a candidate Case while preserving original execution facts and never overwriting the source Case.
- `runs` addresses persisted execution records: `list` discovers Runs, `show` returns one Run's status/results/artifacts, and `logs` returns its event/log stream.
- `providers` exposes safe provider inventory, configuration, and readiness.
- `environments` exposes Environment inventory and diagnostics. Mutation is not public in this phase.
- `doctor` performs workspace-level diagnostics; `ui` starts the Control Plane adapter.

The first phase does not expose extension management, public capability/action discovery, Environment mutation, Run mutation, a daemon, async queues, sharding, or workers. `test`, `replay`, and `run` are not public top-level execution commands and are not retained as silent aliases.

## Workspace Rule

Except for `init`, every command requires `.fsq-agent-workspace` in the current working directory. Commands do not search parent directories, auto-initialize, or accept an alternate workspace flag. Failure uses Application error code `workspace.not_initialized` and tells a human to run `fsq init` or change to an initialized Workspace. Detailed `init` redesign is outside this change; existing supported initialization behavior remains until separately specified.

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

CLI maps stable Application Errors to the documented exit categories and presentation protocol. Malformed command syntax and unsupported legacy options fail before invoking Application. Interrupted operations exit `130`. Machine-mode errors remain valid JSON or JSONL and never include tracebacks, secrets, or hidden reasoning.

## Verification Scope

Verification covers command/option parsing, workspace precondition presentation, Application request mapping, human/JSON/JSONL rendering, non-interactive behavior, exit-code mapping, legacy rejection/migration guidance, and absence of direct domain/runtime orchestration.

## Current Invariants

- CLI is a transport adapter over Application.
- Existing Case source files are never overwritten by `case test` or `--suggest`.
- Machine output is stable, structured, and safe for Coding Agents.
- Public command names and hierarchy match this specification exactly.
