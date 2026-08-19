# Module: application

## Purpose

Provide the shared, transport-neutral Application layer used by the FSQ CLI, Control Plane, and future Coding Agent APIs. The package exposes application operations grouped by Workspace, Case, Run, Provider, and Environment and coordinates existing module authorities without reimplementing their rules.

## Dependencies

Application may consume public APIs from `models`, `config`, `providers`, `agent`, `execution`, `fsq`, `core`, and `report`. It must not import adapters, frontend code, Click, HTTP/SSE frameworks, terminal rendering, or concrete UI types. Lower-level modules must not import `application`.

## Public Interface

The package exports transport-neutral operations and their Request, Result, Event, and Error contracts through `__init__.py`. The same symbols are available from their canonical resource modules so callers may depend on the narrow boundary they use. Operations are organized by resource domain rather than exposed through one generic `execute(command)` facade:

- Workspace operations support the shared workspace precondition, platform target resolution, Driver readiness/install coordination, and workspace initialization needed by adapters.
- Case operations support creating a Case from a Goal and testing an existing Case, including the optional suggestion policy.
- Run operations support persisted Run listing, detail lookup, and log streaming or retrieval.
- Provider operations support listing, configuration, and readiness status.
- Environment operations support listing and diagnostics.

Requests contain application inputs, Results contain operation outcomes and safe artifact references, Events describe transport-neutral progress, and Errors contain stable codes plus safe structured details. These contracts contain no Click, HTTP, SSE, terminal, or frontend types. `application.contracts` is the canonical owner of these types and groups them by shared, Workspace, Case, Run, Provider, and Environment concerns. Resource operation modules import those canonical contract objects rather than defining transport-specific or duplicate equivalents.

Canonical resource modules are:

- `application.workspace`: Workspace operations.
- `application.cases`: Case creation and testing operations.
- `application.runs`: persisted Run query and log operations.
- `application.providers`: Provider operations.
- `application.environments`: Environment operations.

`application.runs` preserves the currently supported Run query behavior and does not expand Run storage, platform selection, or execution semantics.

## Ownership Boundaries

Application owns cross-module orchestration, shared request validation, workspace enforcement, operation-level event production, and consistent results/errors for all adapters. It delegates authoritative behavior to existing modules:

- `agent` owns AI planning, model/tool orchestration, and dynamic verification.
- `execution` owns complete dynamic/deterministic run coordination, Case lifecycle semantics, cancellation/teardown ordering, and candidate Case recording.
- `fsq` owns Case DSL parsing, validation, and canonical deterministic-step adaptation.
- `core` owns capability execution, runtime-secret handling, evidence policy, and Harness/Driver routing.
- `report` owns transformation of persisted execution facts into reports and failure analysis.
- concrete drivers own platform automation and backend-error normalization.

Application must not copy, reinterpret, or fork those rules. This specification does not require `case create`, `case test`, and suggestion handling to be three independent internal Use Cases.

Workspace initialization accepts an exact current-directory root, workspace name, one platform's target inputs/environment, Driver-install authorization, and controlled-update intent. Application derives no second workspace directory and creates no marker. Before any workspace mutation it validates the request and resolves the complete target, then asks the platform runtime service to check Driver readiness and optionally coordinates one authorized supported installation and bounded recheck. Web target resolution requires an explicit channel and either validates the explicit executable path or discovers exactly one compatible host executable. Application delegates filesystem validation, existing-project adoption, platform persistence, registry mutation, idempotency, revision handling, and rollback to Config only after these prerequisites succeed, then returns committed workspace name/root/platform/status plus safe readiness/discovery facts needed by CLI or Control Plane presentation. The shared workspace precondition resolves the exact current directory through Config registry and workspace truth; a marker directory alone never satisfies it.

Application also exposes transport-neutral workspace create, add-platform, and update-platform operations used by Control Plane. Each operation accepts complete target/environment input plus the identity and revision fields required by that mutation, resolves every target, completes readiness, and only then calls Config persistence. Control Plane does not call Config workspace mutation operations directly.

Target resolution finishes before Driver check, installation, or Config mutation. It rejects cross-platform fields and missing required values; normalizes and validates explicit local paths for existence, regular-file shape, executable eligibility where applicable, and exact Web channel compatibility; and resolves an omitted Web executable only when discovery returns exactly one normalized candidate. Zero or ambiguous candidates are configuration errors and cause no runtime or persistence side effects.
For an explicit Web executable, exact compatibility uses Core's component-aware path identity contract rather than discovery membership or generic substring matching. A non-standard installation root is accepted when the normalized basename and directory or application-bundle components prove the selected product and channel. An ambiguous shared basename without the required channel identity is rejected with safe guidance to omit the path for discovery or provide a channel-identified path.

Application owns the transport-neutral workspace initialization, platform readiness, Driver check/install, and Web executable discovery use cases shared by CLI and Control Plane. It does not implement package-manager commands, filesystem registry formats, browser path tables, ADB/Appium/backend protocols, or transport wording. Platform runtime services own bounded platform-specific detection/installation mechanics; Config owns target validation and persistence. CLI and Control Plane decode inputs and project Application results/errors without reproducing this orchestration.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: resource-grouped operations and transport-neutral Request, Result, Event, and Error contracts exported from `__init__.py`.
- Dependency direction: CLI and Control Plane adapters depend on Application; Application depends on owning module public APIs; owning modules do not depend on Application.
- Rationale: the package coordinates several existing authorities and presents one consistent application boundary to multiple transports without introducing repositories, a database, a daemon, a queue, or Clean Architecture ceremony.

## Internal Structure

- `__init__.py`: Complete convenience exports for the public Application API.
- `contracts/`: Canonical transport-neutral Request, Result, Event, Error, summary, and machine-record contracts grouped by resource concern.
- `workspace.py`: Public Workspace operation boundary and private Workspace orchestration helpers.
- `cases.py`: Public Case creation/testing operation boundary and private Case orchestration helpers.
- `runs.py`: Public persisted Run query/log boundary.
- `providers.py`: Public Provider operation boundary.
- `environments.py`: Public Environment operation boundary.
- Private `_*.py` files may support these public modules but are not imported across package boundaries.

## Error Handling

Application normalizes expected operation failures into stable application Errors and preserves safe structured details. It never exposes secrets, hidden model reasoning, backend objects, transport status codes, or tracebacks. Adapters map Application Errors to exit codes, HTTP statuses, and presentation text.

## Current Invariants

- CLI and Control Plane business operations pass through Application.
- CLI and Control Plane use the same Config-owned registered workspace identity and `.fsq` layout; Application contains no legacy marker-based workspace authority.
- Shared Driver readiness, supported installation, and Web executable discovery flow through Application; adapters do not execute installers or maintain browser discovery tables.
- All CLI and Control Plane workspace mutations flow through Application; Config remains the persistence and transaction owner.
- Application is a real Python package and an architectural layer, not a documentation-only label.
- There is no generic command-string facade.
- Application contracts have one canonical definition under `application.contracts`; package-root and resource-module exports reference the same objects.
- Resource modules contain the authoritative implementation for their operation group; compatibility exports do not copy behavior or state.
- Run resource organization does not add or alter `fsq runs` behavior.
- Transport concerns remain in adapters.
- Domain and runtime rules remain in their owning modules.
- Case operations coordinate through public Execution services and do not import package-root or adapter-private execution helpers.
