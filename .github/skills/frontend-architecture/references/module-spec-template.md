# Frontend Module SPEC Template

Use this template when creating or updating a frontend module `SPEC.md`. Keep only current behavior, ownership, dependencies, architecture, error semantics, verification obligations, and invariants.

## SPEC Hygiene

- Parent specs link child specs and state only parent-owned policy.
- Child specs own application behavior, state flow, integration boundaries, and source structure.
- Describe the framework and source language that exist in the module now.
- Current development constraints may name required defaults and documented exceptions.
- Keep design exploration, rejected alternatives, migration plans, planned signatures, and detailed test matrices in design documents or tests.
- Do not claim React, TypeScript, accessibility behavior, responsive behavior, or test coverage that the current implementation does not provide.

## Template

```text
# Module: {module_path}

## Purpose
{Owned user or build behavior. State adjacent behavior this module does not own.}

## Dependencies
- Parent workspace: {manifest, lock, build, or shared policy consumed}
- Backend contracts: {HTTP, SSE, WebSocket, media, or other transport surfaces}
- External dependencies: {runtime libraries and browser APIs}
- Forbidden dependencies: {backend implementation or sibling-private imports}

## Public Interface
- Entry points: {HTML/TSX entries, routes, exports, or scripts}
- User-visible workflows: {stable behaviors and commands}
- Integration contracts: {consumed APIs without duplicating backend semantics}

## Data And State Flow
- {server-owned data}
- {durable browser state}
- {transient interaction state}
- {derived view state}
- {subscription, stream, timer, or cleanup rules}

## Internal Structure
- `{file_or_directory}`: {responsibility}

## Frontend Architecture
- Architecture level: {1-3 and name, or a named current legacy exception}
- Runtime boundary: {browser, worker, build-only, or package boundary}
- State boundary: {where each state category is owned}
- Integration boundary: {API/client adapters and transport ownership}
- Dependency direction: {allowed and forbidden imports}
- Current framework and language: {what exists now}

## Error Handling
{Loading, empty, error, unavailable, retry, stale-data, cancellation, and conflict behavior that currently exists.}

## Verification Scope
{Current build, type, lint, unit/component, integration, browser, accessibility, responsive, and visual obligations.}

## Current Invariants
- {Present-tense constraints that prevent ownership or behavior drift.}
```

## Parent Workspace Specs

A parent workspace SPEC may omit application-only sections when they do not apply. It should still define purpose, dependencies, build interfaces, internal structure, build error behavior, verification, child navigation, generated-output policy, and cross-module invariants.