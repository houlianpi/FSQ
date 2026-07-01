# Platform-Owned Config Files and CLI Platform Selection Design

## Goal

Make platform startup user-facing through `--platform` instead of `--config`, and treat platform YAML files as committed repository presets rather than user-edited local files.

## Scope

- Remove `config.example.yaml` from the repository.
- Rename committed platform presets:
  - `config.local.android.yaml` -> `config.android.yaml`
  - `config.local.web.yaml` -> `config.web.yaml`
  - `config.local.windows.yaml` -> `config.windows.yaml`
  - `config.local.macos.yaml` -> `config.macos.yaml`
- Replace public CLI `--config PATH` options with `--platform android|web|windows|macos` for `init`, `run`, `report`, and `playground`.
- Automatically resolve `--platform windows` to `config.windows.yaml`, etc.
- Update `.vscode/launch.json` to use `--platform` and the renamed config files indirectly through CLI resolution.
- Update README to document `--platform` only.
- Keep `.env` as the user-owned place for local paths, target identifiers, credentials, secrets, and machine-specific values.

## Non-Goals

- Do not introduce user-editable config authoring in README.
- Do not move sensitive values into platform YAML files.
- Do not change platform harness behavior, FSQ parsing, dynamic execution, strict execution, report generation, or playground routing beyond config selection.
- Do not keep public `--config` compatibility. This is a breaking CLI cleanup.

## Proposed Design

### Config Resolution

Add a config-layer helper, for example `load_platform_settings(platform, workspace=None)`, that maps a validated platform id to a repository-root config path:

| Platform | Config path |
|---|---|
| `android` | `config.android.yaml` |
| `web` | `config.web.yaml` |
| `windows` | `config.windows.yaml` |
| `macos` | `config.macos.yaml` |

The existing `load_settings(path, workspace)` remains available for internal tests and lower-level callers, but default config discovery should stop depending on `config.example.yaml`. If no explicit path is supplied to `load_settings`, default discovery may use `config.yaml`/`config.yml` only for developer override scenarios.

If a platform config file is missing, raise `ConfigurationError` with the platform and expected path.

### CLI Public Interface

Each command accepts `--platform` instead of `--config`:

```text
fsq-agent init --platform windows
fsq-agent run --platform windows --goal "Launch Edge and verify search results are visible."
fsq-agent run --platform windows --strict --case-yaml path/to/case.codex.yaml
fsq-agent report --platform windows --run-id RUN_ID --format markdown
fsq-agent playground --platform windows
```

`--platform` uses Click choices for `android`, `web`, `windows`, and `macos`. The CLI calls the config helper to load the corresponding repository preset before validation/execution. Public `--config` is removed, so old `--config` invocations fail with Click's unknown option behavior.

### Platform Presets

The renamed `config.<platform>.yaml` files are committed, non-secret presets. They may contain stable defaults such as provider selection, tracing policy, harness platform/backend, execution delays, runtime secret allowlist names, and configured skill bundles. User-local values remain in `.env`.

### Documentation and Launch Config

README should show:

1. Install the platform extra.
2. Copy/edit `.env`.
3. Run `fsq-agent ... --platform <platform>`.
4. CLI examples using `--platform`.

`.vscode/launch.json` should replace every `--config config.local.*.yaml` pair with `--platform <platform>`. Existing launch profiles should keep their goals, case inputs, record flags, and report inputs.

## Python Architecture

- Architecture level: 3 Layered Application.
- Config owns mapping platform ids to repository preset paths and loading settings from those paths.
- CLI owns user-facing argument parsing and passes a platform id to config loading.
- Models continue to own platform id validation types where applicable.
- Core, agent, playground runtime internals, FSQ parsing, and report generation remain unaware of CLI argument shape.
- Boundary rule: no module outside CLI should parse CLI flags; no core/agent runtime should read platform config files directly.

## Affected Specs

- Root `SPEC.md`: runtime configuration defaults and platform config ownership.
- `fsq_agent/config/SPEC.md`: platform config path mapping and public helper.
- `fsq_agent/cli/SPEC.md`: public CLI command signatures and platform option behavior.
- README and `.vscode/launch.json` are documentation/developer-entry artifacts and should be synchronized with the new CLI.

## Verification Expectations

- Rename/delete config files and update references.
- Unit tests for platform config path resolution and missing platform config errors.
- CLI tests proving `--platform` loads the matching platform preset and `--config` is no longer accepted.
- Existing focused CLI/config/playground tests updated to use the new public entry where they exercise CLI behavior.
- `git diff --check`.
- Focused pytest: `tests/test_config.py tests/test_cli.py tests/test_playground.py`.
- Independent SPEC implementation audit before completion.
