---
name: requirements-to-design
description: "Optional design phase for clarifying a requested project modification"
argument-hint: "Describe the project modification"
---

# Requirements To Design

This is an optional, explicit user-invoked project design aid. Read `.github/skills/requirements-to-design/SKILL.md` and follow it exactly. Project implementation may instead start from a direct `/spec-driven <direct-project-change-request>` invocation.

Use the requested project modification passed to this prompt. If no request is provided, ask the user to invoke `/requirements-to-design <request>` and do not write any file.

This prompt applies only to project development. If the request changes only workflow-control files (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/prompts/**`, or `.github/skills/**`), explain that a clear ordinary edit request is sufficient and stop without writing a design document.

Do not write implementation code or update `SPEC.md` files. The only permitted repository write is the user-confirmed design document. End by giving its path and telling the user to invoke `/spec-driven <confirmed-design-document-path>` explicitly.
