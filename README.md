<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/logo-light.svg">
    <img alt="FSQ — Fully Self Quality" src="docs/assets/logo-light.svg" width="320">
  </picture>
</p>

<h3 align="center">
  An evidence-first agent harness for replayable, verifiable AI UI automation.
</h3>

<p align="center">
  <a href="https://github.com/microsoft/FSQ/actions/workflows/ci.yml"><img src="https://github.com/microsoft/FSQ/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <!-- <a href="https://pypi.org/project/fsq-agent/"><img src="https://img.shields.io/pypi/v/fsq-agent?color=blue" alt="PyPI"></a> -->
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#why-fsq">Why FSQ</a> •
  <a href="#supported-platforms">Platforms</a> •
  <a href="docs/">Documentation</a> •
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

<!-- TODO: Replace with actual demo GIF showing a full FSQ run -->
<!-- GIF should show: goal input → agent executing → evidence captured → verification → YAML generated -->
<p align="center">
  <img src="docs/assets/demo.gif" alt="FSQ Demo: goal → execution → evidence → verification → replay YAML" width="720">
</p>

---

## Why FSQ?

<table>
<tr>
<td width="33%" align="center">

**Evidence-First**

Every step captures screenshots, UI snapshots, and action traces. You verify through evidence, not agent self-reports.

</td>
<td width="33%" align="center">

**Replayable**

Successful AI runs auto-generate strict YAML. Replay deterministically without LLM — same harness, same evidence, zero flakiness.

</td>
<td width="33%" align="center">

**Verifiable**

Results are judged by an evidence-based verifier, not the agent claiming success. Auditable, trustworthy, CI-ready.

</td>
</tr>
</table>

> **Other AI agents say "I'm done." FSQ shows you the proof.**

---

## See It in Action

```
┌──────────────────────────────────────────────────────────────────────┐
│ $ cd /path/to/workspaces/web-demo                                   │
│ $ fsq-agent run --platform web --record                             │
│     --goal "Search for FSQ on Bing"                                │
├──────────────────────────────────────────────────────────────────────┤
│  ► Planning: 3 key actions identified                                │
│  ► Step 1: startBrowser          📸 screenshot + UI snapshot         │
│  ► Step 2: navigateTo bing.com   📸 screenshot + UI snapshot         │
│  ► Step 3: typeText "FSQ"        📸 screenshot + UI snapshot         │
│  ► Step 4: pressKey Enter        📸 screenshot + UI snapshot         │
│  ► Verification: PASSED ✅ (evidence-based)                          │
│  ► Recording manifest → .fsq/runs/web/<run-id>/recording.json       │
│  ► Replayable YAML → .fsq/runs/web/<run-id>/recorded.fsq.yaml       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## What Can FSQ Do?

<table>
<tr>
<th></th>
<th>Dynamic Mode 🤖<br><sub>AI-driven exploration</sub></th>
<th>Strict Mode 🔁<br><sub>Deterministic replay</sub></th>
</tr>
<tr><td><b>AI explores and operates your app</b></td><td align="center">✅</td><td align="center">—</td></tr>
<tr><td><b>Evidence captured on every step</b></td><td align="center">✅</td><td align="center">✅</td></tr>
<tr><td><b>Auto-generates replayable YAML</b></td><td align="center">✅</td><td align="center">—</td></tr>
<tr><td><b>Deterministic regression execution</b></td><td align="center">—</td><td align="center">✅</td></tr>
<tr><td><b>AI-powered visual assertions</b></td><td align="center">✅</td><td align="center">✅</td></tr>
<tr><td><b>Runs without LLM</b></td><td align="center">—</td><td align="center">✅</td></tr>
</table>

**The Dual Loop:** AI explores → evidence proves it worked → strict YAML locks it down → replay catches regressions.

---

## Quick Start

### 1. Install

```bash
pip install fsq-agent[web]
```

<details>
<summary><b>Using uv (recommended for development)</b></summary>

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --extra dev --extra web
```

</details>

### 2. Create a Workspace

```bash
fsq-agent control-plane
```

Open **Workspace**, create a workspace for the application under test, and give it a unique name such as `web-demo`. A workspace can contain any combination of Android, Web, Windows, and macOS platform configurations. Add one or more platforms during creation, then add or edit platforms independently from the workspace configuration page.

For non-interactive setup, `init` creates exactly one platform per invocation:

```bash
cd /path/to/workspaces

# Create and register a Web workspace platform.
fsq-agent init --name web-demo \
  --platform web \
  --browser-executable-path /path/to/google-chrome

# Add Android to the same registered workspace.
fsq-agent init --name web-demo \
  --platform android \
  --app-id com.example.app
```

`init` always creates or updates `<current-directory>/<name>`. Platform target options are:

| Platform | `init` target options |
|---|---|
| Android | `--app-id APP_ID` (required) |
| Web | `--browser-executable-path FILE` (required) |
| Windows | `--app-path PATH` (required), plus optional `--window-title-re` and `--launch-args` |
| macOS | `--bundle-id` or `--app-path` (at least one required) |

Repeating an equal platform configuration returns `unchanged`. If its target or private environment mapping differs, pass `--update-existing` to replace only that platform's target and `--env NAME=VALUE` entries. Use `fsq-agent --output json init ...` or `--output jsonl` for one-record machine output. Command-line environment values may be visible in shell history or process inspection.

`run` must be launched from the exact workspace root and requires an explicit configured platform. It validates the current directory directly instead of looking up a registry name or searching parent directories. `report` and `playground` keep their registered workspace-name selection and can run outside the workspace directory. Legacy `.fsq/config.yaml` and `.fsq-agent-workspace` layouts are not migrated.

### 3. Configure a Provider

Open **Config**, select **Add configuration**, and configure one active Provider:

| Provider | Setup |
|---|---|
| GitHub Copilot GPT | Model name and GitHub device-code authentication |
| Azure GPT | Azure OpenAI-compatible base URL, model/deployment name, and API key |

Provider configuration is stored under `~/.fsq` and is used by the next complete FSQ task. Config is available only when Control Plane is bound to and accessed through a loopback address.

### 4. Run

```bash
cd /path/to/workspaces/web-demo

# Dynamic: AI-driven exploration with full evidence
fsq-agent run --platform web \
  --record \
  --goal "Open https://www.bing.com, search for 'FSQ automation', verify results appear."
```

```bash
# Strict: Deterministic replay from YAML (no LLM needed)
fsq-agent run --platform web --strict \
  --case-yaml path/to/case.fsq.yaml

# Strict batch: Run matching cases under cases/web/.
fsq-agent run --platform web --strict
```

Strict directory runs, including the no-input default, recursively load exact `.fsq.yaml` files and skip cases authored for another platform. If files are present but none match `--platform`, the command reports zero cases and succeeds without creating run artifacts. A single `--case-yaml` platform mismatch is an error.

**Output:** Every executed run writes evidence and a report under `.fsq/runs/<platform>/<run-id>/`. For a dynamic run, `--record` writes a `recording.json` manifest for the recording attempt and writes `recorded.fsq.yaml` when the run is eligible and contains replayable commands. Failed runs are skipped unless `--record-on-failure` is also supplied. Strict runs do not record new cases.

### Control Plane

Launch the local browser Control Plane for multi-platform workspace management, platform readiness, target and case discovery, Explore runs, Strict Replay, and live evidence:

```bash
fsq-agent control-plane
```

It listens on `127.0.0.1:8879` and opens a browser by default. Use `--host`, `--port`, and `--no-open-browser` to override those defaults. A wheel installation includes the compiled frontend and needs no Node.js runtime. From a source checkout, run `npm ci && npm run build` before starting the Control Plane.

---

## Supported Platforms

<table>
<tr>
<th>Platform</th>
<th>Backend</th>
<th>Install</th>
</tr>
<tr>
<td>🌐 <b>Web</b></td>
<td>Playwright</td>
<td><code>pip install fsq-agent[web]</code></td>
</tr>
<tr>
<td>📱 <b>Android</b></td>
<td>uiautomator2</td>
<td><code>pip install fsq-agent[android]</code></td>
</tr>
<tr>
<td>🖥️ <b>Windows</b></td>
<td>pywinauto</td>
<td><code>pip install fsq-agent[windows]</code></td>
</tr>
<tr>
<td>🍎 <b>macOS</b></td>
<td>Appium Mac2</td>
<td><code>pip install fsq-agent[macos]</code></td>
</tr>
</table>

All platforms share the same `HarnessInterface`, evidence model, and FSQ YAML format. A registered workspace may configure one or more platforms independently:

```text
<workspace-root>/
  .fsq/config/config.<platform>.yaml
  cases/<platform>/
  knowledge/<platform>/
  .fsq/runs/<platform>/
```

The `run` command requires `--platform PLATFORM` and uses the exact current directory as its workspace root. The `report` and `playground` commands require both `--workspace NAME` and `--platform PLATFORM`. The `control-plane` command manages browser selection instead and accepts neither option.

<details>
<summary><b>Platform setup details</b></summary>

**Web** — Set the browser executable in `.fsq/config/config.web.yaml`:
```yaml
target:
  browser_executable_path: /usr/bin/google-chrome
```

**Android** — Set the app ID in `.fsq/config/config.android.yaml`, then select a connected ADB device per run:
```yaml
target:
  app_id: com.example.app
```
```bash
cd /path/to/workspaces/my-workspace
fsq-agent run --platform android \
  --android-serial emulator-5554 --goal "Open the app"
```
When exactly one device is online, `--android-serial` may be omitted.

**Windows** — Keep `backend_kind` in the repository preset `config.windows.yaml`; set app-specific values in `.fsq/config/config.windows.yaml`:
```yaml
target:
  app_path: C:\Program Files\MyApp\app.exe
  window_title_re: .*MyApp.*
```

**macOS** — Keep `appium_server_url` in the repository preset `config.macos.yaml`; set the app identity in `.fsq/config/config.macos.yaml`:
```yaml
target:
  bundle_id: com.example.app
```

</details>

---

## How It Works

<p align="center">
  <img src="docs/assets/fsq-agent-architecture-v2.png" alt="FSQ Architecture: Dual Loop, Shared Harness, Knowledge System, and Debug System" width="720">
</p>

**The Dual Loop in a nutshell:**
- **Dynamic (AI)** → LLM agent explores → evidence captured at every step → replayable YAML generated
- **Strict (Replay)** → replays YAML deterministically (no LLM) → evidence captured → pass/fail

---

## Compared To...

| | **FSQ** | Browser Use | Midscene.js | Playwright | Appium |
|---|---|---|---|---|---|
| **Evidence per step** | ✅ screenshots + UI snapshots + traces | ❌ | ❌ | ❌ | ❌ |
| **AI → Replay YAML** | ✅ auto-generated strict cases | ❌ | ❌ | Codegen (manual) | ❌ |
| **Verification** | Evidence-based verifier | Agent self-report | Vision assert | Manual assertion | Manual assertion |
| **Cross-platform** | Web + Android + Windows + macOS | Web only | Web + Mobile | Web only | Multi (different APIs) |
| **Runs without LLM** | ✅ Strict mode | ❌ | ❌ | ✅ | ✅ |
| **Extensible harness** | Protocol-based plugin system | ❌ | ❌ | ❌ | Driver plugins |

---

## Documentation

| Resource | Description |
|---|---|
| [Architecture Overview](docs/fsq-agent-architecture-v2.md) | Dual Loop design and module structure |
| [Platform Setup](docs/) | Detailed per-platform configuration |
| [FSQ YAML Reference](docs/) | DSL syntax, lifecycle hooks, replay semantics |
| [Harness Development Guide](docs/) | Build a new platform harness |
| [Roadmap](ROADMAP.md) | Product direction and planned phases |
| [Governance](GOVERNANCE.md) | Roles, decisions, and maintainer responsibilities |

<!-- TODO: Set up docs site (mkdocs-material + GitHub Pages) -->

---

## Contributing

We welcome contributions! FSQ is designed to be extended.

```bash
git clone https://github.com/microsoft/FSQ.git && cd FSQ
uv sync --extra dev
npm ci && npm run build
uv run python -m pytest
```

**Ways to contribute:**

| Path | For whom |
|---|---|
| 🐛 Report bugs / suggest features | Everyone |
| 📝 Improve docs and examples | Beginners welcome |
| 🧪 Add FSQ YAML test cases | QA engineers |
| 🔌 Build a new platform harness | Platform experts |
| ⚡ Improve agent / verification | AI engineers |

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide and contributor growth path. Project decisions and role progression follow [GOVERNANCE.md](GOVERNANCE.md).

<!-- TODO: Add "good first issue" link once issues are created -->

---

## License

[MIT](LICENSE) — Copyright (c) Microsoft Corporation.

---

<p align="center">
  <sub>Built with ❤️ by the FSQ team at Microsoft</sub>
</p>
