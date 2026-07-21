# Windows Mouse Actions Design

## Goal

Add recordable Windows pywinauto mouse actions for hovering, scrolling, and drag-and-drop while preserving the existing separation between semantic step descriptions and deterministic control locators.

The new Windows PlatformTools are:

- `hover_on` with authored alias `hoverOn`
- `scroll_on` with authored alias `scrollOn`
- `drag_to` with authored alias `dragTo`

The implementation may use the external `pywinauto-mcp-server/tools/mouse_tool.py` as a behavioral reference, but fsq-agent will own its parameter models, capability declarations, execution, error handling, evidence, and replay contracts.

## Scope

- Add typed Windows boundary models for mouse points, offsets, drag endpoints, and the three action payloads.
- Add the three actions to the Windows action catalog and driver protocol.
- Implement the actions in `PywinautoWindowsDriver` using pywinauto mouse APIs.
- Reuse the existing Windows locator-to-wrapper resolution path for element-based mouse coordinates.
- Expose the actions through the existing decorator-driven capability registry and strict replay aliases.
- Update Windows harness guidance and focused tests.

## Non-Goals

- Do not add a generic `mouseAction` capability.
- Do not copy the MCP server's transport fields such as `caller`, `control_framework`, `scenario`, `step_raw`, `need_snapshot`, or `timeout`.
- Do not add parent-locator behavior as part of this change.
- Do not add configurable motion timing, movement step size, or sleep duration to the public action schemas.
- Do not use semantic `target` text to locate controls.
- Do not add negative absolute coordinates; absolute points are constrained to non-negative integers.
- Do not add mouse actions to Android, Web, or macOS.

## Proposed Design

### Public Actions

#### `hoverOn`

Payload:

- `target: str`: required non-empty semantic description of the step target.
- `locator: WindowsLocator`: required non-empty deterministic control locator.

Behavior:

1. Resolve `locator` to a pywinauto wrapper through the existing Windows control lookup path.
2. Read the wrapper rectangle midpoint.
3. Move the mouse to that point.
4. Return a passed driver result.

`hoverOn` is recordable but does not enable default evidence capture because hovering is not normally state-changing.

#### `scrollOn`

Payload:

- `target: str`: required non-empty semantic description.
- `locator: WindowsLocator`: required non-empty deterministic control locator.
- `wheel_dist: int`: required non-zero wheel distance; positive values scroll up and negative values scroll down.

Behavior:

1. Resolve `locator` to a wrapper.
2. Read its rectangle midpoint.
3. Invoke pywinauto mouse scrolling at that point with `wheel_dist`.
4. Return a passed driver result.

`scrollOn` enables default evidence capture.

#### `dragTo`

Payload:

- `target: str`: required non-empty semantic description of the drag operation.
- `source`: required endpoint containing exactly one of:
  - `locator: WindowsLocator`
  - `point: WindowsPoint`
- `destination`: required endpoint containing exactly one of:
  - `locator: WindowsLocator`
  - `point: WindowsPoint`
  - `offset: WindowsOffset`
- `mouse_button`: optional Windows mouse button, default `left`.

Boundary models:

- `WindowsPoint`: integer `x` and `y`, both greater than or equal to zero.
- `WindowsOffset`: signed integer `x` and `y`; at least one must be non-zero.
- Source and destination endpoint models reject missing or conflicting location modes.

Behavior:

1. Resolve a source locator to its wrapper midpoint, or use the source absolute point.
2. Resolve a destination locator to its wrapper midpoint, use an absolute destination point, or add the destination offset to the source point.
3. Press `mouse_button` at the source point.
4. Move along a straight path in bounded internal pixel steps.
5. Release `mouse_button` at the destination point.
6. Return a passed driver result.

The movement step size and any short pacing delay are backend implementation constants, not public schema fields. `dragTo` enables default evidence capture.

### Locator Semantics

- `target` remains a required semantic step field and is preserved in replay payloads and diagnostics.
- `target` never participates in Windows control lookup.
- Element-based mouse operations use only `WindowsLocator`.
- Existing exact-title matching and title-regex fallback behavior remains unchanged.
- Successful lookup returns `wrapper_object()` before rectangle or interaction methods are used.

### Mouse Backend Boundary

`PywinautoWindowsDriver` will import `pywinauto.mouse` lazily at execution time, consistent with the existing lazy pywinauto application import. No new package or service abstraction is introduced.

A small private helper may centralize:

- lazy mouse module access,
- wrapper midpoint extraction,
- endpoint-to-coordinate resolution,
- drag path movement.

These helpers remain internal to `_pywinauto_driver.py` unless implementation evidence shows a real reuse boundary.

## Error Handling

- Pydantic models reject missing, empty, conflicting, or invalid payload fields before the driver is invoked.
- Invalid `wheel_dist=0`, negative absolute coordinates, zero offsets, and conflicting endpoint modes are configuration errors with field-level validation details.
- Missing locator controls continue to raise the existing lookup failure containing the effective `query_dict`; `WindowsHarness` classifies that failure as `target_resolution_error`.
- Rectangle or wrapper failures propagate as backend execution failures unless they are caused by control lookup.
- Drag should release the pressed mouse button in a `finally` path when a failure occurs after press, preventing a stuck pressed-button state. The original failure remains visible; release cleanup must not mask it.

## Data And Control Flow

1. FSQ or dynamic SDK action resolves through the Windows capability registry.
2. `WindowsHarness` validates the action payload with its catalog-declared Pydantic model.
3. The harness calls the decorated `PywinautoWindowsDriver` method.
4. The driver resolves any element locators to wrappers and derives coordinates.
5. The driver invokes pywinauto mouse operations.
6. `StepRunner` applies capability-derived evidence and replay metadata.
7. Strict recording writes the authored alias and validated safe payload without transport-only MCP fields.

## Module Ownership

- `fsq_agent.models`: owns mouse boundary models and Windows action catalog entries.
- `fsq_agent.core.harness._windows_driver`: owns protocol method signatures.
- `fsq_agent.core.harness._pywinauto_driver`: owns pywinauto mouse execution and private coordinate helpers.
- `fsq_agent.core.harness._driver_tools`: consumes new catalog entries automatically; no platform-specific execution logic is added there.
- `knowledge/skills/windows-harness.md`: documents when and how the active actions should be used.
- `tests/test_windows_harness.py`: covers schemas, dispatch, wrapper midpoint use, mouse calls, drag modes, cleanup, errors, and capability metadata.
- Model/catalog contract tests cover validation and export behavior where existing test ownership requires it.

## Python Architecture

- Architecture level: Level 2, Simple package.
- Public API: Windows PlatformTool action schemas exposed through capability discovery; public parameter models exported through `fsq_agent.models` following existing conventions.
- Internal modules: pywinauto execution remains in `_pywinauto_driver.py`; no new public implementation module is introduced.
- Domain boundaries: payload invariants live in Pydantic boundary models; pywinauto mechanics live in the concrete backend driver.
- Boundary models: Windows mouse point, offset, endpoint, hover, scroll, and drag parameter models.
- Dependency direction: `core` may import public `models`; `models` must not import `core` or pywinauto; pywinauto remains a lazy backend dependency.
- Rationale: the existing Windows driver and catalog already provide the required ownership boundaries. Additional layers would only pass calls through without isolating meaningful domain complexity.

## Specifications Expected To Change

- Root `SPEC.md`: Windows first-batch action surface.
- `fsq_agent/core/SPEC.md`: Windows PlatformTool list, aliases, mouse behavior, evidence intent, and backend ownership.
- `fsq_agent/models/SPEC.md`: Windows mouse boundary model contracts and validation rules if the model SPEC enumerates these public models during synchronization.

No implementation starts until these SPEC changes are presented and confirmed through the `spec-driven` workflow.

## Verification Expectations

Focused verification:

- Windows action-space schemas expose `hover_on`, `scroll_on`, and `drag_to` with the expected aliases and required fields.
- Harness dispatch calls the correct driver methods.
- Hover moves to the resolved wrapper midpoint.
- Scroll invokes pywinauto mouse scrolling at the wrapper midpoint and preserves wheel direction.
- Drag covers:
  - locator to locator,
  - locator to absolute point,
  - point to locator,
  - point to absolute point,
  - locator or point to relative offset,
  - non-default mouse button,
  - release cleanup after movement failure.
- Locator lookup failures preserve `query_dict` and classify as `target_resolution_error`.
- Invalid points, offsets, endpoint combinations, missing target, and missing locators fail at model validation.
- Capability metadata applies no default evidence capture to hover and enables it for scroll and drag.

Expected commands:

```text
python -m pytest tests/test_windows_harness.py tests/test_models.py -q
python -m pytest tests/test_capabilities.py tests/test_core_contracts.py -q
```

Broader tests should run if catalog or export changes affect shared capability discovery.

## Resolved Questions

- Scope includes all three reference mouse behaviors: hover, scroll, and drag-drop.
- Drag supports destination locator, absolute point, and relative offset.
- Scroll uses pywinauto-native `wheel_dist` semantics.
- Absolute points allow only non-negative coordinates.
- Hover does not enable default evidence capture; scroll and drag do.
- The design uses typed semantic actions rather than copying the MCP transport signature.
