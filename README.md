# fsq-agent

fsq-agent is a goal-driven automated testing agent for FSQ YAML-guided tasks. It executes harness-generated platform actions plus common local utilities, captures evidence, verifies one pre-plan-derived goal, and generates reports.

The project follows spec-driven development. See root [SPEC.md](SPEC.md) and each relevant module `SPEC.md` before changing public interfaces.

## Platform Setup

Platform defaults are maintained by the repository for now. For normal local use, copy the example environment file, edit `.env`, choose the target platform in the CLI command, and run.

On Windows PowerShell:

```powershell
copy .env.example .env
```

On macOS/Linux shells:

```bash
cp .env.example .env
```

### Android

Install the Android extra and connect an emulator or device with ADB:

```powershell
python -m pip install -e ".[dev,android]"
```

Set Android values in `.env`:

```dotenv
FSQ_ANDROID_APP_ID=com.microsoft.emmx
FSQ_ANDROID_SERIAL=emulator-5554
```

Leave `FSQ_ANDROID_SERIAL` blank when only one Android target is connected.

Start Android runs:

```powershell
fsq-agent init --platform android
fsq-agent run --platform android --goal "Access Downloads through the browser overflow menu from the New Tab Page, then return to the New Tab Page."
```

### Web With Local Chrome

Install the Web extra and point fsq-agent at the local browser executable:

```powershell
python -m pip install -e ".[dev,web]"
```

Set Web values in `.env`:

```dotenv
FSQ_WEB_BROWSER_EXECUTABLE_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
```

Start Web runs:

```powershell
fsq-agent init --platform web
fsq-agent run --platform web --goal "Open https://www.bing.com, search for Playwright, and verify the results page is visible."
```

### Windows Desktop With Edge

Install the Windows extra and point fsq-agent at the target application:

```powershell
python -m pip install -e ".[dev,windows]"
```

Set Windows values in `.env`:

```dotenv
FSQ_WINDOWS_APP_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
FSQ_WINDOWS_BACKEND_KIND=uia
FSQ_WINDOWS_WINDOW_TITLE_RE=.*Microsoft.*Edge.*
FSQ_WINDOWS_LAUNCH_ARGS=--no-first-run --disable-features=msImplicitSignin
```

`FSQ_WINDOWS_BACKEND_KIND` is the pywinauto automation mode for the target app. Use `uia` first; switch to `win32` only when the app exposes better controls through the older Win32 backend.

Start Windows desktop runs:

```powershell
fsq-agent init --platform windows
fsq-agent run --platform windows --goal "Launch Edge, search for Windows automation, and verify the results page is visible."
```

### macOS With Appium Mac2

Install the macOS extra. Appium 2 and the Mac2 driver must be installed and running on the Mac being automated:

```bash
python -m pip install -e ".[dev,macos]"
npm install -g appium
appium driver install mac2
appium --address 127.0.0.1 --port 4723
```

Set macOS values in `.env`:

```dotenv
FSQ_MACOS_APPIUM_SERVER_URL=http://127.0.0.1:4723
FSQ_MACOS_BUNDLE_ID=com.microsoft.edgemac
FSQ_MACOS_APP_PATH=/Applications/Microsoft Edge.app
```

Start macOS runs:

```bash
fsq-agent init --platform macos
fsq-agent run --platform macos --goal "Open Microsoft Edge, inspect the visible window, and verify the expected controls are visible."
```

Existing process environment variables take precedence over `.env` values. Secret values such as API keys and test-account passwords should stay in `.env` or the process environment.

## CLI Examples

Use the platform that matches the target: `android`, `web`, `windows`, or `macos`.

Initialize and check readiness:

```powershell
fsq-agent init --platform <platform>
```

Run from a natural-language goal:

```powershell
fsq-agent run --platform <platform> --goal "Open the target app and verify the expected page or controls are visible."
```

Run from FSQ case files as dynamic reference material:

```powershell
fsq-agent run --platform <platform> --case-yaml path/to/case.codex.yaml
fsq-agent run --platform <platform> --case-dir path/to/cases
```

Run authored FSQ cases through deterministic strict-core execution:

```powershell
fsq-agent run --platform <platform> --strict --case-yaml path/to/case.codex.yaml
fsq-agent run --platform <platform> --strict --case-dir path/to/cases
```

Open the local playground or print a stored report:

```powershell
fsq-agent playground --platform <platform>
fsq-agent report --platform <platform> --run-id RUN_ID --format markdown
```

## Current Scope

This implementation provides validated models, configuration loading, runtime wiring, harness/driver configuration, common local tooling, descriptive skill loading, evidence manifests, and report generation. Task execution requires authentication for the selected model provider.

Runtime artifacts are written under the fsq-agent workspace `output` directory. Shell execution settings are no longer part of runtime configuration.
