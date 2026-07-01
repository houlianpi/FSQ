# Windows Env-Owned Runtime Adapter Configuration Design

## Goal

Move Windows runtime adapter values that vary by user, target application, or local automation compatibility out of YAML project configuration and into environment variables.

The Windows YAML block should remain a stable platform selection surface. User-local target and pywinauto adaptation values should be supplied through `.env` or process environment, matching the existing Android, Web, and macOS configuration boundary.

## Scope

In scope:

- Keep `harness.platform: windows` and `harness.windows.backend: pywinauto` as YAML-owned platform configuration.
- Move the effective pywinauto automation mode to `FSQ_WINDOWS_BACKEND_KIND`, with `uia` as the default when unset and `win32` as the other supported value.
- Move the optional launched-window title matcher to `FSQ_WINDOWS_WINDOW_TITLE_RE`.
- Move optional default launch arguments to `FSQ_WINDOWS_LAUNCH_ARGS` as a command-line string, for example `--no-first-run --disable-features=msImplicitSignin`.
- Keep `FSQ_WINDOWS_APP_PATH` as the env-owned local executable path.
- Update `config.local.windows.yaml`, `.env.example`, README, root/module specs, loader behavior, validation errors, and tests to reflect the env-owned Windows shape.

Out of scope:

- Adding a second FSQ Windows backend. The only Windows backend remains `pywinauto`.
- Changing Windows capability names, FSQ action syntax, or the `launchApp.extra_args` per-step override.
- Changing pywinauto launch/session mechanics except for where defaults are read from.

## Proposed Design

### YAML Shape

New Windows examples should use this minimal platform-owned YAML shape:

```yaml
harness:
  platform: windows
  windows:
    backend: pywinauto
```

`backend_kind`, `window_title_re`, and `launch_args` should no longer appear in default local YAML examples because they are target-application and machine/operator adaptation values.

### Environment Variables

Windows runtime env variables:

```dotenv
FSQ_WINDOWS_APP_PATH=C:\Program Files\Microsoft\Edge\Application\msedge.exe
FSQ_WINDOWS_BACKEND_KIND=uia
FSQ_WINDOWS_WINDOW_TITLE_RE=.*Microsoft.*Edge
FSQ_WINDOWS_LAUNCH_ARGS=--no-first-run --disable-features=msImplicitSignin
```

`FSQ_WINDOWS_BACKEND_KIND` is optional. Empty means `uia`. Non-empty values must be one of `uia` or `win32`.

`FSQ_WINDOWS_WINDOW_TITLE_RE` is optional. Empty means the driver resolves the process top window.

`FSQ_WINDOWS_LAUNCH_ARGS` is optional. Empty means no configured default launch arguments. The loader parses it as a command-line string into a list of arguments before passing settings to `PywinautoWindowsDriver`. Per-step `launchApp.extra_args` continue to append after these configured defaults.

### Compatibility

The preferred public configuration shape is env-owned. Existing YAML-owned Windows adapter keys may either be rejected as invalid configuration or retained as explicit compatibility inputs for one migration cycle, but the implementation must make env values take precedence when both are present.

The recommended implementation is to retain compatibility only if it avoids breaking existing local configs during this cycle, while removing these keys from all repo-owned examples and docs except migration notes.

### Module Ownership

- `config` owns env loading, parsing, validation, precedence, and error messages.
- `models` owns the runtime settings fields consumed by the driver. If YAML compatibility is removed, env-backed Windows adapter fields should become private runtime attributes with validated property setters, following Web/macOS patterns.
- `core` continues consuming normalized settings values and passing them into `PywinautoWindowsDriver`; it does not read environment variables directly.
- `agent`, `playground`, and report/runtime metadata continue displaying only whether values are configured, not sensitive or local raw values.

## Python Architecture

- Architecture level: Level 2 Simple Package for `models` and `config`; Level 3 Layered Application consumers remain unchanged.
- Rationale: This is a configuration-boundary correction. It does not require new services, persistence, or cross-module abstractions.

## Affected Specs

- Root `SPEC.md`: Windows platform/config boundary examples should state env-owned local desktop adapter values.
- `fsq_agent/config/SPEC.md`: Windows configuration section and design decisions should define the new env variables, parsing, validation, and precedence.
- `fsq_agent/models/SPEC.md`: Update `WindowsHarnessSettings` public/runtime fields if YAML compatibility is removed or private attrs are introduced.
- `fsq_agent/core/SPEC.md`: Clarify that `backend_kind` is a normalized pywinauto adapter value, not a second FSQ backend, if needed.

## Verification Expectations

- Unit tests for loading Windows env values into settings.
- Unit tests for invalid `FSQ_WINDOWS_BACKEND_KIND` values.
- Unit tests for command-line parsing of `FSQ_WINDOWS_LAUNCH_ARGS`.
- Existing Windows harness tests should continue proving the driver receives launch args and title regex.
- Targeted command: `python -m pytest tests/test_config.py tests/test_windows_harness.py tests/test_playground.py`.