# Copilot Token Exchange Compatibility Design

Date: 2026-07-21
Status: Confirmed design for SPEC-driven implementation

## Goal

Restore `fsq-agent init --platform <platform> --provider github_copilot` when GitHub device-code authorization succeeds but the subsequent GitHub Copilot token exchange fails.

The observed failure is:

```text
GitHub Copilot authorization successful.
ERROR Error: GitHub Copilot token exchange failed. Confirm the signed-in account has Copilot access.
Aborted!
```

The design targets the smallest compatibility fix for GitHub Copilot readiness. It should keep the current provider abstraction, straight-line setup flow, command shape, model default, token-cache location, and no-live-model-verification boundary intact.

## Scope

In scope:

- Update GitHub Copilot provider authentication internals so device-code OAuth and Copilot token exchange use a currently compatible request shape and bounded auth endpoint timeout.
- Request an explicit GitHub OAuth scope for Copilot setup instead of relying on an empty device-code scope.
- Add focused provider tests for the request shape.

Out of scope:

- No provider fallback to Azure OpenAI.
- No Copilot model override or model selection redesign; GitHub Copilot remains `gpt-5.5` unless existing settings already resolve otherwise.
- No live Responses API model request during `init`.
- No new public CLI command or option.
- No attempt to read VS Code's private Copilot credential state.
- No provider logout, token revocation, or migration command.
- No automatic token-cache invalidation, retry loop, endpoint fallback, provider fallback, or expanded CLI diagnostics.

## Local Evidence

The controlling code path is `init --provider github_copilot` in the `cli` module delegating to public `providers` APIs. The concrete Copilot behavior lives in the private provider implementation:

```text
cli setup -> prepare_model_provider_session(settings, interactive_auth=True)
providers factory -> build_github_copilot_client_config(...)
_resolve_github_token(...) -> device-code auth or cached GitHub OAuth token
_get_copilot_plan(...)
_get_copilot_token(...)
```

The failure happens after successful GitHub device-code authorization, which means the local break is most likely one of these conditions:

- The GitHub OAuth token was created without an explicit scope for Copilot setup.
- The Copilot internal token endpoint now rejects part of the request shape, such as API-version metadata or auth metadata.
- The account genuinely lacks Copilot access, which should still fail clearly.

## Proposed Design

### Provider Request Compatibility

The `providers` module remains the only owner of GitHub Copilot auth internals. Implementation should refresh the Copilot request shape inside the private GitHub Copilot provider module, not in `cli`.

The provider should keep the existing straight-line flow and only adjust the request shape:

- Use an explicit GitHub OAuth scope for device-code authorization.
- Keep GitHub OAuth token values and Copilot API token values out of logs, events, exceptions, and test assertion messages.
- Use a supported GitHub API-version header and explicit bounded timeout for plan detection and token exchange.
- Keep model invocation headers separate from GitHub auth/token-exchange headers.
- Parse the Copilot token response for the token and expiry as today, and keep the existing plan-to-endpoint mapping.

The design intentionally avoids hardcoding behavior from VS Code's private extension state. The implementation may compare public-safe request constants against the installed extension or GitHub API behavior during development, but the source of truth in fsq-agent remains its own provider implementation and SPEC.

### Error Handling And Diagnostics

Copilot failures should keep the existing `ConfigurationError` style: concise messages with non-secret status or error context where already present. This design does not add new CLI diagnostic rendering or retry-specific error state.

### Public Behavior

The public command remains:

```text
fsq-agent init --platform android --provider github_copilot
```

Expected behavior after implementation:

- If no valid cached OAuth token exists, the command starts GitHub device-code auth, caches the resulting OAuth token, performs Copilot plan/token readiness, and reports provider readiness without making a model inference request.
- If the signed-in account lacks Copilot access, the command fails clearly and does not keep retrying.
- `init --platform <platform>` without `--provider` still must not start Copilot auth.
- `prepare_model_provider_session(..., interactive_auth=False)` still must not prompt or mutate auth files.

## Python Architecture

Affected architecture levels remain unchanged:

- `providers`: Level 2 Simple Package. It owns provider authentication, token cache behavior, Copilot request compatibility, plan detection, token exchange, endpoint selection, and provider session construction.
- `cli`: Level 3 Layered Application. It owns command parsing, setup orchestration, `.env` upsert behavior, and user-facing setup output. It must call public provider APIs and must not import provider internals.
- `config`: Level 2 Simple Package. No ownership change; it continues to resolve provider selection and workspace paths.

No Repository, Unit of Work, Clean Architecture, or DDD pattern is justified. The change is an external-integration compatibility repair inside an existing provider boundary.

## Affected Specs Expected To Change

- Root `SPEC.md`: clarify that Copilot setup uses explicit OAuth scopes and still does not send model inference requests.
- `fsq_agent/providers/SPEC.md`: update GitHub Copilot auth behavior to include explicit OAuth scope and request/header compatibility.

No `config` or `models` SPEC change is expected unless implementation needs a shared public status model, which this design does not require.

## Resolved Questions

- Scope is a minimal GitHub Copilot token exchange/readiness fix.
- Do not add Azure fallback.
- Do not add automatic cache invalidation, retry, endpoint fallback, or expanded CLI diagnostics.
- Do not redesign model selection or provider command shape.
- Preserve no-live-model-verification during `init`.
- Keep provider internals private to `providers`; CLI should not inspect token files or provider-private functions.

## Verification Expectations

Focused automated verification after implementation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_copilot_provider.py tests/test_cli.py
```

Provider tests should cover:

- Device-code requests include the explicit OAuth scope expected by Copilot setup.
- Copilot token exchange uses the refreshed request headers.
- `interactive_auth=False` never authenticates interactively or mutates auth files.
- Copilot token responses without a token still fail clearly.

CLI tests should continue covering:

- `init --provider github_copilot` writes only `FSQ_LLM_PROVIDER=github_copilot` and delegates interactive readiness through public providers APIs.
- `init` without `--provider` does not update `.env` or start provider auth.
- Provider setup errors remain concise and non-secret.

Optional manual verification after SPEC-driven implementation:

```powershell
.\.venv\Scripts\python.exe -m fsq_agent.cli init --platform android --provider github_copilot
```

The manual check should be run from the intended setup root. It may require completing GitHub device-code auth in the browser. Success proves local auth readiness only; it does not prove a model inference call.