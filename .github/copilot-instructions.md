# Copilot Instructions

This repository uses Spec-Driven Development for project development.

Root `SPEC.md` and relevant module `SPEC.md` files are the grounding truth for project code and project logic. They do not define the SDD workflow.

This file, `.github/prompts/`, and `.github/skills/` control agent write authorization and SDD phase transitions. Project `SPEC.md` files must not duplicate or override those workflow rules.

Ordinary discussion, explanation, review, and planning are read-only. Do not automatically load or invoke repository workflow skills.

Before creating, modifying, renaming, or deleting project development files, require the user to explicitly invoke `/spec-driven <confirmed-design-document-path | direct-project-change-request>`. Project development includes project or module `SPEC.md` files, source, behavior-defining tests, runtime/build configuration, public interfaces, module ownership, dependency direction, and documentation of supported project behavior. A natural-language project edit request outside that explicit prompt is not authorization to write; stop and direct the user to `/spec-driven`.

`/requirements-to-design <request>` is an optional design aid. It helps the user clarify a project change and produces a confirmed design document as higher-quality `/spec-driven` input, but it is not a prerequisite for project modification.

A clear ordinary user request to create, modify, rename, or delete workflow-control files directly authorizes that maintenance without SDD. Workflow-control files are `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/prompts/**`, and `.github/skills/**`. Ambiguous approval, discussion, or a skill name mentioned in prose is not authorization. If a workflow-control edit also changes project behavior, use project SDD.

During `/spec-driven`, determine whether the requested project change requires a SPEC delta. If it does, update relevant `SPEC.md` files and receive user confirmation before non-SPEC project files change. If the implementation only restores behavior already grounded in current SPEC, record the no-SPEC-delta evidence and proceed without an artificial SPEC edit.

Read repository skills only when an explicitly invoked project SDD prompt directs you to them. This file is an agent workflow entry point, not a project specification; keep project and module requirements in `SPEC.md` files and detailed workflow procedures in `.github/skills/`.

New Python source files must start with:

```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
```
