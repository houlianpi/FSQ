# FSQ Release Acceptance Checklist

Use this checklist for every release candidate. The release workflow automates source quality, package metadata, distribution checks, and clean installed-package smoke across GitHub-hosted Linux, macOS, and Windows runners. Complete the real-host platform matrix on hosts that provide the real applications, browsers, devices, and services under test. A mocked unit test does not count as a platform acceptance result.

Record the commit SHA, operating system, Python version, installed artifact checksum, target identity, result, and evidence path for each run. Do not record credentials, tokens, API keys, `Authorization`, `Cookie`, or private target data.

## Release Gate

A release candidate is ready only when:

- quality, backend tests, frontend tests, frontend build, package metadata guards, wheel build, and sdist build pass;
- the verified wheel can be installed with `pip install fsq-agent` semantics in clean Python 3.11+ environments on Linux, macOS, and Windows without platform extras;
- the installed distribution provides both `fsq` and `fsq-agent`, package-owned configuration/templates/skills, and both compiled frontends;
- one real-host acceptance row passes for every supported platform included in the release;
- Provider CLI and Control Plane read the same user-level configuration in both directions;
- Case creation, deterministic Case testing, suggestion analysis, Run queries, offline HTML reporting, and `fsq ui` pass through installed entry points; and
- no command installs Python packages, Drivers, Runtimes, browsers, applications, devices, or host services.

If a required real platform is unavailable, record the gate as blocked rather than passed.

## 1. Source and Automated Verification

From the repository root:

```bash
git status --short
test -z "$(git status --porcelain)"
uv sync --extra dev
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync python -m pytest
npm ci
npm run typecheck
npm test
npm run build
uv build
```

Expected: all commands succeed, including the explicit clean-worktree assertion. Run this gate from a clean checkout of the candidate commit, not from an implementation worktree that still contains the proposed diff. Generated frontend output must exist before Python distributions are built. Local `.fsq/`, `runs/`, credentials, and test evidence must not enter the release commit or distribution.

The release workflow runs the equivalent automated gate before publication, including package metadata guardrails, `twine check`, distribution contract tests, and upload of one verified `dist/` artifact consumed by downstream smoke and publish jobs.

The CI package job is the executable contract for archive inspection. Confirm that it checks:

- exactly one wheel and one sdist;
- Control Plane and Playground HTML, JavaScript, CSS, and `entry-assets.json` in both archives;
- repository platform presets, default prompt templates, and configured skills in both archives;
- default dependencies for uiautomator2, Playwright, pywinauto, Pillow, and Appium Python Client;
- no platform extras;
- `fsq` and `fsq-agent` console scripts; and
- installed-package Control Plane HTML resolution.

## 2. Clean Installation

The release workflow automatically runs this smoke from the verified wheel artifact on `ubuntu-latest`, `macos-latest`, and `windows-latest`. Use this section for local reproduction, release-candidate spot checks, or investigating a failed matrix cell.

Create a new temporary environment and install the built wheel without the repository on `PYTHONPATH`:

```bash
uv venv --python 3.11 /tmp/fsq-release-smoke
uv pip install --python /tmp/fsq-release-smoke/bin/python dist/fsq_agent-*.whl
/tmp/fsq-release-smoke/bin/fsq --help
/tmp/fsq-release-smoke/bin/fsq-agent --help
/tmp/fsq-release-smoke/bin/python -c "import fsq_agent"
```

On Windows use the corresponding paths:

```powershell
.\fsq-release-smoke\Scripts\fsq.exe --help
.\fsq-release-smoke\Scripts\fsq-agent.exe --help
.\fsq-release-smoke\Scripts\python.exe -c "import fsq_agent"
```

Both help outputs must expose exactly the current top-level command families: `init`, `doctor`, `providers`, `case`, `runs`, and `ui`.

Run the remaining sections with the installed `fsq` executable.

## 3. Platform Workspace Matrix

Use a separate empty project directory and isolated user profile for each row. `fsq init` must either commit the canonical Workspace layout after readiness succeeds or fail without creating partial Workspace/registry state. It must not install missing prerequisites.

| Platform | Host prerequisites | Initialization command | Required acceptance |
| --- | --- | --- | --- |
| Web | Supported Chrome/Edge/Chromium channel installed | `fsq init --platform web --browser-channel chrome` | Discovers one matching browser or safely requests an explicit path; creates Web layout only after readiness |
| Android | ADB-visible device and installed app | `fsq init --platform android --app-id com.example.app` | Reports device/runtime truth without installing or connecting during readiness; creates Android layout only when ready |
| Windows | Windows host and existing application path | `fsq init --platform windows --app-path 'C:\Path\To\App.exe'` | Validates pywinauto/runtime and target; creates Windows layout only when ready |
| macOS | macOS host, existing app identity, reachable Appium Mac2 service | `fsq init --platform macos --bundle-id com.example.app` | Validates Python runtime, app identity, and service prerequisite without starting Appium; creates macOS layout only when ready |

For every successful row verify:

```text
.fsq/config/config.<platform>.yaml
.fsq/runs/<platform>/
cases/<platform>/
knowledge/<platform>/project.md
```

Repeat the same `init` and expect `unchanged`. Change a target without `--update-existing` and expect a safe conflict with no mutation. Then use `--update-existing` and verify that only the selected platform configuration changes. Verify that `--install-driver` is rejected.

## 4. Doctor

From each exact registered Workspace root run:

```bash
fsq doctor
fsq --output json doctor
fsq --output jsonl doctor
```

Human and machine output must agree. Doctor must inspect every configured platform in Android, Web, Windows, macOS order and report readiness for `case test`, `case test --suggest`, and `case create`. Re-run while one external prerequisite is intentionally unavailable and verify safe `partial` or `unavailable` output and an actionable repair instruction. Doctor must not mutate files, authenticate interactively, invoke a model, launch a target, or create an external session.

## 5. Provider CLI and Control Plane

Use a disposable user-level FSQ configuration root or disposable OS account. Never use production credentials for release acceptance.

CLI-to-UI direction:

```bash
fsq providers configure github_copilot
fsq providers status
fsq ui --host 127.0.0.1 --port 8879 --no-open-browser
```

Complete device-code authentication and model selection in Human mode. Open Control Plane Config and verify the same active Provider and model.

UI-to-CLI direction: replace the configuration in Control Plane with a disposable Azure OpenAI endpoint, deployment/model, and API key, then run:

```bash
fsq providers status
fsq --output json providers status
```

Verify the CLI reads the same active Provider/model/readiness. Replace configuration with an intentionally invalid candidate and confirm the previous Provider remains usable. No output, log, report, browser response, or exception detail may expose credentials.

## 6. Case and Run Lifecycle

From a ready Workspace, use a small deterministic goal that can be verified from visible UI:

```bash
fsq case create --platform <platform> --goal '<goal>'
fsq case test --platform <platform> path/to/case.fsq.yaml
fsq case test --platform <platform> --suggest path/to/case.fsq.yaml
```

Verify:

- `case create` performs one real execution and preserves evidence under one Run;
- `case test` executes the source Case exactly once and does not modify it;
- `--suggest` executes the Case exactly once, then analyzes only the original Case, report, and persisted evidence;
- suggestion analysis performs no additional UI actions and cannot change the authoritative execution result; and
- suggestions and an optional candidate Case remain inside the Run directory and do not modify `cases/<platform>`.

Capture the resulting `RUN_ID`, then run:

```bash
fsq runs list
fsq runs list --platform <platform> --limit 10
fsq runs show <RUN_ID>
fsq runs logs <RUN_ID> --limit 200
fsq runs show <RUN_ID> --open
```

Verify Workspace-wide discovery, filters, summary fields, stable log ordering, and the offline HTML report. JSON, JSONL, logs, metadata, and HTML must redact secrets and avoid unnecessary absolute host paths. `show --open` must not alter `run.json` or invoke a Provider, Driver, or live UI.

## 7. Installed UI

From outside a Workspace run:

```bash
fsq ui --host 127.0.0.1 --port 8879 --no-open-browser
```

Request `/` from the printed loopback address and verify a successful HTML response plus successful referenced JS/CSS requests. Exercise Workspace selection, Config, Cases, Runs, and evidence views. Confirm no Node.js process, frontend source checkout, network asset download, or startup-directory Workspace is required. Stop the server cleanly with an interrupt.

## 8. Acceptance Record

Copy this table into the release issue or pull request:

| Gate | Host/artifact | Result | Evidence | Reviewer |
| --- | --- | --- | --- | --- |
| Source quality and tests | | | | |
| Frontend typecheck/tests/build | | | | |
| Wheel/sdist contract | | | | |
| Clean installation | | | | |
| Web init/doctor/lifecycle | | | | |
| Android init/doctor/lifecycle | | | | |
| Windows init/doctor/lifecycle | | | | |
| macOS init/doctor/lifecycle | | | | |
| Provider CLI ↔ UI | | | | |
| Runs and offline HTML | | | | |
| Installed Control Plane | | | | |

Fill every blank Result cell before release. Allowed final results are `pass`, `fail`, `blocked`, and `not-applicable` only when the release scope explicitly excludes the gate. Every failure links to a blocking issue; every blocked result names the missing environment or authority.

### Current real-host verification record (2026-08-31)

This development-branch record is evidence for the next release issue; it is not a substitute for running the checklist against the final release commit and installed artifact. No credentials, device codes, or private Provider responses are retained.

| Gate | Host/artifact | Result | Evidence | Reviewer |
| --- | --- | --- | --- | --- |
| Web init/doctor/lifecycle | macOS real host, installed Edge/Chrome-compatible browser | pass | Real Workspace initialization, Doctor, Case lifecycle, Runs, and UI acceptance completed | FSQ development acceptance |
| Android init/doctor/lifecycle | macOS host, ADB device, Microsoft Edge Stable | pass | Edge launch and visible main-screen assertions; deterministic Case and Run-local suggestion lifecycle completed | FSQ development acceptance |
| Windows init/doctor/lifecycle | No Windows real host available | blocked | `windows_status=skipped_by_user`; `windows_verified=false` | FSQ development acceptance |
| macOS init/doctor/lifecycle | macOS real host | pass | Real-host acceptance completed | FSQ development acceptance |
| Provider CLI → UI | User-level GitHub Copilot Provider | pass | CLI reported `github_copilot` / `gpt-5.5` ready; Control Plane Config displayed the same authenticated Provider and model | FSQ development acceptance |
| Provider UI → CLI | User-level GitHub Copilot Provider | blocked | Contract tests cover shared persistence and failed replacement preservation, but the real UI re-save could not complete because GitHub rejected the disposable device code; the prior Provider remained ready | FSQ development acceptance |
