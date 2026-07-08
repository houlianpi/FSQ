# Module: fsq

## Purpose

Load FSQ AI Test DSL YAML cases from the merged FSQ testcase repository, including generated strict replay refs and pure waits, resolve authored action names through the platform-selected capability registry, and convert parsed cases into deterministic canonical execution-core steps for strict-core execution. Dynamic LLM execution that uses a YAML file reads that file as raw text in the CLI layer and deliberately bypasses this module.

Goal-only FSQ cases may omit the command document or provide an empty command list; parsed goal-only cases produce no executable steps.

## Dependencies

- `models`: Uses `FsqCase`, `FsqCaseConfig`, shared configuration errors, execution-core contracts such as `ExecutableStep`, `SourceRef`, and `EvidencePolicy`, strict replay refs such as `RuntimeSecretRef`, capability registry snapshots, replay policy metadata, and shared capability parameter models for deterministic command payload normalization and step kind classification.

The fsq module must not import `capabilities`, `core`, or `tools`. It receives a `CapabilityRegistrySnapshot` from entry code and resolves authored command names through that serializable snapshot.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `FsqCaseLoader`: Loads `.codex.yaml` FSQ cases from explicit paths or the configured read-only case directory for strict-core execution. It accepts traditional metadata-plus-command cases and goal-only metadata cases.
- `FsqExecutableStepAdapter`: Converts an `FsqCase` command document into ordered canonical `ExecutableStep` records for deterministic core execution using a registry snapshot.
- `is_fsq_case_file`: Detects FSQ case file names.

The first deterministic step adapter exposes a narrow API:

```python
adapter = FsqExecutableStepAdapter(registry_snapshot=registry.snapshot())
steps = adapter.to_executable_steps(case)
```

`FsqExecutableStepAdapter` resolves authored FSQ action names through canonical capability names and `ReplayPolicy(kind="fsq_command").alias` values in the registry, then stores the canonical capability name in `ExecutableStep.action_name`. Authored names such as `tapOn`, `inputText`, `pressKey`, `assertVisible`, `assert`, `assertWithAI`, `startBrowser`, `closeBrowser`, `clickOn`, `typeText`, `uiSnapshot`, `assertElementsOrder`, and generated replay alias `waitMs` are preserved in `ExecutableStep.metadata["authored_action_name"]`.

The adapter should normalize each known YAML command into `ExecutableStep.params` by resolving the action alias to a `CapabilityDefinition`, validating object-shaped payloads against `capability.params_model`, then storing `model_dump(mode="json", exclude_none=True)`. Known action payloads should be authored in the same field shape as their parameter models rather than relying on action-specific scalar shorthand. The first-batch canonical forms are grouped by active platform PlatformTools plus inherited CommonTool commands. AgentTools are not present in strict registries and cannot appear as executable FSQ commands.

Android command block:

| FSQ command shape | canonical `action_name` | `params` |
|---|---|---|
| `launchApp` | `launch_app` | `{}` |
| `killApp` | `kill_app` | `{}` |
| `pressKey: {key: Enter}` | `press_key` | `{"key": "Enter"}` |
| `tapOn: {target: Login}` | `tap_on` | `{"target": "Login"}` |
| `inputText: {text: bing.com, ...}` | `input_text` | validated `AndroidInputTextParams` dump |
| `assertVisible: {...}` | `assert_visible` | validated `AndroidAssertVisibleParams` dump |
| `assertNotVisible: {...}` | `assert_not_visible` | validated `AndroidAssertNotVisibleParams` dump |
| `longPressOn: {...}` | `long_press_on` | validated `AndroidLongPressOnParams` dump |
| `swipe: {...}` | `swipe` | validated `AndroidSwipeParams` dump |
| `assert: {element: ..., text: ...}` | `assert_state` | validated `AndroidAssertStateParams` dump |
| `assertWithAI: {prompt: ...}` | `assert_with_ai` | validated `AndroidAssertWithAIParams` dump |
| `inputText: {text: {runtimeSecret: TEST_PASSWORD}, ...}` | `input_text` | pre-resolution params preserving `{"text": {"runtimeSecret": "TEST_PASSWORD"}}` for strict entry resolution |

Web command block:

| FSQ command shape | canonical `action_name` | `params` |
|---|---|---|
| `startBrowser: {}` | `start_browser` | validated `WebStartBrowserParams` dump |
| `closeBrowser: {}` | `close_browser` | validated `WebCloseBrowserParams` dump |
| `navigateTo: {url: https://example.test}` | `navigate_to` | validated `WebNavigateToParams` dump |
| `navigateBack: {}` | `navigate_back` | validated `WebNavigateBackParams` dump |
| `clickOn: {target: Submit}` | `click_on` | validated `WebClickOnParams` dump |
| `typeText: {target: Email, text: user@example.test}` | `type_text` | validated `WebTypeTextParams` dump |
| `selectOption: {target: Country, values: [US]}` | `select_option` | validated `WebSelectOptionParams` dump |
| `hoverOn: {target: Menu}` | `hover_on` | validated `WebHoverOnParams` dump |
| `waitFor: {text: Loaded}` | `wait_for` | validated `WebWaitForParams` dump |
| `takeScreenshot: {full_page: true}` | `take_screenshot` | validated `WebTakeScreenshotParams` dump |
| `assertText: {text: {contains: Welcome}}` | `assert_text` | validated `WebAssertTextParams` dump |
| `pageSnapshot: {}` | `page_snapshot` | validated `WebPageSnapshotParams` dump |

macOS command block:

| FSQ command shape | canonical `action_name` | `params` |
|---|---|---|
| `launchApp: {}` | `launch_app` | validated `MacOSLaunchAppParams` dump |
| `killApp: {}` | `kill_app` | validated `MacOSKillAppParams` dump |
| `clickOn: {target: Submit}` | `click_on` | validated `MacOSClickOnParams` dump |
| `clickOn: {point: {x: 120, y: 240}}` | `click_on` | validated `MacOSClickOnParams` dump with explicit point |
| `doubleClickOn: {target: File}` | `double_click_on` | validated `MacOSDoubleClickOnParams` dump |
| `rightClickOn: {target: File}` | `right_click_on` | validated `MacOSRightClickOnParams` dump |
| `typeText: {target: Search, text: query}` | `type_text` | validated `MacOSTypeTextParams` dump |
| `pressKey: {key: Enter}` | `press_key` | validated `MacOSPressKeyParams` dump |
| `hoverOn: {target: Menu}` | `hover_on` | validated `MacOSHoverOnParams` dump |
| `dragTo: {source: {target: File}, destination: {target: Folder}}` | `drag_to` | validated `MacOSDragToParams` dump |
| `takeScreenshot: {}` | `take_screenshot` | validated `MacOSTakeScreenshotParams` dump |
| `uiSnapshot: {}` | `ui_snapshot` | validated `MacOSUiSnapshotParams` dump |
| `assertVisible: {target: Done}` | `assert_visible` | validated `MacOSAssertVisibleParams` dump |
| `assertElementsOrder: {direction: vertical, elements: [...]}` | `assert_elements_order` | validated `MacOSAssertElementsOrderParams` dump |
| `assertWithAI: {prompt: ...}` | `assert_with_ai` | validated `MacOSAssertWithAIParams` dump |

Shared command block:

| FSQ command shape | canonical `action_name` | `params` |
|---|---|---|
| `waitMs: {duration_ms: 1000, reason: settle}` | `wait_ms` | validated `WaitMsParams` dump |

For commands containing `runtimeSecret` replay refs, `FsqExecutableStepAdapter` may validate the non-secret shape using placeholder text while preserving the `RuntimeSecretRef` object/dict in `ExecutableStep.params`. Final capability parameter validation with the real secret value is owned by the strict CLI entry after in-memory resolution.

Runner-owned metadata such as valid `timeout` values should be extracted before driver parameter validation and stored in `ExecutableStep.timeout_ms`, not passed through to driver parameter models. The original raw command remains available in `ExecutableStep.metadata` for evidence and debugging.

Step kind mapping for known actions is owned by capability metadata:

| Authored alias | `ExecutableStep.kind` |
|---|---|
| `launchApp` | `setup` |
| `killApp` | `teardown` |
| `startBrowser` | `setup` |
| `closeBrowser` | `teardown` |
| `assert`, `assertVisible`, `assertNotVisible`, `assertText`, `assertElementsOrder`, `assertWithAI` | `assertion` |
| `takeScreenshot`, `startRecording`, `stopRecording`, `pageSnapshot`, `uiSnapshot` | `observation` |
| `waitMs` | `action` |
| all other commands | `action` |

Each generated step should include:

- `step_id`: stable within the case, using the case id and one-based command index, for example `fundamental_test_bing_com_website-step-001`.
- `source_ref`: `source_type="fsq"`, `source_id` set to the case path string, `step_index` set to the zero-based command index, and metadata containing the case name and platform.
- `metadata`: the original command payload, `authored_action_name`, canonical `capability_name`, replay metadata when applicable, and selected case metadata useful for evidence and debugging.
- `timeout_ms`: copied from command object `timeout` when present and valid.
- `evidence_policy`: default shared model policy. Rich FSQ evidence controls are a later batch; during execution, `core.StepRunner` derives the effective evidence policy from capability metadata and any explicit step policy.

Malformed command entries that cannot be reduced to one FSQ action must raise `ConfigurationError` with the case path and command index. Unknown actions, ambiguous replay aliases, actions without active `fsq_command` replay support in strict input, and payloads that fail the resolved capability parameter model validation must also raise `ConfigurationError` before execution starts, with enough context to identify the case path, command index, action name, and validation problem. A generated `inputText.text.runtimeSecret` ref is valid only as a pre-resolution replay value; other redaction markers or unresolved secret-like objects are invalid. Optional commands are still converted into executable steps; optional/non-blocking execution semantics belong to the core runner or a later policy layer, not this adapter.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: YAML parsing, validation of FSQ document shape, goal-only case normalization, and batch discovery.
- `_step_adapter.py`: Converts loaded FSQ commands into ordered canonical `ExecutableStep` records using a capability registry snapshot.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 2 Simple Package.
- Public API: `FsqCaseLoader`, `FsqExecutableStepAdapter`, and `is_fsq_case_file` exported from `__init__.py`.
- Internal modules: `_loader.py` and `_step_adapter.py` are private implementation modules.
- Domain boundaries: this module owns deterministic YAML loading and conversion to shared executable-step contracts. It does not execute steps, resolve real secrets, construct registries, create harnesses, or generate reports.
- Boundary models: parsed cases, executable steps, runtime secret refs, and capability metadata models come from `models`.
- Dependency direction: imports public `models` only; registry snapshots are passed in by entry modules.
- Rationale: focused parsing/normalization behavior fits Level 2 and does not require orchestration layers.

## Error Handling

Invalid FSQ YAML raises `ConfigurationError` with the failing path. Unsupported schema versions, missing platform values, and malformed command documents are rejected before strict-core execution starts. A missing command document or empty command list is valid only as a goal-only case and is normalized to `commands=[]`.

## Design Decisions

- `.codex.yaml` is the canonical test case input format.
- Single-document `.codex.yaml` files containing only valid case metadata are supported as goal-only cases. Two-document cases with `[]` or an otherwise empty command list are also goal-only cases.
- Configured `cases.dir` is treated as read-only input. Strict-core execution may parse FSQ case files from it, while dynamic LLM execution may read case files from it as raw text. Generated files and evidence must be written under the output root.
- Markdown conversion reports are intentionally ignored and are not loaded as task inputs.
- FSQ commands are deterministic ordered input for the strict-core execution path when converted by `FsqExecutableStepAdapter`. Generated recorded cases may include strict replay refs and pure wait commands, but those are still deterministic authored input by the time strict execution begins.
- Deterministic command payload normalization uses the platform-selected capability registry snapshot. Authored command payloads use the same object field names as the resolved capability parameter models, which keeps case parsing, future case generation, harness dispatch, and SDK schemas aligned to one payload contract while preserving authored names in metadata. Strict replay refs are the sole exception: the adapter may preserve `RuntimeSecretRef` values in pre-resolution params so the CLI strict entry can resolve them before final validation.
- Capability decorators and platform action catalogs are declaration-time inputs only. FSQ parsing consumes resolved `CapabilityDefinition` data from the registry snapshot and must not inspect decorated functions or platform catalog objects directly.
- `waitMs` is a generated strict replay alias for the inherited `wait_ms` CommonTool capability. It is validated by `WaitMsParams`, converted into an `ExecutableStep(action_name="wait_ms")`, and later handled by `StepRunner` through the normal registry path without invoking Android gesture or Web page actions.
- `assertWithAI` is parsed and validated like any other authored assertion command. This module does not evaluate AI assertions, build provider-backed evaluators, capture screenshots, or decide assertion verdicts.
- Web replay aliases such as `startBrowser`, `closeBrowser`, `navigateTo`, `navigateBack`, `clickOn`, `typeText`, `selectOption`, `hoverOn`, `waitFor`, `takeScreenshot`, `assertText`, and `pageSnapshot` are accepted only when the supplied registry snapshot contains the corresponding Web capabilities. Android registries must not accept Web-only replay aliases, and Web registries must not accept Android-only replay aliases.
- macOS replay aliases such as `launchApp`, `killApp`, `clickOn`, `doubleClickOn`, `rightClickOn`, `typeText`, `pressKey`, `hoverOn`, `dragTo`, `takeScreenshot`, `uiSnapshot`, `assertVisible`, `assertElementsOrder`, and `assertWithAI` are accepted only when the supplied registry snapshot contains the corresponding macOS capabilities. Shared replay aliases resolve to the active platform's capability definition from the registry snapshot; replay aliases unique to another platform remain invalid.
- `launchApp`/`killApp` and `startBrowser`/`closeBrowser` are treated as setup and teardown step kinds for strict-core execution. A trailing `closeBrowser` command should be passed to `StepSequenceRunner` as teardown so it still executes after an earlier normal-step failure.
- Commands marked `optional: true` are still converted into executable steps; optional/non-blocking execution semantics do not belong to this adapter.
- Parsed FSQ cases are not converted into LLM `Task` descriptions. For normal LLM `run --case-yaml` and `run --case-dir`, the CLI reads raw file text and builds goal/reference tasks without calling this module.
- `FsqExecutableStepAdapter` must not import or call `core`; it produces shared model contracts only. Higher-level entry code is responsible for passing those steps into core runners.
