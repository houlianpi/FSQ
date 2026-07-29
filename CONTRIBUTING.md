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

Documentation-only, repository metadata, and open-source readiness changes do not require the spec-driven development workflow. Code changes that affect supported behavior, public interfaces, or project requirements should follow the repository `SPEC.md` guidance.

## Development

Install dependencies:

```powershell
uv sync --extra dev
```

Run tests:

```powershell
uv run python -m pytest
```

Use focused tests for the area you changed when possible.

## Security Issues

Do not report security vulnerabilities through public GitHub issues. Follow the reporting instructions in [SECURITY.md](SECURITY.md).

## Secrets

Do not commit credentials, tokens, test-account passwords, personal account data, local `.env` files, generated logs, reports, screenshots, or local workspace output.