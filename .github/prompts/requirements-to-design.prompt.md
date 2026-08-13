---
name: requirements-to-design
description: "Optional design phase for clarifying any requested change"
argument-hint: "Describe the requested change"
---

# Requirements To Design

This is an optional, explicit user-invoked design aid that is available for any requested change. Read `.github/skills/requirements-to-design/SKILL.md` and follow it exactly. Do not reject an explicit invocation because the requested implementation could proceed without SDD.

Use the requested change passed to this prompt. If no request is provided, ask the user to invoke `/requirements-to-design <request>` and do not write any file.

Determine whether downstream implementation requires `/spec-driven` under the repository authorization rules. Workflow-control-only changes and verified local-only writes to untracked Git-ignored files remain valid design inputs even though their later implementation does not require SDD.

Do not write implementation code or update `SPEC.md` files. The only permitted repository write is the user-confirmed design document. End by giving its path and the correct next step: explicitly invoke `/spec-driven <confirmed-design-document-path>` when downstream implementation requires SDD, or submit a clear ordinary implementation request when it is exempt.
