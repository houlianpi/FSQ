# Module: adapters

## Purpose

Own external protocol adaptation for the public CLI, local Control Plane, local Playground, and coding-agent runtimes. Adapters decode external inputs, invoke inward public contracts, and project safe output. They do not own Application validation, execution semantics, persistence formats, capability policy, or platform automation.

## Dependencies

Adapters may import public APIs from `application`, `models`, `config`, `providers`, `agent`, `fsq`, `core`, and `report`, plus root-SPEC-approved package-private entry composition helpers. Inward modules must not import `adapters`. Adapter subpackages must not form cycles.

## Public Interface

- `adapters.cli` owns the `fsq` Click command tree and exports `main`.
- `adapters.control_plane` owns `ControlPlaneServer`, `ControlPlaneServerOptions`, `run_control_plane`, and the documented HTTP/SSE/static API.
- `adapters.control_plane.playground` owns `PlaygroundServer`, `PlaygroundServerOptions`, `run_playground`, and the documented Playground HTTP/static API.
- `adapters.coding_agent` is not introduced by this transport migration.

The installed script and existing `fsq_agent.cli`, `fsq_agent.control_plane`, and `fsq_agent.playground` imports remain compatibility entries. Each public compatibility symbol references the canonical adapter object. Compatibility private submodule imports resolve to the canonical module object when mutable state or monkeypatch identity is observable.

## Internal Structure

- `cli/`: CLI parsing, presentation, output modes, and exit mapping.
- `control_plane/`: Control Plane HTTP/SSE/static transport, projections, and state.
- `control_plane/playground/`: Playground HTTP/static transport and independent session/task state.
- Adapter-private `_*.py` files are not imported by inward modules.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: adapter entry points and documented transport contracts.
- Domain boundaries: external protocol decoding and presentation only.
- Boundary models: Click values and HTTP/JSON/SSE dictionaries remain at adapter boundaries.
- Dependency direction: adapters depend inward; Application and lower modules never import adapters.
- Rationale: the entry surfaces coordinate frameworks, state, static delivery, and inward services without requiring another domain layer.

## Error Handling

Adapters map stable inward failures into documented exit codes or safe HTTP/SSE responses. Compatibility paths preserve exception identity, state identity, redaction, and output behavior.

## Current Invariants

- Canonical and compatibility paths do not duplicate transport implementations or mutable state.
- CLI and Control Plane business operations continue through Application.
- Control Plane and Playground remain behaviorally and statefully independent.
- Static assets remain generated package data with unchanged URL and wheel behavior.
- Module relocation does not change CLI, HTTP, SSE, frontend, workspace, Case, evidence, report, Provider, or Runs contracts.
