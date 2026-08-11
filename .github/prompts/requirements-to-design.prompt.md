---
name: requirements-to-design
description: "Explicit SDD design phase for a requested repository modification"
argument-hint: "Describe the repository modification"
---

# Requirements To Design

This is an explicit user-invoked SDD entry point. Read `.github/skills/requirements-to-design/SKILL.md` and follow it exactly.

Use the requested repository modification passed to this prompt. If no request is provided, ask the user to invoke `/requirements-to-design <request>` and do not write any file.

Do not write implementation code or update `SPEC.md` files. The only permitted repository write is the user-confirmed design document. End by giving its path and telling the user to invoke `/spec-driven <confirmed-design-document-path>` explicitly.
