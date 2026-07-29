# Playground Vite Frontend Design

## Goal

Move the Playground browser UI into an npm-managed Vite frontend so third-party browser dependencies are versioned through npm instead of committed vendor files. Preserve the Python Playground CLI, HTTP API, packaged-wheel behavior, and existing user-visible functionality while leaving a clean path for additional independent web pages.

## Scope

- Introduce one repository-root npm/Vite frontend project.
- Move authored Playground HTML, JavaScript, CSS, and lifecycle editor JavaScript into `frontend/playground/`.
- Manage `ts-ebml` as an exact npm dependency and consume it through an ES module import.
- Generate the Python-served Playground static assets with Vite.
- Keep generated frontend assets out of Git.
- Preserve all current Playground UI behavior, including existing uncommitted Preview/Report mode-state and UI snapshot diff fixes.
- Support a development workflow with a Vite development server proxying Playground API requests to the Python server.
- Keep the production and installed-wheel workflow as one Python Playground process.
- Structure Vite so later independent page entries can be added without replacing the Playground entry or output.

## Non-Goals

- Do not introduce React, another UI framework, or TypeScript in this migration.
- Do not change Playground HTTP endpoint paths or payloads.
- Do not change `fsq-agent playground` CLI arguments or platform behavior.
- Do not implement the planned second web page.
- Do not move Playground API or execution behavior into Node.js.
- Do not require Node.js for users installing and running a prebuilt Python wheel.
- Do not commit Vite-generated bundles or npm `node_modules`.

## Proposed Design

### Frontend Project

The repository root owns `package.json`, `package-lock.json`, and `vite.config.js`. The package is private and defines at least:

- `dev`: start Vite for frontend development.
- `build`: build all configured frontend entries.

`ts-ebml` is pinned exactly to version `3.0.2`. Vite is a pinned development dependency through the npm lock file. The initial authored source tree is:

```text
frontend/
  playground/
    index.html
    playground.js
    playground.css
    lifecycle-editor-model.js
```

The existing Playground source assets move from `fsq_agent/playground/static/` to this tree. The existing `fsq_agent/playground/static/vendor/ts-ebml.min.js` file is removed from Git.

`playground.js` imports the browser API directly from `ts-ebml`. The seekable-WebM implementation uses imported `Decoder`, `Reader`, and `tools` values rather than probing global names on `window`. Vite bundles the dependency and its browser transitive dependencies.

### Build Output

Vite writes the Playground production entry and hashed assets under `fsq_agent/playground/static/`. This directory is generated output and is ignored by Git. Vite may empty only the managed generated output for the complete configured multi-page build; all current and future entries must be declared in the same build configuration before enabling output cleanup.

`pyproject.toml` continues to include `fsq_agent/playground/static` in the Python wheel. Release CI must run the npm build before the Python wheel build. A prebuilt wheel therefore remains self-contained and requires neither Node.js nor network access at runtime.

A source checkout without generated assets is not directly runnable through the production static server. Playground startup must fail clearly when the generated static root or required entry is absent, with an actionable message to run `npm ci` followed by `npm run build`.

### Development Flow

Frontend development uses two processes:

1. Start the Python Playground server on `127.0.0.1:8878` for APIs and runtime behavior.
2. Run `npm run dev` and open the Vite URL, normally `http://127.0.0.1:5173/`.

Vite proxies Playground API, SSE, report, replay, video, YAML, screenshot, runtime, session, and artifact requests to the Python origin. The proxy target defaults to `http://127.0.0.1:8878` and may be overridden by a frontend development environment variable. Static frontend requests remain owned by Vite.

Production-like local verification runs `npm ci`, `npm run build`, then starts only `fsq-agent playground` and opens the Python server URL.

### Multiple Page Extensibility

The Vite configuration is a multi-page application configuration. Playground is a named entry rather than an assumed permanent single page. A later page may add its own authored directory and HTML entry, and Vite will emit it to a distinct route/output path.

The initial migration preserves the current Python Playground root URL `/`. Future page routing is outside this migration and must receive its own design/spec cycle. The build configuration must not allow one entry to overwrite another entry's HTML or assets.

### Python Ownership

The `playground` Python module continues to own:

- The Playground HTTP API.
- Production static serving from packaged generated assets.
- CLI startup validation of required static output.
- Existing runtime, execution, report, replay, YAML, screenshot, and step-artifact behavior.

The npm project owns authored browser source and frontend dependency resolution. It does not become a Python module and does not import Python implementation details.

## Python Architecture

- Architecture level: Level 3 Layered Application, unchanged.
- Public API: Existing `PlaygroundServer`, `PlaygroundServerOptions`, `run_playground`, CLI behavior, and HTTP endpoints remain unchanged.
- Internal modules: Existing Python internals remain unchanged; authored frontend source moves outside the Python package while generated assets remain package data.
- Domain boundaries: Python retains execution and HTTP behavior. Vite owns frontend compilation only.
- Boundary models: Existing JSON HTTP payloads remain unchanged.
- Dependency direction: Python runtime does not depend on Node.js. The release build depends on npm/Vite before Python packaging. Browser code depends on generated npm bundles and Python HTTP contracts.
- Rationale: The migration changes frontend build ownership but does not add domain behavior or justify a higher Python architecture level.

## Error Handling And Edge Cases

- Missing generated static output fails at Playground startup with the required npm build commands.
- Missing or incompatible `ts-ebml` imports fail the Vite build rather than degrading at browser runtime.
- Vite development proxy errors remain visible as failed API requests and do not trigger a second execution implementation.
- SSE endpoints must remain streamable through the Vite proxy.
- Binary replay video responses and HTTP range requests must pass through the Vite proxy without response transformation.
- Vite base paths and emitted asset paths must work both through the Vite development origin and the Python root origin.
- Windows, macOS, Linux, Android, and Web Playground modes share the same generated frontend.
- Existing dirty workspace changes in Playground source and tests must be preserved during file migration. Unrelated untracked files must not be modified.

## Specifications Expected To Change

- Root `SPEC.md`: add the repository frontend build/package boundary and release-build requirement where project-level development rules are owned.
- `fsq_agent/playground/SPEC.md`: replace package-authored static source ownership with npm-authored source/generated package assets; document development and packaged runtime behavior, missing-build errors, and npm `ts-ebml` ownership.
- `fsq_agent/cli/SPEC.md`: only if startup error behavior is specified there; no CLI syntax or public command behavior changes.

## Verification Expectations

- `npm ci` succeeds from the lock file.
- `npm run build` succeeds and creates the production Playground entry and assets under `fsq_agent/playground/static/`.
- Generated HTML does not reference `/vendor/ts-ebml.min.js` and the vendor file is absent from tracked source.
- The Python Playground static server serves the generated entry and hashed assets.
- Missing generated output produces the documented actionable startup error.
- Existing Playground Python tests pass after adapting source/static fixture paths where necessary.
- Frontend-focused tests verify the imported `ts-ebml` seekable-WebM path.
- Browser verification covers initial render, Goal/YAML/Strict YAML mode switching, Preview/Report restoration, UI snapshot before/after diff display, replay generation, stored replay playback, and seeking.
- Browser verification runs against a desktop and a narrow viewport and checks that the app remains nonblank and controls do not overlap.
- A Python wheel built after the frontend build contains all required Playground production assets and runs without Node.js installed.
- Final implementation is audited against confirmed root and Playground specifications.

## Resolved Decisions

- Generated Vite bundles are not committed to Git.
- The repository uses one root npm project rather than one npm project per page.
- Vite uses a multi-page structure to support future independent pages.
- Vanilla JavaScript remains the frontend implementation language for this migration.
- A prebuilt wheel is the Node-free distribution unit; source builds require the npm frontend build before Python packaging.
