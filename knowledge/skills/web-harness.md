# Web Harness Skill

Use when `harness.platform` is Web. This skill contains Web-specific stability guidance; the active tool schema already defines callable names and arguments.

## Snapshot-First Rules

- Start browser-owned workflows with `start_browser`, then navigate with `navigate_to`. Do not treat navigation as browser startup.
- Close browser-owned workflows with `close_browser` as the final lifecycle action. For multi-cycle workflows, call `close_browser` before the next `start_browser` cycle.
- Call `page_snapshot` after navigation and after state-changing actions when the next target is not already unambiguous.
- Prefer replayable semantic locators and stable selectors over snapshot `ref` values, coordinates, or visual guessing.
- Do not infer that a page changed from a screenshot path alone. Use a fresh snapshot or assertion after the action.
- Treat screenshots as evidence artifacts. They can support debugging, but they do not replace `page_snapshot` for action targeting.
- If a target is stale or missing, refresh the snapshot once and retry the same semantic action with corrected schema-valid arguments.

## Verification and Assertion Rules

- Use `assert_text` for deterministic page text or field text requirements.
- Use `assert_visible` or `assert_not_visible` for required presence or absence of page elements.
- Use `assert_with_ai` only when the assertion requires visual judgment or page interpretation that deterministic selectors/text cannot express.
- Use `page_snapshot` to inspect, locate, or collect context before an assertion.

## Argument Rules

- Use `wait_for` for waits so waiting does not change page state.
- Do not use `Alt+F4`, `Control+W`, or other key presses as browser lifecycle controls. Use `close_browser`.

## Correct Key Examples

Use one payload from the matching semantic action. Do not combine unrelated fields.

### `pressKey: {key: Enter}`

```json
{
  "key": "Enter"
}
```

### `typeText` with a runtime secret

```json
{
  "target": "Password field",
  "text": {
    "runtimeSecret": "TEST_ACCOUNT_PASSWORD"
  }
}
```

## Tool Usage Error Recovery

- If a Web tool validation fails, rebuild the payload from the active schema and the requested semantic action.
- If an action executes but the expected state is not present, take a fresh `page_snapshot`, then decide whether retrying the same semantic action is justified.
- If a key action returns the wrong page state, do not count it. Retry the requested key/action with schema-valid payload or report the mismatch.
- Before `assert_with_ai`, use `wait_for` for required waits and keep the page at the intended visual state.
- For `assert_with_ai`, use the returned verdict rather than deciding from screenshot existence.