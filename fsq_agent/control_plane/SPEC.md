# Module: control_plane

## Purpose

Serve the local, single-user FSQ Control Plane as an HTTP/SSE/static transport adapter over the shared Application package. It owns browser transport, local server lifecycle, safe serialization, resumable streaming, cancellation transport, and generated frontend delivery. It does not independently orchestrate Case creation/testing, Runs, Providers, Environments, Agent, Core, FSQ, Report, or Drivers.

## Dependencies

- `application`: All business operations and transport-neutral Request, Result, Event, and Error contracts.
- `models`: Shared primitive/domain values where required by Application contracts.
- Python HTTP, threading, path, MIME, JSON, and browser-opening facilities for transport and server lifecycle.

The module must not import CLI, Playground, frontend source, another module's private files, concrete harnesses/drivers, or OpenAI Agents SDK runtime types. Application and lower-level modules must not import Control Plane.

## Public Interface

`__init__.py` exports `ControlPlaneServer`, `ControlPlaneServerOptions`, and `run_control_plane`. The public HTTP prefix is `/api/control-plane`.

HTTP resources provide safe adapter projections for Workspace/bootstrap, Case create/test, Run lookup/events/cancellation where supported, Provider status/configuration, Environment inventory/diagnostics, and evidence artifact retrieval. The HTTP vocabulary may preserve a versioned compatibility shape while mapping business requests to the same Workspace, Case, Run, Provider, and Environment Application operations used by CLI.

Case discovery treats `*.fsq.yaml` as canonical and may surface `*.codex.yaml` with a deprecation warning for one compatibility cycle. Natural-language Case creation and existing-Case testing correspond to `fsq case create` and `fsq case test`; suggestion policy corresponds to `case test --suggest`. The source Case is immutable.

SSE carries serialized Application Events and safe transport state. Payloads do not embed screenshot bytes, large UI snapshots, hidden reasoning, secrets, unrestricted backend objects, or arbitrary filesystem paths. Artifact reads are restricted to Application-supplied safe references.

## Adapter State

The local server may own connection state, stream cursors, cancellation requests, HTTP request correlation, and one-active-request presentation policy. It must not treat those transport concerns as authoritative Run or execution semantics. Persisted Run facts and business status come from Application Results and Events.

## Python Architecture

- Architecture level: Level 3 transport adapter.
- Public API: server options and startup API plus the documented local HTTP surface.
- Domain boundary: HTTP/SSE/static delivery and safe browser projections only.
- Dependency direction: Control Plane to Application; never Application to Control Plane. CLI may call the public server startup API for `fsq ui`.

## Error Handling

Control Plane maps Application Errors to stable HTTP statuses and safe error envelopes. Malformed transport inputs, missing resources, conflicts, oversized evidence, and unavailable streams are represented without tracebacks or secret data. SSE disconnects do not mutate operation status. Static serving rejects traversal and cross-entry fallback.

## Verification Scope

Verification covers request-to-Application mapping, safe result/error serialization, SSE event ordering/resume, cancellation transport, artifact containment, static delivery, compatibility warnings, and proof that the adapter contains no duplicated business orchestration.

## Current Invariants

- Control Plane and CLI share Application operations rather than parallel implementations.
- HTTP, SSE, browser, and frontend types do not cross into Application contracts.
- Browser-visible events and errors are safe projections of Application contracts.
- Control Plane remains independent from Playground.
