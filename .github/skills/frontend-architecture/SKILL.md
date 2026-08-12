---
name: frontend-architecture
description: "Internal frontend architecture, design, implementation, verification, and audit rules loaded only when an explicitly invoked repository SDD prompt directs the agent to this skill."
user-invocable: false
disable-model-invocation: true
---

# Frontend Architecture

Apply project-specific frontend rules inside the repository's existing two-phase SDD workflow. This skill is a rules layer, not a third workflow or an implementation entry point.

## Invocation Gate

Load this skill only when an explicitly invoked repository prompt directs the agent to it. Ordinary discussion, explanation, review, planning, natural-language edit requests, skill-name mentions, and prose approvals must not trigger it.

## Core Principles

- Root and module `SPEC.md` files are the implementation grounding truth.
- Use the lowest frontend architecture level that keeps ownership, state, integration, and verification clear.
- Parent and child specs link across ownership boundaries without copying contracts.
- Vite owns frontend development and production compilation.
- New frontend application modules default to React with TypeScript/TSX unless their confirmed module SPEC records an exception.
- Existing modules keep their confirmed framework and source language until a SPEC update is confirmed. Do not mix an unplanned partial migration into feature work.
- Runtime guidance is repository-local and deterministic. Do not fetch remote skill instructions during execution.

## Phase Routing

Load only the references needed for the active SDD phase:

| Phase | References |
|---|---|
| Requirements and design | [Architecture levels](./references/architecture-levels.md) and, for visible UI changes, [design rules](./references/design-rules.md) |
| SPEC authoring or ownership | [Architecture levels](./references/architecture-levels.md) and [module SPEC template](./references/module-spec-template.md) |
| Implementation | [Implementation rules](./references/implementation-rules.md) |
| Verification | [Verification checklist](./references/verification-checklist.md) |
| Consolidated project audit | [Audit checklist](./references/audit-checklist.md) |

Do not load design rules for dependency-only, build-only, documentation-only, or internal refactoring work that has no user-visible effect.

## Ownership Rules

- The root frontend workspace owns package management, the lock file, Vite configuration, shared build policy, and child-module navigation.
- Each independently owned frontend application directory has one module `SPEC.md`.
- Implementation folders such as `components`, `hooks`, `styles`, and `assets` do not need separate specs unless they become independent ownership boundaries.
- Frontend modules consume backend behavior through documented transport contracts. They do not import backend implementation modules.
- Generated assets are build outputs, not authored frontend source or a second ownership surface.

## Completion Rule

Frontend work is not complete until the confirmed specs match the implementation, available deterministic checks pass, required browser evidence is collected for visible changes, and the diff passes the frontend SPEC audit.