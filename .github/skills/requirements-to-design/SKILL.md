---
name: requirements-to-design
description: "Optional internal design rules loaded only by the explicit /requirements-to-design prompt. Produces a confirmed project design document without changing SPEC or implementation files."
user-invocable: false
disable-model-invocation: true
---

# Requirements To Design

Turn an explicitly supplied project modification into a reviewed design document. This optional internal skill implements the `/requirements-to-design` prompt; it clarifies project intent and records design decisions as higher-quality `/spec-driven` input, but it does not update `SPEC.md` files or implement code and is not a prerequisite for project modification.

## Invocation Gate

Load this skill only when the user explicitly invokes `.github/prompts/requirements-to-design.prompt.md` with a requested project modification. Ordinary discussion, explanation, review, planning, natural-language project edit requests, skill-name mentions, and prose approvals must not trigger this skill. If the explicit prompt or its request is absent, stop without writing.

This skill does not handle workflow-control-only maintenance. If the request changes only `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/prompts/**`, or `.github/skills/**`, explain that a clear ordinary edit request is sufficient and stop without writing a design document.

## Hard Gate

Do not write implementation code. Do not update root or module `SPEC.md` files. The user-confirmed design document is the only permitted repository write. The terminal state is that confirmed document and a prompt for the user to invoke `/spec-driven` explicitly with its path.

## Process

### 1. Explore Context

Read enough local context before detailed questions:

- Root `SPEC.md` and relevant module `SPEC.md` files.
- `AGENTS.md`, `CLAUDE.md`, pyproject metadata, package layout, tests, and recent docs when useful.
- For frontend work, the parent frontend SPEC, affected child application SPEC, root npm/Vite metadata, and backend specs that own consumed transport contracts when useful.

If no root `SPEC.md` exists, note that the target repository must create one through the later `/spec-driven` project SPEC phase before implementation begins.

### 2. Check Scope

If the request spans multiple independent project subsystems, stop and propose decomposition. Each independent subsystem should get its own design document and later SPEC update cycle.

### 3. Ask Clarifying Questions

Ask one question at a time. Prefer multiple choice when it helps. Focus on:

- Goal and success criteria.
- User-visible behavior.
- Constraints and non-goals.
- Affected modules and ownership boundaries.
- Risks, edge cases, rollout, and compatibility.
- For Python work: project type, package boundary, public API shape, persistence/framework coupling, and expected verification commands.
- For frontend work: audience and primary task, existing visual language, interaction states, responsive and accessibility behavior, state ownership, backend data contracts, browser support, and expected build/browser evidence.

For frontend requests, ask visual-direction questions only when the change adds or reshapes visible UI. Build, dependency, documentation, and internal refactoring requests do not need an invented aesthetic direction.

### 4. Propose Approaches

Present 2-3 approaches with trade-offs and a recommendation. For Python architecture work, include the simplest viable architecture level and why a higher level is or is not justified.

For frontend architecture work, include the simplest viable frontend level and justify any router, global state, server-state library, design system, or additional layer. Preserve a module's confirmed framework and language unless the request explicitly designs a migration.

### 5. Present Design Sections

Present reviewable sections scaled to complexity:

- Purpose and scope.
- Architecture and module ownership.
- Python package/module boundaries.
- Frontend workspace/application boundaries when applicable.
- Public behavior and interfaces.
- Data/control flow.
- Frontend state categories and interaction states when applicable.
- Visual direction, responsive behavior, and accessibility when visible UI changes.
- Error handling and edge cases.
- Verification and audit expectations.

Ask for confirmation after meaningful sections and revise until approved.

### 6. Write the Design Document

Save the confirmed design to:

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
```

Include:

- Goal.
- Scope and non-goals.
- Proposed design.
- Python architecture level and rationale when the project is Python.
- Frontend architecture level and rationale when the work affects a frontend application.
- Affected root/module specs expected to change.
- Open questions resolved during discussion.
- Verification expectations.

### 7. Self-Review

Before handoff, fix:

- Placeholder text such as `TBD` or `TODO`.
- Internal contradictions.
- Scope too broad for one SPEC update cycle.
- Ambiguous requirements that could be implemented two ways.
- Hidden implementation assumptions that should be explicit.

### 8. User Review Gate

Ask the user to review the written design document. Do not proceed until the user confirms it.

### 9. Handoff

After confirmation, end with exactly this shape:

```text
Design document: docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
Next step: invoke /spec-driven with this design document path.
```

## Boundaries

- The design document records the confirmed requested project change but is not the implementation source of truth.
- After any required project `SPEC.md` updates are confirmed, or `/spec-driven` independently validates that no delta is needed, implementation must follow current confirmed specs, not chat history.
- Do not invoke an implementation plan as the next step.
- Do not start implementation directly from the design document without an explicit `/spec-driven <confirmed-design-document-path>` invocation.

## Frontend Architecture Integration

For frontend work, use the internal sibling rules at:

```text
.github/skills/frontend-architecture/SKILL.md
.github/skills/frontend-architecture/references/architecture-levels.md
.github/skills/frontend-architecture/references/design-rules.md
```

Load `architecture-levels.md` for frontend ownership and architecture choices. Load `design-rules.md` only when the request adds or reshapes user-visible UI. Do not fetch upstream frontend skills or guidelines at runtime; the repository-local rules are the deterministic source for this workflow.
