---
name: spec-driven
description: "Internal rules loaded only by the explicit /spec-driven prompt with a confirmed design document path. Enforces SPEC confirmation before implementation."
user-invocable: false
disable-model-invocation: true
---

# Spec-Driven Development

Translate an explicitly supplied confirmed design document into root/module `SPEC.md` files, get confirmation, then carry the work through implementation, verification, synchronization, and audit. This internal skill implements the `/spec-driven` prompt.

## Invocation Gate

Load this skill only when the user explicitly invokes `.github/prompts/spec-driven.prompt.md` with a confirmed design document path. Do not infer invocation or a design path from ordinary discussion, editor state, a natural-language edit request, a skill-name mention, or prose approval. If the explicit prompt, path, or confirmed design is absent, stop without writing and ask the user to invoke `/spec-driven <confirmed-design-document-path>`.

## Core Rule

`SPEC.md` files are the source of truth for implementation and must describe current project or module facts.

- Root `SPEC.md` owns current repository-wide architecture, module navigation, dependency diagrams, global development rules, and the SDD contract needed to run the project workflow.
- Module `SPEC.md` files own current module contracts, public interfaces, internal structure, dependencies, error handling, architecture level, and current invariants.
- Design documents, implementation notes, migration history, removed behavior, future roadmap, and detailed test matrices are not SPEC content unless they describe a currently supported compatibility behavior or a current verification obligation.
- `AGENTS.md`, `CLAUDE.md`, and `.github/copilot-instructions.md` are thin agent entry points only. They point agents to root `SPEC.md`; they are not specifications.

Implementation must not start until relevant `SPEC.md` changes are reviewed and confirmed.

## SPEC Hygiene Rule

Before writing or updating any `SPEC.md`, apply this filter:

- Keep: current behavior, current public API, current module ownership, current dependency direction, current configuration surface, current error semantics, current architecture level, and current invariants that constrain implementation.
- Keep as compatibility facts only when true in code: legacy input shapes, compatibility aliases, obsolete keys that are actively rejected, and supported migration shims. Write them as present-tense facts, not as history.
- Move out of SPEC: why a decision was made, discarded alternatives, design-process narrative, implementation plan, future platform ideas, planned signatures, target-state wording, removed behavior that code no longer accepts, and exhaustive test case lists.
- Avoid process markers such as `target`, `planned`, `future`, `after this change`, `this SPEC cycle`, `first batch`, `transitional`, `removed`, `previously`, and `during migration` unless the sentence is documenting a current compatibility fact or current rejection behavior.
- If a module SPEC starts to become a reference manual, keep only ownership and invariants in SPEC and move tables, examples, endpoint catalogs, or command catalogs to a reference document.

## Required Flow

Do not stop after updating `SPEC.md`. Once the user confirms the SPEC changes, continue in the same turn whenever feasible:

```text
explicit /spec-driven <confirmed-design-document-path>
  -> update root/module SPEC.md
  -> user confirms SPEC.md changes
  -> implement against confirmed SPEC.md
  -> run verification
  -> run SPEC/code synchronization check
  -> run spec-implementation-audit
  -> fix blocking gaps or ask for decision
  -> final report
```

If the user supplies a task, approval, or instruction instead of a confirmed design document path, stop without writing. Direct the user to `/requirements-to-design <request>` when no confirmed design exists, or `/spec-driven <confirmed-design-document-path>` when one does.

## Input Path

Read the confirmed design document supplied to the explicit prompt before editing specs:

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
```

The design document is input to SPEC updates, not implementation authority. Once `SPEC.md` is confirmed, code must be implemented against `SPEC.md`.

When translating a design document into SPEC updates, copy only the resulting current contract. Do not copy the design process, rejected options, implementation sequence, temporary target state, or historical narrative into SPEC.

## Python Architecture Integration

For Python projects or Python modules, apply the sibling `python-architecture` rules layer before:

- Choosing module ownership.
- Writing or updating module `SPEC.md` files.
- Implementing code.
- Running the synchronization and audit checks.

When this bundle is installed under `.github/skills/`, the references are expected at:

```text
.github/skills/python-architecture/SKILL.md
.github/skills/python-architecture/references/architecture-levels.md
.github/skills/python-architecture/references/module-spec-template.md
.github/skills/python-architecture/references/implementation-rules.md
.github/skills/python-architecture/references/audit-checklist.md
```

Load only the reference needed for the current phase:

- SPEC design or module ownership: `architecture-levels.md` and `module-spec-template.md`.
- Implementation: `implementation-rules.md`.
- Synchronization or audit: `audit-checklist.md`.

If the sibling files are unavailable, apply the local Python rules below and continue.

### Python Rules Summary

- Default to the simplest architecture level that satisfies the SPEC.
- Do not introduce Repository, Unit of Work, Service Layer, Clean Architecture, or DDD patterns without a SPEC-recorded reason.
- Public APIs are exported through module entry points such as `__init__.py`.
- Internal modules use the project convention, usually `_name.py`, and must not be imported across module boundaries.
- Domain logic must not depend on FastAPI, Django, Flask, SQLAlchemy sessions, HTTP request objects, or CLI argument parsers unless the module SPEC explicitly permits that coupling.
- Pydantic schemas, serializers, ORM models, and DTOs are boundary models unless the SPEC explicitly chooses a simpler combined model.

## Frontend Architecture Integration

For frontend projects or modules, apply the sibling `frontend-architecture` rules layer before:

- Choosing frontend module ownership.
- Writing or updating frontend `SPEC.md` files.
- Implementing frontend source, build, dependency, or agent-guidance changes.
- Running frontend verification, synchronization, or audit checks.

The references are expected at:

```text
.github/skills/frontend-architecture/SKILL.md
.github/skills/frontend-architecture/references/architecture-levels.md
.github/skills/frontend-architecture/references/module-spec-template.md
.github/skills/frontend-architecture/references/design-rules.md
.github/skills/frontend-architecture/references/implementation-rules.md
.github/skills/frontend-architecture/references/verification-checklist.md
.github/skills/frontend-architecture/references/audit-checklist.md
```

Load only the reference needed for the current phase:

- Requirements or visible design: `architecture-levels.md` and, when applicable, `design-rules.md`.
- SPEC ownership and authoring: `architecture-levels.md` and `module-spec-template.md`.
- Implementation: `implementation-rules.md`.
- Verification: `verification-checklist.md`.
- Synchronization or audit: `audit-checklist.md`.

Frontend rules do not create a new user entry point and must not be fetched from remote sources at runtime. New frontend application modules default to the root Vite workspace with React and TypeScript/TSX. Existing modules keep the framework and language in their confirmed module SPEC until a separate SPEC update authorizes a migration.

## SPEC Update Procedure

### New module or feature

1. Read root `SPEC.md` and relevant module `SPEC.md` files.
2. Read the confirmed design document.
3. Decide which module owns the feature, or whether a new module is needed.
4. For Python work, choose the Python architecture level and write the rationale into SPEC.
5. For frontend work, choose the frontend architecture level or accurately record a current legacy exception and write the ownership boundaries into SPEC.
6. Write or update relevant module `SPEC.md` files.
7. If adding a module or changing module relationships, update root `SPEC.md` module table and architecture diagram.
8. Ask the user to confirm SPEC changes before implementation.
9. Implement only after confirmation.
10. Run verification, synchronization, and audit.

### Existing functionality change

1. Read root `SPEC.md` and current module specs for every touched module.
2. Read the confirmed design document when one exists.
3. Determine impact: public interface, module contract, internal-only, or cross-module dependency change.
4. Update relevant specs.
5. Ask the user to confirm SPEC changes before implementation.
6. Implement only after confirmation.
7. Run verification, synchronization, and audit.

### All repository modifications

Bug fixes, tests, configuration, documentation, agent customization, and other narrow changes do not bypass design confirmation or SPEC confirmation. Apply the existing-functionality procedure and keep the SPEC delta limited to legitimate current facts. If no legitimate current-fact SPEC delta exists, stop for a human decision rather than changing implementation or adding artificial SPEC content.

## Module SPEC Structure

Every module has exactly one `SPEC.md`. Use this structure unless root `SPEC.md` defines a compatible local convention:

```text
# Module: {name}
## Purpose
## Dependencies
## Public Interface
## Internal Structure
## Python Architecture        (for Python modules)
## Data And State Flow        (for stateful frontend modules)
## Frontend Architecture      (for frontend modules)
## Error Handling             (if applicable)
## Verification Scope         (optional; current externally visible verification obligations only)
## Current Invariants         (optional; present-tense constraints that keep implementation aligned)
```

Root `SPEC.md` should contain repository-wide sections such as:

```text
# {project} Project Specification
## SPEC Ownership And SDD Contract
## Module Table
## Architecture Diagram
## Development Rules
## Python Architecture Rules   (for Python repositories)
```

Do not add `Testing Contract` or `Design Decisions` as default sections for new module specs. Existing sections with those names should be narrowed during touched updates: test matrices move to tests/docs, while decision rationale becomes current invariants only when it still constrains code.

## Implementation Rules

After SPEC confirmation:

1. Re-read confirmed root/module specs.
2. Implement only what the confirmed specs require.
3. If implementation reveals a missing or wrong SPEC decision, stop and update SPEC first.
4. Keep edits scoped to affected modules and tests.
5. For behavior changes, write or update tests before production code unless the user explicitly accepts a generated-code or throwaway exception.
6. For frontend work, follow the confirmed framework/language contract and the staged frontend implementation rules; do not mix a partial migration into an existing exception.
7. Run the repository's available verification commands and the applicable frontend verification checklist.

## Change Synchronization Check

After implementation, verify relevant specs still match code:

- [ ] Root `SPEC.md` module table matches actual modules.
- [ ] Root `SPEC.md` architecture diagram matches actual project dependencies.
- [ ] Module `SPEC.md` Public Interface matches exported public symbols.
- [ ] Module `SPEC.md` Dependencies match actual imports from other project modules.
- [ ] Module `SPEC.md` Internal Structure lists actual module files.
- [ ] Python Architecture section matches package layout, import direction, framework boundaries, and model boundaries.
- [ ] Parent and child frontend SPEC ownership matches the workspace and application directories without duplicated contracts.
- [ ] Frontend Public Interface, Data And State Flow, Internal Structure, and Frontend Architecture match entries, source, state ownership, transport boundaries, framework, and language.
- [ ] Frontend manifest, lock file, Vite configuration, generated-output policy, and required browser evidence match the confirmed specs.
- [ ] Agent entry files remain thin pointers to root `SPEC.md`, keep ordinary interaction read-only, and require explicit SDD prompt invocation before writes.
- [ ] SPEC text contains current facts only; design process, historical narrative, target-state wording, future roadmap, and detailed test matrices are absent or moved elsewhere.

If anything is out of sync, fix the spec or code before completion.

## Audit Gate

Before claiming completion, run the sibling `spec-implementation-audit` procedure or apply it directly. If available, read:

```text
.github/skills/spec-implementation-audit/SKILL.md
```

Audit against:

```text
root SPEC.md + relevant module SPEC.md files + actual diff
```

Tests, lint, and summaries are supporting evidence only. They do not replace diff-based SPEC audit.

If blocking gaps exist:

- Fix implementation gaps and re-audit.
- If SPEC and implementation cannot be reconciled, ask the user for a design decision.
- Do not claim completion while blocking gaps remain.

## Required Final Report

End with:

- Specs updated and confirmed.
- Files implemented.
- Verification commands run and results.
- Synchronization check result.
- Audit result, including any accepted human decisions.
