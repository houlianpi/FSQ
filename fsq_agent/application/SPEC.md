# Module: application

## Purpose

Provide the shared, transport-neutral Application layer used by the FSQ CLI, Control Plane, and future Coding Agent APIs. The package exposes application operations grouped by Workspace, Case, Run, Provider, and Environment and coordinates existing module authorities without reimplementing their rules.

## Dependencies

Application may consume public APIs from `models`, `config`, `providers`, `agent`, `fsq`, `core`, and `report`. It must not import `cli`, `control_plane`, frontend code, Click, HTTP/SSE frameworks, terminal rendering, or concrete UI types. Lower-level modules must not import `application`.

## Public Interface

The package exports transport-neutral operations and their Request, Result, Event, and Error contracts through `__init__.py`. Operations are organized by resource domain rather than exposed through one generic `execute(command)` facade:

- Workspace operations support the shared workspace precondition and workspace-facing readiness needed by adapters.
- Case operations support creating a Case from a Goal and testing an existing Case, including the optional suggestion policy.
- Run operations support persisted Run listing, detail lookup, and log streaming or retrieval.
- Provider operations support listing, configuration, and readiness status.
- Environment operations support listing and diagnostics.

Requests contain application inputs, Results contain operation outcomes and safe artifact references, Events describe transport-neutral progress, and Errors contain stable codes plus safe structured details. These contracts contain no Click, HTTP, SSE, terminal, or frontend types. Exact operation class/function decomposition is an implementation decision as long as the resource boundaries and contracts remain explicit.

## Ownership Boundaries

Application owns cross-module orchestration, shared request validation, workspace enforcement, operation-level event production, and consistent results/errors for all adapters. It delegates authoritative behavior to existing modules:

- `agent` owns AI planning, model/tool orchestration, and dynamic verification.
- `fsq` owns Case DSL parsing, validation, and canonical deterministic-step adaptation.
- `core` owns capability execution, runtime-secret handling, evidence policy, and Harness/Driver routing.
- `report` owns transformation of persisted execution facts into reports and failure analysis.
- concrete drivers own platform automation and backend-error normalization.

Application must not copy, reinterpret, or fork those rules. This specification does not require `case create`, `case test`, and suggestion handling to be three independent internal Use Cases.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: resource-grouped operations and transport-neutral Request, Result, Event, and Error contracts exported from `__init__.py`.
- Dependency direction: CLI and Control Plane adapters depend on Application; Application depends on owning module public APIs; owning modules do not depend on Application.
- Rationale: the package coordinates several existing authorities and presents one consistent application boundary to multiple transports without introducing repositories, a database, a daemon, a queue, or Clean Architecture ceremony.

## Error Handling

Application normalizes expected operation failures into stable application Errors and preserves safe structured details. It never exposes secrets, hidden model reasoning, backend objects, transport status codes, or tracebacks. Adapters map Application Errors to exit codes, HTTP statuses, and presentation text.

## Current Invariants

- CLI and Control Plane business operations pass through Application.
- Application is a real Python package and an architectural layer, not a documentation-only label.
- There is no generic command-string facade.
- Transport concerns remain in adapters.
- Domain and runtime rules remain in their owning modules.
