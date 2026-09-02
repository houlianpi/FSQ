# Getting Started

This guide takes a new user from installation to a deterministic Web run against public [TodoMVC](https://todomvc.com/examples/react/dist/). FSQ v0.1.0 is alpha software; review [support and stability](support-and-stability.md) before production adoption.

## Prerequisites

- Python 3.11 or newer.
- A supported installed Chromium-family browser. The examples use stable Chrome.
- An empty directory you can use as a local FSQ Workspace.

AI exploration and suggestion analysis also require GitHub Copilot or Azure OpenAI. Deterministic Case replay does not require a planning LLM unless the authored Case contains an AI assertion.

## Install

```bash
python -m pip install fsq-agent
fsq --help
```

The package includes all supported platform Python dependencies. FSQ does not install browsers, applications, ADB, devices, Appium services, or other host prerequisites.

## Initialize an empty Workspace

```bash
mkdir fsq-web-demo
cd fsq-web-demo
fsq init --platform web --browser-channel chrome
fsq doctor
```

An empty current directory becomes the Workspace root. When the current directory is non-empty, `init` preserves it and creates an absent `<current-directory>/<workspace-name>` child instead. Other Workspace commands must run from the exact registered root; they do not search parent directories.

## Run the public deterministic example

Download the current [`examples/web/example-domain.fsq.yaml`](../examples/web/example-domain.fsq.yaml) into `cases/web/` in the Workspace, then run:

```bash
mkdir -p cases/web
curl --fail --location --output cases/web/example-domain.fsq.yaml \
  https://raw.githubusercontent.com/microsoft/FSQ/main/examples/web/example-domain.fsq.yaml
fsq case test --platform web cases/web/example-domain.fsq.yaml
fsq runs list --platform web
```

The Case starts the configured browser, opens TodoMVC, adds two tasks, completes the first task, filters to active tasks, verifies the expected visible state, and closes the browser. Evidence is stored below `.fsq/runs/web/<run-id>/`.

## Configure AI exploration

```bash
fsq providers configure github_copilot
fsq providers status
```

Alternatively run `fsq providers configure azure_openai`. Provider configuration is user-level, stored below `~/.fsq`, and shared with the local Control Plane.

## Explore and inspect

```bash
fsq case create --platform web --goal "Open https://example.com and verify the Example Domain heading is visible."
fsq runs list
fsq runs show RUN_ID
fsq runs logs RUN_ID
fsq runs show RUN_ID --open
```

The final command creates an offline report from persisted Run facts. It does not operate the target UI or invoke a Provider.

## Analyze a deterministic run

```bash
fsq case test --platform web --suggest cases/web/example-domain.fsq.yaml
```

The Case is executed exactly once. AI analysis then consumes only the source Case, report, and persisted evidence. Suggestions and any candidate Case remain inside the corresponding Run.

## Open the Control Plane

```bash
fsq ui
```

The installed frontend is served locally on `127.0.0.1:8879` by default.

## Next steps

- Review [platform prerequisites](platform-prerequisites.md).
- Learn the [Case format](case-format.md).
- See the [CLI reference](cli-reference.md).
- Review the root and module `SPEC.md` files for implementation-level architecture and behavior contracts.
