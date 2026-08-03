# GitHub Actions CI Design

**Status:** Confirmed
**Date:** 2026-08-03

## Goal

Give every pull request and every update to `main` a reproducible, least-privilege validation result. Contributors should receive separate feedback for Python quality, cross-platform tests, frontend compilation, and wheel packaging, while maintainers should have one stable required check for the default-branch ruleset.

## Context

The repository currently has no files under `.github/workflows`, so pull requests receive no automated validation. Root `SPEC.md` already defines the local quality contract:

- Repository Python must pass the locked Ruff lint and format checks.
- Repository changes must pass the complete pytest suite.
- Frontend source is built by the root npm project.
- A distributable wheel must be built after the frontend so it contains generated Playground static assets.

The following commands have been validated locally with the committed lock files:

```text
uv sync --frozen --extra dev
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
uv run --frozen --all-extras python -m pytest
npm ci
npm run build
uv build --wheel
```

The complete pytest suite currently passes with 600 tests. Ruff lint and format validation pass. The frontend clean install and build pass, and a directly built wheel contains the generated Playground assets and can be installed in isolation.

A full `uv build` currently fails on its sdist-to-wheel stage because generated `fsq_agent/playground/static` assets are not present in the sdist. This design validates the supported direct wheel path with `uv build --wheel`; changing the sdist contract is a separate packaging change.

Default whole-repository type checking is not ready to become a blocking gate. Current measurements produce hundreds of errors with either mypy or Pyright across production and test code. Type-checker selection, configuration, remediation, and CI adoption require a separate SDD cycle.

## Scope

Add one workflow:

```text
.github/workflows/ci.yml
```

The workflow will contain independent jobs for:

- Locked Ruff lint and format validation.
- The complete pytest suite on Python 3.11, 3.12, and 3.13 across Ubuntu, Windows, and macOS.
- Frontend clean installation and production compilation on supported Node.js major versions.
- Direct wheel construction, static-asset inspection, isolated installation, and CLI smoke validation.
- One stable aggregate required check for the default-branch ruleset.

## Non-Goals

- PyPI publication, GitHub Releases, release notes, version bumps, or release credentials.
- sdist repair or sdist-to-wheel validation.
- Mypy, Pyright, or another type-checking gate.
- Coverage collection, Codecov upload, or a coverage threshold.
- Device-backed Android, browser, Windows desktop, or macOS Appium integration tests.
- Installing Playwright browser binaries, Android SDKs, Appium servers, or desktop applications.
- Changes to runtime code, frontend source, dependency versions, or public APIs.
- Path-based workflow skipping.

## Approaches Considered

### One Workflow With Independent Jobs

Use one `ci.yml` with separate quality, test-matrix, frontend, package, and aggregate jobs. Triggers, permissions, concurrency, and required-check naming stay centralized. GitHub can re-run failed jobs and their dependants without re-running successful independent jobs. This is the selected approach.

### Separate Workflows By Toolchain

Use separate Python, frontend, and package workflows. This makes each workflow independently dispatchable, but duplicates trigger and permission policy and creates several workflow-level checks to maintain in the branch ruleset. The initial CI surface does not need that operational separation.

### One Combined Matrix Job

Run lint, tests, frontend compilation, and packaging inside one large matrix. This minimizes YAML structure but repeats unrelated work, consumes more runner time, and makes failures and selective retries less clear. This was rejected.

## Architecture and Ownership

This change adds repository automation and does not enter the Python package dependency graph. Existing Python architecture levels, module ownership, public APIs, and dependency direction remain unchanged.

The `.github/workflows` directory owns CI orchestration. Existing manifests remain authoritative:

- `uv.lock` and `pyproject.toml` own Python dependency resolution and quality-tool versions.
- `package-lock.json` and `package.json` own frontend dependency resolution and supported Node.js versions.
- `vite.config.js` owns frontend output into `fsq_agent/playground/static`.
- Root `SPEC.md` owns the project-level current quality and frontend build contracts.

## Trigger and Concurrency Design

The workflow name and trigger surface will be stable:

- Workflow name: `CI`.
- `pull_request` targeting `main`.
- `push` to `main`.
- `workflow_dispatch` for an explicit maintainer-run validation.

One concurrency group will be used per pull request or branch reference. A newer run for the same group cancels the obsolete in-progress run. Runs for different pull requests remain independent.

The workflow will not use path filters. Documentation-only and repository-metadata pull requests still execute the required workflow, preventing a required check from remaining absent or pending and ensuring contribution metadata is validated in the same repository state.

## Security and Permissions

The workflow will:

- Declare `contents: read` as its only workflow permission.
- Use `pull_request`, not `pull_request_target`, so fork code never executes in a privileged base-repository context.
- Receive no repository or publication secrets.
- Disable persisted checkout credentials.
- Pin every referenced action to an immutable full commit SHA and retain the corresponding release tag in a comment for maintainability.
- Use frozen Python and npm lock-file installation paths.
- Avoid uploading artifacts unless a later design establishes a concrete retention or diagnostic need.

Because pull request code is untrusted, every job must remain safe when run from a fork. No job may write repository contents, publish packages, mutate Issues or pull requests, or obtain an identity token.

## Job Design

### Quality

Stable job name: `Quality`.

Run on Ubuntu with Python 3.11, the repository's minimum supported Python version:

```text
uv sync --frozen --extra dev
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
```

This job validates the exact Ruff version and policy committed in `pyproject.toml` and `uv.lock`. It does not mutate source files.

### Tests

Job-name pattern: `Tests (<runner>, Python <version>)`.

Use a full matrix:

| Runner | Python versions |
| --- | --- |
| `ubuntu-latest` | 3.11, 3.12, 3.13 |
| `windows-latest` | 3.11, 3.12, 3.13 |
| `macos-latest` | 3.11, 3.12, 3.13 |

Set `strategy.fail-fast: false`. One failing matrix entry must not cancel other operating-system or Python-version entries, so the first run reports the complete compatibility result.

Each matrix entry runs:

```text
uv sync --frozen --all-extras
uv run --frozen --all-extras python -m pytest
```

Platform extras are installed to verify their locked Python dependency sets and permit collection of the existing fake-driver tests. The workflow does not provision real platform targets or run external-device integration tests.

### Frontend

Job-name pattern: `Frontend (Node <version>)`.

Run on Ubuntu with Node.js 20 and 22, matching the supported major-version families in `package.json`:

```text
npm ci
npm run build
```

The npm cache may be restored through the setup action using `package-lock.json` as the cache dependency path. `node_modules` and generated static assets are not committed or uploaded.

### Package

Stable job name: `Package`.

Run independently on Ubuntu with Node.js 22 and Python 3.11. The job will:

1. Run `npm ci` and `npm run build`.
2. Run `uv build --wheel`.
3. Inspect the wheel as a ZIP archive and fail unless it contains the generated Playground HTML entry and generated asset files under `fsq_agent/playground/static`.
4. Create an isolated virtual environment outside the project environment.
5. Install only the newly built wheel and its declared runtime dependencies.
6. Run an import smoke check and `fsq-agent --help` from that isolated environment.

The package job rebuilds the frontend rather than consuming another job's artifact. This keeps the job independently retryable and verifies the actual ordering required by the package contract.

### Required

Stable job name: `Required`.

This job has `needs` dependencies on `Quality`, `Tests`, `Frontend`, and `Package`, and runs with `if: always()`. It succeeds only when every required upstream job result is `success`; failed, cancelled, or skipped upstream validation makes it fail.

The default-branch ruleset should require the single check `CI / Required`. This gives branch protection a stable check name even if the internal matrix later changes. GitHub's `Re-run failed jobs` operation re-runs failed jobs and dependent jobs; successful independent jobs remain complete, while `Required` is recalculated from the retried results.

## Caching and Reproducibility

- Python dependency caching will use uv's supported cache integration and `uv.lock`.
- Node dependency caching will use the setup action's npm cache and `package-lock.json`.
- Caches are performance hints only. `uv sync --frozen` and `npm ci` remain authoritative and must fail on lock drift.
- No cache will contain repository credentials or local runtime configuration.
- Floating dependency installation commands such as `uv add`, `pip install` without a built wheel, or `npm install` are prohibited in CI validation jobs.

## Failure and Retry Semantics

- Every job has a finite timeout so stalled dependency installation or tests do not consume a runner indefinitely.
- Matrix fail-fast is disabled to expose all compatibility failures in one run.
- A failed quality, matrix, frontend, or package job reports its own tool output and non-zero status.
- The aggregate `Required` job reports the upstream result names when it fails.
- Maintainers may select `Re-run failed jobs`; GitHub re-runs failures and their dependent `Required` job without re-running successful independent jobs.
- A manually cancelled or superseded run is not acceptable for merge; the newest commit must have a successful `CI / Required` check.

## Specification Impact

Expected specification changes:

- Root `SPEC.md`: add concise present-tense facts that GitHub Actions validates pull requests and `main` updates through the locked quality checks, full cross-platform Python matrix, frontend build, packaged-wheel checks, and a stable aggregate required result.

No module `SPEC.md` changes are expected. If implementation reveals a runtime, public-interface, module-ownership, dependency-direction, or packaging-contract change beyond the direct wheel behavior already specified, implementation must stop until the relevant SPEC delta is separately confirmed.

## Python Architecture

- Architecture level: unchanged.
- Public API: unchanged.
- Internal modules: unchanged.
- Domain boundaries: unchanged.
- Boundary models: unchanged.
- Dependency direction: unchanged.
- Rationale: CI orchestrates existing repository commands and does not add Python runtime behavior or package dependencies.

## Resolved Questions

- Workflow organization: one `ci.yml` with multiple jobs.
- Retry behavior: independent jobs plus a dependent aggregate gate; successful independent jobs do not need to be rerun.
- Python compatibility: full three-OS by three-version matrix for Python 3.11, 3.12, and 3.13.
- Matrix behavior: `fail-fast: false`.
- Frontend compatibility: Node.js 20 and 22 build entries.
- Package target: direct wheel build after frontend compilation.
- Branch protection: require one stable `CI / Required` check.
- Type checking: deferred to a separate remediation and adoption cycle.
- Release automation: excluded from this CI cycle.

## Verification Expectations

### Local and Static Validation

- Parse `.github/workflows/ci.yml` as YAML.
- Validate GitHub Actions workflow structure and expressions with an Actions-aware linter.
- Confirm the workflow requests only `contents: read` and uses no secrets or privileged pull-request trigger.
- Confirm all referenced actions use immutable full commit SHAs.
- Confirm matrix entries, `fail-fast: false`, timeouts, concurrency, frozen installs, and the aggregate result logic are present.
- Re-run the locked Ruff checks, complete local pytest suite, frontend build, direct wheel build, wheel-content inspection, and isolated install smoke check.
- Verify the final diff contains no runtime source, frontend source, module SPEC, dependency, release, coverage, or type-checking changes.

### After Push

- Open or update a pull request and verify all quality, nine test-matrix, two frontend, package, and aggregate checks appear.
- Introduce a temporary failure on a test branch, verify the corresponding job and `Required` fail, then use `Re-run failed jobs` and confirm successful independent jobs are not rerun.
- Verify a newer commit cancels an obsolete in-progress run for the same pull request without cancelling other pull requests.
- Verify a fork pull request runs without approval-dependent secrets and has read-only permissions.
- Configure the `main` ruleset to require `CI / Required` after that check name has appeared on the repository.
- Verify a pull request cannot merge when `CI / Required` fails and can satisfy the CI requirement when it succeeds.