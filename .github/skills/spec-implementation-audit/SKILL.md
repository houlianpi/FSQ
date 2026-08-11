---
name: spec-implementation-audit
description: "Internal diff-based SPEC audit rules loaded only when an explicitly invoked repository prompt directs the agent to this file."
user-invocable: false
disable-model-invocation: true
---

# SPEC Implementation Audit

Determine whether implementation from an explicitly invoked SDD workflow satisfies confirmed specifications. This is a SPEC-centered, diff-based audit. It is not a general test pass check and not a restatement of the implementer's summary.

## Invocation Gate

Load this skill only when an explicitly invoked repository prompt directs the agent to this file. Ordinary discussion, explanation, review, planning, natural-language edit requests, skill-name mentions, and prose approvals must not trigger it.

## Core Rule

Completion cannot be claimed until implementation is audited against:

```text
root SPEC.md + relevant module SPEC.md files + actual diff
```

Tests, lint, keyword scans, and implementation summaries are auxiliary evidence only. They do not replace diff-based SPEC audit.

## Independence Requirement

Use a fresh reviewer or independent context whenever the platform supports it. The reviewer must not inherit the implementation agent's conversation history or rely on its self-report.

Reviewer input is limited to:

- Root `SPEC.md`.
- Relevant module `SPEC.md` files.
- Worktree diff or commit range.
- Minimal navigation instructions required to locate modules and public APIs.
- Optional verification command outputs as auxiliary evidence.

Do not provide persuasive summaries such as "this is complete" or "tests pass, so it should be fine".

## Audit Procedure

1. Identify SPEC items that apply to the change.
2. Read the diff and locate concrete implementation evidence for each SPEC item.
3. For Python work, apply `python-architecture` audit rules or `references/audit-checklist.md` from that skill.
4. For frontend work, apply `frontend-architecture/references/audit-checklist.md` and inspect required browser evidence.
5. Classify each item with a verdict.
6. Report blocking gaps before quality/style feedback.
7. If blocking gaps exist, return to implementation or to `spec-driven` when SPEC itself needs correction.
8. Re-audit after fixes.

## Python Architecture Audit

For Python modules, also verify:

- Public Interface in SPEC matches `__init__.py` exports, endpoints, commands, events, or documented public symbols.
- Dependencies in SPEC match actual project imports.
- Internal Structure in SPEC matches actual files.
- No cross-module imports from `_private` implementation files.
- Dependency direction follows root `SPEC.md`.
- Domain/application/infrastructure/framework boundaries match SPEC.
- Boundary model choices match SPEC: Pydantic schemas, ORM models, DTOs, serializers, and domain objects do not silently swap roles.
- Tests cover public behavior and invariants promised by SPEC.

## Frontend Architecture Audit

For frontend-owned files, also verify:

- Root module navigation and parent/child frontend SPEC links match actual ownership boundaries.
- Parent specs own workspace/build policy while child specs own application behavior, state flow, source structure, and browser integration.
- The implemented framework and source language match the module SPEC, including named legacy exceptions.
- npm manifest, lock file, Vite configuration, imports, and generated-output policy agree.
- Frontend code consumes documented backend transport contracts without importing backend implementation or duplicating backend security/filesystem policy.
- Server data, durable browser preferences, transient interaction state, derived values, streams, timers, and cleanup follow the documented owners.
- Loading, empty, error, disabled, cancellation, conflict, completion, responsive, keyboard, focus, and reduced-motion behavior required by SPEC is implemented.
- Available build, type, lint, unit/component, integration, package, browser, accessibility, and visual checks required by SPEC were run.

Use `.github/skills/frontend-architecture/references/audit-checklist.md` for the full checklist. Missing browser or screenshot evidence is blocking when the confirmed SPEC requires it.

## Verdicts

- `implemented`: Diff contains concrete implementation satisfying the SPEC item.
- `incomplete`: Diff partially implements the SPEC item but leaves required behavior uncovered.
- `missing`: No meaningful implementation evidence exists in the diff.
- `diverged`: Implementation contradicts the SPEC item.
- `documentation-only`: Diff changes docs/specs but not required implementation.
- `interface-only`: Diff exposes signatures, exports, config, or declarations without required behavior.
- `mock-or-stub`: Diff uses placeholders, hardcoded responses, fake paths, or non-production behavior in place of required implementation.
- `boundary-violation`: Python imports, exports, layering, or model boundaries violate confirmed SPEC.
- `needs-human-decision`: SPEC and implementation cannot be reconciled without a product or design decision.

Any verdict except `implemented` is blocking unless the user explicitly accepts `needs-human-decision` as out of scope for the current change.

## Required Output

Produce a table or structured list:

```text
SPEC item | Diff evidence | Verdict | Notes
```

Each evidence entry must cite concrete files and, when possible, line numbers or changed symbols. If evidence is absent, say so directly.

## What Not To Accept

- "The tests pass" as proof that a SPEC item is implemented.
- "The implementation agent said it handled this" as proof.
- Keyword search as proof without reading the changed code path.
- A design document as final authority after `SPEC.md` exists.
- Public API declarations without backing behavior.
- Mocks, stubs, hardcoded success paths, or placeholder fallbacks as production implementation.
- Python layers or patterns that exist only as empty pass-through abstractions.

## Completion Gate

Before claiming completion, state:

- Which root/module `SPEC.md` files were audited.
- Which diff or commit range was audited.
- Whether every blocking SPEC item is `implemented`.
- Any remaining `needs-human-decision` items accepted by the user.

If blocking gaps remain, do not claim completion.
