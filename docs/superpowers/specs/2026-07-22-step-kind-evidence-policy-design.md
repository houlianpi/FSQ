# Step-Kind Evidence Policy Design

Date: 2026-07-22
Status: Draft for user review

## Goal

Centralize evidence capture policy so dynamic and strict execution use one shared rule set based on `executor_kind` and `ExecutableStep.kind`, instead of scattering capture decisions across concrete driver decorators, platform action definitions such as `MACOS_ACTION_DEFINITIONS`, and per-step capture flags. As part of this cleanup, remove `harness` from the capability `executor_kind` contract so recordable execution has only `common` and `driver` executor kinds.

The design also unifies platform observation capture behind a common driver observation interface. Every platform driver interface exposes screenshot capture plus a normalized `ui_snapshot` observation for runner evidence capture. Existing authored replay aliases such as Android `uiTree`, Web `pageSnapshot`, and desktop `uiSnapshot` remain valid for explicit observation commands and dynamic recording compatibility, but automatic capture stores the structured observation under the unified internal artifact kind `ui_snapshot`.

The intended user-visible outcome is that playground screenshots and step artifacts are easier to reason about because every platform follows the same step-kind timing rules:

- `action`: capture before and after.
- `assertion`: capture before only.
- `setup`: capture after only.
- `teardown`: capture before only.

For step kinds that capture after, the after capture happens after invoke returns whether the invoke status is passed, failed, skipped, or cancelled. There is no separate extra failure screenshot phase in this design.

## Scope

This design covers recordable driver PlatformTool evidence policy for both execution modes. CommonTools remain in the capability registry but are excluded from automatic screenshot capture.

- Dynamic LLM runs through the SDK capability adapter and `StepRunner`.
- Strict FSQ YAML runs through `StepSequenceRunner` and `StepRunner`.
- Playground dynamic/strict execution insofar as it consumes the same runner artifacts and events.
- Platform capability declaration cleanup for Android, Web, Windows, and macOS.
- Capability executor-kind cleanup that removes `harness` from new capability declarations, registry metadata, and SDK capability payloads.
- Driver observation interface cleanup so platform drivers expose a shared screenshot plus `ui_snapshot` capture surface for automatic evidence.

The change is limited to default automatic evidence capture and observation naming policy. Existing explicit observation commands and replay aliases remain in scope only for compatibility; they are not the automatic capture control surface.

## Non-Goals

- Do not change FSQ YAML syntax or add user-facing evidence policy controls in this iteration.
- Do not change post-action delay behavior.
- Do not change dynamic recording eligibility or replay command generation.
- Do not change which capabilities are exposed to dynamic agents or strict replay.
- Do not change provider-backed `assertWithAI`'s invocation-owned screenshot behavior, except that the assertion step itself now receives the step-kind default before capture.
- Do not introduce platform-specific action-name allowlists in `StepRunner`.
- Do not remove existing run artifact display endpoints from playground.
- Do not break historical run/report loading solely because older persisted events used `tool_origin="harness"`; historical display compatibility may remain, but new capability metadata must not emit `executor_kind="harness"`.
- Do not rename existing authored FSQ replay aliases such as `uiTree`, `pageSnapshot`, or `uiSnapshot`; only automatic capture artifact naming is unified.

## Current Problem

Evidence capture is currently controlled by `CapabilityDefinition.capture_evidence` plus `EvidencePolicy` fields such as `capture_before`, `capture_after`, `capture_on_failure`, and `artifact_kinds`. Their values and effects are spread across several places:

- Android sets `capture_evidence=True` mostly on concrete driver method decorators.
- Web and macOS set it mostly in platform action definition catalogs.
- Windows sets it in a local catalog helper in `core.harness._driver_tools`.
- Special cases such as Windows/macOS `launchApp` use decorator metadata to tune before/failure capture.
- `StepRunner` maps platform names to different structured observation kinds: Android `ui_tree`, Web `page_snapshot`, and Windows/macOS `ui_snapshot`.

This creates three problems:

1. The same concept is declared in different places by platform, making it difficult to audit which commands produce screenshots.
2. Step timing rules are mixed into capability declaration metadata, even though the timing decision belongs to the runner execution policy.
3. Automatic capture has to know platform-specific observation names, while every platform really needs the same runner-level evidence pair: screenshot plus a UI/application snapshot.

## Approaches Considered

### Approach A: Normalize `capture_evidence` Into All Platform Action Definitions

Add `capture_evidence` to Android action definitions and move Windows defaults into a shared Windows action catalog shape, so every platform declares evidence defaults in action definitions.

Pros:

- Improves consistency compared with the current mixed decorator/catalog shape.
- Minimal runner behavior change.

Cons:

- Still requires per-action evidence flags even though the desired behavior is step-kind based.
- Future actions can still drift if authors forget the right flag.
- Does not directly encode assertion/setup/teardown timing rules.
- Keeps platform-specific observation artifact names in the runner policy.

### Approach B: Step-Kind Policy In `StepRunner` With Existing Platform Observation Names

Remove default capture decisions from concrete driver decorators and platform action definitions. Remove `harness` from the capability executor-kind contract. `StepRunner` derives the default evidence policy from `ExecutableStep.kind` for supported recordable driver capabilities, while continuing to map platforms to Android `ui_tree`, Web `page_snapshot`, and desktop `ui_snapshot` artifact kinds.

Pros:

- One shared policy applies to dynamic and strict because both paths already converge at `StepRunner`.
- Capture timing becomes auditable in one place.
- New platform actions inherit correct behavior when their `step_kind` is correct.
- Reduces platform-specific duplication and removes current Android/Web/Windows/macOS declaration asymmetry.
- Simplifies capability routing by making `driver` the only PlatformTool executor kind in this design cycle.

Cons:

- Broadens automatic evidence for assertion/setup/teardown steps compared with the current `capture_evidence=True` list.
- Requires careful compatibility decisions for observation/diagnostic/CommonTool steps.
- Existing tests that assert per-capability `capture_evidence` flags must be updated.
- Existing code paths and tests that mention `executor_kind="harness"` must be audited and either removed or narrowed to historical event display compatibility.
- Keeps automatic capture coupled to platform-specific observation names.

### Approach C: Unified Driver Observation Interface And Step-Kind Policy (Recommended)

Remove default capture decisions from concrete driver decorators and platform action definitions. Remove `harness` from capability executor kinds. Add a shared driver observation contract for automatic capture: every concrete platform driver implements screenshot capture plus normalized `ui_snapshot` capture, and `StepRunner` uses `executor_kind="driver"` plus `step.kind` to decide timing.

Pros:

- One shared policy applies to dynamic and strict because both paths converge at `StepRunner`.
- Capture timing is controlled by `executor_kind + step_kind`, not scattered flags.
- Automatic capture always writes the same evidence pair: `screenshot` plus `ui_snapshot`.
- Platform-specific authored observation aliases can remain for strict replay and dynamic recording compatibility without leaking into runner capture policy.
- New platform drivers have a clear interface contract: implement screenshot and UI snapshot capture.
- Removes unused `harness` executor kind and simplifies live capability routing.

Cons:

- Requires a compatibility mapping from existing platform observation implementations into normalized `ui_snapshot` artifacts.
- Existing tests and reports that expect Android automatic `ui_tree` or Web automatic `page_snapshot` artifacts must be updated to expect automatic `ui_snapshot`, while explicit `uiTree` and `pageSnapshot` commands remain valid.
- Requires careful SPEC wording so `ui_snapshot` is understood as the normalized evidence artifact kind, not necessarily the authored replay alias.

### Approach D: Separate EvidencePolicyResolver Service

Introduce a new resolver class used by `StepRunner` and tests, with `StepRunner` delegating effective policy construction to it.

Pros:

- Makes policy independently testable.
- Keeps `StepRunner` smaller if policy grows.

Cons:

- Adds an abstraction before there is enough complexity to justify it.
- Still must be owned by `core` and invoked only from `StepRunner`, so it does not materially change boundaries.

The recommended implementation is Approach C, using a private `StepRunner` helper or small private `core.runner` helper first. Escalate to a separate resolver class only if implementation reveals policy complexity that makes a private helper unwieldy.

## Proposed Design

### Central Default Policy

`StepRunner` derives an effective evidence policy from `ExecutableStep.kind` when all of the following are true:

- The resolved capability exists.
- The capability is a recordable driver PlatformTool.
- The step kind is one of `action`, `assertion`, `setup`, or `teardown`.

This replaces normal use of `CapabilityDefinition.capture_evidence`, `EvidencePolicy.capture_before`, `EvidencePolicy.capture_after`, `EvidencePolicy.capture_on_failure`, and `EvidencePolicy.artifact_kinds` for default automatic capture. If implementation can remove these fields without excessive compatibility risk, it should remove them. If they must remain for a transition, they should no longer control default runner capture.

The default policy table is:

| Step kind | Capture before | Capture after | Notes |
|---|---:|---:|---|
| `action` | yes | yes | After capture happens for success and failure outcomes. |
| `assertion` | yes | no | Captures the state being asserted before the assertion runs. |
| `setup` | no | yes | Captures the post-setup state, including failed setup attempts when the backend can provide artifacts. |
| `teardown` | yes | no | Captures the state before teardown removes the app/browser/window/session. |
| `observation` | no | no | Observation tools are themselves evidence-producing or read-only. |
| `diagnostic` | no | no | Diagnostics do not get automatic screenshots by default. |

The default artifact pair is platform-neutral:

- `screenshot`
- `ui_snapshot`

Each platform driver implements the `ui_snapshot` capture contract using its native mechanism:

- Android may produce the same content currently exposed by explicit `uiTree`, but automatic capture stores it as `ui_snapshot`.
- Web may produce the same content currently exposed by explicit `pageSnapshot`, but automatic capture stores it as `ui_snapshot`.
- Windows and macOS continue to produce desktop UI snapshots as `ui_snapshot`.

There is no separate failure artifact by default. After capture already represents the post-invoke state for step kinds that need post-invoke evidence, including failed invokes.

### Driver Observation Interface

Introduce or formalize a shared observation interface that every platform driver interface inherits.

The interface should require:

- `screenshot(...) -> bytes`, or the existing platform-equivalent screenshot method adapted through the harness.
- `ui_snapshot(...) -> dict[str, object]`, returning a serializable structured snapshot suitable for `ArtifactStore.write_json(kind="ui_snapshot", ...)`.

Concrete driver implementations own native details:

- Android maps `ui_snapshot` to uiautomator2 hierarchy capture.
- Web maps `ui_snapshot` to Playwright accessibility/page snapshot capture.
- Windows maps `ui_snapshot` to pywinauto control-tree capture.
- macOS maps `ui_snapshot` to Appium Mac2 page-source/control-tree capture.

Harnesses continue to own artifact writing and runtime service delegation. `StepRunner` should not branch on Android/Web/desktop observation command names.

### Declaration Cleanup

Default evidence capture should no longer be declared on concrete driver decorators, platform action definitions, or `EvidencePolicy` default fields.

Implementation should remove default evidence flags from:

- Android concrete driver decorators such as `_android_driver_tool(..., capture_evidence=True)`.
- Web `WebActionDefinition(..., capture_evidence=True)` entries.
- Windows `_windows_action(..., capture_evidence=True)` entries.
- macOS `MacOSActionDefinition(..., capture_evidence=True)` entries.

The capability declaration layer may keep `CapabilityDefinition.capture_evidence` as a compatibility field if removing it is too broad for one implementation cycle, but default runner behavior must not depend on it. If retained, it should be documented as legacy or explicit opt-in metadata rather than the normal default capture source.

Decorator metadata such as `evidence_capture_before` and `evidence_capture_on_failure` should not be used for the default policy after this change. Platform lifecycle edge cases should be handled by step-kind rules:

- `setup` captures after only.
- `teardown` captures before only.

### Executor-Kind Cleanup

The implementation should remove `harness` as a capability executor kind from new runtime contracts.

Expected changes:

- `CapabilityExecutorKind` becomes `Literal["common", "driver"]`.
- Neutral capability validation rejects `executor_kind="harness"`.
- `harness_capability` and `platform_capability` decorator helpers are removed if they are unused, or made private compatibility shims only if implementation discovers an unavoidable transitional dependency.
- `StepRunner` evidence policy checks `executor_kind == "driver"` for automatic platform evidence. CommonTools remain excluded.
- New SDK capability payloads, registry snapshots, and reports must not emit `executor_kind="harness"`.
- Historical run/report display code may continue accepting `tool_origin="harness"` when reading old `events.jsonl`, but that is display compatibility rather than a live capability executor kind.

### Explicit Capture Flags

The target design removes the need for `capture_evidence`, `capture_before`, `capture_after`, `capture_on_failure`, and `artifact_kinds` as the default capture control surface.

If implementation cannot remove every field in one cycle, retained fields must be treated as legacy compatibility only and must not create a second default policy path. A later SPEC may reintroduce an explicit override mechanism if a concrete user-facing need appears, but this design intentionally keeps default capture controlled only by `executor_kind + step_kind`.

### Dynamic And Strict Parity

Dynamic execution already creates canonical `ExecutableStep` values and delegates execution to `StepRunner`. Strict execution already converts YAML into canonical `ExecutableStep` values and delegates execution through `StepSequenceRunner -> StepRunner`.

Therefore, the shared policy must live in `StepRunner` or a private core helper called only by `StepRunner`. Neither the dynamic SDK adapter nor the strict FSQ adapter should duplicate evidence policy logic.

Expected flows:

Dynamic:

1. SDK tool call is adapted to `ExecutableStep` with canonical `executor_kind` and `step.kind` metadata.
2. `StepRunner` resolves capability metadata and reads `step.kind`.
3. `StepRunner` applies the centralized `executor_kind + step_kind` capture policy.
4. Tool output and persisted run events receive the resulting artifact refs.

Strict:

1. FSQ YAML is parsed into `ExecutableStep` records with canonical step kinds.
2. Strict replay resolution updates params only.
3. `StepSequenceRunner` calls `StepRunner` for each step.
4. `StepRunner` applies the same centralized `executor_kind + step_kind` capture policy.
5. Evidence manifest and core report receive the resulting artifact refs.

## Module Ownership

### `core`

`core.StepRunner` owns centralized default evidence policy because it owns execution phases, harness invocation, artifact capture, and dynamic/strict convergence. The live PlatformTool executor kind is `driver`; harnesses remain runtime gateways through `HarnessInterface.invoke_action`, not capability executor kinds.

Responsibilities:

- Derive default evidence policy from `ExecutableStep.kind`.
- Capture the normalized default artifact pair: `screenshot` plus `ui_snapshot`.
- Emit the same runner events and phase reports as today.
- Avoid action-name branches and platform-specific action lists.
- Exclude CommonTools and any historical `harness` compatibility labels from automatic platform evidence.

### `models`

`models` owns the shared contracts only.

Expected changes during spec-driven implementation:

- Remove or deprecate `EvidencePolicy` capture control fields if they no longer have a live use after the centralized policy change.
- Revisit `CapabilityDefinition.capture_evidence` wording so it is not described as the normal default evidence source.
- Remove `capture_evidence` from platform action definition dataclasses if no longer needed for declaration compatibility.
- Remove `harness` from `CapabilityExecutorKind` and update capability metadata docs to describe only `common` and `driver`.
- Add or document a shared driver observation interface contract for `screenshot` and `ui_snapshot`.

### `capabilities`

`capabilities` owns declaration metadata and discovery, not execution policy.

Expected changes during spec-driven implementation:

- Remove `capture_evidence` from `CapabilityActionDefinition` and decorator catalog defaults if it is no longer used.
- Or keep the field only as legacy explicit metadata if removal would make the implementation cycle too large.
- Ensure platform driver decorators remain catalog-backed for action name, params model, replay alias, step kind, owner, and method validation.
- Remove or deprecate unused harness/platform capability decorator helpers that create `executor_kind="harness"` declarations.
- Ensure platform catalogs do not encode default screenshot or observation timing.

### `agent`

`agent` remains an SDK adapter and runtime orchestrator. It must not own default evidence policy. It should continue to build canonical `ExecutableStep` values and call `StepRunner`.

### `fsq`

`fsq` remains YAML parsing and step adaptation. It must not derive default screenshot policies.

### `cli` And `playground`

`cli` and `playground` consume runner output. They should receive changed artifacts through the same runner and evidence manifest/event paths. They should not add local policy branches.

## Public Behavior

After implementation, recordable capabilities with these step kinds should capture artifacts consistently in dynamic and strict modes:

- `action`: before `screenshot`/`ui_snapshot` and after `screenshot`/`ui_snapshot`.
- `assertion`: before `screenshot`/`ui_snapshot` only.
- `setup`: after `screenshot`/`ui_snapshot` only.
- `teardown`: before `screenshot`/`ui_snapshot` only.

Observation and diagnostic steps do not get automatic before/after artifacts. If an observation capability returns its own artifact or inline output, that remains the observation capability's invoke result, not automatic runner evidence.

For step kinds with after capture, the after capture runs after invoke even when invoke returns a failed, skipped, or cancelled result, provided the harness can still capture artifacts. This is the only default failure-state capture; no second `reason="failure"` artifact is produced by default.

Existing explicit observation command aliases remain valid:

- Android `uiTree` continues to resolve to the Android observation capability for authored strict cases and dynamic tool use.
- Web `pageSnapshot` continues to resolve to the Web observation capability.
- Windows/macOS `uiSnapshot` continue to resolve to desktop observation capabilities.

Those aliases do not control automatic capture artifact naming. Automatic capture writes normalized `ui_snapshot` artifacts across all platforms.

## Edge Cases

- If setup fails before a session/page/window exists, after capture may itself fail. Existing runner artifact error behavior should report this as an artifact failure unless SPEC implementation explicitly decides that unavailable setup artifacts are non-fatal for setup steps. The preferred first implementation is to preserve current runner error semantics.
- Teardown after capture is intentionally disabled by default because teardown may destroy the page/window/session needed for artifact capture.
- Assertions capture before only so the asserted state is visible without producing redundant after screenshots for read-only checks.
- `assertWithAI` may still produce invocation-owned AI assertion screenshot artifacts through shared backend support. The step-kind default adds before-state `screenshot` and `ui_snapshot` evidence, not a replacement for the AI assertion screenshot.
- CommonTool steps such as `wait_ms` and `get_runtime_secret` should not receive screenshot evidence in this design unless a later SPEC explicitly includes CommonTools in the step-kind policy.
- If an existing platform driver cannot provide `ui_snapshot` before the backend session/page/window exists, the failure should surface through the existing artifact error path unless the SPEC update explicitly defines a non-fatal unavailable-artifact result for setup startup edges.

## Affected Specs Expected To Change

The spec-driven phase should update and confirm at least these specs before implementation:

- Root `SPEC.md`: replace capability-flag-driven default evidence wording with centralized step-kind evidence policy.
- `fsq_agent/core/SPEC.md`: define the step-kind policy table, failure semantics, dynamic/strict parity, normalized `ui_snapshot` capture, and the removal of live `harness` executor-kind routing.
- `fsq_agent/models/SPEC.md`: revise `CapabilityDefinition.capture_evidence`, `CapabilityExecutorKind`, `EvidencePolicy`, driver observation interface contracts, and platform action definition descriptions.
- `fsq_agent/capabilities/SPEC.md`: revise catalog/decorator ownership so evidence defaults do not live in platform action catalogs by default, and remove live `harness` capability declarations.
- `fsq_agent/agent/SPEC.md`: update dynamic execution wording to say `StepRunner` derives evidence from step kind rather than `CapabilityDefinition.capture_evidence`.
- `fsq_agent/cli/SPEC.md`: update strict execution wording to reference centralized step-kind policy.
- `fsq_agent/playground/SPEC.md`: update screenshot/artifact expectations if tests or UI wording mention capture-enabled PlatformTools.
- `fsq_agent/report/SPEC.md`: update artifact naming expectations from platform-specific automatic observation names to normalized automatic `ui_snapshot` where reports describe automatic evidence, and distinguish historical `tool_origin="harness"` display compatibility from live capability executor kinds if needed.

## Verification Expectations

Focused tests should cover:

- `StepRunner` derives action before+after artifacts from `step.kind="action"` without requiring `CapabilityDefinition.capture_evidence=True`.
- `StepRunner` derives assertion before-only artifacts from `step.kind="assertion"`.
- `StepRunner` derives setup after-only artifacts from `step.kind="setup"`.
- `StepRunner` derives teardown before-only artifacts from `step.kind="teardown"`.
- Observation and diagnostic steps do not receive automatic before/after artifacts.
- Failed action/setup invocations still receive their after artifacts, without an additional default failure artifact.
- Default capture does not depend on `capture_evidence`, `capture_before`, `capture_after`, `capture_on_failure`, or `artifact_kinds`.
- Dynamic SDK capability calls and strict FSQ replay both use the same policy via `StepRunner`.
- Platform automatic observation artifact kind is always `ui_snapshot`.
- Android and Web explicit observation aliases still work for authored commands, but automatic capture stores normalized `ui_snapshot` artifacts.
- Platform driver interfaces expose a shared screenshot plus `ui_snapshot` observation contract.
- Capability declaration tests no longer require per-action `capture_evidence` values in Android/Web/Windows/macOS catalogs or concrete decorators.
- `CapabilityExecutorKind` no longer accepts `harness`, and declaration validation rejects `executor_kind="harness"` for new capabilities.
- Dynamic SDK capability payloads and strict registry snapshots expose only `common` or `driver` executor kinds.
- Historical event/report fixtures that contain `tool_origin="harness"` continue to render only if compatibility is intentionally retained.

Recommended verification commands for implementation:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_step_runner.py tests/test_openai_runtime.py tests/test_cli_core_execution.py tests/test_android_harness.py tests/test_web_harness.py tests/test_windows_harness.py tests/test_macos_harness.py tests/test_capabilities.py tests/test_playground.py
```

Broader test runs are appropriate if implementation removes `capture_evidence` or `EvidencePolicy` fields from shared models or public exports in a way that affects report, recording, playground, or compatibility paths.

## Audit Expectations

The post-implementation audit should check:

- No default capture decisions remain in concrete driver decorators.
- No default capture decisions remain in platform action definitions such as `MACOS_ACTION_DEFINITIONS`.
- `StepRunner` contains no platform action-name allowlists.
- Dynamic and strict paths both call the same evidence policy code.
- Automatic capture writes `screenshot` plus normalized `ui_snapshot` artifacts for every platform.
- No live capability definitions, registry snapshots, SDK capability payloads, or strict replay metadata use `executor_kind="harness"`.
- `fsq` does not import `core` or duplicate evidence logic.
- `models` remains contract-only and does not gain runner behavior.
- Playground screenshot/replay behavior changes are a result of runner artifacts, not a separate playground policy.

## Open Questions Resolved

- Failure handling: for step kinds with after capture, after capture includes both successful and failed invokes. The design does not add a separate default failure screenshot.
- Scope: this design changes automatic evidence capture policy only. Playground presentation improvements can build on the resulting artifacts but are not a separate UI redesign in this cycle.
- Executor kinds: remove live `harness` capability executor kind. Keep only historical display compatibility for persisted `tool_origin="harness"` values if needed.
- Observation naming: automatic capture uses normalized `ui_snapshot` across all platforms. Existing authored observation aliases remain unchanged.
