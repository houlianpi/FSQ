# Runtime Secret Text Input Design

## Goal

Make credential and other runtime-secret text entry reliable across dynamic LLM execution, generated recording, and strict replay.

The agent should no longer depend on the LLM remembering or copying secret plaintext from a previous `get_runtime_secret` tool result. Instead, the LLM should select an allowed runtime environment variable name, and FSQ-Agent should resolve the value locally immediately before invoking the platform text-input driver.

The primary failure this design addresses is a dynamic run where the model called `get_runtime_secret(TEST_ACCOUNT_EMAIL)` but later invoked `input_text` with the literal text `${TEST_ACCOUNT_EMAIL}` because the secret value was missing from, filtered out of, or no longer salient in model context.

## Scope

In scope:

- Runtime-secret-backed text input for recordable text-entry PlatformTools.
- Runtime initialization validation of configured runtime secret environment names, with safe warnings when configured names have no effective value.
- Dynamic LLM execution through the OpenAI Agents SDK runtime and playground.
- Strict FSQ replay through CLI and playground strict execution.
- Dynamic run recording into generated strict YAML.
- Android `input_text` / `inputText`.
- Web `type_text` / `typeText`.
- Windows `type_text` / `typeText`.
- macOS `type_text` / `typeText`.
- Prompt/task/pre-plan context that tells the LLM which runtime secret names are available.
- Safe event/report/recording behavior that preserves secret references but not secret values.
- Complete removal of the old LLM-facing `get_runtime_secret` CommonTool path and related inference code once the text-source resolver is in place. Existing recorded YAML compatibility is handled through text-input runtime-secret refs, not through `get_runtime_secret` event replay.

Out of scope:

- Changing how `.env` files are loaded by `config`; config still loads `.env` into `os.environ` before runtime construction.
- Replacing all environment variable use in provider/auth configuration.
- Exposing secret values to the LLM as the normal credential entry path.
- Adding remote or persistent secret storage beyond the local process environment.
- Supporting secret references in non-text fields such as URLs, locators, shell commands, or assertion prompts.
- Renaming `runtimeSecret` as the text source type value. The `runtimeSecret` value remains the explicit `textType` used by the new input-text schema.
- Adding UI for editing `.env` values in the playground.

## Requirements Summary

1. Build a runtime secret store during runtime initialization from `settings.runtime_secrets.allowed_env_names` and the current process environment.
2. Validate every configured runtime secret name during store construction. Missing or empty values should produce safe warnings that include the environment variable name but not a value. Missing values are not startup-fatal unless a run actually tries to use that secret.
3. Include the available runtime secret names, not values, in pre-plan and main execution task context. Missing configured names may appear in safe warning metadata but should not be advertised as usable names.
4. Add an explicit text source marker to all platform text-entry parameters so text can be literal or a runtime secret reference.
5. Resolve runtime secret references locally before calling a platform driver.
6. Make dynamic execution, strict replay, and generated recording use the same reference shape and resolver semantics.
7. Preserve backwards compatibility for existing strict YAML that has no `textType` field. Missing `textType` means `literal`.
8. Remove `get_runtime_secret` from the active LLM/CommonTool execution path: the model should not receive a secret-fetch tool for credential entry, and new recording should not depend on `get_runtime_secret` events.
9. Keep default diagnostics, reports, artifacts, and generated YAML free of secret plaintext.

## Approaches Considered

### Approach A: Keep `get_runtime_secret` and improve model visibility

The runtime could keep returning secret values to the model and relax filtering so the LLM sees old secret outputs for more turns.

Pros:

- Smallest implementation change.
- Preserves the current mental model of calling `get_runtime_secret` then `input_text`.

Cons:

- Still depends on LLM memory and copying.
- Fails when history is trimmed, filtered, or distracted by intervening tool calls.
- Increases accidental plaintext exposure risk.
- Does not unify dynamic execution with strict replay.

Decision: Reject and remove from active LLM-facing credential entry. No compatibility requirement remains for old `get_runtime_secret` event inference; related case YAML can be regenerated offline using the new text-input runtime-secret reference format.

### Approach B: Prompt-only rule to use environment variable placeholders

The prompt could tell the LLM to type `${TEST_ACCOUNT_EMAIL}` or similar, and platform drivers could interpret shell-like placeholders.

Pros:

- Very small schema change if implemented as string preprocessing.

Cons:

- Ambiguous placeholder syntaxes (`${NAME}`, `$NAME`, `%NAME%`) create cross-platform confusion.
- Literal strings that happen to look like placeholders become unsafe.
- Error handling is hidden inside string parsing.
- Generated YAML is less explicit and harder to audit.

Decision: Reject. Placeholder parsing should not be the API.

### Approach C: Explicit text source type with local resolution

Text-entry tools accept a literal string plus an explicit source marker. For runtime-secret text, the LLM supplies the environment variable name and `textType: runtimeSecret`; the runtime resolves it locally right before invoking the driver.

Pros:

- Does not require LLM access to secret plaintext.
- Works even when many tool calls occur between planning and text entry.
- Gives deterministic validation and error handling.
- Produces auditable generated YAML without secret values.
- Can unify dynamic execution, strict replay, and recording.

Cons:

- Requires schema updates across four platform text-entry parameter models.
- Requires a shared resolver path before driver invocation.
- Requires compatibility handling for existing YAML that omits the new `textType` field.

Decision: Adopt Approach C.

## Proposed Public Text Shape

The model-facing and YAML-facing shape should use the existing `text` field plus a new `textType` field.

Literal text:

```json
{
  "target": "Search box",
  "text": "weather tomorrow",
  "textType": "literal"
}
```

Runtime secret text:

```json
{
  "target": "Email input",
  "locator": {"resourceId": "emailTextInput"},
  "text": "TEST_ACCOUNT_EMAIL",
  "textType": "runtimeSecret"
}
```

Compatibility rules:

- `textType` defaults to `literal` when omitted. This is required for compatibility with historical recorded YAML that predates the `textType` field.
- Existing dynamic and strict steps with `text: "hello"` and no `textType` remain valid and are treated exactly as literal text.
- Literal text may contain strings like `${TEST_ACCOUNT_EMAIL}`; they are treated literally unless `textType` is `runtimeSecret`.

The public serialized field name is `textType`. Python internals may use `text_type` with a Pydantic alias, but all event/YAML/tool JSON should render `textType`.

## Runtime Secret Store

Introduce a small runtime secret store/resolver built from `RuntimeSecretSettings` and the current process environment after config loading has completed.

Responsibilities:

- Store the allowlisted names from `settings.runtime_secrets.allowed_env_names`.
- Check all configured names at construction time and record safe warning diagnostics for names that are missing or empty in the process environment.
- Resolve a name to the current process value only when the name is allowlisted and set.
- Return structured errors when a name is not allowlisted or not set.
- Expose safe metadata containing names, presence, and warning diagnostics, but never secret values.
- Provide a list of available names with values for prompt context. Missing configured names should be available to operator diagnostics but not presented as usable input choices.

The store should be process-local and task-run-local enough that a playground restart picks up `.env` changes. It should not write secrets to disk.

Implementation ownership should be in `core`, not `agent`, because strict replay and dynamic execution should share it. `core` may depend on `models.RuntimeSecretSettings` and the standard library, but must not import `config`.

Candidate public or semi-public core contract:

```python
store = RuntimeSecretStore.from_settings(settings.runtime_secrets)
value = store.resolve("TEST_ACCOUNT_EMAIL")
names = store.available_names()
warnings = store.warnings()
```

If the project prefers to keep the class private, the public behavior still needs to be described in `core/SPEC.md` and injected into `StepRunner` or the harness construction path.

## Prompt And Task Context

Pre-plan input and main execution task input should include safe runtime secret names, not values. `runtime_secret_names` should contain only configured names that currently have non-empty values. Safe warnings can identify configured names that are missing so the model and operator can avoid guessing.

Recommended task/pre-plan JSON fragment:

```json
{
  "runtime_secret_names": [
    "TEST_ACCOUNT_EMAIL",
    "TEST_ACCOUNT_PASSWORD"
  ],
  "runtime_secret_warnings": [
    "Runtime secret TEST_OPTIONAL_ACCOUNT is configured but not set."
  ]
}
```

Prompt instructions should state:

- For credential entry, use `textType: runtimeSecret` with one of the listed names.
- Do not call `get_runtime_secret` to type a credential. In the target design, `get_runtime_secret` should not be exposed as a normal LLM action tool.
- Do not write shell/template placeholders such as `${TEST_ACCOUNT_EMAIL}`, `$TEST_ACCOUNT_EMAIL`, or `%TEST_ACCOUNT_EMAIL%` into input fields.
- Do not pass runtime secret plaintext as ordinary literal text.
- If a needed credential is not listed, stop with a clear failed or inconclusive result.

Historical `get_runtime_secret` events do not need compatibility support after this cleanup. Any affected generated case YAML should be re-recorded offline into the new `textType: runtimeSecret` form.

## Execution Flow

### Dynamic Execution

1. CLI or playground loads settings; config loads `.env` into `os.environ` as it does today.
2. `FsqAgent` / `OpenAIAgentsRuntime` constructs or receives a runtime secret store from the active settings.
3. Store construction checks every configured runtime secret name. Missing values emit safe warnings in startup/run diagnostics and in model-facing warning context when appropriate.
4. Pre-plan and main execution inputs include the store's safe available names.
5. The LLM invokes a platform text-entry tool with `textType: runtimeSecret` and `text: ENV_NAME`.
6. `HarnessToolAdapter` creates an `ExecutableStep` preserving the unresolved safe params.
7. `StepRunner` resolves text inputs before `HarnessInterface.invoke_action`.
8. The platform harness validates and invokes the concrete driver with resolved literal text.
9. Events, reports, and recording metadata use the safe unresolved params for replay and diagnostics, not the resolved value.

### Strict Replay

1. `fsq` parses strict YAML and normalizes old and new runtime secret references into one canonical shape.
2. CLI/playground strict entry may preflight collect referenced names for early validation, but final resolution should use the same resolver path as dynamic execution.
3. `StepRunner` resolves runtime-secret text just before platform invocation.
4. Generated evidence and reports never persist the resolved value.

### Generated Recording

1. Dynamic run events include safe original text params, such as `text: TEST_ACCOUNT_EMAIL` and `textType: runtimeSecret`.
2. Recorder writes that reference form into generated YAML.
3. Recorder must not infer a later input secret from a prior `get_runtime_secret` call.
4. The existing dependency-based inference path should be removed rather than retained as a historical fallback. Affected generated case YAML can be re-recorded offline.

## StepRunner Resolution Design

`StepRunner` is the right shared resolution boundary because it is used by dynamic capability execution and strict replay. It already owns capability lookup, parameter validation, sensitivity policy, event metadata, and driver invocation routing.

Recommended sequence inside one step:

1. Resolve the capability and validate the unresolved params against the capability parameter model.
2. If the capability is a text-entry capability and `textType == runtimeSecret`, resolve `text` through the runtime secret store.
3. Build a resolved step for invocation, with `text` replaced by the secret value and `textType` removed or normalized to `literal` for driver-facing validation.
4. Preserve safe original params in invoke metadata, `safe_replay_params`, or an equivalent field.
5. Invoke the harness/driver with the resolved step.

The concrete drivers should not receive runtime secret names and should not import or query the runtime secret store. Drivers continue to type ordinary strings.

This design intentionally keeps platform-specific branches out of `StepRunner` by using capability metadata or a small helper predicate to identify capabilities whose parameter model contains a `textType`/`text` runtime-secret pair. It must not hard-code Android-only names.

## Parameter Model Changes

Affected platform parameter models:

- `AndroidInputTextParams`
- `WebTypeTextParams`
- `WindowsTypeTextParams`
- `MacOSTypeTextParams`

Each should accept:

```python
text: str
textType: Literal["literal", "runtimeSecret"] = "literal"
```

The exact Python field can be `text_type` with alias `textType` if that matches local style. Public JSON/YAML should use `textType`.

Validation rules:

- `text` must be a string for both modes.
- `textType` must be either `literal` or `runtimeSecret`.
- For `runtimeSecret`, `text` must be non-empty after trimming.
- Allowlist and existence validation happen in the resolver, not in the Pydantic model, because the model should remain independent of process environment.

## Backward Compatibility

Existing historical recorded YAML without `textType` remains valid and literal:

```yaml
- inputText:
  target: Search box
  text: weather tomorrow
```

The absence of `textType` must not make the runner guess whether `text` names an environment variable. The string is literal unless `textType: runtimeSecret` is present. There is no compatibility requirement for `text: {runtimeSecret: NAME}` because no historical cases were recorded with that shape.

Plain text remains unchanged:

```yaml
- inputText:
    target: Search box
    text: weather tomorrow
```

Dynamic runs generated before this change may contain redacted `input_text` arguments and `get_runtime_secret` events. This design does not require preserving the old inference path for those historical runs; affected generated case YAML should be re-recorded offline. Compatibility is required for already recorded strict YAML whose text-entry steps omit `textType`; those steps remain literal.

## Security And Diagnostics

Default behavior:

- The LLM sees runtime secret names, not values.
- The LLM does not receive a `get_runtime_secret` tool for credential entry.
- Events show runtime secret names, not values.
- Reports show runtime secret names, not values.
- Generated YAML shows runtime secret names, not values.
- Evidence manifests and artifact previews must not contain resolved secret text in args, metadata, or safe replay params.

Potential secret leakage still exists in UI screenshots or UI snapshots after typing, because the application under test may visually show typed text. This design only controls FSQ-Agent's own arguments, metadata, reports, and generated YAML.

If `FSQ_DEBUG_SHOW_RUNTIME_SECRETS` or a similar debug switch exists, it may affect diagnostic rendering only. Correct execution must not depend on debug mode.

Error messages:

- Not allowlisted: include the requested name and the configured allowlist names if safe.
- Missing value at initialization: emit a safe warning with the configured name and state that it is unset.
- Missing value at use time: fail the capability with a structured configuration error before invoking the driver.
- Invalid text type: include allowed textType values.
- Never include the resolved secret value.

## Module Ownership

### `models`

Owns the shared boundary representation for text source type.

Expected updates:

- Add `TextSourceType` or equivalent literal type/model.
- Add `textType` to Android/Web/Windows/macOS text-entry parameter models.
- Remove `RuntimeSecretRef` compatibility requirements if it is used only for the old `text: {runtimeSecret: NAME}` shape.
- Update model SPEC exports and platform parameter descriptions.

### `core`

Owns runtime secret resolution at execution time.

Expected updates:

- Add runtime secret store/resolver behavior based on `RuntimeSecretSettings`.
- Inject the store into `StepRunner`, `HarnessFactory`, or another existing core construction path.
- Resolve runtime-secret text before driver invocation.
- Preserve safe replay params with runtime secret references.
- Ensure failed resolution prevents driver invocation.

### `agent`

Owns dynamic prompt/task context and SDK tool exposure integration.

Expected updates:

- Include safe `runtime_secret_names` in pre-plan input and main task input.
- Include safe runtime secret warnings for configured names without values.
- Update prompt templates/instructions to prefer `textType: runtimeSecret` for credentials.
- Ensure `HarnessToolAdapter` returns safe model-visible schemas for `textType` and does not require `get_runtime_secret` for input.
- Remove active `get_runtime_secret` exposure from the normal dynamic LLM tool set once text-source resolution is available.
- Avoid exposing secret values to model context as the normal credential path.

### `fsq`

Owns strict YAML parsing and canonical step normalization.

Expected updates:

- Accept new `text` plus `textType` form.
- Treat omitted `textType` as `literal`; no old `text: {runtimeSecret: NAME}` form needs to be accepted.
- Normalize old form into the new canonical params.
- Keep authored action name metadata unchanged.

### `cli`

Owns public command behavior and dynamic recording.

Expected updates:

- Strict replay should use the shared resolver path rather than a separate pre-substitution path where practical.
- It may still preflight referenced runtime secrets for early errors.
- Dynamic recording should write `textType: runtimeSecret` when input params use runtime secret text.
- Existing `get_runtime_secret` dependency-based recording fallback should be removed. Old persisted runs or generated cases that depended on that inference path are expected to be re-recorded offline.

### `playground`

Owns local browser entry behavior.

Expected updates:

- Dynamic and strict playground execution should construct/pass the same runtime secret store as CLI execution.
- Restarting the playground remains the way to pick up `.env` changes.
- Runtime info may expose runtime secret names, presence, and warnings only if that is considered safe; it must not expose values.

### `report`

Owns rendering persisted facts safely.

Expected updates:

- Render runtime secret text refs as variable names.
- Redact resolved values if any historical runs contain them.
- Keep JSON reports free of secret values.

### `config`

Config remains the owner of `.env` loading and `RuntimeSecretSettings` allowlists.

Expected updates are likely limited to SPEC wording unless implementation chooses to expose a helper for effective runtime secret presence. Config should not own execution-time text resolution.

### `tools`

The dynamic-only AgentTool module should not own runtime secret lookup after this change.

Expected updates:

- Remove any remaining active secret-fetch helper exposure from AgentTool or CommonTool paths.
- Keep artifact/search/file helper behavior unchanged.
- Do not add runtime secret resolver dependencies to `tools`.

## Python Architecture

Architecture level: Level 3 Layered Application for the end-to-end change.

Rationale: This work coordinates entry-layer configuration, model boundary schemas, execution-core resolution, SDK dynamic runtime prompts, strict YAML parsing, generated recording, and reporting. It should remain layered through existing module boundaries rather than introducing a new domain layer or external secret service.

Module-specific architecture remains unchanged:

- `models`: Level 2 Simple Package for boundary models.
- `core`: Level 3 Layered Application execution core.
- `agent`: Level 3 Layered Application runtime orchestration.
- `fsq`: Level 2/3 parsing boundary as currently specified.
- `cli` and `playground`: entry-layer composition.
- `report`: Level 2 Simple Package transformation from persisted facts.

## Error Handling

Runtime secret resolution errors should become structured capability failures with `failure_category="configuration_error"`.

Expected cases:

- A configured runtime secret name is missing or empty at runtime initialization. This produces a safe warning, not a fatal startup error.
- `textType: runtimeSecret` and `text` is empty.
- Secret name is not allowlisted.
- Secret name is allowlisted but missing from the process environment.
- Secret name resolves to an empty string.
- `textType` is unknown.

The runner must not call the platform driver when resolution fails. The run should continue or fail according to the existing agent/strict failure policy for blocking capability failures.

## Verification Expectations

Focused tests should cover at least:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fsq_executable_step_adapter.py tests/test_strict_replay.py
.\.venv\Scripts\python.exe -m pytest tests/test_step_runner.py tests/test_step_sequence_runner.py
.\.venv\Scripts\python.exe -m pytest tests/test_openai_runtime.py tests/test_strict_case_recording.py
.\.venv\Scripts\python.exe -m pytest tests/test_android_harness.py tests/test_web_harness.py tests/test_windows_harness.py tests/test_macos_harness.py
```

Required coverage:

- Dynamic Android `input_text` accepts `textType: runtimeSecret` and the fake driver receives the resolved env value.
- Dynamic Web/Windows/macOS `type_text` accepts `textType: runtimeSecret` and fake drivers receive resolved env values.
- Plain literal text still works with omitted `textType`.
- Historical recorded YAML with `inputText`/`typeText` text fields and no `textType` still works as literal text on all supported platforms.
- New strict YAML form `text: NAME` plus `textType: runtimeSecret` works.
- Missing allowlist entry fails before driver invocation.
- Missing env value fails before driver invocation.
- Configured-but-missing runtime secret names produce startup/run warnings with names only.
- Available runtime secret names in pre-plan/main context exclude missing values or clearly mark them unusable.
- Generated recording emits `textType: runtimeSecret`, not secret plaintext.
- Newly generated dynamic runs do not require or emit `get_runtime_secret` dependency events for credential text input.
- Historical `get_runtime_secret` event compatibility is not required; affected cases are re-recorded offline.
- Already recorded strict YAML remains compatible when it omits `textType` for literal input text.
- Default reports/events do not contain secret values.
- Intervening tool calls between context setup and text input do not affect resolution.
- Existing non-secret action recording behavior remains unchanged.

Optional manual validation:

- Run an Android playground sign-in scenario from a restarted playground process using `TEST_ACCOUNT_EMAIL` and `TEST_ACCOUNT_PASSWORD` from `.env`.
- Confirm `events.jsonl` shows `input_text` with `textType: runtimeSecret` and `text: TEST_ACCOUNT_EMAIL`, not `${TEST_ACCOUNT_EMAIL}` and not the plaintext value.

## Affected SPEC Files Expected Later

The later `spec-driven` phase should update at least:

- Root `SPEC.md`: runtime secret input behavior and recorded strict case artifact policy.
- `fsq_agent/models/SPEC.md`: new text source/type model and affected platform text parameter models.
- `fsq_agent/core/SPEC.md`: runtime secret store/resolver and StepRunner text resolution behavior.
- `fsq_agent/agent/SPEC.md`: runtime secret names in pre-plan/task input and prompt/tool behavior.
- `fsq_agent/tools/SPEC.md`: removal/non-ownership of active secret-fetch helper behavior, if any remains after cleanup.
- `fsq_agent/fsq/SPEC.md`: new and backward-compatible YAML text secret forms.
- `fsq_agent/cli/SPEC.md`: strict replay and dynamic recording behavior.
- `fsq_agent/playground/SPEC.md`: playground execution behavior and restart semantics.
- `fsq_agent/report/SPEC.md`: report redaction and runtime secret ref rendering.
- `fsq_agent/config/SPEC.md`: likely only to clarify that config loads `.env` and supplies allowlists, while execution-time resolution belongs elsewhere.

## Open Questions Resolved

- The normal credential path should not expose secret values to the LLM.
- Runtime initialization should warn, not fail, when an allowlisted secret name has no value; using that missing secret should still fail before driver invocation.
- The model-facing representation should be explicit (`textType: runtimeSecret`) rather than shell placeholder strings.
- `textType` defaults to `literal` for compatibility.
- Historical YAML that lacks `textType` is compatible by definition and must be interpreted as literal text.
- Resolution should happen locally before driver invocation, not inside concrete platform drivers.
- Dynamic execution, strict replay, and generated recording should converge on one runtime-secret text representation.
- The previous LLM-facing `get_runtime_secret` workflow should be cleaned out completely once the text-source resolver exists; historical event compatibility is not required.
- The new `textType` input-text parameter must remain backward compatible with already recorded strict YAML that omits `textType` for literal text. No compatibility is required for `text: {runtimeSecret: NAME}`.
- Debug plaintext display, if present, is diagnostic only and not required for correct execution.

## Handoff Notes

After this design is approved, invoke `spec-driven` with this design document path. The implementation phase must update SPEC files first, wait for SPEC confirmation, then implement, verify, synchronize, and audit against the confirmed SPEC and actual diff.