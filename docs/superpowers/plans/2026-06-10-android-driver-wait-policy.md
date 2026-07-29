# Android Driver Wait Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic uiautomator2-backed element wait behavior to `UiAutomator2AndroidDriver` without changing FSQ YAML or public driver method signatures.

**Architecture:** Waiting stays inside the Android backend driver as a strict target-resolution policy. The driver uses uiautomator2 built-in selector wait APIs when available and falls back to immediate `_exists` only for fake or unsupported selector objects. This is not locator fallback, AI recovery, or testcase mutation.

**Tech Stack:** Python, pytest, uiautomator2 selector APIs, existing `UiAutomator2AndroidDriver`, `AndroidDriverInterface`, and fake-device tests.

---

### File Structure

- Modify: `fsq_agent/core/SPEC.md` to document the driver-owned wait policy.
- Modify: `fsq_agent/core/harness/_uiautomator2_driver.py` to add private wait helpers and use them in target-bearing methods.
- Modify: `tests/test_uiautomator2_android_driver.py` to verify uiautomator2 wait API usage and failure behavior.
- Create: `docs/superpowers/specs/2026-06-10-android-driver-wait-policy-design.md` for the confirmed design.
- Create: `docs/superpowers/plans/2026-06-10-android-driver-wait-policy.md` for this implementation plan.

### Task 1: Add Failing Wait Tests

**Files:**
- Modify: `tests/test_uiautomator2_android_driver.py`

- [x] **Step 1: Extend `FakeSelector` with wait hooks**

Update the existing fake selector to record wait calls and allow wait return values:

```python
class FakeSelector:
    def __init__(self, device: "FakeDevice", query: dict[str, object], exists: bool | None = None) -> None:
        self.device = device
        self.query = query
        self.exists = device.exists if exists is None else exists

    def wait(self, **kwargs: object) -> bool:
        self.device.calls.append(("wait", self.query, kwargs))
        return self.device.wait_result

    def wait_gone(self, **kwargs: object) -> bool:
        self.device.calls.append(("wait_gone", self.query, kwargs))
        return self.device.wait_gone_result
```

Update `FakeDevice.__init__` to accept wait results:

```python
class FakeDevice:
    def __init__(
        self,
        *,
        exists: bool = True,
        text: str = "Loaded",
        wait_result: bool = True,
        wait_gone_result: bool = True,
    ) -> None:
        self.exists = exists
        self.text = text
        self.wait_result = wait_result
        self.wait_gone_result = wait_gone_result
        self.calls: list[tuple[Any, ...]] = []
```

- [x] **Step 2: Add test for target actions using wait before operating**

Add this test:

```python
def test_uiautomator2_driver_waits_for_targets_before_actions() -> None:
    device = FakeDevice(wait_result=True)
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    assert driver.tap_on({"locator": {"resourceId": "login"}})["status"] == "passed"
    assert driver.long_press_on({"locator": {"accessibilityId": "Menu"}})["status"] == "passed"
    assert driver.input_text({"text": "hello", "locator": {"text": "Search"}})["status"] == "passed"

    assert device.calls[:6] == [
        ("select", {"resourceId": "login"}),
        ("wait", {"resourceId": "login"}, {"exists": True, "timeout": 10.0}),
        ("click", {"resourceId": "login"}),
        ("select", {"description": "Menu"}),
        ("wait", {"description": "Menu"}, {"exists": True, "timeout": 10.0}),
        ("long_click", {"description": "Menu"}),
    ]
    assert ("wait", {"text": "Search"}, {"exists": True, "timeout": 10.0}) in device.calls
```

- [x] **Step 3: Add test for assertion wait and timeout failure**

Add this test:

```python
def test_uiautomator2_driver_assert_visible_waits_before_missing_target() -> None:
    device = FakeDevice(exists=False, wait_result=False)
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    result = driver.assert_visible({"locator": {"text": "Missing"}})

    assert result["status"] == "failed"
    assert result["failure_category"] == "target_resolution_error"
    assert device.calls == [
        ("select", {"text": "Missing"}),
        ("wait", {"text": "Missing"}, {"exists": True, "timeout": 10.0}),
    ]
```

- [x] **Step 4: Add test for `assert_not_visible` wait-gone behavior**

Add this test:

```python
def test_uiautomator2_driver_assert_not_visible_waits_for_visible_target_to_disappear() -> None:
    device = FakeDevice(exists=True, wait_gone_result=True)
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    result = driver.assert_not_visible({"locator": {"text": "Dialog"}})

    assert result["status"] == "passed"
    assert device.calls == [
        ("select", {"text": "Dialog"}),
        ("wait_gone", {"text": "Dialog"}, {"timeout": 10.0}),
    ]
```

- [x] **Step 5: Add test for XPath wait signature compatibility**

Add a fake selector that raises `TypeError` when `exists=True` is passed, matching XPath wait signature behavior:

```python
class FakeXPathSelector(FakeSelector):
    def wait(self, **kwargs: object) -> bool:
        self.device.calls.append(("xpath_wait", self.query, kwargs))
        if "exists" in kwargs:
            raise TypeError("xpath wait does not accept exists")
        return self.device.wait_result
```

Change `FakeDevice.xpath` to return `FakeXPathSelector`:

```python
def xpath(self, value: str) -> FakeSelector:
    self.calls.append(("xpath", value))
    return FakeXPathSelector(self, {"xpath": value})
```

Add this test:

```python
def test_uiautomator2_driver_xpath_wait_retries_without_exists_argument() -> None:
    device = FakeDevice(wait_result=True)
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    result = driver.assert_visible({"locator": {"xpath": "//android.widget.TextView[@text='Browse InPrivate']"}})

    assert result["status"] == "passed"
    assert device.calls == [
        ("xpath", "//android.widget.TextView[@text='Browse InPrivate']"),
        ("xpath_wait", {"xpath": "//android.widget.TextView[@text='Browse InPrivate']"}, {"exists": True, "timeout": 10.0}),
        ("xpath_wait", {"xpath": "//android.widget.TextView[@text='Browse InPrivate']"}, {"timeout": 10.0}),
    ]
```

- [x] **Step 6: Verify red**

Run:

```bash
pytest tests/test_uiautomator2_android_driver.py -q
```

Expected: FAIL because `UiAutomator2AndroidDriver` still calls `_exists` directly and does not call selector `wait` or `wait_gone`.

### Task 2: Implement Driver Wait Helpers

**Files:**
- Modify: `fsq_agent/core/harness/_uiautomator2_driver.py`

- [x] **Step 1: Add timeout constant**

Add near the top of the file:

```python
DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS = 10.0
```

- [x] **Step 2: Add private wait helpers**

Add these methods below `_selector_query` and above `_exists`:

```python
def _wait_for_exists(self, selector: object) -> bool:
    wait = getattr(selector, "wait", None)
    if callable(wait):
        try:
            return bool(wait(exists=True, timeout=DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS))
        except TypeError:
            return bool(wait(timeout=DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS))
    return self._exists(selector)

def _wait_for_not_exists(self, selector: object) -> bool:
    wait_gone = getattr(selector, "wait_gone", None)
    if callable(wait_gone):
        return bool(wait_gone(timeout=DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS))

    wait = getattr(selector, "wait", None)
    if callable(wait):
        try:
            return bool(wait(exists=False, timeout=DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS))
        except TypeError:
            pass
    return not self._exists(selector)
```

- [x] **Step 3: Replace target-bearing `_exists` checks**

Update these methods to call `_wait_for_exists(selector)` instead of `_exists(selector)`:

```python
def tap_on(self, params: dict[str, object]) -> dict[str, object]:
    selector = self._selector(params)
    if not self._wait_for_exists(selector):
        return self._target_missing(params)
    selector.click()
    return self._passed()

def long_press_on(self, params: dict[str, object]) -> dict[str, object]:
    selector = self._selector(params)
    if not self._wait_for_exists(selector):
        return self._target_missing(params)
    selector.long_click()
    return self._passed()

def input_text(self, params: dict[str, object]) -> dict[str, object]:
    text = params.get("text")
    if not isinstance(text, str):
        return self._configuration_error("inputText requires a string text parameter.")
    selector = self._selector(params)
    if not self._wait_for_exists(selector):
        return self._target_missing(params)
    selector.set_text(text)
    return self._passed()

def assert_visible(self, params: dict[str, object]) -> dict[str, object]:
    selector = self._selector(params)
    if self._wait_for_exists(selector):
        return self._passed()
    return self._target_missing(params)

def assert_state(self, params: dict[str, object]) -> dict[str, object]:
    selector = self._selector(params, locator_key="element")
    if not self._wait_for_exists(selector):
        return self._target_missing(params)
    ...
```

- [x] **Step 4: Update `assert_not_visible`**

Replace the method with:

```python
def assert_not_visible(self, params: dict[str, object]) -> dict[str, object]:
    selector = self._selector(params)
    if not self._exists(selector):
        return self._passed()
    if self._wait_for_not_exists(selector):
        return self._passed()
    return self._failed("assertion_error", "Target is visible.")
```

This preserves immediate pass for already-absent targets and waits only when the target is currently visible.

- [x] **Step 5: Verify green**

Run:

```bash
pytest tests/test_uiautomator2_android_driver.py -q
```

Expected: PASS.

### Task 3: Verify Integration And Real CLI Case

**Files:**
- Modified files from Tasks 1-2.

- [x] **Step 1: Run related tests**

Run:

```bash
pytest tests/test_uiautomator2_android_driver.py tests/test_android_harness.py tests/test_cli_core_execution.py -q
```

Expected: PASS.

- [x] **Step 2: Run full suite and diff check**

Run:

```bash
pytest -q
git diff --check
```

Expected: `pytest` passes and `git diff --check` exits 0 with no output.

- [x] **Step 3: Re-run the real strict core CLI case when a device is connected**

Run:

```bash
python3 -m fsq_agent.cli run-strict-core \
  --config config.example.yaml \
  --workspace ./.fsq-agent-workspace \
  --task <path-to-case.codex.yaml> \
  --android-serial 145e66aa \
  --run-id cli-strict-core-inprivate-wait-policy
```

Expected: The command writes `core-report.md` and `evidence-manifest.json`. The previous failure point, `assertVisible Browse InPrivate`, should pass if the element appears within the driver's 10-second wait.

- [ ] **Step 4: Commit**

Run:

```bash
git add fsq_agent/core/SPEC.md fsq_agent/core/harness/_uiautomator2_driver.py tests/test_uiautomator2_android_driver.py docs/superpowers/specs/2026-06-10-android-driver-wait-policy-design.md docs/superpowers/plans/2026-06-10-android-driver-wait-policy.md
git commit -m "fix: wait for android driver targets"
```

### Self-Review

- Spec coverage: The plan covers driver-owned wait policy, no YAML timeout fields, uiautomator2 built-in wait usage, XPath wait signature compatibility, and `assert_not_visible` inverse behavior.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: No public protocol signatures change; all new helpers are private methods on `UiAutomator2AndroidDriver`.
