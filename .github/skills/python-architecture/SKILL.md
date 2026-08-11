---
name: python-architecture
description: "Internal Python architecture rules loaded only when an explicitly invoked repository prompt directs the agent to this file."
user-invocable: false
disable-model-invocation: true
---

# Python Architecture

This is the internal Python architecture rules layer for an explicitly invoked SDD workflow. It helps choose the simplest adequate architecture, write Python-aware `SPEC.md` sections, implement against those specs, and audit code/spec synchronization.

## Invocation Gate

Load this skill only when an explicitly invoked repository prompt directs the agent to this file. Ordinary discussion, explanation, review, planning, natural-language edit requests, skill-name mentions, and prose approvals must not trigger it.

## Core Principle

Start simple and escalate only with evidence. Architecture exists to clarify ownership, isolate change, and protect business rules; it is not a template to apply everywhere.

## When To Use

Use for Python work involving:

- New packages, modules, services, CLIs, workers, libraries, or data pipelines.
- Public API design.
- Module boundary changes.
- Domain logic, business rules, persistence, external integrations, or framework boundaries.
- Refactoring Python code with unclear ownership or tangled imports.
- SPEC/code synchronization and architecture audits.

Do not use for tiny one-off scripts unless the script is becoming a maintained module.

## Architecture Level Decision

Choose one level and record the rationale in SPEC for non-trivial work:

| Level | Use when | Avoid when |
| --- | --- | --- |
| 1. Script | One-off utility, no public API, little reuse | It has tests, users, or recurring changes |
| 2. Simple package | Small reusable code with clear functions/classes | Business rules span multiple workflows |
| 3. Layered application | API/CLI/worker with orchestration and persistence | Layers only pass data through |
| 4. Clean Architecture | Business rules must outlive framework/database choices | CRUD is simple and stable |
| 5. Light DDD | Rich domain behavior, invariants, bounded contexts | Domain is mostly data entry/retrieval |

Prefer the lowest level that keeps the module understandable and testable.

## Python SPEC Requirements

For Python modules, include this section in module `SPEC.md`:

```text
## Python Architecture
- Architecture level: {1-5 and name}
- Public API: {exports, commands, endpoints, events, or classes}
- Internal modules: {files not imported outside this module}
- Domain boundaries: {where business rules live}
- Boundary models: {Pydantic schemas, DTOs, ORM models, serializers}
- Dependency direction: {allowed imports and forbidden imports}
- Rationale: {why this level is sufficient}
```

See `references/module-spec-template.md` for a fuller template.

## Boundary Rules

- Export public API through `__init__.py` or the project-designated entry point.
- Prefix internal implementation files with `_` when the project has no other convention.
- Other modules must not import another module's internal files.
- Keep framework, transport, persistence, and CLI parsing details out of domain logic unless SPEC explicitly chooses a simple combined model.
- Pydantic schemas, serializers, ORM models, and DTOs are boundary models by default.
- Application services orchestrate use cases; domain objects enforce business invariants.
- Repositories hide persistence only when that improves testing, transaction boundaries, or dependency direction.
- Unit of Work is justified only when transaction consistency spans multiple repositories or operations.

## Implementation Rules

- Follow existing project packaging, test, formatting, and dependency patterns.
- Write or update tests for public behavior before production code unless the user accepts a narrow exception.
- Keep generated code scoped to confirmed SPEC items.
- Do not add abstractions that only rename a call or pass data through unchanged.
- Use dataclasses, attrs, pydantic, protocols, or ABCs only when they solve an actual boundary or validation problem.
- Keep imports acyclic across project modules.

## Audit Rules

Before completion, check:

- Public Interface in SPEC matches `__init__.py` exports, CLI commands, endpoints, or documented public symbols.
- Dependencies in SPEC match actual project imports.
- Internal Structure in SPEC matches files in the module directory.
- No cross-module imports from `_internal` files.
- Domain/application/infrastructure boundaries match SPEC.
- Tests cover public behavior promised by SPEC.

Use `references/audit-checklist.md` when doing a full audit.

## References

- `references/architecture-levels.md`: detailed level selection guidance.
- `references/module-spec-template.md`: Python module SPEC template.
- `references/implementation-rules.md`: implementation patterns and anti-patterns.
- `references/audit-checklist.md`: SPEC/code audit checklist.
