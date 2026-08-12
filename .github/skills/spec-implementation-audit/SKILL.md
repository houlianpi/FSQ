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
- Worktree diff or commit range.
- SPEC delta mode: `confirmed-update` or `no-delta`.
- Minimal navigation instructions required to locate modules and public APIs.
- Optional verification command outputs as auxiliary evidence.
- For no-SPEC-delta work, the recorded SPEC references and neutral defect reproduction evidence as claims to verify, not accepted proof.
- For incremental re-audit only, the original reviewer-authored baseline and prior audit result plus the repair diff since that result.

Do not provide persuasive summaries such as "this is complete" or "tests pass, so it should be fine".

## Audit Baseline

Before judging implementation, establish a reviewer-owned, task-local baseline containing:

- the root and relevant module SPEC inputs;
- the audited worktree diff or commit range;
- the SPEC delta mode;
- the complete set of applicable SPEC items;
- a stable `item_id` for every applicable item;
- the file, symbol, interface, dependency, configuration, or behavior boundaries relevant to each item;
- an initially empty finding set.

The baseline is structured reviewer output for the current SDD task. It is not a repository file and must not be authored or closed by the implementation agent.

## Complete First-Pass Procedure

1. Establish the complete applicable SPEC item inventory before assigning final verdicts, including independent validation of a no-SPEC-delta decision when applicable.
2. Read the diff and relevant implementation path for every applicable item.
3. Apply the Python and frontend domain checks when those areas are in scope.
4. Record a verdict and concrete diff evidence for every item.
5. Assign a stable `finding_id` to every distinct blocking root cause and associate all affected item IDs.
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

The implementation agent's classification, a `bugfix` label, and passing tests are not sufficient proof. If any condition is unproven, return a blocking `spec-delta-required` finding owned by SPEC/human decision. Project implementation pauses until the relevant SPEC is updated and confirmed; that update invalidates the audit baseline.

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

- `item_id`;
- SPEC source and requirement text or a precise requirement reference;
- represented implementation boundaries;
- concrete diff evidence;
- audit verdict;
- validation mode: `first-pass`, `revalidated`, or `reused`;
- related `finding_id` values, if any;
- notes needed to reproduce or repair a gap.

Each finding records:

- `finding_id`;
- related `item_id` values;
- blocking verdict and concrete evidence;
- repair owner: implementation, SPEC/human decision, or verification environment;
- status: open or closed;
- automatic repair attempt count.

Duplicate observations of the same root cause reuse one finding ID and may reference multiple item IDs. Distinct root causes under one SPEC item receive distinct finding IDs.

## Incremental Re-Audit

Incremental re-audit receives neutral inputs only:

- the current root and relevant module SPEC files;
- the original reviewer-authored baseline and prior result;
- the repair diff since the previous audit pass;
- the current overall diff or commit range for boundary checks;
- required verification output as auxiliary evidence;
- minimal navigation information.

Inspect every open finding, every changed line or represented boundary in the repair diff, every applicable item that overlaps the repair, shared or transitive boundaries affected by the repair, and every new issue introduced by the repair.

An earlier `implemented` result may be reused only when its SPEC input is unchanged, its represented implementation boundary does not overlap the repair, and no shared or transitive contract can be affected. Reused items retain verdict `implemented` and use validation mode `reused`. Inspected items use validation mode `revalidated`.

A repair-introduced root cause receives a new stable finding ID. The reviewer closes a prior finding only when its requirement is satisfied; closing one finding must not hide a newly exposed finding.

## Baseline Invalidation

Incremental reuse is forbidden and the applicable-item inventory must be rebuilt when:

- a root or relevant module SPEC changes;
- the diff expands into a previously unaudited module;
- a module is added, removed, or changes ownership;
- a public interface or export boundary changes beyond the represented baseline boundaries;
- project dependency direction or a cross-module dependency changes;
- frontend workspace, manifest, lock, Vite, generated-output, or backend transport ownership changes outside the represented boundaries;
- the reviewer cannot prove that an earlier result is unaffected.

Rebuilding the inventory creates a new complete pass over the currently applicable scope, not a repository-wide review of unrelated modules.

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
Item ID | SPEC item | Boundaries | Diff evidence | Verdict | Validation mode | Finding IDs | Notes
```

Produce a complete finding table:

```text
Finding ID | Item IDs | Evidence | Verdict | Repair owner | Status | Attempt count
```

State `coverage_complete=true|false`, `spec_delta_mode=confirmed-update|no-delta`, baseline status, audited SPEC inputs, and audited diff or commit range. Each evidence entry must cite concrete files and, when possible, line numbers or changed symbols. If evidence is absent, say so directly.

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
- Which diff or commit range was audited.
- Which SPEC delta mode was audited and, for no-delta work, whether its classification was independently validated.
- Whether the baseline remains valid and `coverage_complete=true`.
- Whether every applicable SPEC item has concrete evidence and verdict `implemented`.
- Which items were `reused` and which were `revalidated`.
- Whether every blocking finding is closed by the independent reviewer.
- Any remaining `needs-human-decision` items accepted by the user.

If the baseline is invalid, coverage is incomplete, required verification is unavailable, or blocking gaps remain, do not claim completion.
