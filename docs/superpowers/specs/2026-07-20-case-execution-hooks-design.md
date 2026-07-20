# Case Execution Hooks Design

Date: 2026-07-20
Status: Confirmed design for SPEC handoff after user review

## Goal

Add strict-mode case lifecycle hooks to recorded FSQ `.codex.yaml` cases so an operator can manually edit an existing recorded case and declare work to run immediately before and immediately after the main case body.

The FSQ lifecycle hook metadata lives in the case configuration document and is executed by strict replay around the main command document:

```yaml
schemaVersion: fsq.ai-test/v1
name: Checkout smoke
platform: web
onCaseStart:
  - runCase: hooks/login.codex.yaml
  - runShell: echo preparing checkout smoke
onCaseComplete:
  - runShell: echo cleaning up checkout smoke
  - runCase: hooks/logout.codex.yaml
---
- startBrowser: {}
- navigateTo:
    url: https://example.test/checkout
- assertVisible:
    target: Checkout
- closeBrowser: {}
```

Strict execution should run:

```text
onCaseStart hooks -> main case commands -> onCaseComplete hooks
```

Each lifecycle phase is independently optional. A case may declare only `onCaseStart`, only `onCaseComplete`, both, or neither.

## Scope

This design covers only strict-mode execution of authored or manually edited `.codex.yaml` files.

Hook declarations are added to the first YAML document, the same metadata/configuration section that already owns case identity, platform, tags, environment metadata, and properties. FSQ names the lifecycle fields `onCaseStart` and `onCaseComplete` because the executable unit in this repository is a case.

Two hook action formats are supported in this cycle:

- `runCase: relative/path.codex.yaml`: execute another recorded FSQ YAML file before returning to the current lifecycle phase.
- `runShell: command string`: execute an operator-authored shell command exactly as provided.

Hook fields may be either a single mapping or a list of mappings. Within each hook entry, `runCase` and `runShell` are independently optional supported actions: an entry may contain only `runCase`, only `runShell`, or both. At least one supported action must be present. When both are present in the same hook entry, FSQ-Agent should execute them in the order configured in YAML. The normalized model should expose ordered hook entries for each declared phase, preserve action order within each entry, and expose empty lists for missing phases.

```yaml
onCaseStart:
  runShell: ./scripts/mark-login-ready.sh
  runCase: hooks/login.codex.yaml

onCaseComplete:
  runShell: ./scripts/cleanup-test-user.sh
```

## Non-Goals

- Do not implement the playground UI for adding hooks in this cycle.
- Do not add CLI flags or commands for generating hooks.
- Do not modify source cases automatically during dynamic recording, strict execution, or playground execution.
- Do not add dynamic LLM execution semantics for hooks. Dynamic `run --case-yaml` continues to read raw case text as planning input material.
- Do not support hook actions beyond `runCase` and `runShell`, per-hook environment overrides, conditional hooks, parameters, JavaScript hooks, or arbitrary nested hook objects in this cycle.
- Do not validate whether `runShell` is appropriate for Windows, Linux, or macOS. The command string is operator-owned.
- Do not introduce recovery, self-healing, locator fallback, or AI repair around hooks.

## Proposed Design

### YAML Shape

Add two optional fields to `FsqCaseConfig`:

- `onCaseStart`
- `onCaseComplete`

Each field is independently optional and accepts either one hook entry or an ordered list of hook entries when present. A hook entry must be a mapping containing `runCase`, `runShell`, or both:

```yaml
onCaseStart:
  - runCase: hooks/setup-account.codex.yaml
```

```yaml
onCaseComplete:
  - runShell: ./scripts/delete-account.sh
```

Both hook phases may be present when a case needs both setup and cleanup. A hook phase may mix `runCase` and `runShell` either inside one entry or by ordering multiple entries. Both forms are valid, and order is authored order:

```yaml
onCaseComplete:
  - runShell: ./scripts/cleanup-test-user.sh
    runCase: hooks/reset-browser.codex.yaml
  - runShell: ./scripts/remove-temp-files.sh
```

When one entry contains both actions, actions run in the YAML order within that mapping. When separate entries are used, entries run in list order.

`runCase` values are workspace-relative or `cases.dir`-relative paths resolved with the same relative-path behavior as current strict `--case-yaml` input: prefer `cases.dir`, then the current working directory. The target must resolve to an FSQ `.codex.yaml` file.

`runShell` values are non-empty strings. FSQ-Agent should pass the string to the local shell execution boundary without platform-specific content validation.

### Hook Model

`models` should own shared hook contracts because parsed hooks cross module boundaries between `fsq`, `cli`, and strict execution helpers.

Add a small set of Pydantic models near the existing FSQ case models:

- `FsqCaseHook`: validated model representing one hook entry that may contain `runCase`, `runShell`, or both, while preserving the authored action order within the entry.
- `FsqCaseHooks`: normalized lifecycle grouping with `on_case_start` and `on_case_complete` lists, if a grouping helper is useful.

The public `FsqCaseConfig` model should expose Pythonic field names with YAML aliases:

- `on_case_start = Field(alias="onCaseStart")`
- `on_case_complete = Field(alias="onCaseComplete")`

Unknown metadata fields remain allowed as today, but hook fields themselves must reject malformed hook entries. The hook model should not collapse a combined entry into unordered Pydantic fields if doing so would lose whether the user configured `runShell` before `runCase` or `runCase` before `runShell`; it may store an ordered list of normalized hook actions or an equivalent explicit order field.

### Module Ownership

- `models`: owns hook data models and validation of supported hook entry shapes.
- `fsq`: loads hook metadata from the first YAML document and validates hook syntax as part of `FsqCaseLoader`/`FsqCaseConfig` validation. It should continue to convert only a case's own command document into `ExecutableStep` records.
- `cli`: owns strict entry orchestration for hook expansion and shell execution because it already resolves case paths, runtime secrets, reports, run directories, and entry-layer side effects.
- `core`: continues to execute canonical `ExecutableStep` lists through `StepRunner` and `StepSequenceRunner`. It should not parse hook YAML, resolve hook file paths, or execute shell commands directly unless a future SPEC promotes shell execution into a recordable capability.
- `report`: consumes evidence manifests and runner results. Hook phase metadata should be visible through step/source metadata, but report internals should not own hook orchestration.
- `playground`: no UI changes in this cycle. If playground strict execution already delegates to the same strict helper, it can inherit hook behavior without a new editing surface.

### Control Flow

Strict execution of one case should use a lifecycle runner at the CLI boundary:

1. Load and validate the root case.
2. Resolve root `onCaseStart` and `onCaseComplete` declarations.
3. Execute `onCaseStart` hook entries in declared order.
4. If every `onCaseStart` hook passes, execute the main case commands exactly as authored.
5. Always execute `onCaseComplete` hook entries in declared order after `onCaseStart` has been attempted, including when `onCaseStart` fails or the main case fails.
6. Mark the overall case failed if any before hook, main command, after hook, or shell hook fails.

Within each hook entry, execute contained `runCase` and `runShell` actions in the YAML order configured by the operator.

Strict lifecycle failure behavior is:

- If `onCaseStart` fails, the main case body is skipped and `onCaseComplete` still runs.
- If the main case body fails, `onCaseComplete` still runs.
- If `onCaseComplete` fails, the overall strict case fails even when the main body passed.

Nested `runCase` hooks execute the target case's main commands. To prevent accidental recursion, a strict lifecycle runner must track the active `runCase` stack by resolved path and fail fast with `ConfigurationError` if a case tries to run itself directly or indirectly through hooks.

### `runCase` Hook Semantics

`runCase` should execute another `.codex.yaml` using the active platform registry and harness binding from the parent strict run. The hook case path resolution should match strict relative path behavior and should occur before external UI actions for that hook begin.

The hook case may have its own `onCaseStart` and `onCaseComplete` declarations, subject to recursion detection. This keeps lifecycle semantics composable and avoids a surprising special case where hook cases ignore their own metadata.

Step identity and source metadata should remain auditable:

- `source_ref.source_id` uses the hook case path for hook case commands.
- `metadata` includes lifecycle phase such as `onCaseStart`, `case`, or `onCaseComplete`.
- `metadata` includes the root case path and parent hook chain when applicable.

The implementation should preserve existing strict teardown behavior inside each executed case: trailing `teardown` steps in that case still run after failures in that case's normal steps.

### `runShell` Hook Semantics

`runShell` executes a local shell command string as a hook step and contributes pass/fail status to the lifecycle result.

The first implementation should keep shell execution an entry-layer hook side effect rather than a new recordable FSQ capability, because the user only asked for manual hook declarations and strict lifecycle execution. Shell commands are not platform automation actions, do not need capability registry aliases, and should not be exposed to the dynamic LLM action surface in this cycle.

Shell execution should capture enough evidence for debugging without leaking secrets intentionally printed by the command:

- command string
- exit code
- bounded stdout/stderr previews or artifact paths, following existing output artifact policy if available
- lifecycle phase and hook index

A non-zero exit code fails the hook. Process launch failures also fail the hook with a configuration or action error category appropriate to the existing runner/report contracts.

### Directory Strict Runs

`fsq-agent run --strict --case-dir PATH` should continue to discover top-level cases from the requested directory and execute them serially. Hook `runCase` targets are dependencies of an individual case execution, not additional top-level cases in the directory summary.

If a discovered top-level case and another case's hook both point to the same file, that file may execute once as a top-level case and once as a hook dependency. The directory runner should report top-level case results as it does today, while hook failures are reflected in the owning top-level case result.

### Error Handling And Edge Cases

- Malformed hook fields fail during FSQ case loading before external UI actions begin.
- Unknown hook actions fail during FSQ case loading.
- Hook entries with neither `runCase` nor `runShell` fail during FSQ case loading.
- Hook entries with both `runCase` and `runShell` are valid; if either contained value is empty or invalid, loading fails for that field.
- Empty `runCase` paths or empty `runShell` commands fail during FSQ case loading.
- Missing `runCase` files fail before that hook begins external actions.
- `runCase` paths must resolve to `.codex.yaml` files.
- Recursive hook chains fail fast with a path chain in the error context.
- Runtime secret resolution remains per executable step before the step is invoked. Hook case steps use the same strict replay secret validation as main case steps.
- Shell command contents are not inspected for portability, destructive behavior, or secrets in this cycle.

## Python Architecture Level And Rationale

The affected modules keep their current architecture levels:

- `models`: Level 2 Simple Package. Hook Pydantic models are shared boundary contracts and fit the existing model ownership.
- `fsq`: Level 2 Simple Package. It validates YAML shape and normalized hook metadata without orchestrating execution.
- `cli`: Level 3 Layered Application. It coordinates strict lifecycle execution, path resolution, shell side effects, hook recursion detection, evidence/report handoff, and per-case status aggregation.
- `core`: Level 3 Layered Application, unchanged. It remains the canonical step execution engine and should not learn YAML hook syntax.

A heavier architecture level is not justified. Hooks are lifecycle orchestration around existing strict execution, not a new domain model, persistence layer, plugin system, or cross-cutting application framework.

## Affected Specs Expected To Change

- Root `SPEC.md`: add strict case lifecycle hook behavior to the Recorded Strict Case Artifacts and/or Platform Blocks sections.
- `fsq_agent/models/SPEC.md`: add hook models to the FSQ case model public contract and describe validation rules.
- `fsq_agent/fsq/SPEC.md`: document hook fields in the metadata document, supported hook entry shapes, malformed hook errors, and the fact that `FsqExecutableStepAdapter` still converts only command documents into executable steps.
- `fsq_agent/cli/SPEC.md`: document strict lifecycle execution order, path resolution, shell hook execution, recursion detection, directory-run aggregation, and FSQ lifecycle failure semantics.
- `fsq_agent/core/SPEC.md`: likely unchanged unless implementation chooses to represent shell hooks as core runner steps. This design recommends keeping shell hook execution at the CLI boundary for this cycle.
- `fsq_agent/report/SPEC.md`: likely unchanged unless report output needs explicit hook phase sections beyond existing evidence manifest data.
- `fsq_agent/playground/SPEC.md`: likely unchanged unless strict playground execution bypasses CLI helpers and must explicitly adopt the lifecycle runner.

## Open Questions Resolved

- Hook naming: use `onCaseStart` and `onCaseComplete` as explicit FSQ case lifecycle events, not `beforeCase`/`afterCase`.
- Hook location: store hooks in the first YAML metadata document, not a third document and not pseudo-commands inside the command list.
- Hook optionality: `onCaseStart` and `onCaseComplete` are independently optional. Within a hook entry, `runCase` and `runShell` are also independently optional supported fields; an entry may contain either one or both.
- Supported hook formats: only `runCase` and `runShell` are in scope for this cycle. A hook entry must contain at least one of them.
- Combined hook entry ordering: when one hook entry contains both `runCase` and `runShell`, execute them in the YAML order configured by the operator.
- Failure behavior: before-hook failure skips the main case but still runs after hooks; after-hook failure fails the overall case.
- Shell portability: FSQ-Agent does not validate whether a shell command is written for Windows, macOS, or Linux.
- Hook authoring UI: no playground UI or automatic trigger for adding hooks in this cycle; manual offline YAML editing is sufficient.

## Verification Expectations

The implementation cycle should include focused tests for:

- `FsqCaseLoader` accepts `onCaseStart` and `onCaseComplete` with single-entry and list-entry forms.
- `FsqCaseLoader` accepts cases with only `onCaseStart`, only `onCaseComplete`, both hook phases, or no hook phases.
- `FsqCaseLoader` accepts hook entries containing only `runCase`, only `runShell`, or both fields together.
- `FsqCaseLoader` rejects malformed hook entries, unknown hook actions, entries with neither supported action, empty paths, and empty shell commands.
- Strict execution preserves configured YAML order inside a combined hook entry, including `runShell` before `runCase` and `runCase` before `runShell`.
- Strict single-case execution runs before hooks, main commands, and after hooks in order.
- If a before hook fails, main commands are skipped and after hooks still run.
- If a main command fails, after hooks still run and the overall case fails.
- If an after hook fails, the overall case fails even when before hooks and main commands pass.
- `runCase` paths resolve with the same relative behavior as strict `--case-yaml` paths.
- Recursive `runCase` hook chains fail before infinite execution.
- Hook case steps preserve source metadata for the hook file and include lifecycle phase metadata.
- `runShell` executes a command string, records exit status/output evidence, passes on exit code 0, and fails on non-zero exit code.
- Strict `--case-dir` summaries attribute hook failures to the owning top-level case without adding hook dependency files as separate top-level results.

Focused verification commands after implementation on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fsq.py tests/test_fsq_executable_step_adapter.py tests/test_cli_core_execution.py tests/test_cli.py
```

Broader strict replay and report tests should run if implementation touches evidence manifests, reports, playground strict execution, or core runner contracts.

## Self-Review

- The design fits one SPEC update cycle centered on `models`, `fsq`, and `cli`.
- The hook syntax is explicit, manually editable, and expressed as FSQ case lifecycle metadata.
- The design keeps dynamic raw-case execution unchanged.
- The design avoids adding playground UI, automatic hook insertion, recovery behavior, or a shell capability surface outside the user's requested scope.
- Hook failure behavior is explicit and confirmed.
- No unresolved requirement markers remain.