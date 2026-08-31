# Contributing

This project welcomes contributions and suggestions.

## Contributor License Agreement

Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and do grant us the rights to use your contribution. For details, visit [https://cla.opensource.microsoft.com](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether a CLA is required and decorate the PR appropriately. Follow the bot instructions if action is needed.

## Code of Conduct

This project follows the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For questions or reports, contact [opencode@microsoft.com](mailto:opencode@microsoft.com).

## How to Contribute

1. Open an issue or comment on an existing issue before starting larger changes.
2. Fork the repository and create a topic branch.
3. Keep the change focused and include tests or documentation when appropriate.
4. Open a pull request with a clear description of the change and validation performed.

For agent-assisted project modifications, explicitly invoke `/spec-driven <confirmed-design-document-path | direct-project-change-request>`. `/requirements-to-design <request>` is an optional design aid that produces higher-quality input for `/spec-driven`, not a prerequisite. During `/spec-driven`, the agent determines whether a SPEC delta is required: required SPEC updates must be confirmed before non-SPEC project files change, while a repair already grounded in current SPEC may proceed after recording concrete no-SPEC-delta evidence. Workflow-control-only maintenance follows the repository agent instruction files and does not use project SDD.

## Contributor Growth Path

Contribution is open to everyone, and no one needs repository permissions to participate. FSQ recognizes the following paths as contributors take on broader responsibility:

| Role | Typical contributions | Responsibility and access |
|---|---|---|
| Contributor | Issues, documentation, tests, code, examples, or reviews | No repository access required |
| Regular Contributor | Sustained, high-quality contributions and community support | Recognition; no automatic permission change |
| Area Reviewer or Triager | Issue triage and reviews in a demonstrated area of expertise | Triage or review responsibilities may be granted |
| Harness Author | Ownership of a platform or backend contribution | Maintains compatibility, tests, evidence behavior, and documentation for that area |
| Maintainer | Cross-project technical and community stewardship | Repository, release, roadmap, and governance responsibilities |

Progression is based on demonstrated stewardship rather than a fixed pull request count. Maintainers consider contribution quality, technical judgment, respect for the spec-driven workflow, constructive collaboration, sustained ownership, and support for other contributors.

An existing maintainer may nominate a contributor for additional responsibility. Active maintainers review the nomination under [GOVERNANCE.md](GOVERNANCE.md), and a repository administrator applies any resulting permission change. Contributors may decline a role or continue contributing without pursuing additional access.

## Development

Install the default distribution, which contains all supported platform Python dependencies, together with the development tools:

```powershell
uv sync --frozen --extra dev
```

### Python Quality

Install the repository Git hook once after syncing the development dependencies:

```powershell
uv run --frozen --extra dev pre-commit install
```

The hook runs the same Ruff lint and format checks as CI before every commit. Run it manually across the repository with:

```powershell
uv run --frozen --extra dev pre-commit run --all-files
```

```powershell
# Validate.
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .

# Apply safe lint fixes and formatting.
uv run --frozen --extra dev ruff check . --fix
uv run --frozen --extra dev ruff format .
```

### Tests

Run the test file or matching test names for the area you changed:

```powershell
uv run --frozen --extra dev python -m pytest tests/test_windows_harness.py
uv run --frozen --extra dev python -m pytest tests/test_windows_harness.py -k launch
```

Maintainers can run the complete repository suite with all locked platform dependencies:

```powershell
uv run --frozen --extra dev python -m pytest
```

### CLI And Control Plane

Use the current public commands when running the CLI from a source checkout:

```powershell
$fsq = (Resolve-Path ".\.venv\Scripts\fsq.exe").Path
& $fsq --help
& $fsq providers status
& $fsq init --platform windows --app-path "C:\Path\To\App.exe"
& $fsq doctor
& $fsq case create --platform windows --goal "Describe the task"
& $fsq case test --platform windows "cases\windows\example.fsq.yaml"
& $fsq runs list --platform windows
& $fsq ui --no-open-browser
```

Build the browser assets before starting the Python-served Control Plane from a source checkout:

```powershell
npm ci
npm run build
```

For live frontend development, run the Control Plane API and Vite in separate terminals after installing npm dependencies:

```powershell
# Terminal 1: Vite proxies API requests to port 8878.
uv run --frozen --extra dev fsq ui --port 8878 --no-open-browser

# Terminal 2
npm run dev
```

### Dependency Changes

Regenerate and verify the Python lock file after changing `pyproject.toml`:

```powershell
uv lock
uv lock --check
```

Commit `package-lock.json` whenever npm dependencies change.

## Security Issues

Do not report security vulnerabilities through public GitHub issues. Follow the reporting instructions in [SECURITY.md](SECURITY.md).

## Secrets

Do not commit credentials, tokens, test-account passwords, personal account data, local `.env` files, generated logs, reports, screenshots, or local workspace output.
