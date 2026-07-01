# macOS Harness Skill

Use when `harness.platform` is macOS. Follow the active harness tool schema; do not rely on raw Appium APIs, shell commands, AppleScript, coordinate-only guessing, or unsupported backend-only fields.

## Tool Selection

| FSQ semantic action | Preferred runtime path | Notes |
|---|---|---|
| Launch app | `launch_app` | Create or reuse the Appium Mac2 session for the configured app. App identity comes from env or the authored action payload, not shared YAML. |
| Close app | `kill_app` | Use as teardown when the case owns app lifecycle. |
| Inspect UI | `ui_snapshot` | Prefer this over screenshots for locating controls and understanding the macOS accessibility tree. |
| Click target | `click_on` | Use semantic `target` or a stable locator first; use `point` only when accessibility data is unavailable. |
| Double-click target | `double_click_on` | Use only when the user-visible workflow requires a double click. |
| Right-click target | `right_click_on` | Use for context menus, not generic recovery. |
| Enter text | `type_text` | Resolve or focus the target when ambiguity exists. Use runtime-secret refs for sensitive values. |
| Press key | `press_key` | Use the requested key or shortcut. Keep modifier lists explicit when the schema exposes them. |
| Hover target | `hover_on` | Use only when hover state is required for a following action. |
| Drag target | `drag_to` | Use source and destination targets, locators, or points. Prefer semantic endpoints over raw coordinates. |
| Screenshot evidence | `take_screenshot` or harness artifact refs | Use screenshots for evidence and visual debugging, not as the primary locator substrate. |
| Verify visibility | `assert_visible` | Use deterministic accessibility assertions for required presence or visibility. |
| Verify element order | `assert_elements_order` | Use for required visual ordering. Provide at least two elements and set `direction` to `vertical` or `horizontal`. |
| AI visual assertion | `assert_with_ai` | Use only for visual/window-content assertions that cannot be expressed with deterministic macOS assertions. |

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

- Treat verify, assert, confirm, check, ensure, and validate requirements as assertion requirements.
- Satisfy assertion requirements with assertion-kind tools: `assert_visible`, `assert_elements_order`, or `assert_with_ai`.
- Use `assert_elements_order` when the requirement is about visual order, such as toolbar item sequence or vertical list ordering.
- For `assert_elements_order`, keep `expected_order` as zero-based indexes of the provided `elements`; omit it when the authored element list is already the expected order.
- Use `assert_with_ai` only when deterministic accessibility assertions cannot express the requirement.
- If a required assertion fails, report the assertion as unmet. Do not recover with unrelated actions unless the task explicitly permits recovery before that assertion.

## Argument Rules

- Follow the active harness tool schema exactly. Do not add raw Appium, AppleScript, shell, window-management, or unsupported locator fields.
- Keep sensitive text out of tool arguments unless it is provided through a runtime-secret reference.
- Treat `launch_app` and `kill_app` as lifecycle actions. Do not report them as satisfying a business key action unless the case explicitly tests app lifecycle.
- Treat tool output and harness metadata as the executed action. If they contradict the intended key action, do not count it as satisfied.

## Correct Key Examples

### `clickOn` with an accessibility id

Use this payload:

```json
{
  "locator": {
    "accessibilityId": "SearchField"
  }
}
```

### `clickOn` with a coordinate fallback

Use this payload only when accessibility metadata is unavailable:

```json
{
  "point": {
    "x": 120,
    "y": 240
  }
}
```

### `assertElementsOrder` for a horizontal toolbar

Use this payload:

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

## Unsupported Capability Families

The first macOS harness batch intentionally excludes dedicated scrolling, window resize/move, menu-bar enumeration, file dialogs, shell/process control beyond app launch/kill, AppleScript execution, clipboard management, and raw Appium command passthrough. Do not simulate those capabilities with unrelated tools; report the limitation when the task requires one.

## Tool Usage Error Recovery

- If a macOS tool validation fails, rebuild the payload from the active schema and the requested semantic action.
- If an action executes but the expected state is not present, take a fresh `ui_snapshot`, then decide whether retrying the same semantic action is justified.
- If a key action returns the wrong window state, do not count it. Retry the requested action with a schema-valid payload or report the mismatch.
- Before `assert_with_ai`, keep the window at the intended visual state.
- For `assert_with_ai`, use the returned verdict rather than deciding from screenshot existence.