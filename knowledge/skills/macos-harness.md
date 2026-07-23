# macOS Harness Skill

Use when `harness.platform` is macOS. This skill contains macOS-specific stability guidance; the active tool schema already defines callable names and arguments.

## Snapshot-First Rules

- Start app-owned workflows with `launch_app`; do not assume a Mac2 session exists before lifecycle setup.
- Call `ui_snapshot` after launch and after state-changing actions when the next target is not already unambiguous.
- Prefer stable macOS accessibility identifiers and names over coordinates.
- Use coordinate `point` values only as an explicit fallback when the target cannot be represented by accessibility metadata.
- Do not infer that the window changed from a screenshot path alone. Use a fresh `ui_snapshot` or assertion after the action.
- If a target is stale or missing, refresh the snapshot once and retry the same semantic action with corrected schema-valid arguments.

## Locator Rules

- A macOS locator may use `accessibilityId`, `name`, `label`, `value`, `role`, `controlType`, `className`, `xpath`, `predicate`, or `point`.
- Prefer `accessibilityId` when available because it is the most stable Appium Mac2 lookup.
- Use `name`, `label`, or `value` for controls that expose user-visible accessibility metadata.
- Use `role`, `controlType`, or `className` only when the current `ui_snapshot` confirms those fields.
- Use `xpath` or `predicate` only when simpler accessibility fields are absent or ambiguous.

## Verification and Assertion Rules

- Use `assert_elements_order` when the requirement is about visual order, such as toolbar item sequence or vertical list ordering.
- For `assert_elements_order`, keep `expected_order` as zero-based indexes of the provided `elements`; omit it when the authored element list is already the expected order.
- Use `assert_visible` for required presence or visibility of a macOS accessibility element.
- Use `assert_with_ai` when deterministic accessibility assertions cannot express the requirement or would require a brittle complex locator.

## Argument Rules

- Treat `launch_app` and `kill_app` as lifecycle actions. Do not report them as satisfying a business key action unless the case explicitly tests app lifecycle.

## Correct Key Examples

### `clickOn` with an accessibility id

```json
{
  "locator": {
    "accessibilityId": "SearchField"
  }
}
```

### `clickOn` with a coordinate fallback

Use this only when accessibility metadata is unavailable:

```json
{
  "point": {
    "x": 120,
    "y": 240
  }
}
```

### `assertElementsOrder` for a horizontal toolbar

```json
{
  "direction": "horizontal",
  "elements": [
    {"target": "Back"},
    {"target": "Forward"},
    {"target": "Share"}
  ]
}
```

## Tool Usage Error Recovery

- If a macOS tool validation fails, rebuild the payload from the active schema and the requested semantic action.
- If an action executes but the expected state is not present, take a fresh `ui_snapshot`, then decide whether retrying the same semantic action is justified.
- If a key action returns the wrong window state, do not count it. Retry the requested action with a schema-valid payload or report the mismatch.
- Before `assert_with_ai`, keep the window at the intended visual state.
- For `assert_with_ai`, use the returned verdict rather than deciding from screenshot existence.