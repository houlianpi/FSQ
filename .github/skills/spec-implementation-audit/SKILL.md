---
name: spec-implementation-audit
description: "Internal diff-based project SPEC audit rules loaded only when an explicitly invoked repository prompt directs the agent to this file."
user-invocable: false
disable-model-invocation: true
---

# SPEC Implementation Audit

Determine whether project-code or project-logic implementation from an explicitly invoked SDD workflow satisfies confirmed project specifications. This is a SPEC-centered, diff-based audit. It is not a general test pass check or a restatement of the implementer's summary.

## Invocation Gate

Load this skill only when an explicitly invoked repository prompt directs the agent to this file. Ordinary discussion, explanation, review, planning, natural-language edit requests, skill-name mentions, and prose approvals must not trigger it.

## Core Rule

This skill audits only project-code or project-logic changes. Agent write authorization, SDD phase transitions, prompt routing, and workflow skills are not project SPEC items.

The audit covers both project paths: implementation after a confirmed SPEC update and implementation under a recorded no-SPEC-delta decision. In the latter path, the reviewer independently verifies that current SPEC remains the complete grounding truth for the changed behavior.

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
- Complete worktree diff artifacts plus their identity manifest, or an exact commit range.
- SPEC delta mode: `confirmed-update` or `no-delta`.
- Minimal navigation instructions required to locate modules and public APIs.
- Optional verification command outputs as auxiliary evidence.
- For no-SPEC-delta work, the recorded SPEC references and neutral defect reproduction evidence as claims to verify, not accepted proof.

Do not provide persuasive summaries such as "this is complete" or "tests pass, so it should be fine".

## Audit Input Integrity

For a worktree audit, validate the supplied artifact path, SHA-256, byte size, `diff --git` entry count, changed-path inventory, and any separate untracked-file artifacts before establishing the applicable-item inventory. Read the complete artifacts, not terminal output or overflow wrappers. If an artifact is missing, unreadable, truncated, wrapped, or inconsistent with its identity manifest, return `audit-blocked` without substituting a live diff or implementation summary.

Record the validated artifact identities in the audit result. The calling `spec-driven` workflow owns the post-audit comparison between these identities and a freshly regenerated worktree snapshot; the reviewer must not claim that later worktree changes are covered. For a commit-range audit, validate and report the exact immutable base and head object ids.

## Complete Audit Scope

Before judging implementation, establish the complete scope for the current audit pass:

- the root and relevant module SPEC inputs;
- the complete current worktree diff or commit range;
- the SPEC delta mode;
- the complete set of applicable SPEC items;
- the file, symbol, interface, dependency, configuration, or behavior boundaries relevant to each item;

Determine this scope independently during every audit pass. Do not reuse verdicts or coverage claims from an earlier pass.

## Complete Audit Procedure

1. Establish the complete applicable SPEC item inventory before assigning final verdicts, including independent validation of a no-SPEC-delta decision when applicable.
2. Read the diff and relevant implementation path for every applicable item.
3. Apply the Python and frontend domain checks when those areas are in scope.
4. Record a verdict and concrete diff evidence for every item.
5. Consolidate duplicate observations of each blocking root cause and reference every affected SPEC item precisely.
6. Record repair ownership as implementation, SPEC/human decision, or verification environment.
7. Record non-blocking quality feedback separately from SPEC verdicts.
8. Return one complete coverage table and the full finding set, with blocking gaps before quality/style feedback.

A blocking issue must not cause an early return. Complete the current pass before implementation repair or a human decision begins. The only early termination is `audit-blocked`, used when required audit input, a required tool, or a required artifact is unavailable. `audit-blocked` is not an implementation verdict, does not consume a repair attempt, and cannot satisfy the completion gate.

If blocking gaps exist, return the complete result to `spec-driven`. The implementation agent may repair findings but may not mark them closed.

## No-SPEC-Delta Audit

When the implementation used the no-SPEC-delta path, independently verify all of the following from current SPEC and the actual diff:

- Current SPEC already grounds the intended supported behavior repaired by the change.
- The diff restores conformance and does not add or change a supported contract.
- Public interfaces, configuration semantics, module ownership, dependency direction, architecture level, and supported-behavior scope remain accurately described.
- Concrete defect evidence demonstrates an implementation mismatch rather than an undocumented requirement.

The implementation agent's classification, a `bugfix` label, and passing tests are not sufficient proof. If any condition is unproven, return a blocking `spec-delta-required` finding owned by SPEC/human decision. Project implementation pauses until the relevant SPEC is updated and confirmed; after reconciliation and verification, start a new complete audit.

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

## Structured Result

Each applicable item records:

- SPEC source and requirement text or a precise requirement reference;
- represented implementation boundaries;
- concrete diff evidence;
- audit verdict;
- notes needed to reproduce or repair a gap.

Each finding records:

- affected SPEC items or precise requirement references;
- the distinct root cause;
- blocking verdict and concrete evidence;
- repair owner: implementation, SPEC/human decision, or verification environment;

Duplicate observations of the same root cause are consolidated into one finding that may reference multiple SPEC items. Distinct root causes under one SPEC item remain distinct findings.

## Repair And Full Re-Audit

An audit pass must finish and return its complete coverage table and finding set before any implementation repair begins. Do not interleave audit and repair.

After a complete audit result:

1. Resolve any SPEC/human-decision or verification-environment blocker that can change or prevent implementation repair.
2. Repair every in-scope implementation-fixable blocking finding in one batch.
3. Finish all verification affected by the complete repair batch.
4. Start a new complete independent audit using the current SPEC inputs, complete current diff or commit range, SPEC delta mode, and neutral verification evidence.
5. Repeat until a complete audit reports no blocking findings.

Every subsequent audit repeats the complete audit procedure. Do not reuse an earlier item verdict, restrict inspection to repaired paths, or start the next audit before the entire repair batch and its verification are complete.

Run at most two automatic repair rounds. An `audit-blocked` result does not consume a repair round because no complete finding set is available to repair. If blocking findings remain after the second repair round, or one round makes no substantive progress, return the complete current result for human decision.

The implementation agent may not declare findings resolved. Resolution is established only when the next complete independent audit gives every applicable item verdict `implemented`.

## Consolidated Synchronization Category

SPEC/code synchronization is part of the applicable-item inventory, not a standalone scan. When applicable, cover:

- root module navigation and dependency direction;
- module public interfaces and exports;
- declared and actual dependencies;
- internal structure and ownership;
- Python architecture and boundary rules;
- frontend parent/child ownership, state, transport, dependency, build, and generated-output contracts;
- current-fact SPEC hygiene.

Report one consolidated synchronization and project implementation audit result.

## Verdicts

- `implemented`: Diff contains concrete implementation satisfying the SPEC item.
- `incomplete`: Diff partially implements the SPEC item but leaves required behavior uncovered.
- `missing`: No meaningful implementation evidence exists in the diff.
- `diverged`: Implementation contradicts the SPEC item.
- `documentation-only`: Diff changes docs/specs but not required implementation.
- `interface-only`: Diff exposes signatures, exports, config, or declarations without required behavior.
- `mock-or-stub`: Diff uses placeholders, hardcoded responses, fake paths, or non-production behavior in place of required implementation.
- `boundary-violation`: Python imports, exports, layering, or model boundaries violate confirmed SPEC.
- `spec-delta-required`: Current SPEC does not ground the changed behavior or would become inaccurate without an update.
- `needs-human-decision`: SPEC and implementation cannot be reconciled without a product or design decision.

Any verdict except `implemented` is blocking unless the user explicitly accepts `needs-human-decision` as out of scope for the current change.

## Required Output

Produce a complete item table:

```text
SPEC item | Boundaries | Diff evidence | Verdict | Notes
```

Produce a complete finding table:

```text
Affected SPEC items | Root cause | Evidence | Verdict | Repair owner
```

State `coverage_complete=true|false`, `spec_delta_mode=confirmed-update|no-delta`, audited SPEC inputs, and validated diff artifact identities or exact commit range. Each evidence entry must cite concrete files and, when possible, line numbers or changed symbols. If evidence is absent, say so directly.

## What Not To Accept

- "The tests pass" as proof that a SPEC item is implemented.
- "The implementation agent said it handled this" as proof.
- Keyword search as proof without reading the changed code path.
- A design document as final authority after `SPEC.md` exists.
- A `bugfix` or `no-spec-delta` label as proof that current SPEC needs no update.
- Agent workflow instructions presented as proof that project behavior satisfies SPEC.
- Public API declarations without backing behavior.
- Mocks, stubs, hardcoded success paths, or placeholder fallbacks as production implementation.
- Python layers or patterns that exist only as empty pass-through abstractions.

## Completion Gate

Before claiming completion, state:

- Which root/module `SPEC.md` files were audited.
- Which validated diff artifact identities or exact commit range was audited.
- Which SPEC delta mode was audited and, for no-delta work, whether its classification was independently validated.
- Whether the latest complete audit has `coverage_complete=true`.
- Whether every applicable SPEC item has concrete evidence and verdict `implemented`.
- Whether the latest complete audit has any blocking findings.
- Any remaining `needs-human-decision` items accepted by the user.

If the latest audit pass is incomplete, coverage is incomplete, required verification is unavailable, or blocking gaps remain, do not claim completion.
