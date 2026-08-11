---
name: spec-driven
description: "Explicit SPEC-first implementation from a confirmed design document"
argument-hint: "Path to the confirmed design document"
---

# Spec Driven

This is an explicit user-invoked SDD entry point. Require the prompt argument to be a confirmed design document path. If the path is missing, invalid, or not confirmed, stop without writing and ask the user to invoke `/spec-driven <confirmed-design-document-path>`; do not infer a path from ordinary conversation or editor state.

Read these files before acting:

- `.github/skills/spec-driven/SKILL.md`
- `.github/skills/python-architecture/SKILL.md` when the work touches Python code
- `.github/skills/spec-implementation-audit/SKILL.md` before claiming completion

Update root/module `SPEC.md` files from the confirmed design and ask the user to confirm the SPEC changes. Do not modify any non-SPEC repository file before that confirmation. Once confirmed, implement against SPEC, verify, synchronize, and audit.

Do not stop after SPEC updates unless the user has not confirmed them yet or a human decision is required.
