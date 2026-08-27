# Module: providers

## Purpose

Own shared model provider construction, observable GitHub Copilot authentication and authenticated model discovery, non-interactive runtime token refresh, real connection testing, and provider-backed model call access for fsq-agent. The module builds Azure OpenAI and GitHub Copilot OpenAI-compatible clients from validated user-provider snapshots, owns Copilot request compatibility, endpoint selection, model-list parsing/filtering, and selected-model activation, exposes OpenAI Agents SDK provider/session construction, and exposes direct Responses-style model access for provider-backed AI assertion evaluators.

The module centralizes provider behavior so the main agent loop, internal pre-planner, evidence-based verifier, and platform AI assertion evaluators reuse the same provider configuration, token cache behavior, model selection, and redaction policy.

## Dependencies

- `models`: Uses `OpenAIAgentsSettings`, `AIAssertionRequest`, `AIAssertionResult`, and `ConfigurationError`.
- `config`: Uses resolved `Settings`, loads the latest saved user provider for connection tests, and activates complete GitHub authentication results through public config operations.

The providers module must not depend on `agent`, `tools`, `core`, `cli`, `report`, `knowledge`, `skills`, or `fsq`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ModelProviderFactory`: Builds provider sessions from resolved `Settings` for OpenAI Agents SDK runs and direct evaluator calls.
- `ModelProviderSession`: Owns the lifecycle of one configured provider client/session and exposes provider metadata, model name, an Agents SDK provider object factory, and direct Responses-style model invocation for evaluator-style calls.
- `AIAssertionEvaluator`: Provider-backed evaluator that satisfies `core`'s synchronous evaluator protocol: it accepts an `AIAssertionRequest`, calls the configured model through a `ModelProviderSession`, and returns an `AIAssertionResult`.
- `CaseSuggestionAnalyzer` and `CaseSuggestionAnalysis`: Read-only post-execution Case analysis boundary. The analyzer accepts source Case text plus bounded completed execution facts, makes one tool-free model request, validates the structured suggestions and optional candidate Case text, closes its Provider session, and exposes no Harness, Driver, capability, filesystem, or UI-action access.
- `prepare_model_provider_session(settings: Settings) -> ModelProviderSession`: Builds a configured session for readiness without sending a model request. For GitHub Copilot it may silently exchange a valid cached GitHub OAuth token when the provider token is absent or expired, but never starts device flow. For Azure it validates and constructs client configuration from the resolved user snapshot.
- `refresh_model_provider_session(settings: Settings) -> ModelProviderSession`: Refreshes provider-local runtime credentials at the beginning of a dynamic task without sending a live model request. For GitHub Copilot, it uses only a valid cached GitHub OAuth token to exchange and cache a fresh short-lived Copilot provider token and never starts device authentication. For Azure OpenAI, it validates and constructs client configuration from the resolved user snapshot.
- `build_model_provider_session(settings: Settings) -> ModelProviderSession`: Convenience factory for runtime construction. For GitHub Copilot it reads the user-level cached provider token and may silently refresh it from a valid cached OAuth token, but never starts device flow.
- `build_ai_assertion_evaluator(settings: Settings) -> AIAssertionEvaluator`: Convenience factory used by entry-layer code when a platform harness needs provider-backed AI assertion. For GitHub Copilot, it follows the same non-interactive provider-token read/refresh rule as `build_model_provider_session`.
- `build_case_suggestion_analyzer(settings: Settings) -> CaseSuggestionAnalyzer`: Convenience factory used by Application after a deterministic Case Run completes. It follows the same non-interactive Provider construction rules and does not send a request until `analyze` is called.
- `request_github_copilot_device_code() -> GitHubDeviceCode`: Requests one GitHub device code with the existing explicit Copilot scopes and returns verification URI, user code, polling interval, and expiration without printing to a terminal or starting polling.
- `GitHubCopilotAuthorization`: Immutable provider-boundary value containing one completed GitHub OAuth/Copilot token exchange for short-lived in-memory use. Credential fields are excluded from representations and are never presentation models.
- `GitHubCopilotModel`: Immutable safe model-list value containing the exact model id and display name.
- `complete_github_copilot_device_flow(device_code: GitHubDeviceCode, *, cancel_requested: Callable[[], bool]) -> GitHubCopilotAuthorization`: Polls with GitHub's interval/slow-down semantics, checks cancellation, exchanges the OAuth token for Copilot plan/provider-token data, and returns an in-memory authorization without activating or writing Provider configuration.
- `list_github_copilot_models(authorization: GitHubCopilotAuthorization) -> tuple[GitHubCopilotModel, ...]`: Requests the authenticated plan endpoint's `/models` collection with bounded timeout and Copilot headers, preserves service order, removes duplicate ids, and returns only picker-enabled chat models whose ids are GPT major version 5 or later and whose id/name do not identify mini, nano, Codex, embedding, audio, realtime, image, search, transcription, or TTS specializations.
- `activate_github_copilot_authorization(authorization: GitHubCopilotAuthorization, *, model: str, user_config_root: str | Path | None = None) -> UserProviderConfig`: Activates the complete pending credentials with one non-empty selected model through `config`'s atomic GitHub replacement operation.
- `test_model_provider_connection(user_config_root: str | Path | None = None) -> ProviderConnectionTestResult`: Loads the latest saved provider, creates a fresh session, sends one fixed minimal prompt requesting a short deterministic acknowledgement, returns provider/model/elapsed duration after a valid response, and always closes the session.

Current usage shape:

```python
session = build_model_provider_session(settings)
setup_session = prepare_model_provider_session(settings)
refreshed_session = refresh_model_provider_session(settings)
provider = session.create_agents_provider(openai_provider_type=OpenAIProvider, async_openai_type=AsyncOpenAI)
result = await session.invoke_responses(messages=[...], response_format=...)
evaluator = build_ai_assertion_evaluator(settings)
assertion = evaluator.evaluate(request)
connection = test_model_provider_connection()
await session.close()
```

Concrete type annotations may use `Any` for OpenAI Agents SDK classes at the boundary so importing this module does not require the SDK unless a provider session is constructed for runtime use.

## Internal Structure

- `__init__.py`: Public exports only.
- `_factory.py`: Settings-based factory functions and `ModelProviderFactory` implementation.
- `_session.py`: `ModelProviderSession` lifecycle wrapper, provider metadata, Agents SDK provider construction, direct Responses-style invocation, and cleanup.
- `_azure_openai.py`: Azure OpenAI client construction from resolved user-provider endpoint/model/API-key values and provider metadata.
- `_github_copilot.py`: Observable device-code request and cancellable polling, non-interactive cached token inspection/refresh under the user auth root, Copilot token exchange, plan detection, endpoint selection, authenticated model discovery/filtering, selected-model activation, and request/header/timeout compatibility.
- `_connection_test.py`: Fresh-session minimal Responses request, acknowledgement validation, elapsed-time measurement, safe result shaping, and guaranteed cleanup.
- `_ai_assertion.py`: `AIAssertionEvaluator` implementation and model-response parsing into `AIAssertionResult`.
- `_case_suggestion.py`: Tool-free completed-Run suggestion request, structured response validation, and Provider session cleanup.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 2 Simple Package.
- Public API: provider session/factory/evaluator types, the read-only Case suggestion analyzer and result, non-interactive preparation/refresh/build helpers, GitHub device-code authorization, safe model discovery, selected-model activation operations and values, and saved-provider connection testing exported from `__init__.py`.
- Internal modules: `_factory.py`, `_session.py`, `_azure_openai.py`, `_github_copilot.py`, `_connection_test.py`, and `_ai_assertion.py` are private implementation files.
- Domain boundaries: providers owns external model/auth protocols, client/session lifecycle, Copilot token exchange, device polling, and model invocation. Config owns files and active-provider persistence; Control Plane owns HTTP and task presentation.
- Boundary models: settings and assertion contracts come from public `config`/`models`; provider-specific device/result records are public immutable values only where callers need protocol facts.
- Dependency direction: providers may depend on public `models` and `config`; it must not import agent, entry-layer, execution, report, or frontend modules.
- Rationale: two provider integrations share a narrow session abstraction and protocol helpers, but no additional application/service layer is justified.

## Error Handling

Provider preparation, authentication, refresh, and test failures raise `ConfigurationError` from `models` with non-secret context such as provider name, endpoint family, token-cache path, safe HTTP category/status, or Copilot plan value. Errors never include API keys, OAuth tokens, Copilot API tokens, authorization headers, cookies, or user/workspace prompt content.

GitHub device authorization distinguishes request failure, polling/network failure, slow-down, expiration, denial, cancellation, token exchange failure, and unknown plan. GitHub model discovery distinguishes authorization, timeout, HTTP, malformed-envelope, and unusable-model failures without exposing raw response bodies or credentials. Azure validation distinguishes incomplete saved values, invalid base URL shape, authorization, unavailable model/deployment, rate limiting, malformed response, timeout, and client construction failure.

Non-interactive readiness and runtime construction never start device polling. They may call token exchange only when a valid cached OAuth token exists and the short-lived provider token is missing or expired. Readiness helpers do not send model requests; only the explicit connection-test operation sends a live model inference request. Authenticated model discovery requests provider metadata only.

Direct evaluator invocation failures should return or raise structured diagnostics that entry-layer code can convert into failed `HarnessActionResult` values. Missing provider credentials for an explicitly authored `assertWithAI` step should produce a configuration failure, not a silent assertion pass or fallback path.

## Current Invariants

- Provider construction belongs in `providers`, not `agent`, because the main runner, pre-planner, verifier, and platform AI assertion evaluator need the same Azure/Copilot behavior.
- `providers` may depend on `config` because it consumes resolved `Settings`, but `config` must not depend on `providers`.
- The resolved `openai_agents.provider` and provider model are the provider/model source for AI assertions. There is no separate AI assertion model override.
- All configured providers use the Responses API and the non-empty model stored in the user-provider record. There is no default provider or fixed GitHub model.
- GitHub keeps the existing explicit OAuth scopes, token exchange, plan detection, plan-specific endpoints, Copilot headers, and expiration behavior, but token files live under `~/.fsq/auth`. Runtime surfaces never start device authentication.
- Azure endpoint, model/deployment name, and API key come from the resolved user-provider snapshot, not fixed environment variables.
- Readiness proves local configuration/token readiness only. The explicit connection test is the sole setup surface that sends a live minimal model request.
- Device-flow operations do not print or prompt. Control Plane owns background transaction state, offered-model allowlisting, expiration, and presentation; `providers` owns protocol timing, cancellation checks, token exchange, model discovery/filtering, and selected-model activation through `config`.
- The providers module owns provider client lifecycle so callers do not leave `AsyncOpenAI` clients open.
- `AIAssertionEvaluator.evaluate` is synchronous to satisfy the current `core` harness protocol. It may internally bridge to asynchronous provider calls, but that detail must not leak into `core`.
- OpenAI Agents SDK runtime objects are not shared models. Provider sessions may construct SDK objects, while `models` stores only serializable settings, requests, results, and metadata.
- `core` must not import `providers`. Platform harnesses receive an evaluator object structurally and call it through an evaluator protocol owned by `core` or supplied by entry-layer code.
- AI assertion evaluator output is evidence, not a recovery mechanism. It must not perform locator fallback, mutate testcases, or convert unrelated strict-core failures into passes.
- Provider diagnostics in events and reports should include provider name, model name, endpoint family, and safe status details, but never secret values.
