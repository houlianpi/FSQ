---
name: requirements-to-design
description: "Internal rules loaded only by the explicit /requirements-to-design prompt. Produces a confirmed SDD design document without changing SPEC or implementation files."
user-invocable: false
disable-model-invocation: true
---

# Requirements To Design

Turn an explicitly supplied request into a reviewed design document. This internal skill implements the `/requirements-to-design` prompt; it clarifies intent and records design decisions, but it does not update `SPEC.md` files or implement code.

## Invocation Gate

Load this skill only when the user explicitly invokes `.github/prompts/requirements-to-design.prompt.md` with a requested repository modification. Ordinary discussion, explanation, review, planning, natural-language edit requests, skill-name mentions, and prose approvals must not trigger this skill. If the explicit prompt or its request is absent, stop without writing.

## Hard Gate

Do not write implementation code. Do not update root or module `SPEC.md` files. The user-confirmed design document is the only permitted repository write. The terminal state is that confirmed document and a prompt for the user to invoke `/spec-driven` explicitly with its path.

## Process

### 1. Explore Context

Read enough local context before detailed questions:

- Root `SPEC.md`, if present.
- Relevant module `SPEC.md` files, if the affected area is obvious.
- `AGENTS.md`, `CLAUDE.md`, pyproject metadata, package layout, tests, and recent docs when useful.

If no root `SPEC.md` exists, note that the target repository must create one through the later `/spec-driven` SPEC phase before implementation begins.

### 2. Check Scope

If the request spans multiple independent subsystems, stop and propose decomposition. Each independent subsystem should get its own design document and later its own `SPEC.md` update cycle.

### 3. Ask Clarifying Questions

Ask one question at a time. Prefer multiple choice when it helps. Focus on:

- Goal and success criteria.
- User-visible behavior.
- Constraints and non-goals.
- Affected modules and ownership boundaries.
- Risks, edge cases, rollout, and compatibility.
- For Python work: project type, package boundary, public API shape, persistence/framework coupling, and expected verification commands.

### 4. Propose Approaches

Present 2-3 approaches with trade-offs and a recommendation. For Python architecture work, include the simplest viable architecture level and why a higher level is or is not justified.

### 5. Present Design Sections

Present reviewable sections scaled to complexity:

- Purpose and scope.
- Architecture and module ownership.
- Python package/module boundaries.
- Public behavior and interfaces.
- Data/control flow.
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

- The design document is not the implementation source of truth.
- After `SPEC.md` files are updated and confirmed, implementation must follow `SPEC.md`, not this design document or chat history.
- Do not invoke an implementation plan as the next step.
- Do not start implementation from the design document.
