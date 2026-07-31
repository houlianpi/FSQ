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
│ $ fsq-agent run --platform web --goal "Search for FSQ on Bing"       │
├──────────────────────────────────────────────────────────────────────┤
│  ► Planning: 3 key actions identified                                │
│  ► Step 1: startBrowser          📸 screenshot + UI snapshot         │
│  ► Step 2: navigateTo bing.com   📸 screenshot + UI snapshot         │
│  ► Step 3: typeText "FSQ"        📸 screenshot + UI snapshot         │
│  ► Step 4: pressKey Enter        📸 screenshot + UI snapshot         │
│  ► Verification: PASSED ✅ (evidence-based)                          │
│  ► Strict YAML generated → output/case.codex.yaml                   │
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

### 2. Initialize

```bash
fsq-agent init --platform web --provider github_copilot
```

<details>
<summary><b>Provider options</b></summary>

| Provider | Setup |
|---|---|
| GitHub Copilot | `--provider github_copilot` (device-code auth) |
| Azure OpenAI | `--provider azure_openai` (API key) |

</details>

### 3. Run

```bash
# Dynamic: AI-driven exploration with full evidence
fsq-agent run --platform web \
  --goal "Open https://www.bing.com, search for 'FSQ automation', verify results appear."
```

```bash
# Strict: Deterministic replay from YAML (no LLM needed)
fsq-agent run --platform web --strict --case-yaml path/to/case.codex.yaml
```

**Output:** `screenshots` + `UI snapshots` + `verification report` + `replayable .codex.yaml`

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

All platforms share the same `HarnessInterface`, evidence model, and FSQ YAML format.

<details>
<summary><b>Platform setup details</b></summary>

**Web** — Set browser path in `.env`:
```dotenv
FSQ_WEB_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome
```

**Android** — Connect device via ADB:
```dotenv
FSQ_ANDROID_APP_ID=com.example.app
FSQ_ANDROID_SERIAL=emulator-5554
```

**Windows** — Point to target app:
```dotenv
FSQ_WINDOWS_APP_PATH=C:\Program Files\MyApp\app.exe
FSQ_WINDOWS_BACKEND_KIND=uia
FSQ_WINDOWS_WINDOW_TITLE_RE=.*MyApp.*
```

**macOS** — Start Appium Mac2 server:
```dotenv
FSQ_MACOS_APPIUM_SERVER_URL=http://127.0.0.1:4723
FSQ_MACOS_BUNDLE_ID=com.example.app
```

</details>

---

## How It Works

```
                         FSQ Dual Loop
    ┌────────────────────────────────────────────────┐
    │                                                │
    │   ┌───────────┐          ┌───────────┐        │
    │   │  Dynamic  │ generates│   Strict  │        │
    │   │   (AI)    │────────▶│  (Replay)  │        │
    │   └─────┬─────┘          └─────┬─────┘        │
    │         │                      │               │
    │         ▼                      ▼               │
    │   ┌─────────────────────────────────────┐      │
    │   │       Shared Harness Core           │      │
    │   │   Web · Android · Windows · macOS   │      │
    │   └──────────────────┬──────────────────┘      │
    │                      │                         │
    │                      ▼                         │
    │   ┌─────────────────────────────────────┐      │
    │   │         Evidence Layer              │      │
    │   │  screenshots · UI snapshots · traces│      │
    │   │  verification · action results      │      │
    │   └─────────────────────────────────────┘      │
    └────────────────────────────────────────────────┘

    Dynamic → LLM agent explores → evidence captured → YAML generated
    Strict  → replays YAML (no LLM) → evidence captured → pass/fail
```

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

<!-- TODO: Add "good first issue" link once issues are created -->

---

## License

[MIT](LICENSE) — Copyright (c) Microsoft Corporation.

---

<p align="center">
  <sub>Built with ❤️ by the FSQ team at Microsoft</sub>
</p>
