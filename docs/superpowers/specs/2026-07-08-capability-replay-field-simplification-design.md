# Capability Replay Field Simplification Design

Date: 2026-07-08
Status: Ready for user review

## Goal

Simplify capability metadata and the dynamic recording to strict replay control flow by making replay metadata the single source of truth for replay eligibility and recorded command names.

This design is the handoff artifact for a later `spec-driven` cycle after user confirmation. It defines the target behavior, module ownership, SPEC update expectations, implementation constraints, and verification requirements for removing duplicated capability fields while preserving existing authored strict YAML names such as `tapOn`, `waitMs`, `startBrowser`, `clickOn`, and `assertWithAI`.

## Selected Design Summary

The target design removes `strict` as a capability metadata field.

`strict` currently controls OpenAI Agents SDK function-tool JSON schema strictness. It is consumed when building SDK tools as `strict_json_schema`. It does not control LLM SDK exposure, dynamic recording, or strict replay. Tool exposure is controlled by active capability registration and harness `action_space()` discovery. If a backend method is unfinished or should not be available to the LLM, the correct control is to omit the capability decorator so it never becomes an active registered capability.

The clearest example is Android `performActions`, which is the only current action definition with `strict=False`, but the uiautomator2 backend method is intentionally not decorated. Therefore it does not appear in `action_space()` or SDK exposure. Its catalog `strict=False` value has no active runtime effect. That means the field is currently carrying future/speculative flexibility rather than required behavior.

The target should remove the per-capability `strict` field from capability definitions, decorators, and action catalogs. SDK tool builders should pass `strict_json_schema=True` for active capabilities by default. If a future active capability truly requires non-strict SDK schema validation, that should be introduced later with an explicitly named field such as `strict_json_schema`, reviewed against the concrete tool that needs it.

`replay` is the replay participation contract. For an active registered capability, `replay is not None` means the capability contributes to dynamic recording and strict replay metadata. `ReplayPolicy.kind == "fsq_command"` means the recorder may emit a strict YAML command using `replay.alias`. `ReplayPolicy.kind == "dependency"` means the recorder tracks dependency metadata, such as `runtimeSecret`, without emitting a standalone command.

`aliases` and `replay.alias` are partially duplicated.

Today `aliases` is used by registry and FSQ parsing to accept authored YAML names, while `replay.alias` is used by the recorder to choose the generated YAML command name. For replayable FSQ command capabilities, those two strings are usually the same primary authored name. The target design derives that primary authored command name from `ReplayPolicy(kind="fsq_command").alias` instead of storing it separately in `CapabilityDefinition.aliases`.

## Scope

This design covers the capability metadata contract, declaration/catalog metadata, active capability registry resolution, FSQ strict YAML parsing, dynamic recording, SDK tool exposure metadata, and tests for those boundaries.

Affected modules:

- `models`: capability metadata contracts such as `CapabilityDefinition`, `ReplayPolicy`, and related declaration/result models.
- `capabilities`: decorators, catalog-backed validation, and discovery that create `CapabilityDefinition` records.
- `core`: active `CapabilityRegistry`, `StepRunner` replay metadata emission, CommonTool and PlatformTool capability exposure.
- `fsq`: authored command name resolution from canonical capability names and replay aliases.
- `cli`: dynamic run recording into strict `.codex.yaml` artifacts and strict replay reference handling.
- `agent`: SDK tool conversion and pre-plan capability summaries.
- `report` and `playground`: metadata display paths that surface aliases or replay metadata.
- Tests covering capability discovery, strict parsing, dynamic recording, runner metadata, and default SDK tool schema strictness.

## Non-Goals

This design does not update root or module `SPEC.md` files and does not implement code. The later `spec-driven` cycle must update and confirm the relevant SPEC files before implementation.

This design does not remove SDK strict schema usage. It removes the current per-capability `strict` override field because no active exposed capability needs non-strict schema validation.

This design does not add new platform capabilities, change command parameter models, mutate source cases, or change the meaning of existing strict YAML command names.

This design does not make catalog-only actions executable. A catalog entry with a replay policy is not enough; only active registered `CapabilityDefinition` records participate in parsing, SDK exposure, recording, or strict replay.

## Proposed Design

### Replay Eligibility

For an active registered capability, replay participation is determined only by `CapabilityDefinition.replay`.

Rules:

- `replay is None`: diagnostic or dynamic-only metadata for recording purposes; the recorder skips it.
- `replay.kind == "fsq_command"`: a successful completed call may be recorded as `{replay.alias: safe_replay_params}`.
- `replay.kind == "dependency"`: a successful completed call records dependency metadata but does not append a strict YAML command.
- The recorder must not infer replayability from canonical names, driver method names, `fsq_action_name`, tool origins, or schema strictness.

The dynamic recorder should require replay metadata for new event logs. Any legacy fallback from `fsq_action_name` should be removed or explicitly isolated as old-run compatibility if a SPEC review decides that historical run recording is still required.

### Remove Per-Capability Strict Field

Keep SDK strict JSON schema behavior, but stop storing it as per-capability metadata unless a concrete active capability needs an override.

The target contract removes capability declaration/catalog metadata named `strict` instead of renaming it immediately. The current codebase has no active exposed capability that requires non-strict SDK schema validation. Android `performActions` is not exposed because it is not decorated, so it must not force the shared capability model to keep a speculative schema override.

Expected semantics:

- Capability exposure is decided before schema strictness: only decorated, discovered, and active registered capabilities may enter harness `action_space()` and SDK tool construction.
- Unimplemented or intentionally hidden backend methods must not be decorated as capabilities. They should not rely on `strict=False`, `strict_json_schema=False`, or any schema flag to stay hidden.
- When an active capability is exposed to the SDK, expose it with strict JSON schema validation by default.
- Capability metadata does not need a schema strictness field until an active reviewed capability requires non-strict schema validation.
- SDK schema strictness has no effect on SDK tool inclusion, dynamic recording eligibility, strict YAML parsing, or strict-core execution.

If implementation keeps a temporary `strict` compatibility input while migrating tests and call sites, it should be ignored or normalized away before producing the target public capability metadata. It should not remain in `CapabilityDefinition`, registry snapshots, action-space schemas, event metadata, reports, or SPEC text as an authoritative capability field.

### Replay Alias As Primary Authored Command Name

For replayable strict YAML commands, `ReplayPolicy.alias` should become the primary authored command name.

Registry resolution should accept:

- The canonical capability name, such as `tap_on` or `wait_ms`.
- `replay.alias` when `replay.kind == "fsq_command"`, such as `tapOn` or `waitMs`.

`ReplayPolicy(kind="dependency", alias="runtimeSecret")` must not create a top-level executable command alias. `runtimeSecret` remains a replay reference shape inside parameters.

The active registry must continue to reject ambiguity:

- A replay alias must not equal another capability's canonical name.
- Two active capabilities must not declare the same replay alias.
- A canonical name and its replay alias must resolve to the same capability.

### Removing Duplicate Alias Declarations

The target `CapabilityDefinition` should not require a separate `aliases` list for the primary replay command alias.

Declaration flow should derive the primary replay alias from the catalog action name or explicit replay policy:

- Platform action catalogs keep the authored action name, such as `tapOn`, as the source for `ReplayPolicy(kind="fsq_command", alias="tapOn")`.
- CommonTools such as `wait_ms` declare `ReplayPolicy(kind="fsq_command", alias="waitMs")` without also declaring `aliases=["waitMs"]`.
- Driver and platform decorators pass replay policy forward; discovery does not need to copy the replay alias into a separate alias field.

If a future capability needs additional accepted names that are not the recorded name, that should be a separate compatibility design. It should not reuse `replay.alias`, because `replay.alias` has exactly one meaning: the name emitted by recording and accepted as the primary strict replay command name.

### Control Flow

Dynamic execution:

1. Capability discovery creates active `CapabilityDefinition` records with canonical names, replay policy metadata, and parameter models.
2. Harness `action_space()` and SDK tool builders expose only active discovered capabilities; unimplemented methods without decorators are absent.
3. SDK tool builders expose canonical tool names and pass `strict_json_schema=True` for those already-selected tools.
4. `StepRunner` includes replay metadata and safe replay params in structured events and capability results.
5. The recorder appends commands only for successful completed events whose replay policy is `fsq_command`.
6. The recorder uses `replay.alias` as the generated YAML key.

Strict replay parsing:

1. The active platform registry is bootstrapped before parsing.
2. `FsqExecutableStepAdapter` resolves each authored YAML command through canonical names or `fsq_command` replay aliases.
3. The adapter stores canonical `ExecutableStep.action_name` and preserves the authored command name in metadata.
4. Runtime secret references are resolved by strict entry-layer code before platform actions execute.

## Public Behavior

Existing authored strict YAML command names remain valid for active capabilities:

- Android examples: `launchApp`, `tapOn`, `inputText`, `waitMs`, `assertWithAI`.
- Web examples: `startBrowser`, `navigateTo`, `clickOn`, `pageSnapshot`.
- Desktop examples: `launchApp`, `clickOn`, `typeText`, `uiSnapshot`.

Generated recorded YAML continues to use the same names, but those names are now controlled only by `replay.alias`.

Capabilities without replay policy are never recorded into generated strict YAML. They may still appear in reports or diagnostics if execution emits safe metadata.

SDK strict schema behavior remains the default for active exposed tools. Non-strict SDK schema validation is not part of the target capability contract unless a later SPEC introduces it for a concrete active tool.

## Python Architecture Level And Rationale

This change stays within the existing architecture levels.

`models` and `capabilities` remain Level 2 Simple Package modules. The change is contract and declaration metadata simplification, not a new orchestration layer.

`core`, `agent`, and `cli` remain Level 3 Layered Application modules because they coordinate execution, SDK exposure, recording, strict replay, and reports. The implementation should adjust existing orchestration paths rather than introduce new services or architectural patterns.

No Repository, Unit of Work, Clean Architecture, or DDD pattern is justified by this change.

## Affected Specs Expected To Change

Expected SPEC updates after this design is confirmed:

- Root `SPEC.md`: clarify that replay policy determines replayability, active registration determines SDK exposure, and replay aliases are primary authored strict command names for active capabilities.
- `fsq_agent/models/SPEC.md`: update `CapabilityDefinition` and `ReplayPolicy` descriptions, and remove the per-capability `strict` field from target metadata.
- `fsq_agent/capabilities/SPEC.md`: update decorator/catalog/discovery contracts to derive primary replay command aliases from replay policy.
- `fsq_agent/core/SPEC.md`: update registry resolution, action-space, SDK schema default, and runner metadata rules.
- `fsq_agent/fsq/SPEC.md`: update authored command resolution through canonical names and replay aliases.
- `fsq_agent/cli/SPEC.md`: update recorder rules to require replay metadata and use `replay.alias` as the only generated command name.
- `fsq_agent/agent/SPEC.md`: update SDK tool construction to use strict JSON schema by default for active capabilities and remove capability summary schema-strictness metadata.
- `fsq_agent/report/SPEC.md` and `fsq_agent/playground/SPEC.md`: update alias/replay metadata display expectations if they expose the removed alias list.

## Spec-Driven Handoff

The subsequent `spec-driven` cycle should treat this document as a design input, not as the implementation source of truth. The implementation source of truth becomes the confirmed root and module `SPEC.md` files produced from this design.

The SPEC update phase should preserve these required outcomes:

- Remove `strict` from target capability metadata, decorator inputs, action catalog entries, registry snapshots, action-space schemas, safe metadata, event metadata, reports, and pre-plan capability summaries.
- Keep SDK tool exposure controlled by active capability registration and harness `action_space()` discovery.
- Keep SDK tool JSON schema strict by default for active exposed capabilities.
- Resolve strict YAML commands through canonical capability names and `ReplayPolicy(kind="fsq_command").alias`.
- Do not create top-level executable command aliases from `ReplayPolicy(kind="dependency")` values such as `runtimeSecret`.
- Remove the primary replay command name from `CapabilityDefinition.aliases`; if compatibility aliases beyond the replay alias are needed later, design them separately.
- Make dynamic recording require replay metadata for new events and use `replay.alias` as the only generated strict YAML command name.

## Design Decisions

`strict` should not remain as a target capability metadata field. Current active tools can use SDK strict JSON schema by default, and the only current `strict=False` example is not exposed because it is not decorated.

SDK tool exposure is not controlled by schema strictness. Unimplemented or intentionally unavailable methods should not receive capability decorators and therefore should not enter the active registry, harness `action_space()`, or SDK tool construction.

For active registered capabilities, `replay is not None` is the replay support signal. `ReplayPolicy.kind` selects command emission or dependency recording.

`aliases` and `replay.alias` are duplicate for the primary replayable strict command name. The primary authored command name should come from `replay.alias` for `fsq_command` capabilities.

`runtimeSecret` is not a top-level command alias. It remains a dependency/reference alias used inside parameter values.

Catalog entries for unimplemented actions do not create replay support. Only discovered and registered capabilities participate.

## Verification Expectations

Implementation should update focused tests before broader checks:

- `./.venv/Scripts/python.exe -m pytest tests/test_capabilities.py`
- `./.venv/Scripts/python.exe -m pytest tests/test_fsq_executable_step_adapter.py tests/test_strict_case_recording.py`
- `./.venv/Scripts/python.exe -m pytest tests/test_step_runner.py tests/test_openai_runtime.py tests/test_tools.py`

The final implementation audit should confirm that no recorder path decides replayability from tool names, `fsq_action_name`, or schema strictness, and that existing strict YAML command names still resolve through the active registry.