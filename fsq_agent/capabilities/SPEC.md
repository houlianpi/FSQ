# Module: capabilities

## Purpose

Own the neutral capability declaration layer for fsq-agent. This module provides shared decorators, thin domain helper decorators, platform action catalog contracts, catalog-backed validation, and decorated-method discovery helpers that produce serializable `CapabilityDefinition` records for recordable CommonTool and PlatformTool capabilities.

This module does not execute capabilities, invoke CommonTool or PlatformTool providers, call harnesses or drivers, construct SDK tools, parse FSQ YAML, build registries, or generate reports. Execution ownership remains in `core`, `agent`, `cli`, and entry-layer bootstrap code. Dynamic-only AgentTools are outside this declaration layer.

## Dependencies

- Internal project dependencies: `models` only. Uses `CapabilityDefinition`, `CapabilityExecutorKind`, `ExecutableStepKind`, `HarnessPlatform`, `ReplayPolicy`, and `ConfigurationError`.
- External dependencies: standard library dataclasses, inspect, typing, and Pydantic `BaseModel` type references.
- Forbidden dependencies: `core`, `tools`, `agent`, `cli`, `fsq`, `config`, `providers`, `report`, `playground`, `observation`, `knowledge`, `skills`, OpenAI Agents SDK types, concrete driver/runtime objects, and backend SDKs.

## Public Interface

Target `__init__.py` exports via `__all__`:

- `CapabilityActionDefinition`: Lightweight catalog entry for authored platform actions. It describes authored action name, canonical capability name, executor kind, owner, parameter model, optional required method name, step kind, replay policy, default evidence policy, optional post-action delay override, and safe metadata defaults. The authored action name supplies `ReplayPolicy(kind="fsq_command").alias` for replayable commands; catalog entries do not carry separate capability aliases or SDK schema strictness flags.
- `CapabilityActionCatalog`: Mapping type alias from authored action name to `CapabilityActionDefinition`.
- `capability`: Neutral low-level decorator that attaches capability declaration metadata to a function or method. It can declare CommonTool or PlatformTool capabilities, but it does not register or execute them.
- `common_capability`: Thin helper around `capability` for CommonTool declarations owned by core platform tool providers.
- `platform_capability`: Thin helper around `capability` for non-driver platform-level PlatformTool declarations. Current Android/Web/Windows/macOS backend actions, including `assert_with_ai`, use catalog-backed driver declarations instead.
- `harness_capability`: Backward-compatible helper for legacy harness-owned declarations; new platform behavior should use `platform_capability` or catalog-backed `platform_driver_capability`.
- `driver_capability`: Compatibility helper for explicit driver-backed PlatformTool declarations that do not need a platform action catalog.
- `platform_driver_capability`: Factory that binds a platform/backend/catalog and returns a decorator for catalog-backed driver-backed PlatformTool declarations.
- `discover_capability_definitions(target: object, *, metadata: dict[str, object] | None = None) -> list[CapabilityDefinition]`: Inspect a decorated class or instance without invoking methods and return serializable capability definitions.

The neutral decorator API accepts canonical name, tool family or compatibility executor kind, owner, parameter model, description, platform, backend, step kind, evidence flag, optional post-action delay override, sensitivity flag, replay policy, safe metadata, and optional catalog/action name inputs. It does not accept a duplicate alias list for primary authored replay command names and does not accept a per-capability SDK schema strictness flag. `post_action_delay_seconds=None` means inherit the configured family default; `0` explicitly disables runner-owned post-action delay for that capability; positive values override the configured default. Domain helpers should be preferred at call sites so CommonTool and PlatformTool declarations remain readable. Android, Web, Windows, and macOS platform actions must be declared through catalog-backed `platform_driver_capability` helpers rather than platform-specific decorator semantics.

## Platform Declaration Blocks

Shared declaration rules:

- `capability`, helper decorators, discovery, and `CapabilityDefinition` output stay platform-neutral.
- Platform-specific authored command names, parameter models, replay policy, evidence defaults, backend metadata, and required driver method names belong in platform action catalogs. Replayable authored command names are represented by `ReplayPolicy(kind="fsq_command").alias` in discovered capability metadata.
- Registry/bootstrap code, not this module, chooses which platform catalog definitions are active.

Android declaration block:

- Android uiautomator2 driver methods use catalog-backed `platform_driver_capability` entries with Android replay aliases and parameter models.
- Android platform-level assertions use `platform_capability` when behavior is not a backend driver method.

Web declaration block:

- Web Playwright driver methods use catalog-backed `platform_driver_capability` entries with Web replay aliases and parameter models, including explicit browser lifecycle actions `startBrowser`/`closeBrowser` alongside page actions such as `navigateTo` and `pageSnapshot`.
- Web platform-level assertions use `platform_capability` when behavior is not a backend driver method.

macOS declaration block:

- macOS Appium Mac2 driver methods use catalog-backed `platform_driver_capability` entries with macOS desktop replay aliases and parameter models, including lifecycle actions `launchApp`/`killApp`, desktop interactions such as `clickOn`, `doubleClickOn`, `rightClickOn`, `typeText`, `pressKey`, `hoverOn`, and `dragTo`, observations such as `takeScreenshot` and `uiSnapshot`, and assertions such as `assertVisible`, `assertElementsOrder`, and `assertWithAI`.
- macOS reuses the existing neutral decorators, catalog validation, discovery, replay metadata, evidence metadata, and backend metadata contracts. It must not introduce a macOS-only decorator, direct MCP schema importer, or runtime Appium discovery path in `capabilities`.
- macOS catalog entries are declaration-time validation inputs only. Registry/bootstrap code chooses whether macOS entries are active based on `harness.platform == "macos"`.

Future platform declaration block:

- New platforms must provide a catalog and reuse existing decorators before registry exposure.
- New platform behavior must not add new decorator semantics unless a later SPEC changes the shared declaration contract.

## Internal Structure

- `__init__.py`: Public exports only.
- `_decorators.py`: Neutral decorator, domain helper decorators, marker metadata, and legal-combination validation.
- `_catalog.py`: `CapabilityActionDefinition`, catalog mapping type, catalog lookup, and catalog-to-capability defaults.
- `_discovery.py`: Reflection helpers that discover decorated methods on classes or instances and convert metadata into `CapabilityDefinition` values.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 2 Simple Package.
- Public API: declaration decorators, catalog entry types, and discovery helpers exported from `__init__.py`.
- Internal modules: `_decorators.py`, `_catalog.py`, and `_discovery.py` are private implementation modules.
- Domain boundaries: this module owns declaration metadata and validation only. CommonTool and PlatformTool safety/invocation live in `core`; AgentTool behavior and SDK helper adaptation live in `tools`; runner routing, harness/provider dispatch, and evidence live in `core`; strict FSQ parsing lives in `fsq` and entry modules.
- Boundary models: serializable capability contracts come from `models`. Decorator marker objects and catalog helper dataclasses are not persisted as runtime results.
- Dependency direction: imports public `models` only; may be imported by `core`; must not import `tools` or any execution or entry-layer module.
- Rationale: the module is a focused reusable declaration utility with validation and reflection only, so Level 2 is sufficient and a higher architecture level would add ceremony without isolating additional side effects.

## Error Handling

Declaration and discovery fail fast with `ConfigurationError` when a decorated capability is inconsistent or unsafe to expose:

- Missing or unresolvable parameter model.
- Unknown catalog action name.
- Catalog entry owner or executor kind incompatible with the selected helper.
- Decorated method name does not match a catalog-required method name.
- Method annotation conflicts with the catalog or explicit parameter model.
- Invalid executor kind, owner, platform, backend, sensitivity, or evidence combination.
- Negative post-action delay values in decorator arguments or catalog entries.
- Capability metadata attempts to store non-serializable runtime objects.

Duplicate capability names, replay alias conflicts, ambiguous replay aliases, and executable routing validation remain registry/bootstrap concerns owned by `core` and entry-layer code.

## Testing Contract

- Unit tests: neutral decorator metadata, domain helper defaults, post-action delay override validation, catalog lookup/validation, method-name and parameter-model validation, discovery from class and instance targets, safe metadata merging, and no method invocation during discovery.
- Regression tests: `common_capability` produces the `CapabilityDefinition` shape expected by platform provider registry/bootstrap; catalog-backed Android, Web, Windows, and macOS PlatformTool declarations produce the expected canonical names, replay aliases through `ReplayPolicy`, parameter models, replay metadata, owner, platform/backend, evidence flags, and post-action delay overrides, without duplicate capability alias lists or schema strictness fields.
- Boundary tests: `capabilities` imports only `models` among project modules and has no dependency on `core`, `tools`, SDK objects, or concrete backend libraries.
- Verification commands: `./.venv/Scripts/python.exe -m pytest tests/test_capabilities.py tests/test_tools.py tests/test_android_harness.py` plus broader capability/runner tests when implementations change.

## Design Decisions

- One declaration mechanism prevents CommonTool, Android, Web, Windows, macOS, future desktop, and future iOS PlatformTool capabilities from growing separate decorator semantics.
- Domain helper decorators are intentionally thin wrappers around the neutral decorator. They preserve readability while keeping one metadata format.
- Platform differences belong in action catalogs, not in per-platform decorator implementations. Android, Web, Windows, and macOS catalogs reuse `platform_driver_capability`; future platforms should follow the same pattern.
- `CapabilityDefinition` remains the runtime contract and registry input. Decorators attach declaration metadata to functions, including optional post-action delay overrides; discovery converts that metadata into serializable definitions.
- Discovery must be side-effect free. It may inspect method signatures and type hints, but it must not call methods, connect to devices, instantiate SDK tools, or build providers.
- Runtime routing is out of scope. Tool family or compatibility `executor_kind` metadata is consumed by `core.StepRunner`; `capabilities` never invokes the selected provider or executor.
- `models` stays contract-only. Keeping decorator behavior out of `models` avoids turning the shared schema module into a reflection/behavior layer.
