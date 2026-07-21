# Module: providers

## Purpose

Own shared model provider construction, local provider setup/auth readiness, and provider-backed model call access for fsq-agent. The providers module builds Azure OpenAI and GitHub Copilot OpenAI-compatible clients from validated, resolved settings, owns provider authentication, Copilot request compatibility, and endpoint selection details, exposes OpenAI Agents SDK provider/session construction for the dynamic agent runtime, exposes provider setup/check helpers for the CLI, and exposes direct Responses-style model access for provider-backed AI assertion evaluators.

The module centralizes provider behavior that was previously agent-private so the main agent loop, internal pre-planner, evidence-based verifier, and platform AI assertion evaluators can reuse the same provider configuration, token cache behavior, model selection, and redaction policy.

## Dependencies

- `models`: Uses `OpenAIAgentsSettings`, `WorkspaceSettings`, `AIAssertionRequest`, `AIAssertionResult`, and `ConfigurationError`.
- `config`: Uses the resolved `Settings` aggregate as provider factory input.

The providers module must not depend on `agent`, `tools`, `core`, `cli`, `report`, `knowledge`, `skills`, or `fsq`.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `ModelProviderFactory`: Builds provider sessions from resolved `Settings` for OpenAI Agents SDK runs and direct evaluator calls.
- `ModelProviderSession`: Owns the lifecycle of one configured provider client/session and exposes provider metadata, model name, an Agents SDK provider object factory, and direct Responses-style model invocation for evaluator-style calls.
- `AIAssertionEvaluator`: Provider-backed evaluator that satisfies `core`'s synchronous evaluator protocol: it accepts an `AIAssertionRequest`, calls the configured model through a `ModelProviderSession`, and returns an `AIAssertionResult`.
- `prepare_model_provider_session(settings: Settings, *, interactive_auth: bool = True) -> ModelProviderSession`: Builds a configured provider session for setup/readiness use without sending a live model request. For GitHub Copilot, `interactive_auth=True` may run device-code authentication with explicit OAuth scopes when no valid cached GitHub OAuth token exists; `interactive_auth=False` must inspect only cached auth state and fail if interactive auth would be needed. For Azure OpenAI, it validates and constructs local client configuration from fixed environment values.
- `build_model_provider_session(settings: Settings) -> ModelProviderSession`: Convenience factory for runtime construction.
- `build_ai_assertion_evaluator(settings: Settings) -> AIAssertionEvaluator`: Convenience factory used by entry-layer code when a platform harness needs provider-backed AI assertion.

Planned signatures:

```python
session = build_model_provider_session(settings)
setup_session = prepare_model_provider_session(settings, interactive_auth=False)
provider = session.create_agents_provider(openai_provider_type=OpenAIProvider, async_openai_type=AsyncOpenAI)
result = await session.invoke_responses(messages=[...], response_format=...)
evaluator = build_ai_assertion_evaluator(settings)
assertion = evaluator.evaluate(request)
await session.close()
```

Concrete type annotations may use `Any` for OpenAI Agents SDK classes at the boundary so importing this module does not require the SDK unless a provider session is constructed for runtime use.

## Internal Structure

- `__init__.py`: Public exports only.
- `_factory.py`: Settings-based factory functions and `ModelProviderFactory` implementation.
- `_session.py`: `ModelProviderSession` lifecycle wrapper, provider metadata, Agents SDK provider construction, direct Responses-style invocation, and cleanup.
- `_azure_openai.py`: Azure OpenAI client construction from fixed environment-backed endpoint/model/API-key values, endpoint normalization assumptions, and provider metadata.
- `_github_copilot.py`: GitHub device-code auth with explicit OAuth scopes, non-interactive cached auth inspection, OAuth token cache loading/saving, Copilot token exchange, plan detection, endpoint selection, request/header/timeout compatibility, and provider metadata.
- `_ai_assertion.py`: `AIAssertionEvaluator` implementation and model-response parsing into `AIAssertionResult`.
- `SPEC.md`: Module design.

## Error Handling

Provider setup failures raise `ConfigurationError` from `models` with non-secret context such as provider name, missing environment variable name, endpoint shape, token-cache path, HTTP status code, or Copilot plan value. Provider errors must never include API keys, OAuth tokens, Copilot API tokens, authorization headers, cookies, or model prompt content containing runtime secrets.

GitHub Copilot device-code authorization failures should distinguish request failure, polling failure, expired device code, authorization denial, token exchange failure, and unknown plan. Azure OpenAI validation failures should distinguish missing fixed environment variables, invalid base URL shape, and client construction failure.

Non-interactive Copilot readiness checks must fail clearly when no valid cached GitHub OAuth token exists or when the cached token is expired, and must not start device-code polling. Provider setup/readiness helpers must not send Responses API model requests.

Direct evaluator invocation failures should return or raise structured diagnostics that entry-layer code can convert into failed `HarnessActionResult` values. Missing provider credentials for an explicitly authored `assertWithAI` step should produce a configuration failure, not a silent assertion pass or fallback path.

## Design Decisions

- Provider construction belongs in `providers`, not `agent`, because the main runner, pre-planner, verifier, and platform AI assertion evaluator need the same Azure/Copilot behavior.
- `providers` may depend on `config` because it consumes resolved `Settings`, but `config` must not depend on `providers`.
- The resolved `openai_agents.provider` and provider model are the first-cycle provider/model source for AI assertions. There is no separate AI assertion model override in this SPEC cycle.
- All configured providers use the Responses API. GitHub Copilot mode is the default provider path, uses Copilot model `gpt-5.5`, and must keep device-code OAuth, explicit OAuth scopes for Copilot token exchange, token cache under the fsq-agent workspace, Copilot token exchange, plan-specific endpoint selection, and Copilot headers.
- Azure OpenAI remains available when config resolves `azure_openai`, but endpoint, model/deployment name, and API key are supplied by fixed environment variables resolved by `config`: `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`, and `AZURE_OPENAI_API_KEY`. Provider diagnostics may name those variables when missing but must never include values.
- Provider setup readiness is local readiness only. It may perform GitHub/Copilot authentication and token exchange, but it must not call model inference endpoints or prove deployment authorization through a live request.
- The providers module owns provider client lifecycle so callers do not leave `AsyncOpenAI` clients open.
- `AIAssertionEvaluator.evaluate` is synchronous to satisfy the current `core` harness protocol. It may internally bridge to asynchronous provider calls, but that detail must not leak into `core`.
- OpenAI Agents SDK runtime objects are not shared models. Provider sessions may construct SDK objects, while `models` stores only serializable settings, requests, results, and metadata.
- `core` must not import `providers`. Platform harnesses receive an evaluator object structurally and call it through an evaluator protocol owned by `core` or supplied by entry-layer code.
- AI assertion evaluator output is evidence, not a recovery mechanism. It must not perform locator fallback, mutate testcases, or convert unrelated strict-core failures into passes.
- Provider diagnostics in events and reports should include provider name, model name, endpoint family, and safe status details, but never secret values.
