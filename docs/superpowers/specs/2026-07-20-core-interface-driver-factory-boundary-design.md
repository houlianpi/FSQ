# Core Interface And Driver Factory Boundary Design

Date: 2026-07-20
Status: Confirmed design for SPEC handoff, amended after user review

## Goal

Continue optimizing the `core` module so external callers depend on interface/protocol definitions and factory classes rather than concrete platform implementation classes. The next architecture step should hide concrete harnesses and backend drivers from public exports while keeping platform driver interfaces public, because upcoming work will add multiple implementations behind the same platform driver interface.

This design is a follow-up to `docs/superpowers/specs/2026-07-15-core-public-api-boundary-design.md`. It tightens that design: concrete platform harness and driver classes should no longer be treated as public API, even though stable core service classes may remain public in this cycle.

## Scope

This design covers the public API and construction boundary for:

- `fsq_agent.core`
- `fsq_agent.core.harness`
- Core capability definition bootstrap used by package entry helpers
- Runtime harness and driver construction used by CLI, agent runtime, and playground entry layers

The implementation cycle should be behavior-preserving. Strict replay, dynamic execution, registry bootstrap, capability metadata, evidence capture, post-action delay, and report-facing runner events should keep their existing semantics.

## Non-Goals

- Do not implement additional driver backends in this cycle.
- Do not introduce third-party plugin discovery, entry-point loading, dependency injection frameworks, Clean Architecture, or DDD.
- Do not rewrite `StepRunner`, `StepSequenceRunner`, evidence recording, capability invocation, or harness method semantics.
- Do not move shared data models or exceptions out of `models`.
- Do not make non-core package code import `fsq_agent.core._*` or `fsq_agent.core.harness._*` private modules as a workaround.
- Do not hide stable core service classes such as `CapabilityRegistry`, `StepRunner`, `StepSequenceRunner`, `ArtifactStore`, and `EvidenceRecorder` in this cycle. They are public execution-core services rather than platform backend implementations. A later SPEC may introduce runner or evidence factories if a concrete need appears.

## Proposed Design

### Public API Shape

`core` public exports should move toward three categories:

- Interface/protocol classes: `HarnessInterface`, `AIAssertionEvaluatorProtocol`, `AndroidDriverInterface`, `WebDriverInterface`, `WindowsDriverInterface`, `MacOSDriverInterface`, and factory protocol interfaces.
- Factory classes: default factories for capability definitions, drivers, and harnesses.
- Stable execution-core service classes/provider classes that remain public in this cycle: `CapabilityRegistry`, `StepRunner`, `StepSequenceRunner`, `ArtifactStore`, `EvidenceRecorder`, and `CommonPlatformTools`.

Concrete platform implementation classes should stop being public exports:

- `AndroidHarness`
- `WebHarness`
- `WindowsHarness`
- `MacOSHarness`
- `UiAutomator2AndroidDriver`
- `PlaywrightWebDriver`
- `PywinautoWindowsDriver`
- `AppiumMac2Driver`

Concrete classes may remain in private implementation modules inside `core`. White-box tests may import private concrete classes when they are testing backend-specific behavior, but package code outside `core` must use public protocols and factories.

### Driver Interfaces Stay Public

Platform driver protocols remain public because they define the stable backend contract for each platform:

- `AndroidDriverInterface`
- `WebDriverInterface`
- `WindowsDriverInterface`
- `MacOSDriverInterface`

Future backend implementations for the same platform should satisfy the appropriate public driver interface and be selected through a factory/backend setting. Public callers should not import the concrete backend class to choose an implementation.

### Driver Factory Boundary

Add a public driver factory class. The factory is not named `Default` because the selected backend comes from config-owned platform backend settings:

```python
driver_factory = DriverFactory()
driver = driver_factory.create_web_driver(settings.web)
```

The driver factory should expose typed platform methods so callers and tests receive the correct protocol type:

```python
driver = DriverFactory().create_web_driver(settings.web)
```

`DriverFactory` should dispatch on each platform settings object's `backend` value and construct the selected private concrete driver. Unsupported backend values should fail with `ConfigurationError` containing the platform, requested backend, and supported backends.

The factory should not import `config` or provider modules. It may consume settings and shared contracts from `models`, which is already an allowed `core` dependency. The factory should preserve existing lazy backend behavior: capability registry bootstrap must never instantiate real drivers, launch browsers, connect to devices, start desktop applications, or connect to Appium.

### Harness Factory Boundary

Add a public harness factory class. The factory is not named `Default` because each supported platform currently has one built-in harness implementation; this class is only the composition boundary:

```python
harness_factory = HarnessFactory(driver_factory=DriverFactory())
harness = harness_factory.create_harness(
	platform=settings.harness.platform,
	harness_settings=settings.harness,
	artifact_store=ArtifactStore(run_dir),
	ai_assertion_evaluator=evaluator,
	runtime_secret_settings=settings.runtime_secrets,
)
```

`HarnessFactory` should return `HarnessInterface`, not a concrete harness type. It should centralize the current platform branching now duplicated across CLI, agent runtime, and playground code:

- Select the appropriate driver through `DriverFactory`.
- Wrap that driver in the private concrete platform harness.
- Pass through `ArtifactStore`, `AIAssertionEvaluatorProtocol`, and `RuntimeSecretSettings`.
- Support current Android overrides without forcing config mutation, such as strict-case `app_id` and playground-selected `serial`.

Entry layers that need to inject fake harnesses can continue accepting `HarnessInterface` or a callable returning `HarnessInterface`. They should not import private concrete harness classes.

### Capability Definition Factory Boundary

`CapabilityDefinitionFactory` should be the public class-based way to discover platform capability definitions. `CommonPlatformTools` remains public for inherited CommonTool capability definitions and CommonTool invocation behavior.

Expected public methods:

```python
common = CommonPlatformTools.capability_definitions()
factory = CapabilityDefinitionFactory()
platform = factory.platform_definitions(
	platform="web",
	backend="playwright",
	include_ai_assertion=True,
)
```

The `backend` argument may default from the current platform's settings in callers that already have settings available. When only one backend exists, behavior remains identical to today. As multiple implementations are added for a platform, capability definition discovery should use the same private backend mapping as `DriverFactory` so the selected registry and selected runtime driver do not drift.

Function-style helpers such as `android_capability_definitions`, `web_capability_definitions`, `windows_capability_definitions`, and `macos_capability_definitions` may remain internal implementation helpers, but they should not be exported from `fsq_agent.core` or imported by non-core package code.

### Shared Internal Backend Catalog

The implementation should avoid duplicating backend dispatch tables across factories. A private core-owned backend catalog can map:

- Platform id and backend id to the private concrete driver class used by `DriverFactory`.
- Platform id to the private concrete harness class used by `HarnessFactory`.
- Platform id and backend id to the driver class used by `CapabilityDefinitionFactory` for decorated capability discovery.

This catalog is an implementation detail. It must not become public API, and it must not instantiate drivers while answering capability-definition queries.

### Entry-Layer Migration

The implementation cycle should migrate current concrete construction sites to factories:

- `fsq_agent._capability_bootstrap` should build common definitions through `CommonPlatformTools` and selected platform definitions through `CapabilityDefinitionFactory`.
- `fsq_agent.cli._main` strict execution should use `HarnessFactory` instead of importing concrete harness and driver classes.
- `fsq_agent.agent._openai_runtime` dynamic execution should use `HarnessFactory` for runtime harness construction while preserving its existing fake-harness injection hook.
- `fsq_agent.playground._execution` and Android playground helpers should use the same factory boundary or accept injected `HarnessInterface` values.

This migration should remove concrete platform implementation imports from non-core package code. Tests may keep backend-specific private imports only where they intentionally test the private backend implementation.

### Error Handling And Edge Cases

- Unsupported platforms or backends fail fast with `ConfigurationError` and supported values.
- Missing local operator settings, such as Android app id, browser executable path, Windows app path, or macOS Appium target values, should preserve existing validation and backend error behavior.
- Absence of an AI assertion evaluator should continue filtering `assert_with_ai` exposure in harness action spaces and capability definitions where already supported.
- The selected backend for capability definitions and the selected backend for driver construction must match for a given platform run.
- Factory construction itself must be side-effect-light. Registry bootstrap and capability discovery must remain safe without installed optional backend dependencies or live devices.

## Python Architecture Level And Rationale

Architecture level remains Level 3 Layered Application for `core`.

The module coordinates execution flows, platform runtime gateways, backend drivers, capability metadata, and evidence coordination. Factory classes clarify ownership and isolate implementation selection without introducing a heavier architecture pattern. Public platform driver protocols are justified because multiple backend implementations will share each platform contract. A plugin system is not justified until there is a concrete external extension requirement.

## Affected Specs Expected To Change

- Root `SPEC.md`: tighten Development Rules or Python Architecture Rules to record that stricter module boundaries should expose protocols/interfaces and factory classes for implementation selection, and that concrete platform implementation classes should not be public API unless explicitly justified.
- `fsq_agent/core/SPEC.md`: update Public Interface, planned subpackage exports, Internal Structure, Python Architecture, Testing Contract, and Design Decisions to add driver and harness factories, keep platform driver interfaces public, keep `CommonPlatformTools` public, and hide concrete platform harness/driver classes.
- Other module `SPEC.md` files are not expected to change unless implementation discovers behavior-significant entry-layer changes. Caller import migration alone should stay within the root/core SPEC update cycle.

## Open Questions Resolved

- Compatibility mode is not required. The implementation should use the strict boundary now rather than keep concrete public exports as deprecated compatibility symbols.
- Platform driver interfaces should remain public because upcoming work needs multiple implementations behind each interface.
- Concrete platform drivers and concrete platform harnesses should not remain public exports.
- Driver selection should have its own factory boundary, separate from harness construction, so future multi-backend work changes one dispatch point rather than every entry layer.
- Stable runner, registry, and evidence service classes remain public for this cycle because hiding them would broaden scope without solving the platform implementation exposure problem.

## Verification Expectations

The implementation cycle should include focused checks for:

- Public exports from `fsq_agent.core` include platform driver interfaces, factory classes, and `CommonPlatformTools`, but not concrete platform harnesses or concrete platform drivers.
- Non-core package code does not import from `fsq_agent.core._*` or `fsq_agent.core.harness._*` private modules.
- CLI, agent runtime, playground, and capability bootstrap use public factories rather than direct concrete backend constructors.
- `DriverFactory` returns objects satisfying the correct platform driver interface for all current built-in backends.
- `HarnessFactory` returns `HarnessInterface` and preserves current strict/dynamic/playground construction behavior.
- `CapabilityDefinitionFactory` returns the same current capability names and aliases for Android, Web, Windows, and macOS when selecting existing backends.
- Registry bootstrap still does not connect to Android devices, launch Playwright browsers, start Windows apps, or connect to Appium Mac2.

Focused verification command after implementation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_contracts.py tests/test_step_runner.py tests/test_android_harness.py tests/test_web_harness.py tests/test_windows_harness.py tests/test_macos_harness.py tests/test_uiautomator2_android_driver.py tests/test_playwright_web_driver.py
```

Broader tests should run if implementation touches CLI, agent runtime, playground, or config behavior beyond import/construction migration.

## Self-Review

- The design fits one SPEC update cycle centered on root and `core` specs.
- The design avoids implementation details that would require a new plugin system.
- The design preserves public driver interfaces for upcoming multiple backend implementations.
- The design keeps concrete platform implementation classes private while preserving behavior through factories.
- No placeholder requirements remain unresolved.