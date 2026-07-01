# fsq-agent

fsq-agent is a goal-driven automated testing agent for FSQ YAML-guided tasks. It executes harness-generated platform actions plus common local utilities, captures evidence, verifies one pre-plan-derived goal, and generates reports.

The project follows spec-driven development. See root [SPEC.md](SPEC.md) and each relevant module `SPEC.md` before changing public interfaces.

## Quick Start

For Android runs:

```bash
python -m pip install -e ".[dev,android]"
copy .env.example .env
fsq-agent init --config config.example.yaml
fsq-agent run --config config.example.yaml --goal "Access Downloads through the browser overflow menu from the New Tab Page, then return to the New Tab Page."
fsq-agent run --config config.example.yaml --case-yaml cases/android/example.codex.yaml
fsq-agent run --config config.example.yaml --strict --case-yaml cases/android/example.codex.yaml
fsq-agent report --config config.example.yaml --run-id RUN_ID --format markdown
```

For Web runs with your locally installed Chrome:

```bash
python -m pip install -e ".[dev,web]"
copy .env.example .env
fsq-agent init --config config.local.web.yaml
fsq-agent run --config config.local.web.yaml --goal "Open https://www.bing.com, search for Playwright, and verify the results page is visible."
```

## Runtime Configuration

For Android runs, install the Android extra, connect an emulator/device, and keep only the platform/backend in config:

```yaml
harness:
  platform: android
  android:
    backend: uiautomator2

execution:
  post_action_delay_seconds:
    platform: 1.0
    common: 0.0
```

Set Android user values in `.env`:

```dotenv
FSQ_ANDROID_APP_ID=com.microsoft.emmx
FSQ_ANDROID_SERIAL=
```

`FSQ_ANDROID_APP_ID` is required for dynamic LLM runs and for strict cases that do not provide `appId` in FSQ case metadata. Set `FSQ_ANDROID_SERIAL` to an `adb devices` serial when more than one device is connected; otherwise leave it blank.

For Web runs, install the Web extra, set the browser executable path in `.env`, and select the Web platform:

```dotenv
FSQ_WEB_BROWSER_EXECUTABLE_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
```

The path is required for Web runs. It must point to an existing local Chrome executable that matches `channel: chrome`.

```yaml
harness:
  platform: web
  web:
    backend: playwright
    channel: chrome
    headless: false
    base_url: null

execution:
  post_action_delay_seconds:
    platform: 1.0
    common: 0.0
```

  `channel: chrome` is the Web browser selector. When a Web task executes `startBrowser`, fsq-agent launches Playwright's Chromium engine with `FSQ_WEB_BROWSER_EXECUTABLE_PATH`, so Web runs use the user's configured local Chrome and do not require `python -m playwright install chromium`.

Web FSQ cases should model browser lifecycle explicitly:

```yaml
schemaVersion: fsq.ai-test/v1
name: Web Example
platform: web
---
- startBrowser
- navigateTo:
    url: https://www.bing.com
- pageSnapshot
- closeBrowser
```

For account-dependent cases, put secret values in `.env` and allow only those names in config:

```yaml
runtime_secrets:
  allowed_env_names:
    - TEST_ACCOUNT_EMAIL
    - TEST_ACCOUNT_PASSWORD
```

Existing process environment variables take precedence over `.env` values. Secret values must not be stored in config YAML.

Knowledge and skills are grouped under the agent context. Relative `skills.dir` and `pre_plan.dir` values resolve under `agent_context.knowledge.root_dir`:

```yaml
agent_context:
  knowledge:
    root_dir: ./knowledge
    skills:
      dir: skills
      items:
        - name: automation-basics
          description: Semantic action and evidence guidance for local runs.
          kind: markdown
          path: automation-basics.md
          required: true
    pre_plan:
      dir: project_android_v1
```

Dynamic LLM runs do not expose a verification-mode setting. Before UI actions begin, pre-plan summarizes the input into ordered execution key actions plus one `verification_goal`; the final verifier checks that single goal against execution evidence. Existing configs that still contain `verification` or `verification.mode` fail validation so the obsolete setting is not silently ignored.

## Running Tasks

Use `run --goal` when you want the agent to start from a natural-language goal:

```bash
fsq-agent run \
	--config config.local.yaml \
	--goal "Access Downloads through the browser overflow menu from the New Tab Page, then return to the New Tab Page."
```

Use `run --case-yaml` or `run --case-dir` for dynamic LLM execution from FSQ YAML reference material. In this mode the CLI reads each `.codex.yaml` file as raw UTF-8 text; it does not parse YAML, extract key actions, derive final verifier requirements, or convert commands into local steps. YAML steps are advisory and may be inaccurate; pre-plan prefers case-level intent when summarizing the final `verification_goal`.

```bash
fsq-agent run --config config.local.yaml --case-yaml path/to/case.codex.yaml
fsq-agent run --config config.local.yaml --case-dir path/to/cases
```

Use `run --strict` for deterministic strict-core execution of authored FSQ YAML. This path parses `.codex.yaml`, runs it through the configured Android driver, writes `evidence-manifest.json`, and generates `core-report.md/json` without LLM participation.

```bash
fsq-agent run --config config.local.yaml --strict --case-yaml path/to/case.codex.yaml
fsq-agent run --config config.local.yaml --strict --case-dir path/to/cases
```

`init` initializes the workspace and reports readiness for both the default LLM run path and the strict-core path. Strict-only users do not need model-provider credentials just to initialize or run `--strict` cases.

You can also create goal-only `.codex.yaml` cases by providing only case metadata. The case name is the goal, and key actions are derived at runtime:

```yaml
schemaVersion: fsq.ai-test/v1
name: Access Downloads through the browser overflow menu from the New Tab Page, then return to the New Tab Page.
platform: android
appId: com.microsoft.emmx
tags:
	- goal-driven
```

Run it with the same command used for normal FSQ cases:

```bash
fsq-agent run --config config.local.yaml --case-yaml path/to/goal-only.codex.yaml
```

## Current Scope

This implementation provides validated models, configuration loading, runtime wiring, harness/driver configuration, common local tooling, descriptive skill loading, evidence manifests, and report generation. Task execution requires authentication for the selected model provider.

Runtime artifacts are written under the fsq-agent workspace `output` directory. Shell execution settings are no longer part of runtime configuration.
