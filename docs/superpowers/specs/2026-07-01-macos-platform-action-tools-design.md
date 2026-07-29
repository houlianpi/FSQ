# macOS Platform Action Tools Design

Date: 2026-07-01
Status: Draft for user review

## Goal

Add first-party macOS platform action tools to FSQ-Agent while preserving the existing dynamic and strict execution architecture.

macOS support should use the already-reserved FSQ platform id `macos`, expose recordable PlatformTools through the existing capability registry and decorator discovery path, execute dynamic and strict actions through `StepRunner -> HarnessInterface.invoke_action`, and use Appium Mac2 as the first backend implementation. An external Appium Mac2 reference project may guide session mechanics and action behavior only; FSQ-Agent should not wrap or delegate to that reference project at runtime.

## Feasibility

Feasibility is high.

Local evidence supporting this:

- `HarnessPlatform` and FSQ platform models already reserve `macos`.
- Android, Web, and Windows already share the same capability metadata, registry bootstrap, `StepRunner`, harness invocation, evidence recording, dynamic SDK exposure, strict replay, and playground patterns.
- Windows is a close internal template for desktop automation: it has a desktop harness, driver protocol, catalog-backed decorators, `ui_snapshot` evidence, AI assertion injection, and unit tests with fake drivers.
- The Appium MCP reference already demonstrates useful Mac2 operations: session lifecycle through `Mac2Options`, page source retrieval, screenshots, coordinate clicks through `macos: click`, text/key input through `macos: keys`, hover, drag/drop, right click, and page source simplification.

The main work is a platform extension across models, config, core harnesses, entry-layer construction, docs, and tests. It should not require changing the execution core or decorator architecture.

## Scope

In scope for the first macOS platform cycle:

- Add `macos` as a supported configured harness platform, using backend id `appium_mac2`.
- Add macOS capability parameter models, action definitions, replay aliases, and catalog-backed driver declarations.
- Add `MacOSHarness`, `MacOSDriverInterface`, and `AppiumMac2Driver` under the existing `core.harness` ownership model.
- Support dynamic LLM execution, strict FSQ YAML replay, and playground execution for macOS through the same active-platform selection used by Android, Web, and Windows.
- Add macOS evidence capture using `screenshot` and `ui_snapshot` artifacts.
- Add `knowledge/skills/macos-harness.md` and update README/config examples so operators know how to configure Appium Mac2 and use macOS tools.
- Apply the cross-platform configuration ownership rule: stable, shareable platform defaults live in YAML; user-specific, machine-specific, sensitive, or required operator-provided values live in environment variables.
- Add focused unit tests using fake macOS drivers, plus narrow tests for registry bootstrap, config loading/validation, strict FSQ parsing, runner evidence mapping, dynamic runtime construction, CLI/playground dispatch, and docs examples.

## Non-Goals

- Do not rewrite `StepRunner`, `StepSequenceRunner`, `HarnessInterface`, evidence recording, report generation, dynamic recording, or the decorator/registry mechanism.
- Do not expose the external Appium MCP server as FSQ-Agent's runtime tool source.
- Do not add MCP protocol support as part of macOS automation.
- Do not duplicate Appium MCP source code; borrow implementation ideas and action semantics only.
- Do not add iOS support in this cycle.
- Do not add AI action repair, locator self-healing, recovery-mode execution, or testcase mutation.
- Do not require a real Appium server during ordinary unit tests.
- Do not store user-specific app paths, bundle ids, device/session URLs, credentials, or machine-local executable paths in shareable config examples.

## Selected Approach

Use first-party `macos` PlatformTools backed by Appium Mac2.

Dynamic and strict flows remain platform-neutral:

```text
settings.harness.platform = macos
  -> active capability registry = CommonTools + macOS PlatformTools
  -> MacOSHarness
  -> AppiumMac2Driver
  -> Appium Mac2 session and macos:* commands
```

FSQ case/config platform spelling is `macos`. Backend spelling is `appium_mac2`. The driver maps those FSQ names to Appium's native `platformName: Mac` and `automationName: Mac2` internally.

This approach preserves the existing architecture and gives macOS the same dynamic/strict/recording/evidence behavior as the other platforms.

## Approaches Considered

### Approach A: First-Party macOS Platform With Appium Mac2

Add macOS models, catalog entries, harness, driver, config, runtime dispatch, docs, and tests. Reuse `platform_driver_capability`, registry snapshots, `StepRunner`, and active-platform entry construction.

Trade-off: broader SPEC and implementation surface, but it fits the repository architecture and keeps strict replay and dynamic recording metadata-driven.

Decision: selected.

### Approach B: Minimal macOS Subset Only

Implement only lifecycle, click, text input, key press, screenshot, UI snapshot, and AI assertion.

Trade-off: faster first patch, but the reference Mac2 implementation already highlights desktop-specific tools such as hover, right click, and drag/drop that are likely needed for real macOS flows. A minimal slice would require a second SPEC cycle soon after.

Decision: rejected for the proposed first batch, but useful as a fallback if implementation risk needs to be reduced after SPEC review.

### Approach C: Wrap The Reference MCP Server

Call the external Appium MCP server from FSQ-Agent and expose its MCP tools to the agent.

Trade-off: lower direct Appium code, but it violates FSQ-Agent's first-party PlatformTool boundary, bypasses the existing decorator registry, complicates strict replay, and makes evidence/report/recording metadata depend on an external tool server.

Decision: rejected.

## Cross-Platform Configuration Ownership Rule

This design introduces a general configuration rule that applies to all platforms, not only macOS:

- YAML config owns stable, non-sensitive, repo-shareable platform policy and defaults.
- Environment variables own values that the user must actually set, values that differ per machine or developer, secrets, local paths, local server URLs, and runtime target identifiers that should not be committed.

Examples of YAML-owned values:

- Active platform selection, such as `harness.platform: macos`.
- Backend selection, such as `harness.macos.backend: appium_mac2`.
- Stable non-sensitive defaults such as action timeout seconds, page-source simplification limits, screenshot format policy, headless/channel-like policy where applicable, and configured skill lists.
- Output, workspace, cases, and knowledge directory policy.

Examples of environment-owned values:

- Appium server URL when it is supplied by a local operator.
- macOS app bundle id or local app path when the operator must choose the target app.
- Android app id and serial.
- Web browser executable path.
- Windows local app executable path when that path is user/machine-specific.
- Credentials, runtime secrets, tokens, and API keys.

The SPEC update should make this rule explicit in root/config documentation and apply it to new macOS settings from the start. Existing platform behavior should not be silently broken. Where current fields do not follow the rule, such as local desktop app paths in YAML, the SPEC update should either define a compatibility path or record an explicit migration decision.

## Proposed macOS Configuration

First-batch YAML shape:

```yaml
harness:
  platform: macos
  macos:
    backend: appium_mac2
    page_source_max_depth: 12
    action_timeout_seconds: 10
```

Recommended macOS environment variables:

```text
FSQ_MACOS_APPIUM_SERVER_URL=http://127.0.0.1:4723
FSQ_MACOS_BUNDLE_ID=com.example.MacApp
FSQ_MACOS_APP_PATH=/Applications/Example.app
```

Rules:

- `harness.platform` accepts `macos`.
- `harness.macos.backend` accepts `appium_mac2`.
- `FSQ_MACOS_APPIUM_SERVER_URL` supplies the operator's local Appium endpoint. A code default may be allowed only if the SPEC explicitly treats `http://127.0.0.1:4723` as a stable default rather than a required user setting.
- `FSQ_MACOS_BUNDLE_ID` and `FSQ_MACOS_APP_PATH` are mutually useful target selectors. The driver may require one of them for app launch unless the case/action supplies a target app identity.
- Strict FSQ case metadata may continue to use the existing case-level `appId` field as an app-under-test identity, but macOS runtime config should prefer environment-backed target identity when the operator must supply it.
- Sensitive or user-local Appium capabilities must not be committed to YAML examples. If advanced capabilities are needed, the SPEC should define a safe split between YAML-owned stable capability defaults and env-owned local overrides.

## macOS Action Set

The first macOS action surface should be desktop-native and close to the Windows/Web naming style rather than Android gesture naming.

| Alias | Canonical name | Step kind | Evidence | Purpose |
|---|---|---|---|---|
| `launchApp` | `launch_app` | `setup` | yes | Create or reuse a Mac2 session and launch/activate the target app. |
| `killApp` | `kill_app` | `teardown` | no | Terminate or close the target app/session. |
| `clickOn` | `click_on` | `action` | yes | Click a macOS UI element or coordinate resolved from the UI snapshot. |
| `doubleClickOn` | `double_click_on` | `action` | yes | Double-click a macOS UI element. |
| `rightClickOn` | `right_click_on` | `action` | yes | Context-click a macOS UI element or coordinate. |
| `typeText` | `type_text` | `action` | yes | Type text into the focused or targeted control. |
| `pressKey` | `press_key` | `action` | yes | Send keyboard keys or shortcuts through Mac2. |
| `hoverOn` | `hover_on` | `action` | no | Move the pointer over a target. |
| `dragTo` | `drag_to` | `action` | yes | Drag from one target/point to another target/point. |
| `takeScreenshot` | `take_screenshot` | `observation` | no | Capture a screenshot artifact on demand. |
| `uiSnapshot` | `ui_snapshot` | `observation` | no | Return a simplified macOS page source/control-tree snapshot. |
| `assertVisible` | `assert_visible` | `assertion` | no | Assert a macOS UI target is present and visible. |
| `assertElementsOrder` | `assert_elements_order` | `assertion` | no | Assert that a list of macOS UI elements appears in the expected vertical or horizontal order. |
| `assertWithAI` | `assert_with_ai` | `assertion` | no | Evaluate an explicit visual assertion through the configured AI evaluator. |

This table intentionally avoids Android aliases such as `tapOn` and `inputText` as the primary macOS API. Desktop platforms should use `clickOn` and `typeText`, matching Windows and Web conventions.

Future macOS cycles may add window management, menu-bar helpers, clipboard helpers, file picker support, multi-window focus, and richer keyboard shortcut modeling after the first backend is stable.

### Reference MCP Tool Scope Classification

The reference Appium MCP project mixes macOS-specific tools, generic Appium tools, mobile-oriented tools, and runtime/session helpers. The SPEC update should preserve that distinction instead of treating every MCP tool as a candidate macOS PlatformTool.

#### Implemented This Cycle, But Not As Standalone macOS PlatformTools

These MCP capabilities are in scope functionally, but FSQ should expose them through existing cross-platform layers, runtime services, or more semantic first-batch actions rather than one-to-one macOS PlatformTool aliases.

| Reference MCP tool | First-batch FSQ treatment | Layer / exposed surface |
|---|---|---|
| `session_close` | Implement as harness/driver cleanup when runs finish, when `killApp` closes the app/session, or when the runtime tears down a failed session. | Harness/driver lifecycle plumbing, not user-authored FSQ. |
| `time_sleep` | Use inherited CommonTool `waitMs`; do not add a macOS-specific wait. | CommonTool. |
| `tap_coordinates_macos` / mac branch of `tap_coordinates` | Support explicit point coordinates inside `clickOn`, without adding a separate public alias. | macOS `clickOn` parameter/driver implementation. |
| `directly_send_keys` | Support focused text/key input through `typeText` or `pressKey`, depending on payload shape. | macOS `typeText` / `pressKey` implementation. |
| `find_element` | Express as `assertVisible` for checks or `uiSnapshot` for observation; do not add a generic diagnostic command. | macOS assertion/observation actions. |

The reference tools already covered as first-batch macOS PlatformTools are `app_launch`, `app_close`, `click_element`/`click_element_macos`, `send_keys`/`send_keys_on_macos`, `press_key`, `right_click_element`, `double_click_element`, `drag_element_to_element`, `mouse_hover`, `verify_elements_order`, `get_page_source_tree`, `verify_visual_task`, and `take_screenshot`.

#### MCP Tools That Are Not macOS Methods

These MCP tools exist in the reference project, but they are generic or mobile-oriented Appium helpers rather than macOS-specific methods. They should not be interpreted as macOS PlatformTool requirements for this design.

| Reference MCP tool | Classification | Treatment |
|---|---|---|
| generic `tap_coordinates` outside the macOS branch | Generic/mobile Appium coordinate tap helper. | Only the macOS-specific coordinate click behavior is considered, and it is folded into `clickOn`. |
| `swipe` | Mobile-style gesture helper. | Not a macOS first-batch method; macOS scrolling/gesture semantics need separate design. |
| `pinch_zoom` | Mobile/trackpad-like gesture helper exposed generically by the MCP project. | Not a macOS first-batch method. |
| `hide_keyboard` | Mobile keyboard helper. | Not applicable to normal macOS desktop automation. |
| `switch_element_to_on` / `switch_element_to_off` | Generic convenience helper for toggle-like controls. | Not treated as a macOS method; first batch uses `clickOn` plus assertions when needed. |

#### macOS MCP Methods Deferred From This Cycle

These are useful macOS-facing capabilities from the reference project, but they are not part of the first implementation batch. They should remain explicit future candidates rather than hidden inside this scope.

| Reference MCP tool | Deferred capability | Reason |
|---|---|---|
| `scroll_to_element` | macOS scroll-to-target action. | Needs a typed macOS scroll/container model and accessibility snapshot semantics rather than a direct MCP payload copy. |
| `app_state` | macOS app/session state diagnostic. | Useful for diagnostics, but first batch focuses on recordable user actions, observations, and assertions; safe session metadata can be exposed through runtime context first. |

## macOS Parameter Models

Shared serializable models belong in `fsq_agent.models`, following the existing Android/Web/Windows pattern.

Suggested first-batch models:

- `MacOSLocator`: optional accessibility id, name, label, value, role/control type, class name, xpath, predicate string, and coordinates. At least one locator field is required when no semantic `target` is supplied.
- `MacOSPoint`: `x` and `y` integer coordinates for coordinate-backed Mac2 commands.
- `MacOSLaunchAppParams`: optional `bundle_id`, `app_path`, `arguments`, and `environment`, with runtime defaults coming from environment settings.
- `MacOSKillAppParams`: optional `bundle_id` or session behavior.
- `MacOSClickOnParams`, `MacOSDoubleClickOnParams`, `MacOSRightClickOnParams`, and `MacOSHoverOnParams`: semantic `target` or `locator` or point, plus optional duration/modifier metadata where Mac2 supports it.
- `MacOSTypeTextParams`: required `text`, optional `target` or `locator`, optional clear-first behavior if supported safely.
- `MacOSPressKeyParams`: required key or key sequence, optional modifier list.
- `MacOSDragToParams`: required source and destination target/locator/point values, optional duration.
- `MacOSTakeScreenshotParams`: optional full-screen/window metadata. ArtifactStore owns paths.
- `MacOSUiSnapshotParams`: optional max depth and simplification flags.
- `MacOSAssertVisibleParams`: target/locator plus optional assertion metadata.
- `MacOSAssertElementsOrderParams`: required ordered `elements` list containing semantic targets or `MacOSLocator` values, optional `expected_order` list of zero-based indices, `direction` constrained to `vertical` or `horizontal`, optional pixel `tolerance`, and optional `require_all` defaulting to true.
- `MacOSAssertWithAIParams`: required prompt plus optional assertion metadata.

Models should forbid unexpected fields, validate mutually exclusive locator forms, and serialize with `model_dump(mode="json", exclude_none=True)`. Runtime-only metadata such as evidence policy, source refs, timeouts, replay provenance, and redaction state stays on `ExecutableStep` and capability metadata.

### `assertElementsOrder` Implementation Notes

The MCP `verify_elements_order` implementation should be the behavioral reference for the first-batch order assertion, but FSQ should expose a typed assertion rather than the raw MCP XPath-only payload.

Target FSQ shape:

```yaml
- assertElementsOrder:
    direction: vertical
    elements:
      - target: First row title
        locator:
          xpath: //XCUIElementTypeStaticText[@label="Alpha"]
      - target: Second row title
        locator:
          xpath: //XCUIElementTypeStaticText[@label="Beta"]
```

Implementation behavior:

- Resolve each element through the same macOS locator pipeline used by `clickOn` and `assertVisible`; XPath is supported, but not required.
- Read each resolved element's `location` and `size` from Appium.
- Compare element center positions on the selected axis: `y + height / 2` for `vertical`, `x + width / 2` for `horizontal`.
- Use source list order as the default expected order, or use `expected_order` when supplied.
- Return a passed assertion when actual sorted element indices match the expected order within the optional tolerance.
- Return a failed assertion, not a configuration error, when elements are found but the order is wrong.
- Return a target resolution failure when required elements cannot be found and `require_all` is true.
- Return structured output with `direction`, `elements_found`, `elements_total`, `actual_order`, `expected_order`, and per-element positions so reports can explain failures without relying on raw page source.

## Harness And Driver Design

Add a macOS harness slice under `fsq_agent.core.harness`:

- `MacOSDriverInterface`: protocol for typed macOS backend methods and observation helpers.
- `MacOSHarness`: runner-facing `HarnessInterface` implementation.
- `AppiumMac2Driver`: concrete Appium Python client backend.
- `_macos_driver_tool`: catalog-backed decorator helper built from the existing `platform_driver_capability` pattern.
- `macos_capability_definitions()`: default capability discovery that does not connect to Appium.

`MacOSHarness` responsibilities:

- Return `HarnessContext(platform="macos", session_id=..., current_url=None, screen_size=..., metadata=...)`.
- Expose `action_space()` from decorated Mac2 driver capabilities and injected AI assertion availability.
- Validate params through the discovered capability parameter model before invoking driver methods.
- Route `assert_with_ai` through the backend-owned AI assertion support, consistent with current backend PlatformTool ownership.
- Capture `screenshot` and `ui_snapshot` artifacts through `ArtifactStore`.
- Classify Appium connection/session/element/timeout errors into existing failure categories.

`AppiumMac2Driver` responsibilities:

- Lazy import Appium/Selenium packages so registry discovery and strict parsing do not require a live Appium install or server.
- Build Mac2 options from stable YAML settings plus environment-backed local target values.
- Create, reuse, and quit Mac2 sessions safely.
- Resolve targets using a stable priority order: explicit locator, Appium element lookup, simplified page-source match, semantic target fallback, and coordinate fallback when explicitly supplied.
- Implement desktop actions using Appium APIs and Mac2 mobile commands where appropriate, including `macos: click`, `macos: keys`, hover, drag/drop, and screenshot/page source calls.
- Implement `assert_elements_order` by resolving each target, reading Appium element geometry, sorting on the requested axis, and returning structured assertion details.
- Return normalized dictionaries that harnesses convert into `HarnessActionResult` values with status, failure category, error message, output, metadata, and artifact refs.

## Reference Implementation Use

The Appium MCP reference should influence implementation choices in these specific ways:

- Use `Mac2Options` and the same Appium Mac2 capability concepts for session creation.
- Follow the reference's practical use of Mac2 execute-script extensions for coordinate click, keyboard input, hover, and drag/drop when the standard WebDriver action path is insufficient.
- Borrow page-source simplification ideas so `uiSnapshot` returns bounded, useful text/JSON instead of unbounded raw XML.
- Borrow target filtering heuristics for avoiding invisible/unhelpful elements, while expressing them through FSQ's typed locator and result contracts.
- Borrow the `verify_elements_order` geometry algorithm, while replacing the MCP XPath-only input with typed FSQ locators and returning assertion-oriented result metadata.
- Borrow lifecycle cleanup patterns such as graceful session quit and app termination, without importing MCP server lifecycle or protocol code.

The implementation should not copy MCP tool names blindly, expose MCP-specific payload shapes, or make the MCP server a dependency.

## Capability Registry And FSQ Parsing

The package capability bootstrap should add macOS support by registering CommonTool capabilities plus macOS PlatformTools only when the selected platform is `macos`.

Expected behavior:

- `build_capability_registry(platform="macos")` includes `wait_ms`, `get_runtime_secret`, and macOS PlatformTools.
- Android/Web/Windows registries do not include macOS aliases.
- `FsqExecutableStepAdapter` remains platform-agnostic and consumes only the active registry snapshot.
- macOS strict cases resolve aliases such as `launchApp`, `clickOn`, `typeText`, `pressKey`, `uiSnapshot`, `assertElementsOrder`, and `assertWithAI` through the macOS registry snapshot.
- Dynamic recording uses replay metadata, not platform-specific name checks, to generate strict YAML commands.

The `fsq` module SPEC should gain a macOS command block similar to the Android/Web blocks. The payload shapes should match the macOS parameter models and preserve runtime-secret refs only where text fields allow them.

## Evidence And Artifacts

macOS should follow the desktop evidence pattern:

- Standard action evidence for capture-enabled macOS PlatformTools is `screenshot` plus `ui_snapshot`.
- Observation actions such as `uiSnapshot` and `takeScreenshot` return explicit artifacts but should not trigger redundant standard capture unless capability metadata says so.
- `StepRunner._standard_capture_evidence_policy()` should map `macos` to `ui_snapshot`, matching Windows rather than falling back to Android `ui_tree`.
- Artifacts should be written through `ArtifactStore` and referenced in manifests/reports using existing evidence contracts.

The SPEC update should verify that `EvidenceArtifactKind` already supports `ui_snapshot` for macOS usage. If additional artifact metadata is needed for Appium page source, it should be added to existing evidence models rather than introducing platform-specific manifest formats.

## Dynamic Runtime

`OpenAIAgentsRuntime` should build the active macOS harness from `settings.harness.platform == "macos"`:

```text
OpenAIAgentsRuntime
  -> AppiumMac2Driver(settings.harness.macos + env values)
  -> MacOSHarness(driver, ArtifactStore(run_dir), optional AI evaluator, runtime secrets)
  -> StepRunner with active macOS registry
```

Startup metadata should include safe fields only, such as platform, backend, Appium server configured state, bundle id presence, app path presence, timeout seconds, driver class, and skill names. It must not log local secrets or full sensitive environment values.

Dynamic SDK tool exposure remains registry/harness-driven. The runtime should not inspect Appium APIs, MCP reference code, or decorator marker attributes directly.

## Strict CLI Execution

Strict CLI execution should add macOS to the same platform dispatch path used by Android/Web/Windows:

- Validate active platform settings before external UI actions begin.
- Build the active registry with `platform="macos"`.
- Parse strict FSQ cases through `FsqExecutableStepAdapter(registry_snapshot)`.
- Resolve runtime-secret refs in memory before final parameter validation.
- Construct `MacOSHarness` and `AppiumMac2Driver` without changing strict replay semantics.
- Execute through `StepSequenceRunner` and `StepRunner` with configured post-action delay settings.
- Inject an AI assertion evaluator only when the strict case explicitly contains `assertWithAI`.

Strict mode must not add locator fallback, AI repair, recovery, testcase mutation, or implicit lifecycle commands.

## Playground Execution

The playground should expose macOS as another active platform, not as a separate server.

Required behavior:

- `/runtime-info` reports `platformId: macos`, backend id, Appium server configured state, bundle id/app path presence, busy state, and last-run summary.
- Android session/setup endpoints return structured unavailable responses when macOS is active.
- Dynamic execution uses `FsqAgent.from_settings` with macOS settings and skills.
- Strict execution uses the same platform-dispatching strict harness builder as CLI.
- `/screenshot`, replay frames, replay video, and report lookup work through existing artifact and preview paths.
- Preview should return a structured unavailable response before a Mac2 session exists or after it is closed.

## macOS Harness Skill And Docs

Add `knowledge/skills/macos-harness.md` with concise model-facing guidance:

- Use when `harness.platform` is `macos`.
- Prefer desktop aliases: `click_on`, `double_click_on`, `right_click_on`, `type_text`, `press_key`, `hover_on`, `drag_to`, `ui_snapshot`, `take_screenshot`, `assert_visible`, `assert_elements_order`, `assert_with_ai`, and `wait_ms`.
- Prefer semantic targets and stable accessibility locators before coordinate actions.
- Use coordinate actions only when the UI snapshot cannot identify a stable element and the coordinate is explicit and current.
- Use assertions for required verify/check/ensure language; observations alone are not verdicts. For order/layout requirements, use `assert_elements_order` instead of narrating over `ui_snapshot` output.
- Rebuild invalid payloads from the active tool schema and inspect a fresh `ui_snapshot` after target misses.
- Use `assert_with_ai` only for explicit visual assertions and treat its verdict metadata, not screenshot existence, as assertion evidence.
- Never ask for or echo secrets; use `get_runtime_secret` only for configured allowed environment names.

Update README and config examples to show:

- Required macOS setup: Appium server, Mac2 driver, macOS accessibility permissions, target app setup, and environment variables.
- Example `harness.platform: macos` YAML using only stable defaults.
- Example env variable names for local values.
- A small strict `.codex.yaml` macOS case using `platform: macos` and desktop aliases.

## Python Architecture Level And Module Ownership

This is a Level 3 layered application change overall because it crosses entry orchestration, runtime construction, core harnesses, shared models, config, docs, and tests. Individual packages should stay at their current architecture levels:

- `models`: Level 1/2 shared serializable contracts. Owns macOS params, action definitions, settings contracts, and platform literals.
- `capabilities`: declaration/discovery only. Reuses existing decorators and must not import core or Appium.
- `core`: harness/driver/runtime execution contracts. Owns macOS harness, driver protocol, Appium driver, default capability discovery, artifact capture, and runner evidence mapping.
- `config`: settings loading, env application, path resolution, and runtime validation.
- `agent`: dynamic runtime construction and SDK exposure from active capability schemas.
- `cli`: strict and dynamic entry dispatch, strict replay secret resolution, provider-backed AI assertion injection, and output rendering.
- `fsq`: deterministic YAML parsing against the supplied registry snapshot only.
- `playground`: local API dispatch and active-platform preview/execution adapters.
- `knowledge` and README/docs: operator and model-facing guidance.

No new architecture layer, service locator, plugin framework, or MCP adapter is justified for this scope.

## Affected Root And Module SPEC Files

Expected SPEC updates during the next `spec-driven` phase:

- Root `SPEC.md`: add macOS platform support, cross-platform config ownership rule, Appium Mac2 as first macOS backend, docs/skill requirements, and platform extension expectations.
- `fsq_agent/models/SPEC.md`: add macOS settings, locators, params, action definitions, exports, and platform-specific command/action contracts.
- `fsq_agent/config/SPEC.md`: add macOS YAML/env loading and validation, plus the general YAML/env ownership rule.
- `fsq_agent/capabilities/SPEC.md`: confirm macOS reuses existing decorator/catalog mechanisms and introduces no platform-specific declaration semantics.
- `fsq_agent/core/SPEC.md`: add MacOSHarness, MacOSDriverInterface, AppiumMac2Driver, default capability definitions, artifact capture, evidence mapping, and error classification.
- `fsq_agent/agent/SPEC.md`: add macOS dynamic runtime construction and safe startup metadata.
- `fsq_agent/cli/SPEC.md`: add macOS strict construction, validation, and AI assertion injection rules.
- `fsq_agent/fsq/SPEC.md`: add macOS strict command block and platform alias rules.
- `fsq_agent/playground/SPEC.md`: add macOS runtime-info, endpoint availability, preview, and execution rules.
- `fsq_agent/report/SPEC.md`: update only if report terminology or artifact rendering needs macOS-specific wording.

## Verification Expectations

Focused verification after implementation should include:

- Unit tests for macOS parameter model validation and alias/action definition metadata.
- Unit tests for `build_capability_registry(platform="macos")`, including absence from other platform registries.
- Unit tests for `MacOSHarness` using a fake driver, mirroring Windows harness tests.
- Unit tests for Appium Mac2 driver lifecycle command construction using fakes/mocks, without requiring a live Appium server.
- Unit tests for `assert_elements_order` covering vertical order, horizontal order, explicit `expected_order`, missing required elements, invalid direction, and order mismatch failures.
- Unit tests for config loading and validation, including YAML/env ownership and env application.
- Unit tests for strict FSQ adapter resolving macOS aliases from the macOS registry.
- Unit tests for `StepRunner` evidence policy mapping `macos` to `ui_snapshot`.
- CLI/playground construction tests that select macOS without requiring Android/Web/Windows dependencies.
- Documentation/example validation where practical.

Candidate commands:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_config.py tests/test_fsq_executable_step_adapter.py tests/test_step_runner.py
.\.venv\Scripts\python.exe -m pytest tests/test_windows_harness.py tests/test_playground.py
```

The implementation should add dedicated macOS tests and include them in the focused verification command once file names exist.

## Resolved Questions

- Platform id: use `macos` in FSQ config and cases.
- Backend id: use `appium_mac2` in FSQ settings and capability metadata.
- Appium native mapping: translate internally to `platformName: Mac` and `automationName: Mac2`.
- Reference project role: use an external Appium Mac2 reference project as an implementation reference, not as a runtime dependency.
- Configuration boundary: YAML is for stable/shareable platform defaults; environment variables are for values users must actually set, user-local paths, machine-specific endpoints, target identifiers, and secrets.

## User Review Gate

Review this design before invoking `spec-driven`. After confirmation, the next SDD step is to update the relevant SPEC files from this design, confirm those SPEC updates, then implement and verify.