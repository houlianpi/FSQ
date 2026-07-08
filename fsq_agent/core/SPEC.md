# Module: core

## Purpose

Define the shared execution-core orchestration layer for FSQ-Agent. The core module owns `StepRunner` as the single execution manager for canonical CommonTool and PlatformTool invocations, runner-owned post-action delay resolution/application, `StepSequenceRunner` ordering, harness and driver protocols, platform CommonTool providers, backend driver capability exposure, and evidence-recording coordination points used by strict replay and dynamic execution.

The module does not parse CLI arguments, parse FSQ YAML, construct provider sessions, construct OpenAI Agents SDK tools, own dynamic-only AgentTools, or generate reports. Entry modules build settings, providers, registries, concrete harnesses, platform CommonTool providers, and backend drivers, then pass registry snapshots and harnesses into core.

## Dependencies

- Internal project dependencies: `models` and `capabilities` only.
- External dependencies: standard library typing/time/path modules and optional platform backend imports only inside concrete backend modules with lazy import behavior.
- Forbidden dependencies: `agent`, `providers`, `tools`, `cli`, `fsq`, `report`, `observation`, `knowledge`, `skills`, and OpenAI Agents SDK runtime types.

Core may consume `CapabilityDefinition`, `CapabilityInvocation`, `CapabilityExecutionResult`, `ReplayPolicy`, `ExecutableStep`, `EvidencePolicy`, runner result/event models, harness result/context models, CommonTool parameter/result models, active platform parameter models, AI assertion models, runtime secret settings, and project exceptions from `models`.
Core may consume shared declaration decorators, platform action catalog helpers, and side-effect-free capability discovery helpers from `capabilities`. Core must not place execution behavior in `capabilities` or import AgentTool implementations from `tools`.

## Public Interface

Target `__init__.py` exports via `__all__`:

- `CapabilityRegistry`: Validated runtime registry for decorated capabilities. It resolves canonical names and `ReplayPolicy(kind="fsq_command").alias` values, rejects duplicate names and ambiguous replay aliases, exposes serializable snapshots, and validates that every capability has a parameter model/schema and executor binding.
- `HarnessInterface`: Protocol describing platform capabilities required by StepRunner. Concrete Android, Web, iOS, and fake harnesses may satisfy the protocol structurally.
- `StepRunner`: Executes one canonical `ExecutableStep` or capability invocation by looking up metadata in `CapabilityRegistry`, validating params with the declared model, applying evidence, post-action delay, and sensitivity policy, invoking the active `HarnessInterface`, normalizing backend/provider output, emitting structured safe events, and returning `RunnerStepResult`.
- `StepSequenceRunner`: Executes ordered `ExecutableStep` records with `StepRunner`, records events and step results, stops normal execution on blocking failures, and always executes supplied teardown steps. It does not own configured sleep or pacing behavior; post-action stabilization is handled inside `StepRunner`.
- `EvidenceRecorder`: Event/result sink that builds an `EvidenceBundle` and writes a JSON manifest for execution facts and artifact references.
- `ArtifactStore`: Evidence artifact path policy and writer for run-local screenshots, UI trees, harness-call JSON, logs, and raw files.
- `AIAssertionEvaluatorProtocol`: Structural protocol for provider-backed visual assertion evaluation. It accepts serializable `AIAssertionRequest` values and returns `AIAssertionResult` values without exposing provider runtime objects to `core`.
- `AndroidDriverInterface`: Protocol describing typed Android backend driver methods that Android driver capabilities may call.
- `CommonPlatformTools`: Instantiable CommonTool provider bound to the active platform for schema generation and common tool invocation. Backend-specific PlatformTool bodies are exposed by concrete drivers.
- `AndroidHarness`: Built-in Android runner-facing harness that satisfies `HarnessInterface`, exposes inherited CommonTools plus decorated Android backend driver capabilities, injects AI assertion runtime services into compatible drivers, and owns Android runtime services such as context, artifact capture, driver access, lifecycle hooks, and error classification.
- `UiAutomator2AndroidDriver`: Optional Android backend driver that satisfies `AndroidDriverInterface` using uiautomator2 when the `android` extra is installed.
- `WebDriverInterface`: Protocol describing typed Web backend driver methods that Web driver capabilities may call.
- `WebHarness`: Built-in Web runner-facing harness that satisfies `HarnessInterface`, exposes inherited CommonTools plus decorated Web backend driver capabilities, injects AI assertion runtime services into compatible drivers, and owns Web runtime services such as context, artifact capture, driver access, lifecycle hooks, and error classification.
- `PlaywrightWebDriver`: Optional Web backend driver that satisfies `WebDriverInterface` using Playwright sync APIs when the `web` extra is installed and a configured local browser executable path is available for the selected Web channel. Construction must record configuration without importing Playwright or launching a browser unless a caller injects an already-active fake/test page.
- `WindowsDriverInterface`: Protocol describing typed Windows desktop backend driver methods that Windows driver capabilities may call.
- `WindowsHarness`: Built-in Windows runner-facing harness that satisfies `HarnessInterface`, exposes inherited CommonTools plus decorated Windows backend driver capabilities, injects AI assertion runtime services into compatible drivers, and owns Windows runtime services such as context, artifact capture, driver access, lifecycle hooks, and error classification.
- `PywinautoWindowsDriver`: Optional Windows backend driver that satisfies `WindowsDriverInterface` using pywinauto when the `windows` extra is installed and a configured local application executable path is available.
- `MacOSDriverInterface`: Protocol describing typed macOS desktop backend driver methods that macOS driver capabilities may call.
- `MacOSHarness`: Built-in macOS runner-facing harness that satisfies `HarnessInterface`, exposes inherited CommonTools plus decorated macOS backend driver capabilities, injects AI assertion runtime services into compatible drivers, and owns macOS runtime services such as context, artifact capture, driver access, lifecycle hooks, and Appium error classification.
- `AppiumMac2Driver`: Optional macOS backend driver that satisfies `MacOSDriverInterface` using Appium Mac2 when the `macos` extra is installed and configured environment-backed Appium/target values are available.
- `driver_tool` compatibility helper and catalog-backed platform driver declaration helpers: Decorate concrete backend methods with capability metadata using the shared `capabilities` declaration layer; they do not execute or register capabilities by themselves. Android-specific behavior is represented by Android action catalog entries rather than a unique decorator implementation.

Planned subpackage exports:

- `fsq_agent.core.registry`: `CapabilityRegistry`, registry validation, alias resolution, and registry snapshots.
- `fsq_agent.core.runner`: `StepRunner`, executor binding protocols, and sequence runner orchestration.
- `fsq_agent.core.harness`: `HarnessInterface`, `AIAssertionEvaluatorProtocol`, CommonTool mixin/provider contracts, active platform tool providers, active platform harness and driver contracts, shared AI assertion backend support, concrete backend implementations, and thin platform declaration helpers backed by `capabilities`.
- `fsq_agent.core.evidence`: `EvidenceRecorder`, `ArtifactStore`, and evidence coordination logic.

`StepRunner` exposes a narrow API:

```python
runner = StepRunner(
	registry=registry,
	harness=harness,
	post_action_delay_seconds=settings.execution.post_action_delay_seconds,
)
result = runner.run_step(run_id="run-1", step=executable_step)
events = runner.events
```

`ExecutableStep.action_name` stores the canonical capability name, such as `wait_ms`, `get_runtime_secret`, `tap_on`, `input_text`, or `assert_with_ai`. Authored names such as `waitMs`, `tapOn`, and `assertWithAI` are preserved in step metadata by parsers and adapters.

For each invocation, `StepRunner` must:

1. Resolve the canonical capability from the registry.
2. Validate params with `capability.params_model`.
3. Build safe invocation context containing run id, step id, source ref, authored action metadata, and capability metadata.
4. Derive the effective evidence policy from capability metadata and any explicit step policy. For PlatformTools with `CapabilityDefinition.capture_evidence=True` and the default `EvidencePolicy()`, the effective policy must capture `screenshot` plus the active platform observation artifact before the action, after the action, and on failure. Android captures `ui_tree`; Web captures `page_snapshot`; Windows and macOS capture `ui_snapshot`. A non-default `ExecutableStep.evidence_policy` is explicit and must not be overwritten by capability metadata.
5. Resolve the effective post-action delay from `CapabilityDefinition.post_action_delay_seconds` when it is not `None`; otherwise use configured `execution.post_action_delay_seconds.common` for CommonTools and `execution.post_action_delay_seconds.platform` for PlatformTools.
6. Route CommonTool and PlatformTool capabilities through `HarnessInterface.invoke_action(step, context)`. The harness executes inherited CommonTools through the active platform tool provider and delegates driver-backed PlatformTools to the concrete driver/backend. AI assertion tools are driver-backed PlatformTools that may use harness-injected evaluator and artifact services through shared backend support.
7. Normalize backend output into the shared runner result contract.
8. Apply a positive post-action delay after invoke completion or structured invoke failure conversion and before finalize begins. For PlatformTools this means before `after_action`, `capture_after`, and `capture_on_failure`; for CommonTools this means before the common finalize phase. Zero delay must not call `time.sleep(0)`.
9. Apply sensitivity rules before persistence.
10. Emit structured events containing safe capability metadata, replay payload fields, artifact refs, post-action delay metadata, and status.
11. Return `RunnerStepResult`.

For replayable PlatformTools, `StepRunner` must include capability-derived `safe_replay_params` in invoke metadata and `last_capability_execution_result` when safe replay params differ from raw tool arguments. Android `tap_at` and point-based `swipe` must record invocation coordinates plus the current `HarnessContext.screen_size` as `reference_screen_size` when a reference is not already supplied, so dynamic recording can produce strict YAML that replays proportionally on a different device resolution.

`StepRunner` must not contain action-name branches for `waitMs`, `wait_ms`, `get_runtime_secret`, platform action names, or evidence-enabled platform mutations. A pure wait is an inherited CommonTool capability. Runtime secret lookup is a sensitive inherited CommonTool capability.

`StepSequenceRunner` exposes a narrow API:

```python
runner = StepSequenceRunner(step_runner=runner, evidence_recorder=recorder)
bundle = runner.run_steps(run_id="run-1", steps=steps, teardown_steps=teardown_steps)
```

It must not import `fsq`, parse YAML, construct platform drivers, resolve strict replay refs, generate reports, sleep between steps for configured pacing, or add synthetic `waitMs` steps for pacing.

`HarnessInterface` provides runner-facing behavior for context, artifact capture, and CommonTool/PlatformTool invocation. `invoke_action` is the long-term stable gateway from `StepRunner` to active platform behavior. Platform harnesses are FSQ-controlled runtime gateways; platform tool providers own inherited CommonTool bodies; concrete drivers own backend PlatformTool bodies, including `assert_with_ai`; harnesses provide invocation context and artifact/evaluator services when a backend tool needs them. Harnesses and drivers do not decide runner ordering, retry policy, event emission, evidence manifest structure, artifact directory policy, case aggregation, or report generation.

### Android Platform Block

Android LLM-exposed capabilities in this SPEC cycle include inherited CommonTools `wait_ms` and `get_runtime_secret` plus driver-backed PlatformTools `launch_app`, `kill_app`, `tap_on`, `tap_at`, `long_press_on`, `input_text`, `press_key`, `swipe`, `assert_visible`, `assert_not_visible`, `assert_state`, `ui_tree`, and `assert_with_ai`. Authored FSQ aliases include `waitMs`, `runtimeSecret` references, `launchApp`, `killApp`, `tapOn`, `tapAt`, `longPressOn`, `inputText`, `pressKey`, `swipe`, `assertVisible`, `assertNotVisible`, `assert`, `uiTree`, and `assertWithAI`. The Android action catalog may describe `perform_actions` / `performActions`, but an unimplemented uiautomator2 backend method must not be decorated as a capability and must not appear in platform `action_space()` or SDK exposure.

Android owns `AndroidHarness`, `AndroidDriverInterface`, `UiAutomator2AndroidDriver`, Android catalog-backed platform declarations, and Android default capability definitions. `UiAutomator2AndroidDriver.assert_with_ai` is a decorated backend tool that calls shared AI assertion support. Android artifact capture supports `screenshot` and `ui_tree`.

`UiAutomator2AndroidDriver.tap_at` and point-based `swipe` accept absolute Android screen coordinates for the current invocation. When params include `reference_screen_size`, the driver must scale supplied points from that reference width/height to the current device screen width/height, clamp computed coordinates inside the current screen bounds, and execute the scaled coordinate action. This scaling exists for generated strict replay artifacts; dynamic agents should still prefer locator-based actions for normal UI elements.

### Web Platform Block

Web LLM-exposed Playwright capabilities in this SPEC cycle are inspired by Playwright MCP core automation and include inherited CommonTools `wait_ms` and `get_runtime_secret` plus driver-backed PlatformTools `start_browser`, `close_browser`, `navigate_to`, `navigate_back`, `click_on`, `type_text`, `select_option`, `hover_on`, `press_key`, `wait_for`, `take_screenshot`, `page_snapshot`, `assert_visible`, `assert_not_visible`, `assert_text`, and `assert_with_ai`. Authored FSQ aliases include `waitMs`, `runtimeSecret` references, `startBrowser`, `closeBrowser`, `navigateTo`, `navigateBack`, `clickOn`, `typeText`, `selectOption`, `hoverOn`, `pressKey`, `waitFor`, `takeScreenshot`, `pageSnapshot`, `assertVisible`, `assertNotVisible`, `assertText`, and `assertWithAI`. Web observation uses `page_snapshot`/`pageSnapshot` and must not reuse Android `ui_tree`/`uiTree` naming. Unsafe JavaScript/evaluate, generated Playwright test code, network/storage/devtools, tabs, drag/drop, file upload, PDF, and coordinate/vision capabilities are out of first-batch scope unless a later SPEC adds opt-in capability groups.

Web browser lifecycle is explicit. `start_browser` is a setup-kind driver capability that starts or reuses the configured browser/page and returns success when already started. `close_browser` is a teardown-kind driver capability that closes owned Playwright state, returns success when already closed, and leaves the driver reusable for a later `start_browser` in the same task. Lifecycle capabilities must not rely on default screenshot plus page-snapshot evidence capture because there may be no page before startup or after shutdown.

Web page-dependent capabilities such as `navigate_to`, `navigate_back`, clicks, typing, waits, screenshots, page snapshots, and deterministic assertions require an active page. If invoked before `start_browser`, the Web driver must return a structured failure with a clear startup-required message instead of launching implicitly. `WebHarness.get_context()` must tolerate the not-started state and return safe metadata such as `browser_started: false` so `StepRunner` prepare can run before browser startup.

Web owns `WebHarness`, `WebDriverInterface`, `PlaywrightWebDriver`, Web catalog-backed platform declarations, and Web default capability definitions. `PlaywrightWebDriver.assert_with_ai` is a decorated backend tool that calls shared AI assertion support. Web artifact capture supports `screenshot` and `page_snapshot` when a page is active. Playwright import and configured channel/executable launch are explicit `start_browser` runtime/backend concerns, not driver-construction or registry-bootstrap concerns. `PlaywrightWebDriver.close()` remains a final resource cleanup hook and must use the same close implementation without turning cleanup into a task-visible `closeBrowser` event.

### Windows Platform Block

Windows LLM-exposed pywinauto capabilities in this SPEC cycle include inherited CommonTools `wait_ms` and `get_runtime_secret` plus driver-backed PlatformTools `launch_app`, `kill_app`, `click_on`, `double_click_on`, `right_click_on`, `type_text`, `press_key`, `assert_visible`, `ui_snapshot`, and `assert_with_ai`. Authored FSQ aliases include `waitMs`, `runtimeSecret` references, `launchApp`, `killApp`, `clickOn`, `doubleClickOn`, `rightClickOn`, `typeText`, `pressKey`, `assertVisible`, `uiSnapshot`, and `assertWithAI`. Windows observation uses `ui_snapshot`/`uiSnapshot` and must not reuse Android `ui_tree`/`uiTree` or Web `page_snapshot`/`pageSnapshot` naming. Windows element resolution uses a control locator built from `title`, `control_type`, `automation_id`, `class_name`, `index`, and optional parent fields.

Windows owns `WindowsHarness`, `WindowsDriverInterface`, `PywinautoWindowsDriver`, Windows catalog-backed platform declarations, and Windows default capability definitions. `PywinautoWindowsDriver.assert_with_ai` is a decorated backend tool that calls shared AI assertion support. Windows artifact capture supports `screenshot` and `ui_snapshot`. pywinauto import and application launch are lazy runtime/backend concerns, not registry-bootstrap concerns. Normalized Windows runtime settings supply the local app path, pywinauto backend kind, optional window title regex, and configured launch arguments; `backend_kind` selects pywinauto's UI automation mode (`uia` or `win32`) and is not a second FSQ Windows backend. An optional configured window title regex resolves the launched application main window by title instead of the process top window, and configured launch arguments are prepended before per-step `launchApp.extra_args`.

### macOS Platform Block

macOS LLM-exposed Appium Mac2 capabilities in this SPEC cycle include inherited CommonTools `wait_ms` and `get_runtime_secret` plus driver-backed PlatformTools `launch_app`, `kill_app`, `click_on`, `double_click_on`, `right_click_on`, `type_text`, `press_key`, `hover_on`, `drag_to`, `take_screenshot`, `ui_snapshot`, `assert_visible`, `assert_elements_order`, and `assert_with_ai`. Authored FSQ aliases include `waitMs`, `runtimeSecret` references, `launchApp`, `killApp`, `clickOn`, `doubleClickOn`, `rightClickOn`, `typeText`, `pressKey`, `hoverOn`, `dragTo`, `takeScreenshot`, `uiSnapshot`, `assertVisible`, `assertElementsOrder`, and `assertWithAI`. macOS observation uses `ui_snapshot`/`uiSnapshot` and must not reuse Android `ui_tree`/`uiTree` or Web `page_snapshot`/`pageSnapshot` naming. macOS target resolution uses a locator built from accessibility id, name, label, value, role/control type, class name, XPath, predicate string, semantic target text, and explicit coordinates.

macOS owns `MacOSHarness`, `MacOSDriverInterface`, `AppiumMac2Driver`, macOS catalog-backed platform declarations, and macOS default capability definitions. `AppiumMac2Driver.assert_with_ai` is a decorated backend tool that calls shared AI assertion support. macOS artifact capture supports `screenshot` and `ui_snapshot`. Appium imports, Mac2 option construction, Appium server connection, and application launch are lazy runtime/backend concerns, not registry-bootstrap concerns. FSQ platform/backend names are `macos` and `appium_mac2`; the driver maps those to Appium native `platformName: Mac` and `automationName: Mac2` internally.

`AppiumMac2Driver.assert_elements_order` resolves each requested element through the same macOS locator pipeline used by actions and `assert_visible`, reads Appium element `location` and `size`, compares element centers on the requested axis, and returns structured assertion details containing `direction`, `elements_found`, `elements_total`, `actual_order`, `expected_order`, and per-element positions. Missing required elements are target-resolution failures when `require_all` is true. Found elements in the wrong order are assertion failures, not configuration errors.

### Future Platform Block

Future Web-adjacent capability groups and future platforms must add their own platform block, parameter models, default capability definitions, harness/driver contracts, and verification expectations before implementation. New platform blocks must keep `StepRunner` and `StepSequenceRunner` platform-neutral.

Capability metadata, not a static Android action table, is the runtime source of truth for platform method name, parameter model, step kind, owner, platform/backend metadata, replay alias, and evidence capture intent. Platform action catalog entries are declaration-time validation inputs that generate capability metadata; they are not an execution path or parser fallback. Capability metadata does not include per-tool SDK schema strictness; SDK adapters expose active capabilities with strict JSON schema by default.

## Internal Structure

- `__init__.py`: Public exports only.
- `_capabilities.py`: Capability registry, alias resolution, duplicate validation, and snapshot creation.
- `_default_capabilities.py`: Android, Web, Windows, and macOS CommonTool/PlatformTool capability definitions used by entry-layer registry bootstrap without constructing a real backend connection.
- `runner/__init__.py`: Runner subpackage exports only.
- `runner/_runner.py`: `StepRunner` implementation for single-step capability execution.
- `runner/_sequence.py`: `StepSequenceRunner` implementation for ordered execution and evidence recording.
- `_platform_tools.py`: CommonPlatformTools and platform-default `wait_ms`/`get_runtime_secret` implementation.
- `harness/_ai_assertion_tool.py`: Shared backend support for decorated platform `assert_with_ai` driver tools, including evaluator invocation, screenshot artifact capture, and backend-shaped result conversion.
- `harness/__init__.py`: Harness subpackage exports only.
- `harness/_interface.py`: `HarnessInterface` and `AIAssertionEvaluatorProtocol` protocols.
- `harness/_android.py`: Built-in `AndroidHarness` implementation and Android runtime-service delegation.
- `harness/_android_driver.py`: `AndroidDriverInterface` protocol and driver-owned contracts.
- `harness/_web.py`: Built-in `WebHarness` implementation and Web runtime-service delegation.
- `harness/_web_driver.py`: `WebDriverInterface` protocol and driver-owned contracts.
- `harness/_windows.py`: Built-in `WindowsHarness` implementation and Windows runtime-service delegation.
- `harness/_windows_driver.py`: `WindowsDriverInterface` protocol and driver-owned contracts.
- `harness/_macos.py`: Built-in `MacOSHarness` implementation and macOS runtime-service delegation.
- `harness/_macos_driver.py`: `MacOSDriverInterface` protocol and driver-owned contracts.
- `harness/_driver_tools.py`: Thin platform declaration compatibility helpers, Android/Web/Windows/macOS action catalog wiring, and function schema/capability discovery wrappers backed by `capabilities`.
- `harness/_uiautomator2_driver.py`: Optional uiautomator2 backend implementation with lazy dependency import and fake-device injection for tests.
- `harness/_playwright_driver.py`: Optional Playwright backend implementation with lazy dependency import, browser/page lifecycle management, and fake-page injection for tests.
- `harness/_pywinauto_driver.py`: Optional pywinauto backend implementation with lazy dependency import, application/window lifecycle management, and fake-window injection for tests.
- `harness/_appium_mac2_driver.py`: Optional Appium Mac2 backend implementation with lazy dependency import, Mac2 session lifecycle management, page-source simplification, macOS command execution, and fake-client injection for tests.
- `evidence/__init__.py`: Evidence subpackage exports only.
- `evidence/_recorder.py`: `EvidenceRecorder` implementation.
- `evidence/_artifact_store.py`: `ArtifactStore` implementation for run-local artifact paths and file writing.
- `SPEC.md`: Module design.

Core must not define Pydantic models shared across modules. Shared models belong in `fsq_agent.models`.

## Python Architecture

- Architecture level: 3 Layered Application.
- Public API: capability registry, CommonTool/PlatformTool provider contracts, Android/Web/Windows/macOS capability definitions, runner, sequence runner, harness protocols, Android/Web/Windows/macOS harness/driver contracts, evidence recorder/store, and provider-neutral AI assertion evaluator protocol exported from package/subpackage `__init__.py` files.
- Internal modules: all `_*.py` files and implementation subpackages remain private outside documented exports.
- Domain boundaries: core owns execution orchestration and provider-neutral platform coordination. Provider construction, SDK tool creation, CLI parsing, FSQ parsing, and report generation live outside core.
- Boundary models: all serializable contracts come from `models`; core protocols and concrete runners operate on those contracts.
- Dependency direction: core imports `models` and `capabilities` only among project modules. Entry modules inject providers, concrete harnesses, platform tool providers, backend drivers, and settings.
- Rationale: execution routing coordinates multiple side-effecting components and evidence flow, so Level 3 is warranted; no persistence/domain complexity justifies Clean Architecture or DDD.

## Error Handling

Registry bootstrap failures are configuration errors and must occur before YAML parsing or SDK tool exposure. Duplicate names, duplicate or ambiguous `fsq_command` replay aliases, replay aliases that conflict with another canonical name, missing parameter models, unsupported executor kinds, invalid sensitivity result shapes, and eager backend connections during registry build fail fast.

Runner phases preserve failure boundaries:

- prepare failures: registry lookup, context, setup, validation, or before-action observation failures
- invoke failures: action, target, timeout, CommonTool, PlatformTool, provider-backed assertion, or backend failures
- finalize failures: after-action observation, artifact capture, stabilization, cleanup, or event persistence failures

Harness action payload validation errors are configuration failures and must be returned as structured failed results before any backend side effect. Driver target misses, assertion failures, action errors, artifact errors, and backend exceptions become structured runner results. Strict mode rejects silent recovery; target misses remain failures unless a future recovery mode runs separately with separate evidence.

Sensitive capabilities must return values in the standard normalized shape `output.value`. Persisted events, manifests, reports, artifacts, previews, and historical tool-output trimming must redact or omit sensitive values. A sensitive capability result that does not use the standard shape fails as a capability implementation/configuration error and raw output must not be persisted.

## Testing Contract

- Unit tests: registry validation, alias resolution, duplicate/ambiguous failures, StepRunner routing through `HarnessInterface.invoke_action`, capability-derived evidence policy application, explicit evidence policy preservation, post-action delay resolution and ordering, sensitivity redaction, structured event payloads, sequence teardown behavior, CommonPlatformTools behavior, Android driver dispatch, Web driver dispatch, Windows driver dispatch, macOS driver dispatch, and harness delegation.
- Integration-style tests with fakes: strict `waitMs` alias resolves to canonical `wait_ms`; dynamic and strict `wait_ms` reach the same inherited CommonTool implementation; dynamic and strict `get_runtime_secret` preserve sensitivity/dependency metadata; Android aliases resolve to canonical Android PlatformTools; Web aliases resolve to canonical Web PlatformTools; Windows aliases resolve to canonical Windows PlatformTools; macOS aliases resolve to canonical macOS PlatformTools; Web `startBrowser`/`closeBrowser` lifecycle aliases resolve and execute through the same driver-backed PlatformTool path as dynamic tools; registry bootstrap does not connect to real Android devices, launch Playwright browsers, start Windows apps, or connect to Appium Mac2.
- Regression tests: no `waitMs` action-name special branch in StepRunner, no static Android action registry dependency in FSQ parsing, no name-based CommonTool replay/sensitivity/delay branches, no synthetic `waitMs` or evidence steps from post-action delay, no StepSequenceRunner configured inter-step sleep, no Web browser launch during `PlaywrightWebDriver` construction, no implicit Web startup from `navigate_to`, no Appium connection during macOS registry/bootstrap or driver construction, no AgentTools in strict registries, no concrete `_assert_with_ai` tool body on `AndroidHarness`/`WebHarness`/`WindowsHarness`/`MacOSHarness`, and no dynamic/strict drift for `capture_evidence=True` PlatformTools.
- Verification commands: `./.venv/Scripts/python.exe -m pytest tests/test_core_contracts.py tests/test_step_runner.py tests/test_android_harness.py tests/test_web_harness.py tests/test_windows_harness.py tests/test_macos_harness.py` plus broader tests when implementation touches CLI/agent/report paths.

## Design Decisions

- Decorator metadata produced through the shared `capabilities` declaration layer is the source of truth for executable capabilities. Android action catalog entries validate declarations and prevent platform drift, but static Android action tables, separate harness schemas, and separate CommonTool definitions are not runtime authorities in the target architecture.
- `StepRunner` owns execution control, metadata-driven routing, evidence policy application, result normalization, sensitivity handling, and structured event emission.
- `StepRunner` owns post-action stabilization delay. It applies `time.sleep` only through a runner-local private helper after invoke and before finalize when the effective delay is positive. Entry layers pass loaded delay settings into `StepRunner`; `core` must not import `config`.
- Post-action delay is metadata/config-driven timing only. Capability metadata can override the configured executor-kind default, including explicit zero to disable delay. The delay must not become a `waitMs` command, replay entry, evidence step, or action result.
- CommonTools are inherited platform-default execution capabilities owned by platform tool providers. They are not AgentTools and are not dynamic-only helpers.
- `wait_ms` is a decorated inherited CommonTool capability with replay alias `waitMs`, not a core-owned special command.
- `get_runtime_secret` is a decorated sensitive inherited CommonTool capability with dependency replay alias `runtimeSecret`, not a report/recorder special case.
- Platform `assert_with_ai` tools use the same catalog-backed capability metadata path as other driver-backed PlatformTools. Their public tool decorators live on concrete backend drivers, while shared backend support handles evaluator invocation and artifact/result shaping.
- Concrete drivers control dynamic exposure by decorating implemented methods with shared capability metadata. A protocol method existing on `AndroidDriverInterface` or `WebDriverInterface`, a Pydantic parameter model, or an action catalog entry is not enough to expose it to the registry or to the LLM. Web, desktop, and iOS platforms should add platform action catalogs and reuse catalog-backed declaration helpers rather than creating platform-specific decorator implementations.
- Android backend construction must be lazy enough that registry bootstrap and strict YAML parsing never require a real device connection.
- Web backend construction must be lazy enough that registry bootstrap, strict YAML parsing, and `PlaywrightWebDriver` construction never require importing Playwright or launching a browser. Browser startup is the explicit `start_browser` capability; browser shutdown is the explicit `close_browser` capability or final driver cleanup when entry layers dispose resources after execution.
- macOS backend construction must be lazy enough that registry bootstrap, strict YAML parsing, and `AppiumMac2Driver` construction never require importing Appium/Selenium, connecting to an Appium server, or launching a macOS app. Appium Mac2 session creation is an explicit lifecycle/runtime concern reached through `launch_app`; other macOS actions require an active session and fail clearly when invoked before launch.
- macOS order assertions are deterministic driver-backed PlatformTools. They borrow the Appium MCP reference's geometry idea, but expose FSQ typed locators and assertion result metadata instead of MCP XPath-only payloads or MCP server calls.
- AI assertion is explicit assertion execution. It may call an injected evaluator only because the authored capability requested AI assertion; it must not be used for locator fallback, action repair, screenshot reinspection of unrelated steps, or testcase mutation.
- Locator self-healing is not part of strict execution. Any deterministic fallback or AI-assisted repair must be represented as recovery execution so reports can compare strict truth with recovery outcome.
- Evidence artifacts use run-relative paths. `ArtifactStore` owns directory layout and artifact writing; runners and harnesses do not construct artifact paths manually.