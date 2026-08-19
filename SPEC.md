# fsq-agent Project Specification

Root `SPEC.md` is the project-level specification and module navigation source of truth. Each module also owns a module-level `SPEC.md`.

## Project Specification Ownership

Root `SPEC.md` and module `SPEC.md` files are the current factual baseline for implementation. They describe present behavior, public contracts, module ownership, dependency direction, configuration surface, error semantics, architecture level, and implementation invariants.

## Tool And Capability Execution

fsq-agent separates dynamic-only helper tools from recordable execution capabilities.

- AgentTools are OpenAI Agents SDK helper tools used only during dynamic execution. They include scoped file reads/writes and bounded run-artifact search/slice helpers. AgentTools are not strict replay capabilities, are not registered in FSQ capability registries, and are never recorded into generated strict YAML.
- CommonTools are recordable platform-default execution capabilities inherited by every active platform. The active CommonTool is `wait_ms`/`waitMs`. Runtime-secret credential input is represented on text-entry PlatformTools with `textType: runtimeSecret` and is resolved by execution core before driver invocation, not by an LLM-facing secret-fetch tool.
- PlatformTools are recordable active-platform capabilities. They include concrete backend driver actions, including backend-owned assertions such as `assert_with_ai`.

All recordable execution behavior is declared through decorator-driven capability metadata. The neutral `capabilities` module owns shared declaration decorators, catalog-backed platform validation, and reflection/discovery helpers that produce `models.CapabilityDefinition` records for CommonTools and PlatformTools. The capability registry is the source of truth for canonical names, replay aliases from `ReplayPolicy(kind="fsq_command")`, parameter schemas, tool family, replay policy, sensitivity, step kind, platform/backend ownership, and provenance. LLM-facing CommonTool and PlatformTool parameter schemas are generated from shared Pydantic parameter models and include concise field descriptions plus model-level guidance for cross-field argument rules such as target-or-locator and runtime-secret text-entry contracts. Live capability executor kinds are `common` for inherited CommonTools and `driver` for driver-backed PlatformTools; `harness` is not a live capability executor kind. Capability metadata does not own per-tool SDK schema strictness or default screenshot capture policy; active SDK capability tools use strict JSON schema by default. Methods that are unfinished or should not be exposed to the LLM must not be decorated as active capabilities.

Decorator unification is a declaration-layer concern, not an AgentTool merge. AgentTools remain dynamic-only helper behavior owned by `tools`; CommonTool and PlatformTool capabilities are owned by `core`. CommonTool bodies live in platform tool providers, while backend-specific PlatformTool bodies live on concrete backend drivers. Concrete harness classes such as `AndroidHarness` and `WebHarness` remain runner-facing runtime gateways and services, but they must not own individual tool bodies such as `assert_with_ai`.

`StepRunner` is the common execution manager for CommonTool and PlatformTool capabilities. It looks up the capability registry, validates params, resolves runtime-secret text input references, applies step-kind evidence capture, post-action delay, and sensitivity policy, emits structured safe events, and invokes recordable capabilities through `HarnessInterface.invoke_action(step, context)`. Harness implementations route CommonTools to inherited platform tool providers and driver-backed PlatformTools to concrete backend drivers while supplying runtime services such as context, artifact capture, evaluator injection, driver access, settings, and error classification. Default automatic evidence capture is derived from the resolved capability plus `ExecutableStep.kind`, not executor kind: `action` captures before and after, `assertion` captures before only, `setup` captures after only, and `teardown` captures before only; observation and diagnostic steps do not receive automatic screenshot capture. CommonTool action steps such as `wait_ms` receive the same automatic capture policy as PlatformTool action steps. Every automatic capture records the platform-neutral pair `screenshot` plus `ui_snapshot`. Existing explicit observation command aliases such as Android `uiTree` and Web/desktop `uiSnapshot` remain valid authored capabilities and replay aliases, but they do not control automatic capture artifact naming. For every capability, the effective post-action delay resolves from `CapabilityDefinition.post_action_delay_seconds` when set, otherwise from configured `execution.post_action_delay_seconds` defaults for CommonTool or PlatformTool capabilities. A positive delay is execution timing only, occurs after invoke and before finalize/after-action evidence capture, and must not create synthetic `waitMs` commands, evidence steps, replay commands, or action results. Executable paths must not branch on names such as `waitMs`, `wait_ms`, Android command names, Web command names, or desktop command names.

Capability registry bootstrap is platform-selected. Entry layers register the active platform's inherited CommonTool capabilities plus only the configured platform's PlatformTool capability set. Android and Web PlatformTools must not be registered together in the default runtime registry, so each platform can expose native canonical names and `fsq_command` replay aliases without cross-platform ambiguity. AgentTools are exposed only to dynamic SDK agents and are excluded from strict replay registries.

## Case Creation And Testing

The public Case workflows are `fsq case create` and `fsq case test`. Case creation accepts a natural-language Goal, uses AI during real testing, and may write a Run-local candidate `*.fsq.yaml`. Case testing accepts an existing `*.fsq.yaml` and preserves the source file. With `--suggest`, AI may produce suggestions and a Run-local candidate while preserving original execution facts; without it, testing does not permit AI-driven Case modification. Adapters invoke both workflows through the shared Application package.

`*.fsq.yaml` is canonical. `*.codex.yaml` may be accepted for one deprecation cycle with a structured warning. `*.intent.yaml` and `fsq.test-intent/v1` are unsupported. Top-level public execution commands named `test`, `replay`, or `run` are not part of the target CLI.

## Recorded Case Artifacts

AI-participating Case operations may record a successful replayable trace as a Run-local candidate `*.fsq.yaml`. The agent persists normalized capability events and Application coordinates conversion of replayable non-observation results according to `ReplayPolicy` metadata. Generated Cases never mutate source Cases or `cases.dir`, and secrets are never persisted.

Recorded strict cases may contain runtime-secret text input references using `textType: runtimeSecret` and `waitMs` replay aliases. Strict execution bootstraps the active platform capability registry before YAML parsing, treats missing `textType` on text-entry commands as literal text for case compatibility, resolves runtime-secret text values in memory before external text-entry actions begin, and resolves `waitMs` through the registry to the inherited `wait_ms` CommonTool capability.

Recorded Web lifecycle commands are ordinary replayable capability results when the dynamic run actually executed `startBrowser` or `closeBrowser`. The recorder must not invent browser lifecycle commands as cleanup or setup guesses.

FSQ Case metadata may declare optional deterministic lifecycle hooks through `onCaseStart` and `onCaseComplete`; platform config may declare reusable hooks through `caseLifecycle`. `runCase` executes another `*.fsq.yaml` using the same contained Case path policy, and recursive chains fail before infinite execution. Application coordinates lifecycle execution through FSQ and Core authorities; adapters do not own lifecycle semantics.

## Dynamic LLM Pre-Plan and Goal Verification

Goal-based Case creation and suggestion-enabled Case testing use pre-plan as the input-understanding boundary before external UI actions begin. The pre-planner receives complete configured skills that load successfully, optional project/page knowledge, and the active capability summary. It produces ordered `key_actions` and one `verification_goal` before external UI actions.

Existing-Case testing parses the Case through FSQ rather than treating YAML as untyped planning text. Suggestion-enabled testing may use the parsed Case and execution facts as AI context, but source steps remain immutable and candidate changes are Run-local artifacts.

## Runtime Configuration Defaults

The exact CLI current directory is a registered workspace root using the canonical `.fsq/config/config.<platform>.yaml`, `.fsq/runs/<platform>/`, `cases/<platform>/`, and `knowledge/<platform>/` layout. CLI does not create or accept `.fsq-agent-workspace` markers, search parents, or auto-initialize. `fsq init` may safely establish one platform in the existing current project root through shared Application and Config workspace operations; all other CLI commands require the exact registered root, and platform operations require the selected platform. Control Plane uses the same registry and layout while retaining explicit browser workspace selection independent of its startup directory.

Default local LLM runs use GitHub Copilot provider authentication with Copilot model `gpt-5.5` and tracing enabled. Provider selection and credentials are managed by the Provider configuration surface rather than workspace initialization. Repository-owned platform YAML presets are committed as `config.android.yaml`, `config.web.yaml`, `config.windows.yaml`, and `config.macos.yaml`; `config.example.yaml` is reference-only. Workspace platform configuration owns local target identity and private runtime-secret values. A Web target always names a browser channel and may omit its executable path so Application can discover exactly one compatible host executable before Driver readiness or workspace mutation.

The local workspace setup entry is `fsq init --platform android|web|windows|macos` with the selected platform's target options. It initializes or updates exactly one platform at the exact current registered workspace root and does not configure Providers or create legacy workspace markers.

## Platform Blocks

Shared platform rules:

- `harness.platform` selects exactly one active platform for normal dynamic, strict, and playground execution.
- Public CLI entry points select the active platform with `--platform android|web|windows|macos` where platform context is needed; config loading maps that platform id to the corresponding repository-owned `config.<platform>.yaml` preset before validation. Public CLI commands do not expose workspace selection and use the exact registered current directory with canonical `.fsq` platform configuration. Provider configuration is separate from `fsq init`.
- Entry layers build a platform-selected capability registry: inherited CommonTool capabilities plus only the active platform's PlatformTool capabilities.
- `StepRunner`, `StepSequenceRunner`, evidence, recording, report generation, and FSQ parsing stay platform-neutral and consume capability metadata rather than platform action-name branches.
- Repository-owned platform YAML presets own stable platform defaults and policy; environment variables own provider selection, required operator-provided values, local paths, local server URLs, target identifiers, credentials, and other machine-specific values. Current compatibility inputs for older YAML-owned local paths must be explicit in module SPECs, and examples use the env-owned shape.
- Platform-specific behavior belongs in platform parameter models, action catalogs, harnesses, drivers, config blocks, and configured skill Markdown.

Android platform block:

- Platform id: `android`.
- Backend: `uiautomator2`.
- Local app/device values come from `FSQ_ANDROID_APP_ID` and `FSQ_ANDROID_SERIAL` or strict FSQ case metadata where allowed.
- Explicit observation capability: canonical `ui_snapshot` with Android alias `uiTree`. Automatic runner evidence captures `screenshot` plus normalized `ui_snapshot` using compact Android UI hierarchy XML content. Android compact UI snapshots keep the existing `{"xml": ...}` payload shape, may use source-level hierarchy compression when available, remove layout-only/default data, clip long text-like attributes to the first 50 characters, and fall back to raw hierarchy XML if compaction is unavailable or unsafe.
- Harness skill: `android-harness.md`.

Web platform block:

- Platform id: `web`.
- Backend: `playwright`.
- Runtime settings include browser channel, environment-backed browser executable path, headless mode, optional base URL, and optional viewport fields when specified by module specs.
- Browser lifecycle is explicit through `start_browser`/`startBrowser` and `close_browser`/`closeBrowser`. Runtime, CLI, FSQ parsing, StepRunner, StepSequenceRunner, and playground entry paths must not auto-inject lifecycle commands or launch a browser as a driver-construction side effect.
- `startBrowser` is idempotent and reuses the active browser/page when one is already started. `closeBrowser` is idempotent, closes the active browser/page when present, resets driver-owned state, and permits a later `startBrowser` in the same task.
- Web page-dependent actions, including `navigateTo`, require an active browser/page and must fail clearly when invoked before `startBrowser`; `navigateTo` must not implicitly start the browser.
- Explicit observation capability: `ui_snapshot` with alias `uiSnapshot`; Web must not expose Android `ui_tree`/`uiTree` naming. Automatic runner evidence captures `screenshot` plus normalized `ui_snapshot` using Web page/accessibility snapshot content.
- Current action surface follows Playwright MCP core automation semantics: snapshot-first targets, semantic actions, screenshots as observation/evidence, and no unsafe/opt-in capability families.
- Harness skill: `web-harness.md`.

Windows platform block:

- Platform id: `windows`.
- Backend: `pywinauto`.
- Operator-local values come from environment variables: `FSQ_WINDOWS_APP_PATH`, `FSQ_WINDOWS_BACKEND_KIND`, `FSQ_WINDOWS_WINDOW_TITLE_RE`, and `FSQ_WINDOWS_LAUNCH_ARGS`. YAML owns only stable Windows platform/backend selection. `FSQ_WINDOWS_BACKEND_KIND` selects pywinauto's UI automation mode (`uia` by default, or `win32`) and is not a second FSQ Windows backend.
- Windows action surface exposes desktop aliases through the existing PlatformTool registry: `launchApp`, `killApp`, `clickOn`, `doubleClickOn`, `rightClickOn`, `typeText`, `pressKey`, `hoverOn`, `scrollOn`, `dragTo`, `assertVisible`, `uiSnapshot`, and `assertWithAI`.
- Explicit observation capability: `ui_snapshot` with alias `uiSnapshot`; Windows must not expose Android `ui_tree`/`uiTree` naming. Automatic runner evidence captures `screenshot` plus normalized `ui_snapshot`.
- Harness skill: `windows-harness.md`.

macOS platform block:

- Platform id: `macos`.
- Backend: `appium_mac2`.
- Runtime maps FSQ names internally to Appium native `platformName: Mac` and `automationName: Mac2`.
- Operator-local values come from environment variables: `FSQ_MACOS_APPIUM_SERVER_URL`, `FSQ_MACOS_BUNDLE_ID`, and `FSQ_MACOS_APP_PATH`. YAML owns stable macOS defaults such as backend selection, page-source simplification depth, and action timeout seconds.
- Current action surface exposes desktop aliases through the existing PlatformTool registry: `launchApp`, `killApp`, `clickOn`, `doubleClickOn`, `rightClickOn`, `typeText`, `pressKey`, `hoverOn`, `dragTo`, `takeScreenshot`, `uiSnapshot`, `assertVisible`, `assertElementsOrder`, and `assertWithAI`.
- Explicit observation capability: `ui_snapshot` with alias `uiSnapshot`; macOS must not expose Android `ui_tree`/`uiTree` naming. Automatic runner evidence captures `screenshot` plus normalized `ui_snapshot` using a bounded compact semantic Appium Mac2 control tree that preserves useful locator, text, state, and geometry signals.
- Harness skill: `macos-harness.md`.
- The Appium MCP reference project may guide Mac2 session mechanics and action semantics, but fsq-agent must not wrap or depend on that MCP server as a runtime capability source.

## Prompt Context Boundaries

Dynamic LLM prompt context has four distinct channels. `agent_instructions.j2` owns stable dynamic execution rules. `task_input.j2` owns one task's structured input, ordered key actions, and final `verification_goal`. `knowledge/project.md` owns tested-project-specific guidance loaded for normal dynamic execution and, when present, may also inform pre-plan. Configured skills under the knowledge root own composable execution guidance such as platform and harness rules and are included in pre-plan only when they load successfully. Optional page graph knowledge is pre-plan-only: `index.md` is loaded when present under the resolved pre-plan knowledge directory, and indexed page files are read on demand. There is no separate custom-instruction configuration channel; ad hoc operator guidance must be represented as project knowledge or configured skills.

Loader diagnostics such as missing optional skills or missing optional knowledge references are operational signals and must not be rendered into model-facing prompts. Required skill failures remain fail-fast. Optional broken skills are skipped with operator-visible diagnostics and are not passed to the LLM as warning-only or partial guidance. Runtime Markdown knowledge and skill content should stay concise, current, and aligned with exposed AgentTool, CommonTool, and PlatformTool surfaces.

## Module Table

| Module | SPEC | Purpose |
|---|---|---|
| models | fsq_agent/models/SPEC.md | Owns shared domain models, platform-runtime status facts, FSQ case and lifecycle hook metadata/settings models, capability metadata/registry contracts, invocation/result contracts, replay reference models, and exceptions. |
| capabilities | fsq_agent/capabilities/SPEC.md | Owns neutral capability declaration decorators, catalog-backed platform action validation, and metadata discovery helpers used by `core` recordable capabilities. |
| config | fsq_agent/config/SPEC.md | Loads and validates env/YAML runtime, provider, harness/driver/platform-tool, tracing, execution post-action delay, strict case lifecycle hook settings, strict replay secret, agent context, AgentTool output, CommonTool secret, and workspace configuration. |
| providers | fsq_agent/providers/SPEC.md | Builds shared Azure OpenAI and GitHub Copilot provider sessions for agent runs, verifier/pre-planner calls, and provider-backed AI assertion evaluators. |
| tools | fsq_agent/tools/SPEC.md | Provides dynamic-only AgentTool providers, scoped file helpers, bounded artifact lookup helpers, and the OpenAI Agents SDK AgentTool adapter. |
| observation | fsq_agent/observation/SPEC.md | Persists run event timelines; screenshots, UI trees, and other observations are represented by platform evidence artifacts or AgentTool artifact refs. |
| knowledge | fsq_agent/knowledge/SPEC.md | Loads project-specific application knowledge and task-referenced knowledge assets. |
| fsq | fsq_agent/fsq/SPEC.md | Loads FSQ AI Test DSL YAML cases, validates case lifecycle hook metadata, resolves authored action aliases through the capability registry, validates replay references, and converts parsed command documents into canonical deterministic executable steps. |
| skills | fsq_agent/skills/SPEC.md | Loads complete configured automation skill instruction bundles and skips or fails broken bundles according to requiredness. |
| report | fsq_agent/report/SPEC.md | Generates LLM task reports, strict-core evidence reports, reconstructs tool calls from structured capability metadata, and resolves stored reports by run id. |
| core | fsq_agent/core/SPEC.md | Defines execution orchestration, platform-runtime prerequisite checks/install and browser discovery, CommonTool/PlatformTool providers, active platform harness and driver interfaces, factories, private backends, and evidence coordination. |
| agent | fsq_agent/agent/SPEC.md | Orchestrates dynamic goal/reference execution through OpenAI Agents SDK, AgentTool exposure, active-platform capability exposure, verification, replayable event metadata, and report generation. |
| execution | fsq_agent/execution/SPEC.md | Coordinates transport-neutral dynamic and deterministic runs, Case lifecycle ordering, cancellation/teardown, and Run-local candidate Case recording. |
| application | fsq_agent/application/SPEC.md | Provides transport-neutral Workspace, Case, Run, Provider, and Environment operations through resource-owned modules, with shared Request, Result, Event, and Error contracts organized under `application/contracts`. |
| adapters | fsq_agent/adapters/SPEC.md | Owns CLI, Control Plane, Playground, and coding-agent external protocol adaptation while depending inward on Application and public runtime contracts. |
| playground | fsq_agent/playground/SPEC.md | Serves the local browser playground for active-platform runtime status, Android session setup where applicable, dynamic goal/raw-case execution, strict YAML execution, loading existing run results, screenshots, replay video preview, and report lookup. |
| control_plane | fsq_agent/control_plane/SPEC.md | Adapts Application operations to local HTTP/SSE/static delivery, cancellation transport, and browser evidence projection. |
| cli | fsq_agent/cli/SPEC.md | Adapts the public `fsq` command tree to Application operations with human, JSON, and JSONL output and stable exit categories. |
| frontend | frontend/SPEC.md | Owns the repository npm/Vite workspace, browser dependency and build policy, generated-asset boundary, and navigation to independently owned frontend application modules. |

## Frontend Build Boundary

- The repository root npm project owns browser-source dependency resolution and Vite compilation for repository web pages. It uses one lock file and a multi-page Vite configuration so independently owned page entries build to distinct output paths.
- `frontend/SPEC.md` owns the frontend workspace contract and links to child application specs without repeating their behavior. `frontend/playground/SPEC.md` and `frontend/control-plane/SPEC.md` own their authored browser applications; the corresponding Python modules own HTTP contracts and production static serving.
- New frontend application modules use Vite, React, and TypeScript/TSX unless their confirmed module SPEC records a concrete exception. The current `frontend/playground` module is a documented Vite-built vanilla JavaScript application and remains governed by its current module SPEC.
- `ts-ebml` is an exact npm dependency consumed through an ES module import. Third-party browser bundles and Vite-generated assets are not tracked in Git.
- Vite-generated Playground and Control Plane assets live under `fsq_agent/playground/static` and `fsq_agent/control_plane/static` and are included in the Python wheel. Release builds run the npm build before Python wheel construction. A prebuilt wheel is self-contained and does not require Node.js or network access at runtime.
- Frontend development may use the Vite development server with API and streaming requests proxied to the corresponding Python server. Production and installed-wheel usage serve each generated entry and its APIs from its owning Python process.

## Architecture Diagram

```mermaid
flowchart TD
    Adapters[adapters] --> CLI[adapters/cli]
    Adapters --> ControlPlane[adapters/control_plane]
    CLI --> Application[application]
    CLI --> ControlPlane
    ControlPlane --> Application
    ControlPlane --> Playground[adapters/control_plane/playground]
    ControlPlane --> Execution[execution]
    Playground --> Execution
    Application --> Agent[agent]
    Application --> Execution
    Application --> Core[core]
    Application --> FSQ[fsq]
    Application --> Config[config]
    Application --> Providers[providers]
    Application --> Models[models]
    Application --> Report[report]
    Agent --> Core[core]
    Agent --> Config[config]
    Agent --> Providers[providers]
    Agent --> Models[models]
    Agent --> Tools[tools]
    Agent --> Observation[observation]
    Agent --> Knowledge[knowledge]
    Agent --> Skills[skills]
    Agent --> Report[report]
    Execution --> Agent
    Execution --> Core
    Execution --> FSQ
    Execution --> Config
    Execution --> Models
    Execution --> Report
    Config --> Models
    Providers --> Config
    Providers --> Models
    Tools --> Models
    Observation --> Models
    Knowledge --> Models
    FSQ --> Models
    Skills --> Models
    Report --> Models
    Core --> Models
    Capabilities[capabilities] --> Models
    Core --> Capabilities
    Frontend[frontend] --> FrontendPlayground[frontend/playground]
    Frontend --> FrontendControlPlane[frontend/control-plane]
    FrontendPlayground --> Playground
    FrontendPlayground --> StaticAssets[generated static assets]
    Playground --> StaticAssets
    FrontendControlPlane --> ControlPlane
    FrontendControlPlane --> ControlPlaneStatic[generated Control Plane static assets]
    ControlPlane --> ControlPlaneStatic
```

## Development Rules

- Each Python module exposes public symbols only from `__init__.py` using explicit `__all__`.
- A package may organize one module's public implementation into resource-owned public modules and subpackages while retaining `__init__.py` as its complete convenience export boundary. Public resource modules must not duplicate contracts or behavior.
- `pyproject.toml` is the source of truth for the repository's pinned Ruff version, lint policy, formatter policy, thresholds, and scoped exclusions. Repository-owned Python must conform to that configuration without separate lint baselines or blanket suppression mechanisms.
- Repository Python changes must pass the locked Ruff lint and format validation plus the complete pytest suite. Formatting or remediation must preserve current public interfaces, runtime behavior, module ownership, and dependency direction.
- Frontend dependency changes update the root npm manifest and lock file. Generated frontend assets and `node_modules` remain untracked; source-checkout production startup requires a successful frontend build, while installed wheels contain the generated assets.
- Repository CI is defined by `.github/workflows/ci.yml`; that workflow is the source of truth for current automated validation.
- Python public API boundary optimization is incremental. When a Python module SPEC adopts the stricter boundary, public exports should be limited to interfaces/protocols, abstract classes, stable service classes that are themselves the public contract, and approved factory classes. Concrete implementation-selection classes such as platform harnesses, platform backends, and provider adapters should sit behind public protocols/factories unless the module SPEC records a named exception with allowed importers, rationale, and revisit condition. Function-style helpers, decorators, and discovery utilities require the same SPEC-visible exception policy.
- Internal Python implementation files are prefixed with `_`.
- Shared data structures and exceptions live only in the `models` module. Capability declaration decorators, catalog-backed platform validation, and decorated-method discovery live only in the `capabilities` module.
- Module imports must follow the DAG in the architecture diagram.
- Transport implementation lives under `adapters`. The legacy `cli`, `control_plane`, and `playground` paths are compatibility entries exposing the same canonical adapter objects and modules without duplicate transport behavior or mutable state.
- Package-private composition helpers at the `fsq_agent` package root may compose public module APIs for shared entry-layer capability bootstrap, registry-metadata-based provider requirement detection, strict lifecycle orchestration, and dynamic-run recording used by CLI, Playground, and Control Plane. Provider requirement detection compares the active platform registry with and without provider-backed capabilities and resolves executable steps through the registry snapshot rather than branching on action names. These helpers must remain private, must not expose public module contracts, and must not be imported by `models`, `capabilities`, `tools`, `fsq`, `core`, `providers`, or `report`.
- `capabilities` may import `models` only among project modules. It must not import `tools`, `core`, `agent`, `cli`, `fsq`, `providers`, `report`, `playground`, SDK objects, concrete drivers, or backend runtime types.
- Provider construction lives in `providers`; `core` must use provider-neutral protocols and must not import provider/runtime modules.
- Dynamic-only local helper utilities live as AgentTools in `tools`; recordable CommonTool and PlatformTool capabilities live in `core`, with CommonTool bodies in platform tool providers and backend PlatformTool bodies on concrete drivers. CommonTools and PlatformTools declare executable metadata through `capabilities`. All recordable capabilities must be registered before strict YAML parsing or SDK capability exposure, and platform registries must contain only inherited CommonTools plus the active platform's PlatformTools. AgentTools must not be registered for strict replay.
- Replay, sensitivity, evidence, and tool-origin behavior must come from capability metadata and normalized `StepRunner` results, not hard-coded tool-name sets.
- New platforms or capability groups reuse shared capability declaration and registry contracts unless the project specification defines a changed shared contract.

## Python Architecture Rules

- Use the lowest architecture level that keeps the module clear, testable, and changeable.
- `models`, `capabilities`, `tools`, `fsq`, `report`, `knowledge`, `skills`, `config`, `providers`, and `observation` default to Level 2 Simple Package unless a module SPEC records a stronger need.
- `core`, `agent`, `execution`, `application`, `adapters`, `cli`, `playground`, and `control_plane` use Level 3 because they coordinate execution flows, external SDKs, harnesses, providers, persistence, shared application operations, or transport entry points.
- Public APIs must be exported from module `__init__.py` files, and internal implementation modules must remain private across module boundaries. Modules that have adopted the stricter public API boundary must not export concrete implementation-selection classes, helper functions, decorators, or discovery utilities unless their module SPEC records an explicit exception. Public factories should own construction/selection of private implementations when a caller only needs a protocol or service contract.
- Do not introduce Repository, Unit of Work, Clean Architecture, or DDD patterns unless a confirmed SPEC records the concrete reason.
