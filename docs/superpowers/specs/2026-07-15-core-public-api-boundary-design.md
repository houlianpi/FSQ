# Core Public API Boundary Design

Date: 2026-07-15
Status: Ready for user review

## Goal

Optimize the `fsq_agent.core` module architecture so its public API exposes only interfaces/protocols, abstract classes, concrete implementation classes, and approved factory classes. The optimization should make `core` a reference pattern for later module-by-module boundary cleanup without forcing other modules to import private implementation files or violate the same rule.

## Scope

This design covers the public export surfaces of:

- `fsq_agent.core`
- `fsq_agent.core.harness`
- `fsq_agent.core.runner`
- `fsq_agent.core.evidence`

The first implementation cycle should focus on export shape and caller migration, not behavior changes. Existing execution semantics for registry bootstrap, platform capability discovery, step running, evidence recording, harness invocation, and concrete backend drivers must remain unchanged.

## Non-Goals

- Do not rewrite `StepRunner`, harnesses, drivers, evidence recording, or capability invocation semantics.
- Do not introduce Clean Architecture, DDD, plugin loading, or a new dependency injection framework.
- Do not move shared data models from `models` into `core`.
- Do not make entry layers import `core._*` private modules as a workaround for public API cleanup.
- Do not apply the same export cleanup to every repository module in this cycle. The design should establish a pattern that later modules can adopt incrementally.

## Proposed Design

### Public API Rule

`core` public exports should be limited to:

- Interface/protocol types, such as `HarnessInterface`, `AIAssertionEvaluatorProtocol`, and platform driver interfaces.
- Abstract classes, if future SPEC work introduces ABC-based contracts.
- Concrete implementation classes, such as `StepRunner`, `StepSequenceRunner`, `CapabilityRegistry`, `EvidenceRecorder`, `ArtifactStore`, concrete harnesses, concrete drivers, and `CommonPlatformTools`.
- Factory implementation classes whose responsibility is to construct or return core-owned public contracts without exposing internal helper functions.

Function-style helpers, decorators, and discovery utilities are not part of the normal public API. If one must remain public, the relevant SPEC must list it as an explicit exception with a concrete complexity reason.

### Capability Definition Factory

Replace public function exports for default platform capability definitions with a public factory class. The exact class name can be finalized in SPEC, but the intended shape is:

```python
factory = DefaultCapabilityDefinitionFactory()
definitions = factory.platform_definitions(platform="web", include_ai_assertion=True)
```

The factory should preserve current behavior of the existing internal functions:

- Android definitions are discovered from `UiAutomator2AndroidDriver`.
- Web definitions are discovered from `PlaywrightWebDriver`.
- Windows definitions are discovered from `PywinautoWindowsDriver`.
- macOS definitions are discovered from `AppiumMac2Driver`.
- AI assertion filtering remains available through an `include_ai_assertion` option.
- Registry bootstrap must remain lazy and must not connect to devices, launch browsers, start desktop apps, or connect to Appium.

The existing functions may remain as private implementation details inside `_default_capabilities.py`, but they should no longer be exported from `fsq_agent.core.__init__` or treated as cross-module API.

### Entry-Layer Migration

Entry-layer bootstrap code should use the factory class rather than importing private core modules. In the current codebase, the important caller is `fsq_agent._capability_bootstrap`, which imports `android_capability_definitions`, `web_capability_definitions`, `windows_capability_definitions`, and `macos_capability_definitions` from `fsq_agent.core`.

After the SPEC update, that caller should depend on the new public factory class. This preserves the root SPEC rule that package-private composition helpers at the `fsq_agent` package root may compose public module APIs while avoiding private `core._*` imports.

### Harness Declaration Helpers

`fsq_agent.core.harness` currently exports `driver_tool`. That helper is a declaration/decorator utility rather than an interface, abstract class, implementation class, or factory class. It should stop being a public subpackage export unless the SPEC confirms it as a named exception.

Platform-specific decorator helpers such as `_android_driver_tool`, `_web_driver_tool`, `_windows_driver_tool`, and `_macos_driver_tool` should remain internal. Concrete drivers inside `core.harness` may continue using those private helpers because they are in the same module ownership boundary.

### Subpackage Export Consistency

`core.runner` and `core.evidence` already expose only concrete implementation classes. They should remain aligned with the rule:

- `core.runner`: `StepRunner`, `StepSequenceRunner`
- `core.evidence`: `ArtifactStore`, `EvidenceRecorder`

`core.harness` should expose only interfaces/protocols and concrete harness/driver classes after removing or explicitly excepting declaration helpers.

### Exception Policy

Small exceptions are allowed only when converting a helper to a class or hiding it would make code significantly more complex. Exceptions must be SPEC-visible and should include:

- The exported symbol name.
- Why it cannot reasonably be represented as an interface, abstract class, implementation class, or factory class.
- Which modules may import it.
- When the exception should be revisited.

No exception is currently required by this design. If implementation reveals one, the SPEC update should record it before code changes proceed.

## Python Architecture Level And Rationale

Architecture level remains Level 3 Layered Application for `core`.

This change tightens module boundaries but does not add enough domain complexity to justify Clean Architecture or DDD. `core` still coordinates side-effecting execution flows, harnesses, drivers, capability metadata, and evidence coordination. A small factory class is sufficient to express the platform capability definition boundary while preserving existing layered responsibilities.

## Module Ownership And Dependency Boundaries

`core` continues to own:

- Capability registry construction contracts and registry validation implementation.
- Step and sequence runner implementation.
- Harness interfaces and concrete platform harnesses.
- Driver interfaces and concrete backend drivers.
- Common platform tools.
- Evidence recorder and artifact store implementation.
- Public factory class for default core capability definitions.

`core` must continue importing only `models` and `capabilities` among project modules. Entry modules may instantiate the public factory and pass results into `CapabilityRegistry`, but they must not import `core._default_capabilities` or `core.harness._driver_tools`.

## Public Behavior

This architecture optimization should be behavior-preserving:

- Existing strict and dynamic execution should resolve the same CommonTool and PlatformTool capabilities.
- Platform-selected registries should still include inherited CommonTools plus only the active platform's PlatformTools.
- Replay aliases, sensitivity policy, evidence capture, and post-action delay behavior should not change.
- Optional backend dependencies must remain lazy.
- Public imports that remain valid should point at class-based contracts rather than helper functions.

The only intended compatibility change is that function-style helper exports from `fsq_agent.core` and `fsq_agent.core.harness` are no longer public API after the SPEC-confirmed implementation. Internal functions may remain for compatibility within the core module boundary.

## Affected Specs Expected To Change

- Root `SPEC.md`: update the Development Rules or Python Architecture Rules to record the public-export principle and the exception policy as the direction for incremental module cleanup.
- `fsq_agent/core/SPEC.md`: update the Public Interface, planned subpackage exports, Internal Structure, Python Architecture, Testing Contract, and Design Decisions to replace public capability definition functions with the factory class and to remove or explicitly except `driver_tool`.
- Other module SPEC files are not expected to change unless implementation finds direct cross-module reliance on helper exports outside the known entry-layer bootstrap path.

## Open Questions Resolved

- Factory classes are acceptable public API because they are concrete implementation classes with a clear construction responsibility.
- The cleanup scope covers `fsq_agent.core` and its public subpackages `harness`, `runner`, and `evidence`.
- Small exceptions are acceptable only when SPEC-visible and justified by avoiding disproportionate complexity.

## Verification Expectations

The implementation cycle should include:

- Import-boundary checks showing no non-core module imports from `fsq_agent.core._*` or `fsq_agent.core.harness._*`.
- Public export checks for `fsq_agent.core`, `fsq_agent.core.harness`, `fsq_agent.core.runner`, and `fsq_agent.core.evidence` confirming exported names fit the allowed categories or documented exceptions.
- Existing focused core tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_core_contracts.py tests/test_step_runner.py tests/test_android_harness.py tests/test_web_harness.py tests/test_windows_harness.py tests/test_macos_harness.py
```

- Capability bootstrap tests or equivalent focused tests confirming platform registries still expose the same capability names and aliases for Android, Web, Windows, and macOS.
- A diff-based SPEC implementation audit before claiming completion.

## Review Notes

This design intentionally chooses a small class-based boundary change over a broader plugin/SPI redesign. The goal is to make the public API rule enforceable and repeatable while keeping the first implementation cycle low-risk and behavior-preserving.