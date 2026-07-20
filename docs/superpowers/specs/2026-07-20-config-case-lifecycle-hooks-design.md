# Config Case Lifecycle Hooks Design

Date: 2026-07-20
Status: Confirmed design for SPEC handoff after user review

## Goal

Allow platform config YAML files such as `config.android.yaml` to declare reusable strict case lifecycle hooks. This lets operators keep common setup and cleanup flows in a few config files instead of manually adding the same `onCaseStart` and `onCaseComplete` entries to many recorded cases.

The strict lifecycle execution order becomes:

```text
config onCaseStart -> case onCaseStart -> main case commands -> case onCaseComplete -> config onCaseComplete
```

## Scope

This design covers strict-mode execution only. The new config field is a top-level `caseLifecycle` block in platform config YAML files:

```yaml
caseLifecycle:
  onCaseStart:
    - runCase: cases/hooks/login.codex.yaml
    - runShell: echo config before
  onCaseComplete:
    - runShell: echo config after
```

`caseLifecycle.onCaseStart` and `caseLifecycle.onCaseComplete` use the same hook entry syntax as case-level lifecycle metadata:

- Each lifecycle field is optional.
- Each lifecycle field may be a single mapping or a list of mappings.
- Each hook entry may contain `runCase`, `runShell`, or both.
- Each hook entry must contain at least one supported action.
- When one hook entry contains both `runCase` and `runShell`, strict execution preserves the configured YAML order.

The implementation should also add a repository-root `config.example.yaml` as a human-readable reference example for optional config fields such as `caseLifecycle`. This file is documentation-like sample YAML only: it must not become a runtime preset, and default config discovery must continue to ignore `config.example.yaml`.

## Non-Goals

- Do not add config-level hooks to dynamic LLM `--case-yaml` or `--case-dir`; dynamic case inputs remain raw planning text.
- Do not add CLI flags for selecting hooks. Operators switch hook sets by choosing or editing config files and platform presets.
- Do not add playground UI for editing config-level hooks in this cycle.
- Do not support hook actions beyond `runCase` and `runShell`.
- Do not add per-hook environment overrides, conditionals, parameters, JavaScript hooks, or platform-specific shell validation.
- Do not mutate recorded cases based on config hooks.

## Proposed Design

### YAML Shape

Add a top-level `caseLifecycle` block to `Settings` and platform presets:

```yaml
caseLifecycle:
  onCaseStart:
    runCase: hooks/login.codex.yaml
  onCaseComplete:
    - runShell: echo cleanup complete
```

The field name is intentionally separate from `cases.dir`. `cases` owns input discovery and path roots; `caseLifecycle` owns execution lifecycle policy.

Add a root-level `config.example.yaml` showing a complete reference shape for one platform, including the optional `caseLifecycle` block. It should make clear through comments that operators normally use `config.android.yaml`, `config.web.yaml`, `config.windows.yaml`, or `config.macos.yaml` for public CLI platform runs, and that `config.example.yaml` is a copy/reference starting point for manual local config experiments only.

The config hook entry schema should reuse the existing FSQ lifecycle hook models so config-level and case-level hooks cannot drift. The model should expose Pythonic field names with aliases:

- `case_lifecycle.on_case_start` from `caseLifecycle.onCaseStart`
- `case_lifecycle.on_case_complete` from `caseLifecycle.onCaseComplete`

### Execution Order

Strict execution of one root case should run lifecycle phases in this order:

1. Config `onCaseStart` hooks.
2. Case `onCaseStart` hooks.
3. Main case command body, only when all before hooks passed.
4. Case `onCaseComplete` hooks.
5. Config `onCaseComplete` hooks.

After hooks must run after before hooks have been attempted, including when config before hooks, case before hooks, or the main case body fail.

If any config before hook fails, the case before hooks and main case body are skipped, but case after hooks and config after hooks still run. If any case before hook fails, the main case body is skipped, but case after hooks and config after hooks still run. If any main, case after, or config after step fails, the overall strict case fails.

### Path Resolution

Config-level `runCase` paths should use the same strict relative path policy already used by strict `--case-yaml` inputs and case-level `runCase` hooks: prefer `settings.cases.dir`, then the current working directory.

This means platform configs can use paths under the configured case directory for reusable hooks:

```yaml
caseLifecycle:
  onCaseStart:
    runCase: hooks/common-login.codex.yaml
```

### Directory Runs

For `fsq-agent run --strict --case-dir PATH`, config-level hooks apply to every top-level case in the directory run. A config-level `runCase` hook target is a dependency of each top-level case execution, not its own top-level directory result.

Top-level case discovery should exclude hook dependency files referenced by either config-level hooks or case-level hooks when those files are inside the discovered directory tree.

### Recursion Detection

Recursive hook chains must include both config-level and case-level `runCase` dependencies. A case that appears in the active stack through config hooks, case hooks, or nested hook cases must fail with `ConfigurationError` before infinite execution.

### Report And Logs

Existing lifecycle report and strict progress logging should include config hooks without a separate report format. Config before hooks should appear under `Before case`; config after hooks should appear under `After case`. The step/source metadata should include the hook origin, such as `config` or `case`, so JSON evidence can distinguish a config hook from a case hook even when both are grouped under the same lifecycle phase.

### Module Ownership

- `models`: owns reusable lifecycle hook models and adds a config lifecycle settings model that reuses them.
- `config`: loads and validates `caseLifecycle` from config YAML through `Settings`. It does not execute hooks, resolve hook paths, or run shell commands.
- `cli`: owns strict lifecycle orchestration and combines config-level and case-level hooks in the required order.
- `fsq`: continues to load case-level lifecycle metadata from `.codex.yaml` files. It does not read config-level hooks.
- `report`: consumes persisted lifecycle metadata and should not need new execution knowledge beyond the existing lifecycle fields and hook origin metadata.

## Python Architecture Level And Rationale

The affected modules keep their current architecture levels:

- `models`: Level 2 Simple Package. Config lifecycle hook settings are shared Pydantic boundary contracts.
- `config`: Level 2 Simple Package. It validates and normalizes YAML settings without executing lifecycle behavior.
- `cli`: Level 3 Layered Application. It coordinates strict execution order, shell side effects, path resolution, recursion detection, reports, and exit behavior.
- `fsq`: Level 2 Simple Package, unchanged ownership for case-level hook metadata.
- `report`: Level 2 Simple Package, unchanged persisted-evidence rendering ownership.

No heavier architecture pattern is justified because this feature extends the existing strict lifecycle orchestration rather than introducing persistence, plugins, or a new domain subsystem.

## Affected Specs Expected To Change

- Root `SPEC.md`: document config-level lifecycle hook support and strict precedence.
- `fsq_agent/models/SPEC.md`: add the config lifecycle settings model to public contracts.
- `fsq_agent/config/SPEC.md`: add `caseLifecycle` YAML shape, validation ownership, and path policy notes.
- `config.example.yaml`: create a reference-only example that demonstrates `caseLifecycle` and other common optional fields without changing runtime preset selection.
- `fsq_agent/cli/SPEC.md`: update strict lifecycle ordering, directory-run dependency filtering, recursion detection, and logging/report metadata expectations.
- `fsq_agent/fsq/SPEC.md`: likely unchanged except if implementation needs to clarify that config hooks are outside `fsq` ownership.
- `fsq_agent/report/SPEC.md`: likely unchanged unless implementation adds explicit hook-origin display requirements beyond existing lifecycle grouping.

## Open Questions Resolved

- Config field name: use top-level `caseLifecycle`.
- Hook syntax: reuse existing `onCaseStart` and `onCaseComplete` lifecycle names and hook entry shape.
- Precedence: config before hooks run before case before hooks; config after hooks run after case after hooks.
- Config-level hooks apply only to strict execution.
- Config-level `runCase` paths use the same strict relative path policy as existing strict case inputs and case-level hooks.
- Add `config.example.yaml` as a reference-only sample. It must not be loaded by default config discovery and must not replace platform presets.

## Verification Expectations

Implementation should include focused tests for:

- `Settings` loads omitted `caseLifecycle` as empty hooks.
- `Settings` loads `caseLifecycle.onCaseStart` and `caseLifecycle.onCaseComplete` with single-entry and list-entry forms.
- Config hook validation rejects unknown hook actions, empty `runCase`, empty `runShell`, malformed hook fields, and entries with no supported action.
- `config.example.yaml` exists, includes a commented or explicit `caseLifecycle` example, and is not used by `load_platform_settings` or default config discovery.
- Strict single-case execution order is config before, case before, main case body, case after, config after.
- Config before failure skips case before and main case body but still runs case after and config after.
- Case before failure still runs case after and config after.
- Config after failure fails the overall strict case.
- Strict directory runs apply config hooks to each top-level case and exclude config hook dependencies from top-level summaries.
- Reports/log metadata can distinguish config hooks from case hooks in JSON evidence while still grouping them under before or after lifecycle phases.

Focused verification commands on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_cli_core_execution.py tests/test_cli.py
```

Broader tests should run if implementation changes shared hook models, report rendering, or strict directory aggregation behavior.

## Self-Review

- The design fits one SPEC update cycle centered on `models`, `config`, and `cli`.
- The config shape is explicit and separate from case discovery settings.
- Config hooks reuse existing case hook syntax instead of creating a parallel DSL.
- Strict execution order and failure behavior are explicit.
- Dynamic raw-case execution remains unchanged.
- No unresolved requirement markers remain.