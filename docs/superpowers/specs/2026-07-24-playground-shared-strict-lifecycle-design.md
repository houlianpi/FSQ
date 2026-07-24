# Playground Shared Strict Lifecycle Design

## Goal

Make Playground Strict YAML execute the same complete lifecycle sequence as CLI strict runs by introducing a package-private strict lifecycle orchestration service and switching only Playground to it in this cycle.

The lifecycle sequence is:

1. Config `onCaseStart`.
2. Case `onCaseStart`.
3. Main case commands.
4. Case `onCaseComplete`.
5. Config `onCaseComplete`.

CLI behavior, imports, implementation, and tests remain unchanged in this cycle.

## Scope

### In scope

- Add a package-private shared strict lifecycle orchestration module.
- Execute config-level and case-level lifecycle hooks from Playground Strict YAML.
- Support ordered and repeated `runCase` and `runShell` actions.
- Preserve current CLI lifecycle ordering and failure semantics in the new service.
- Preserve recursive `runCase` detection and strict case path resolution policy.
- Execute Windows `runShell` commands through non-interactive Windows PowerShell and other platforms through the local system shell.
- Record lifecycle synthetic steps and child/main command steps into one evidence manifest and core report.
- Feed lifecycle and command events through Playground progress, active-step, preview, replay, and cancellation integrations.
- Use the same service for Playground strict cases with and without lifecycle hooks.

### Non-goals

- Changing CLI to call the shared service.
- Deleting or refactoring `fsq_agent/cli/_case_lifecycle.py`.
- Deduplicating CLI and shared lifecycle implementations in this cycle.
- Changing lifecycle YAML syntax, shared models, loader behavior, or CLI lifecycle semantics.
- Changing dynamic YAML execution.
- Adding lifecycle behavior to `core.StepRunner` or `FsqExecutableStepAdapter`.
- Changing report format or lifecycle evidence schema beyond producing the already-supported lifecycle metadata.

## Confirmed Decisions

- Playground executes both config and case hooks.
- CLI remains on its current private lifecycle implementation.
- Temporary implementation duplication is accepted to reduce migration risk.
- The shared service lives at package root as a private composition helper, not in `core`, `fsq`, `cli`, or `playground`.
- Playground always calls the shared service for strict execution, even when the case contains no hooks.

## Architecture

### Module placement

Add:

```text
fsq_agent/_strict_lifecycle.py
```

The module is package-private and is not exported from `fsq_agent/__init__.py`. It is an entry-layer composition helper permitted by the root architecture rules. It composes public APIs from:

- `config`
- `core`
- `fsq`
- `models`
- `report`

It must not import:

- `fsq_agent.cli` or CLI private modules.
- `fsq_agent.playground` or Playground private modules.
- `capabilities` or decorator internals.
- Concrete backend drivers.

### Python architecture level

The new module is a focused Level 2 internal service. It contains orchestration behavior and injected boundaries but introduces no package, repository, unit of work, framework layer, or public API.

Playground remains a Level 3 Layered Application. It owns task state, browser progress, harness construction, cancellation, and execution adaptation.

### Transitional duplication

The shared service initially mirrors lifecycle behavior from `cli/_case_lifecycle.py`. CLI continues to use its existing implementation unchanged. This duplication is intentional and temporary.

A later separately confirmed cycle may:

- Switch CLI to the shared service.
- Remove duplicated CLI implementation.
- Consolidate shared tests.

No code in this cycle should partially delegate CLI behavior to the shared service.

## Shared Service Interface

The package-private entry point is conceptually:

```python
artifact = run_strict_lifecycle_case(
    case_path=case_path,
    case=case,
    settings=settings,
    harness=harness,
    output_dir=run_dir,
    run_id=run_id,
    registry=registry,
    registry_snapshot=registry_snapshot,
    post_action_delay_seconds=settings.execution.post_action_delay_seconds,
    recorder=recorder,
    resolve_steps=resolve_steps,
    cancellation_check=cancellation_check,
)
```

### Required arguments

- `case_path`: Resolved root case path.
- `case`: Loaded root `FsqCase`.
- `settings`: Runtime settings, including cases directory, config lifecycle hooks, runtime secrets, and post-action policy.
- `harness`: Caller-built harness. The service never selects platform/backend or constructs drivers.
- `output_dir`: Run output directory.
- `run_id`: Root strict run id.
- `registry` and `registry_snapshot`: Active-platform strict capability registry.
- `post_action_delay_seconds`: Existing core runner timing settings.

### Injected boundaries

- `recorder`: Optional EvidenceRecorder-compatible object. When absent, the service constructs a standard `EvidenceRecorder`. Playground supplies `_PlaygroundEvidenceRecorder` so all lifecycle/main events update browser state and share one manifest.
- `resolve_steps`: Callback that receives canonical steps plus case context and returns strict replay-resolved steps. Playground injects its existing runtime-secret resolution path. This prevents the shared service from importing CLI private replay helpers.
- `cancellation_check`: Optional no-argument callback. Playground supplies a callback that raises `PlaygroundTaskCancelled`; absent callback is a no-op.

The recorder boundary requires:

- `record_event(event)`
- `record_step_result(result)`
- `build_bundle()`
- `write_manifest()`

No new public Protocol is required unless implementation shows that local private typing materially improves clarity.

## Lifecycle Behavior

### Ordering

For the root case:

1. Config `onCaseStart` actions in authored order.
2. Case `onCaseStart` actions in authored order.
3. Main case commands.
4. Case `onCaseComplete` actions in authored order.
5. Config `onCaseComplete` actions in authored order.

For child `runCase` cases:

- Execute child case-level lifecycle hooks and main commands recursively.
- Root config hooks apply only to the root case.
- Preserve parent lifecycle phase metadata through nested child execution.

### Failure policy

- Config-before failure skips remaining config-before actions, case-before actions, and main commands.
- Case-before failure skips remaining case-before actions and main commands.
- Case-after hooks run even when before/main failed.
- Root config-after hooks run after case-after hooks even when earlier work failed.
- After-hook execution continues after individual failures.
- Any config hook, case hook, child case, or main command failure fails the overall strict result/report.

### Recursion

Resolve `runCase` values using the same candidate order as strict case inputs. Detect a path already present in the active case stack and raise `ConfigurationError` with the chain before infinite recursion.

### Shell execution

- Windows: `powershell.exe -NoProfile -NonInteractive -Command <authored command>`.
- Other platforms: local system shell using the current `shell=True` behavior.
- Capture exit code and stdout/stderr byte counts.
- Do not expose shell output as model input or change report content beyond existing lifecycle metadata.
- Nonzero exit code produces a failed synthetic lifecycle step with `action_error`.
- Startup failure produces a failed synthetic lifecycle step with a concise error.

### Cancellation

Call `cancellation_check`:

- Before each lifecycle action.
- Before resolving/executing each child case.
- Before adapting/executing each case command group.
- Between completed hook actions.

Main UI actions additionally remain protected by Playground's cancellable harness wrapper. Cancellation exceptions propagate to Playground task cancellation handling rather than becoming ordinary failed hooks.

## Evidence and Reporting

The shared service owns one recorder for the complete root lifecycle run.

It records:

- Synthetic `runShell` lifecycle steps.
- Synthetic parent `runCase` lifecycle result steps.
- Child case command steps.
- Root main command steps.
- Lifecycle phase, hook origin, hook/action indices, root/case paths, case id, hook chain, command/target, exit code, and parent hook metadata.

All events and step results are written into one `evidence-manifest.json`. `CoreEvidenceReportGenerator` generates the existing lifecycle-aware `core-report.md/json` from that manifest.

Playground's recorder receives the same events. It must continue to:

- Update active strict step metadata.
- Update preview when screenshot artifacts are captured.
- Make screenshots discoverable by replay generation.

Synthetic shell hooks normally produce no screenshots. Child/main UI commands retain standard StepRunner evidence.

## Playground Integration

Update `_run_strict_case_yaml`:

1. Resolve and load the root case.
2. Validate platform, provider need, and strict settings.
3. Build active registry and harness exactly as today.
4. Bind the harness to the Playground execution handle.
5. Wrap the harness with `_CancellableHarness`.
6. Construct `_PlaygroundEvidenceRecorder` with root lifecycle metadata.
7. Call the shared strict lifecycle service for every strict case.
8. Pass Playground's strict replay resolver callback and cancellation callback.
9. Read report status and publish existing `run_completed`/TaskResult behavior.

Remove the direct `_run_strict_core_steps` call from Playground strict execution. The old helper may remain only if used by tests or another local path; otherwise remove it after references are verified.

Playground must not import `cli/_case_lifecycle.py`.

## CLI Preservation

This cycle must not modify:

- CLI calls to `run_strict_fsq_lifecycle_case`.
- CLI lifecycle ordering or error behavior.
- CLI collector/executor classes.
- CLI lifecycle tests except where unrelated shared behavior already changed before this design.

`cli/_case_lifecycle.py` remains the CLI source of truth until a later migration cycle.

## Error Handling

- Invalid lifecycle syntax continues to fail in `FsqCaseLoader` before execution.
- Invalid strict command params fail before external UI actions.
- Missing/invalid child case paths fail with case/hook context.
- Recursive `runCase` fails with the full path chain.
- Shell nonzero exits become structured failed hook steps.
- Cancellation propagates as cancellation, not hook failure.
- Report/manifest write failures propagate to Playground task error handling.
- Playground task errors retain structured FSQ context.
- Replay generation occurs only when a strict run result exists; known no-frame runs remain structured unavailable responses rather than secondary 404 errors.

## Affected Specifications

Expected updates:

- Root `SPEC.md`
  - Add the private shared strict lifecycle composition helper to package-root ownership rules/internal structure if that structure is enumerated.
  - Record that Playground may consume it while CLI remains temporarily on its existing private implementation.
- `fsq_agent/playground/SPEC.md`
  - Require full config/case lifecycle orchestration for Strict YAML.
  - Add the package-private shared lifecycle dependency and evidence/cancellation behavior.
  - Update internal execution ownership and testing contract.

No lifecycle behavior change is required in:

- `fsq_agent/cli/SPEC.md` because CLI remains unchanged.
- `fsq_agent/fsq/SPEC.md` because parsing/validation ownership remains unchanged.
- `fsq_agent/core/SPEC.md` because lifecycle orchestration remains entry-layer behavior.
- `fsq_agent/models/SPEC.md` because lifecycle models remain unchanged.

## Verification Expectations

### Shared service tests

- Root config/case before/main/case-after/config-after order.
- Repeated ordered `runCase` and `runShell` actions.
- Combined mapping action order compatibility.
- Config-before and case-before failure skip policy.
- Case/config after hooks continue after failure.
- Child case lifecycle recursion and parent metadata.
- Recursive `runCase` rejection.
- Windows PowerShell and non-Windows shell invocation contracts.
- Shell success, nonzero exit, and startup failure evidence.
- Cancellation before shell, child, and main execution.
- Single manifest/report containing lifecycle and main steps.

### Playground tests

- Strict YAML with case `onCaseStart runShell` executes before main commands.
- Strict YAML with case `onCaseComplete runShell` executes after main commands.
- Config lifecycle hooks surround case lifecycle hooks.
- Child `runCase` executes through shared service.
- Playground recorder receives lifecycle and command events in one manifest.
- Active-step/progress metadata includes lifecycle synthetic steps where applicable.
- Child/main screenshot evidence remains available to preview/replay.
- Before failure skips main and still executes after hooks.
- Cancellation propagates through hooks.
- Strict cases without hooks still execute successfully through the shared service.
- Existing CLI lifecycle test suite remains unchanged and passes.

### Commands

- `python -m pytest tests/test_playground.py tests/test_cli_core_execution.py tests/test_fsq.py tests/test_fsq_executable_step_adapter.py`
- `python -m pytest`
- `git diff --check`
- Independent SPEC implementation audit against root and Playground SPEC plus actual diff.

## Resolved Questions

- Playground executes config and case hooks.
- CLI remains entirely on its existing implementation this cycle.
- The new module is package-private and not exported.
- Recorder, replay resolver, and cancellation are injected.
- Temporary duplication is accepted until a separate CLI migration design.
