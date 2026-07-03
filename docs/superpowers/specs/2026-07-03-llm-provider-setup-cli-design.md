# LLM Provider Setup CLI Design

Date: 2026-07-03
Status: Confirmed design for SPEC-driven implementation

## Goal

Add a manually executed CLI flow for setting up, updating, and checking only the fsq-agent LLM provider environment. The first implementation cycle supports GitHub Copilot and Azure OpenAI provider modes.

The CLI must let an operator configure the selected provider locally before running dynamic LLM tasks or provider-backed `assertWithAI` steps. It must keep platform harness setup out of scope.

## Scope

In scope:

- Add an independent command surface: `fsq-agent setup llm --provider github_copilot|azure_openai [--check-only]`.
- Use the current working directory as the local setup root.
- Use the current working directory `.env` file as the local environment file.
- Use the current working directory `.fsq-agent-workspace` directory as the managed workspace for Copilot token cache and setup-local workspace state.
- Move provider mode selection to environment ownership through `FSQ_LLM_PROVIDER=github_copilot|azure_openai`.
- Update `.env` during normal setup/update mode.
- Support read-only provider checks through `--check-only`.
- Trigger GitHub Copilot device-code authentication during Copilot setup when no valid cached GitHub OAuth token is available.
- Prompt for Azure OpenAI endpoint, model/deployment, and API key during Azure setup.
- Perform local provider configuration and authentication validation only; do not send a live model request.

Out of scope:

- Platform setup for Android, Web, Windows, or macOS harness settings.
- Live model verification requests for Azure OpenAI or GitHub Copilot.
- Path override flags such as `--env-file`, `--workspace`, or `--platform` on `setup llm`.
- Mutating `config.<platform>.yaml` files at runtime.
- Provider logout, token revocation, or token cache migration.
- Copilot model overrides; GitHub Copilot keeps the fixed `gpt-5.5` model.
- Alternate Azure environment variable names.

## Proposed CLI Behavior

The public CLI gains a new command group and subcommand:

```text
fsq-agent setup llm --provider github_copilot
fsq-agent setup llm --provider azure_openai
fsq-agent setup llm --provider github_copilot --check-only
fsq-agent setup llm --provider azure_openai --check-only
```

`--provider` is required and accepts only `github_copilot` or `azure_openai`.

Without `--check-only`, the command is a setup/update flow. It may create or update `.env`, may initialize `.fsq-agent-workspace`, and may perform Copilot device-code authentication. It exits nonzero when setup cannot complete or provider-local validation fails.

With `--check-only`, the command is read-only. It must not write `.env`, must not create or modify auth files, and must not start Copilot device-code authentication. It exits zero only when the selected provider is locally ready according to the non-live validation rules below.

The command prints a concise summary containing the selected provider, setup root, `.env` path, workspace path, provider readiness, and any next action. It must never print API key values, GitHub OAuth tokens, Copilot API tokens, authorization headers, cookies, or prompt content that may contain runtime secrets.

## Environment Ownership

Provider selection moves from YAML ownership to environment ownership:

```text
FSQ_LLM_PROVIDER=github_copilot
FSQ_LLM_PROVIDER=azure_openai
```

`config` must load `FSQ_LLM_PROVIDER` from process environment or `.env` and validate that its value is one of the supported providers. Existing process environment values take precedence over `.env` values, following the repository's existing environment precedence rule.

If `FSQ_LLM_PROVIDER` is absent, `github_copilot` remains the default provider. Existing YAML `openai_agents.provider` values may remain as a compatibility fallback during migration, but repository-owned platform presets should no longer be the primary provider selection source after the SPEC update. Runtime CLI setup must not edit platform YAML presets.

Azure OpenAI keeps the existing fixed environment variable names:

```text
AZURE_OPENAI_BASE_URL
AZURE_OPENAI_MODEL
AZURE_OPENAI_API_KEY
```

GitHub Copilot mode ignores Azure-specific environment variables.

## `.env` Update Rules

Normal setup/update mode writes only the current directory `.env` file.

The writer should preserve unrelated lines and comments, replace existing assignments for managed keys, and append missing managed keys. It should create `.env` if it does not exist. Managed keys for this design are:

- `FSQ_LLM_PROVIDER`
- `AZURE_OPENAI_BASE_URL`
- `AZURE_OPENAI_MODEL`
- `AZURE_OPENAI_API_KEY`

Copilot setup writes only `FSQ_LLM_PROVIDER=github_copilot`; it does not delete existing Azure variables.

Azure setup writes `FSQ_LLM_PROVIDER=azure_openai` plus the three Azure variables. The endpoint and model prompts may show existing non-secret values as defaults. The API key prompt must use hidden input. If a non-placeholder API key already exists, the operator may keep it without echoing it. Placeholder values such as `replace-with-...` are not accepted as ready values.

When a process environment variable conflicts with the value written to `.env`, the CLI must warn that process environment takes precedence. The command should validate against the effective value that future fsq-agent commands will see under the same process environment.

## Copilot Setup Flow

For `fsq-agent setup llm --provider github_copilot`:

1. Ensure the setup root is the current working directory.
2. Ensure `.fsq-agent-workspace` exists and is marked as an fsq-agent workspace using the same marker policy as the config workspace resolver.
3. Upsert `FSQ_LLM_PROVIDER=github_copilot` into `.env`.
4. Load provider settings with the fixed setup workspace.
5. Validate provider-only settings without validating platform harness settings.
6. Ask the providers module to ensure Copilot provider authentication is ready in interactive mode.
7. If no valid cached GitHub OAuth token exists, run the existing GitHub device-code flow, cache the GitHub OAuth token under `.fsq-agent-workspace/auth/github-copilot-token.json`, perform Copilot plan detection and Copilot token exchange, and report success.
8. Close any provider session resources.

This flow may contact GitHub authentication and Copilot token endpoints, because that is auth setup. It must not send a Responses API model request.

For `--check-only`, the command must not call an interactive authentication path. It should validate local provider settings and report whether a usable cached Copilot auth state exists when that can be determined without starting device-code auth. If auth is missing or expired, it should fail with a message telling the operator to run `fsq-agent setup llm --provider github_copilot`.

## Azure OpenAI Setup Flow

For `fsq-agent setup llm --provider azure_openai`:

1. Ensure the setup root is the current working directory.
2. Ensure `.fsq-agent-workspace` exists and is marked as an fsq-agent workspace using the same marker policy as the config workspace resolver.
3. Prompt for `AZURE_OPENAI_BASE_URL`.
4. Prompt for `AZURE_OPENAI_MODEL`.
5. Prompt for `AZURE_OPENAI_API_KEY` using hidden input, or allow keeping an existing non-placeholder effective key without displaying it.
6. Upsert `FSQ_LLM_PROVIDER=azure_openai` and the Azure values into `.env`.
7. Load provider settings with the fixed setup workspace.
8. Validate provider-only settings, including Azure endpoint normalization to `/openai/v1/`, model presence, API key presence, and placeholder-key rejection.
9. Build or inspect provider client configuration as needed to catch local construction errors, then report readiness.

This flow must not send a live Azure model request. It cannot prove that the API key, deployment, or endpoint authorizes a model call; it should say that readiness is local configuration readiness.

For `--check-only`, the command must not prompt and must not write `.env`. It validates the effective Azure provider environment and fails with missing variable names or invalid endpoint/key diagnostics when not ready.

## Architecture And Module Ownership

### Python Architecture Level

The affected architecture levels remain the existing levels:

- `cli`: Level 3 Layered Application. It owns command parsing, interactive prompts, `.env` update orchestration, setup output, exit behavior, and calls into config/providers.
- `config`: Level 2 Simple Package. It owns environment loading, provider selection overlay, endpoint normalization, workspace path resolution helpers, and provider-only validation.
- `providers`: Level 2 Simple Package. It owns provider authentication, token cache behavior, Copilot endpoint/plan/token exchange, Azure/Copilot client construction, and any non-interactive auth readiness helper needed by check-only mode.
- `models`: Level 2 Simple Package. It owns shared provider settings documentation and any shared setup-status model only if implementation needs one across module boundaries.

No repository, unit-of-work, Clean Architecture, or DDD patterns are justified for this change.

### CLI Module

`cli` should add the public `setup` command group with an `llm` subcommand. Internal helpers may live in private modules such as `_llm_setup.py` or `_env_file.py` if that keeps `_main.py` thin.

`cli` must not import provider internals such as `_github_copilot`. It should use public config and providers APIs. It may own the `.env` upsert helper because this is command-entry behavior, not general runtime config loading.

### Config Module

`config` should read and validate `FSQ_LLM_PROVIDER` before provider-specific normalization. The effective provider controls whether GitHub Copilot defaults or Azure env-backed values are applied.

`config` should expose or document provider-only validation so `setup llm` can validate LLM provider readiness without requiring Android app id, Web browser path, Windows app path, or macOS Appium settings. Existing `validate_runtime_settings` should continue to validate both provider and active harness readiness for dynamic runs. Existing `validate_strict_core_settings(..., requires_ai_assertion=True)` should continue to validate provider readiness when strict cases require AI assertion.

### Providers Module

`providers` should remain the only owner of Copilot OAuth/device-code behavior and Azure/Copilot provider session construction.

If check-only mode needs to inspect Copilot auth readiness without starting device-code auth, that capability should be exposed through a public providers API or an explicit non-interactive option on provider setup/session construction. CLI must not reach into private provider functions or token-cache file internals.

### Models Module

`OpenAIAgentsSettings` remains the shared settings model for provider selection and resolved provider runtime values. Its SPEC documentation should be updated to state that `FSQ_LLM_PROVIDER` is the primary local provider selection source, with GitHub Copilot as the default when absent.

## Error Handling And Edge Cases

- Unsupported provider values fail during option parsing or config validation.
- `.env` read/write errors fail with the target path and no secret values.
- Hidden API key prompts must not echo input.
- Non-interactive terminals must fail clearly when setup mode requires prompting and values are missing.
- `--check-only` must not write files, initialize auth, or start device-code polling.
- Existing process environment values override `.env`; conflicts are warnings unless the effective value fails validation.
- Azure endpoint values should be normalized using the existing config rules for `/openai/responses`, `/openai/v1`, bare Azure OpenAI resource hosts, and Cognitive Services hosts.
- Azure API key placeholder values are not ready values.
- Copilot unknown plan, denied authorization, expired device code, polling failure, token exchange failure, or plan detection failure should surface as `ConfigurationError` diagnostics without token values.
- The command should not delete existing Azure variables when switching to Copilot; switching provider should be reversible by changing `FSQ_LLM_PROVIDER`.

## Affected Specs Expected To Change

- Root `SPEC.md`: runtime configuration defaults should state that `FSQ_LLM_PROVIDER` owns provider selection, GitHub Copilot remains the default, Azure values remain fixed env variables, and `setup llm` is the manual provider setup/check entry.
- `fsq_agent/cli/SPEC.md`: public command table, command validation rules, setup output, internal structure, error handling, and tests should include `setup llm`.
- `fsq_agent/config/SPEC.md`: environment overlay, public validation APIs, design decisions, `.env.example` expectations, and provider source precedence should include `FSQ_LLM_PROVIDER`.
- `fsq_agent/providers/SPEC.md`: provider setup/check behavior, Copilot interactive vs non-interactive auth readiness, and no-live-model verification boundary should be explicit.
- `fsq_agent/models/SPEC.md`: `OpenAIAgentsSettings` provider source documentation should mention env-owned provider selection.
- Repository platform presets: remove `openai_agents.provider` from committed `config.<platform>.yaml` files if SPEC confirmation chooses the env-owned source as primary.
- `.env.example`: add `FSQ_LLM_PROVIDER` with comments explaining Copilot and Azure modes.

## Verification Expectations

Focused tests should cover:

- `load_settings` applies `FSQ_LLM_PROVIDER` from `.env` and process env, with process env precedence.
- Missing `FSQ_LLM_PROVIDER` defaults to `github_copilot`.
- Invalid `FSQ_LLM_PROVIDER` raises `ConfigurationError` with supported values.
- Azure normalization and fixed env validation still work when provider selection comes from `FSQ_LLM_PROVIDER`.
- `validate_provider_settings` or equivalent provider-only validation does not require platform harness values.
- CLI command registration includes `setup` and existing commands continue to work.
- `setup llm --provider azure_openai` upserts managed `.env` keys, hides API key input, rejects placeholders, and does not print secret values.
- `setup llm --provider github_copilot` upserts `FSQ_LLM_PROVIDER`, uses the fixed current-directory workspace, and delegates auth setup through public providers APIs.
- `--check-only` for both providers performs no writes and does not start Copilot device-code auth.
- Process env versus `.env` conflicts produce a warning and validation uses the effective process value.

Suggested focused commands after implementation:

```text
./.venv/bin/python -m pytest tests/test_config.py tests/test_cli.py tests/test_copilot_provider.py tests/test_provider_session.py
```

## Resolved Questions

- Copilot setup should actively perform device-code login and cache the token.
- Azure setup should interactively write endpoint, model, and API key to `.env`.
- The feature should use an independent command, not `init`.
- The command shape is `fsq-agent setup llm --provider ...`.
- The default mode is setup/update; `--check-only` is the read-only mode.
- The command does not accept `--platform`, `--workspace`, or `--env-file` in the first cycle.
- Provider mode selection moves from YAML to env through `FSQ_LLM_PROVIDER`.
- Setup/check should not send a live model verification request.