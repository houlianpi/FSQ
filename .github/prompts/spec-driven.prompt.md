---
name: spec-driven
description: "Required project modification workflow from a confirmed design or direct request"
argument-hint: "Confirmed design path or direct project change request"
---

# Spec Driven

This is the required explicit user-invoked entry point for project modification. Accept either a confirmed project design document path or a direct project change request. If no argument is provided, stop without writing and ask the user to invoke `/spec-driven <confirmed-design-document-path | direct-project-change-request>`; do not infer an input from ordinary conversation or editor state.

Read these files before acting:

- `.github/skills/spec-driven/SKILL.md`
- `.github/skills/python-architecture/SKILL.md` when the work touches Python code
- `.github/skills/spec-implementation-audit/SKILL.md` before claiming completion

This prompt applies only to project development. If the input changes only workflow-control files, stop and explain that a clear ordinary edit request is sufficient. Do the same when every non-workflow path is verified to be both untracked and ignored by Git and the requested writes are local-only. A tracked file does not qualify even if it matches an ignore rule, and changes to ignore rules follow normal project authorization.

Read the input, current root/module `SPEC.md` files, and enough implementation evidence to determine whether the requested change requires a SPEC delta. Do not rely on a user-supplied `no-spec-delta` label.

If a SPEC delta is required, update the relevant specs and ask the user to confirm them before modifying non-SPEC project files. If the request only restores behavior already grounded in current SPEC, record concrete no-SPEC-delta evidence and proceed without an artificial SPEC edit. Then implement against SPEC, verify, and run the consolidated project implementation audit.

Do not stop after SPEC updates unless required confirmation is pending or a human decision is required.
