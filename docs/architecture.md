# FSQ Architecture

FSQ separates intent, execution, evidence, and review so that UI automation results can be inspected instead of accepted only from an agent response.

```text
CLI / local Control Plane
          |
          v
Application use cases ---- Config and user-level Providers
          |
          v
Case DSL / execution core ---- Run metadata and evidence
          |
          v
Platform Harness ---- Playwright / uiautomator2 / pywinauto / Appium Mac2
```

## Execution paths

Goal-driven Case creation may use a configured Provider to understand a goal and operate the selected platform. FSQ records the actions and evidence in one Run and may produce a Run-local candidate Case for review.

Case testing parses an authored `*.fsq.yaml` file and dispatches its commands through the selected platform capability registry. The source Case is not modified. With `--suggest`, the Case still executes exactly once; a separate read-only AI analysis then consumes only the source Case and persisted execution facts.

## Responsibilities

- Adapters expose the CLI and local Control Plane without owning execution rules.
- Application use cases coordinate Workspace, Provider, Case, and Run operations.
- Config owns Workspace identity, platform target settings, and user-level Provider configuration.
- The Case DSL validates portable commands and resolves them against the active platform capabilities.
- Execution core orders commands, applies evidence policy, and protects terminal Run state.
- Harnesses adapt shared execution contracts to platform Drivers.
- Playwright, uiautomator2, pywinauto, and Appium perform platform interaction; FSQ does not replace their host prerequisites.

## Local state

Workspace configuration, Cases, knowledge, and Run evidence remain beneath the exact registered Workspace root. Provider configuration is user-level and shared by the CLI and Control Plane. Reports are generated from persisted Run facts and should be reviewed before sharing because UI evidence can contain application data.

For implementation-level contracts, use the root and module `SPEC.md` files. They are the source of truth; older design and deep-dive documents are supporting material rather than release contracts.
