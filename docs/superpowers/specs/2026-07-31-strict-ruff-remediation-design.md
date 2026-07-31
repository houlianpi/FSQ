# Strict Ruff Configuration And Remediation Design

## Goal

Define and enforce a focused Ruff policy for FSQ, based on the Societas backend configuration and augmented with repository-specific safeguards, then repair the complete tracked Python codebase until lint and formatting pass.

A successful implementation leaves the repository with:

- One pinned Ruff version in the development dependency set.
- One explicit Ruff configuration covering the selected high-value rule families.
- Zero Ruff lint violations and zero Ruff formatting differences.
- The full Python test suite passing after remediation.

## Scope

### Included

- Add Ruff to the pinned `dev` dependency set and update `uv.lock`.
- Configure Ruff lint and format policy in `pyproject.toml`.
- Apply Ruff formatting to the complete tracked Python surface.
- Apply reviewed safe fixes and manually repair all remaining findings.
- Refactor behavior-sensitive findings without weakening existing module boundaries or public contracts.
- Update contributor documentation with the exact Ruff commands.
- Add concise root `SPEC.md` current-fact requirements for repository Python quality.

### Excluded

- GitHub Actions or any other CI/CD workflow.
- Frontend installation, compilation, linting, or formatting.
- Python wheel construction, inspection, publication, or installation smoke tests.
- Pillow or other test dependency corrections unrelated to Ruff.
- Configuration-test environment isolation changes.
- Coverage thresholds.
- Type checking by mypy, Pyright, or another separate type checker.
- Runtime feature changes, new public APIs, or module architecture changes.

## Standard Rationale

FSQ follows the curated Ruff approach used by the Societas backend instead of enabling `ALL`. The shared baseline covers pycodestyle, Pyflakes, import order, naming, modernization, bugbear, built-in shadowing, comprehensions, datetime handling, pytest practices, return conventions, simplification, import boundaries, type-checking imports, unused arguments, pathlib usage, Pylint, and asynchronous code.

FSQ adds security (`S`), Ruff-native (`RUF`), performance (`PERF`), exception handling (`TRY` and `BLE`), logging (`LOG` and `G`), and copyright (`CPY`) rules. These additions catch repository-relevant defects without enabling the high-volume annotation and docstring-presence families that made the previous `ALL` policy slow to remediate and noisy for existing code.

The policy intentionally differs from Societas where FSQ has a stronger local requirement or a different runtime baseline: FSQ keeps Python 3.11, uses a 200-character line length, requires the Microsoft copyright notice, and continues to reject unused local variables (`F841`) and bare `except` statements (`E722`). Ruff 0.16.1 reports 372 findings under this configuration, of which 201 are safely auto-fixable.

## Ruff Policy

### Version And Baseline

Ruff is pinned to `0.16.1` in the `dev` extra and required by the Ruff configuration. Contributors use the locked version through `uv run`; repository validation must not depend on a separately floating `uvx ruff` installation.

The repository adopts the following curated policy:

```toml
[tool.ruff]
required-version = "==0.16.1"
target-version = "py311"
line-length = 200
indent-width = 4
preview = false
fix = false
unsafe-fixes = false
show-fixes = true
respect-gitignore = true

[tool.ruff.lint]
select = [
    "A", "ARG", "ASYNC", "B", "BLE", "C4", "CPY", "DTZ", "E", "F",
    "G", "I", "ISC", "LOG", "N", "PERF", "PIE", "PL", "PTH", "PT",
    "RET", "RUF", "S", "SIM", "TC", "TID", "TRY", "UP", "W",
]
ignore = [
    "ARG001", "ARG002", "ARG004", "ARG005",
    "ASYNC109", "ASYNC230",
    "B007", "B008",
    "DTZ005", "DTZ007",
    "E402", "E701", "E741",
    "N802", "N806", "N999",
    "PLC0206", "PLC0415",
    "PLR0911", "PLR0912", "PLR0913", "PLR0915", "PLR0917", "PLR1714", "PLR2004",
    "PT006", "PT009",
    "PTH100", "PTH103", "PTH107", "PTH109", "PTH118", "PTH120", "PTH123",
    "RET503", "RET504",
    "SIM102", "SIM105", "SIM108",
    "TRY003",
]
extend-ignore = [
    "COM812",
    "COM819",
    "E111",
    "E114",
    "E117",
    "E501",
    "ISC001",
    "ISC002",
    "W191",
]
fixable = ["ALL"]
unfixable = []
dummy-variable-rgx = "^(_+|(_+[a-zA-Z0-9_]*[a-zA-Z0-9]+?))$"

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]

[tool.ruff.lint.flake8-copyright]
notice-rgx = "Copyright \\(c\\) Microsoft Corporation\\."

[tool.ruff.lint.isort]
known-first-party = ["fsq_agent"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
```

### Global Exclusions

The formatter-related exclusions follow Ruff's formatter compatibility guidance. The remaining exclusions follow Societas conventions for existing interface signatures, local imports, complexity, pathlib migrations, pytest compatibility, and readability preferences. `TRY003` is excluded because requiring custom exception classes or pre-bound messages for every raised exception creates substantial churn without improving FSQ's error contracts.

FSQ deliberately does not inherit Societas exclusions for `F841` or `E722`. Unused local variables and bare exception handlers remain errors. Security, blind-exception, Ruff-native, performance, and logging families also remain enabled.

### Test-Specific Exclusions

The only test-specific exclusion is `S101`, because pytest uses native `assert`. Other compatibility exclusions are global where they represent accepted project-wide patterns.

### Suppression Policy

- No lint baseline file.
- No `--exit-zero`.
- No changed-files-only enforcement.
- No blanket `# noqa` or file-level blanket suppression beyond the configured compatibility policy.
- Every remaining `noqa` names the exact rule code.
- An intentional security or architecture exception has a short rationale immediately above the affected line.
- `RUF100` remains enabled so obsolete suppressions fail validation.
- New Ruff versions are adopted deliberately through a dependency update; the exact version pin prevents surprise rule changes on unrelated work.

## Development Dependency Policy

The `dev` extra adds only `ruff==0.16.1` for this scope. Runtime dependencies and platform extras remain unchanged.

`uv.lock` is regenerated through uv and must contain the exact Ruff version. Ruff validation uses the frozen `dev` extra. The complete cross-platform pytest suite uses all frozen extras because collection imports existing platform dependencies.

## Remediation Method

1. Update Ruff configuration and the locked development dependency.
2. Run Ruff format over the complete tracked Python surface.
3. Run Ruff safe fixes over the complete tracked Python surface.
4. Review the mechanical diff and run the full test suite.
5. Repair remaining findings by rule family, using focused tests after every behavior-sensitive group.
6. Refactor complexity, boolean-trap, exception-design, annotation, async-blocking, and security findings instead of raising thresholds or adding broad exclusions.
7. Re-run Ruff lint, Ruff format check, and the complete pytest suite until all pass.

Unsafe automatic fixes are not applied in bulk. A specific unsafe fix may be applied only after reviewing its exact diff and validating the affected tests.

Because formatting touches many files, formatting and import-order changes should be completed before behavior-sensitive manual repairs. Unrelated architectural refactoring is prohibited.

## Documentation Changes

`CONTRIBUTING.md` will document the locked local commands:

```text
uv sync --frozen --extra dev
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
uv run --frozen --all-extras python -m pytest
```

The documentation will distinguish validation commands from optional platform runtime setup.

## Python Architecture

No Python architecture level changes are introduced. Existing module ownership, public APIs, dependency direction, runtime behavior, and package boundaries remain unchanged.

Lint repair must preserve those boundaries. A lint finding does not authorize moving shared models, exposing private implementations, changing public exports, or introducing new architecture layers. Complexity repair uses the lowest architecture level already assigned by the root and module specifications.

## Specification Impact

Expected specification changes:

- Root `SPEC.md`: add concise current-fact requirements that repository-owned Python passes the pinned Ruff lint and format policy.

No module `SPEC.md` changes are expected because runtime configuration behavior, public interfaces, dependencies between modules, and error semantics do not change. If remediation reveals that behavior or a module contract must change, implementation stops until the relevant SPEC delta is separately confirmed.

## Error Handling And Edge Cases

- A stale `uv.lock` fails frozen dependency synchronization.
- Ruff version mismatch fails through `required-version`.
- Formatter-owned rules are not duplicated as lint policy.
- Test framework semantics are excluded only in the test tree.
- Intentional subprocess, XML, URL, template, or fake-secret behavior receives narrow reviewed handling rather than category-wide suppression.
- Existing `noqa` comments are validated by `RUF100` and removed when obsolete.
- Formatting and safe fixes are followed by tests before behavior-sensitive repairs proceed.

## Verification And Audit Expectations

Required executable checks after implementation:

```text
uv sync --frozen --extra dev
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
uv run --frozen --all-extras python -m pytest
```

The final audit verifies:

- The implementation matches the confirmed root SPEC delta.
- Ruff configuration matches the curated Societas-derived policy and the documented FSQ additions.
- Every targeted suppression is narrow and justified.
- All tracked Python files are formatted.
- The full Python test suite passes after remediation.
- The diff contains no CI, frontend, packaging, coverage, type-checker, runtime-feature, or unrelated architecture changes.

## Resolved Decisions

- Use a curated Societas-derived rule set instead of Ruff `ALL`.
- Add focused security, Ruff-native, performance, exception, logging, and copyright checks.
- Keep compatibility exclusions explicit in `pyproject.toml`, with only `S101` scoped specifically to tests.
- Preserve `F841` and `E722` as high-signal correctness rules.
- Pin Ruff exactly in the development dependency set.
- Repair the complete repository-owned Python surface in this scope.
- Preserve runtime behavior and architecture contracts while repairing findings.
