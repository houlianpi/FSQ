# Init Provider Setup Design

## Goal

Simplify the public CLI setup model by merging the current provider setup flow into `init`, removing the separate `setup llm` command, and making the fsq-agent workspace location fixed and predictable.

## Scope

- Replace `fsq-agent setup llm --provider github_copilot|azure_openai [--check-only]` with optional provider setup on `fsq-agent init`.
- Make the managed workspace always resolve to the current directory `.fsq-agent-workspace` for public CLI commands.
- Remove public `--workspace` options from `init`, `run`, `report`, and `playground`.
- Update CLI specs, root spec references, tests, and README examples to match the simplified command surface.

## Non-Goals

- Do not change provider internals, Copilot token exchange, Copilot plan detection, Azure client construction, or model invocation behavior.
- Do not add platform dependency installers or platform setup subcommands.
- Do not add a compatibility alias for deleted `setup llm` commands.
- Do not send live model inference requests during initialization.

## Proposed Public CLI Behavior

`init` becomes the single local setup/readiness entry point:

```powershell
uv run fsq-agent init --platform android
uv run fsq-agent init --platform android --provider github_copilot
uv run fsq-agent init --platform android --provider azure_openai
```

- `--platform android|web|windows|macos` remains required.
- `--provider github_copilot|azure_openai` is optional.
- Without `--provider`, `init` initializes/checks the current directory `.fsq-agent-workspace` and reports platform/runtime readiness without mutating provider settings or starting provider authentication.
- With `--provider github_copilot`, `init` writes or updates current directory `.env` with `FSQ_LLM_PROVIDER=github_copilot`, prepares provider readiness, and may run GitHub device-code authorization when no valid cached token exists.
- With `--provider azure_openai`, `init` writes or updates current directory `.env` with `FSQ_LLM_PROVIDER=azure_openai`, `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`, and `AZURE_OPENAI_API_KEY`, prompting interactively as today and hiding API key input.
- Copilot token cache remains under `.fsq-agent-workspace/auth/github-copilot-token.json`.
- Provider setup remains local readiness only and must not send a Responses API model inference request.

The deleted command surface is:

```powershell
fsq-agent setup llm --provider github_copilot
fsq-agent setup llm --provider azure_openai
fsq-agent setup llm --provider github_copilot --check-only
fsq-agent setup llm --provider azure_openai --check-only
```

## Workspace Behavior

All public CLI commands use the current directory `.fsq-agent-workspace` as the managed workspace. Public commands no longer expose `--workspace`.

Affected commands:

```powershell
fsq-agent init --platform <platform> [--provider <provider>]
fsq-agent run --platform <platform> ...
fsq-agent report --platform <platform> --run-id <id> [--format markdown|json]
fsq-agent playground --platform <platform> ...
```

This preserves a simple operator rule: run commands from the project/setup root whose `.env` and `.fsq-agent-workspace` should be used.

## Architecture And Module Ownership

- `cli` owns public command shape, argument validation, `.env` upsert orchestration for provider setup, and rendering readiness output.
- `config` continues to own `.env` loading, environment precedence, provider normalization, platform preset loading, and workspace path resolution.
- `providers` continues to own Copilot authentication, token cache interpretation, Copilot token exchange, plan detection, Azure/Copilot client construction, and provider readiness session construction.
- `README.md` documents the simplified initialization flow.

Python architecture level remains Level 3 Layered Application for `cli`; the change keeps command handlers as thin orchestration adapters and does not introduce new service abstractions.

## Error Handling And Edge Cases

- `init --provider` failures must not leak API keys, OAuth tokens, Copilot tokens, authorization headers, cookies, or prompt content containing secrets.
- Existing process environment values continue to take precedence over `.env`; warnings should remain non-secret.
- Deleted `setup` commands should fail as unknown commands.
- Deleted `--workspace` options should fail as unknown options.
- Provider setup errors should still distinguish unsupported provider, Azure prompt/config validation failures, Copilot auth failures, and token exchange failures.
- `init --platform <platform>` without `--provider` should not start Copilot device-code authorization.

## Expected SPEC Changes

- Root `SPEC.md`: update runtime configuration defaults and platform CLI rules to describe `init --provider` and current-directory workspace behavior; update module table summary for `cli`.
- `fsq_agent/cli/SPEC.md`: replace `setup llm` public interface and design decisions with merged `init` behavior; remove public `--workspace` from command signatures; update testing contract and internal structure notes if helper naming changes.
- `fsq_agent/config/SPEC.md`: update workspace resolution/public CLI behavior notes where they currently mention `--workspace`.

## Verification Expectations

- Run focused CLI tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli.py
```

- Run provider-focused tests if CLI/provider setup integration changes require it:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_copilot_provider.py tests/test_config.py
```

- Run a SPEC/code synchronization audit before completion.
*** End Patch