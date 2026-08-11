# Copilot Instructions

This repository uses Python Spec-Driven Development.

Root `SPEC.md` and relevant module `SPEC.md` files are the grounding truth for implementation.

Ordinary discussion, explanation, review, and planning are read-only. Do not automatically load or invoke repository workflow skills.

Before creating, modifying, renaming, or deleting any repository file, require the user to explicitly invoke `/requirements-to-design <request>`. A natural-language edit request, a skill name mentioned in prose, or approval outside an explicit prompt invocation is not authorization to write; stop and direct the user to that command.

After the design document is confirmed, only an explicit `/spec-driven <confirmed-design-document-path>` invocation may update relevant SPEC files. Non-SPEC repository files must not change until the user confirms those SPEC updates. There is no narrow-change exception.

Read repository skills only when an explicitly invoked prompt directs you to them. This file is an entry point, not a project specification; keep project and module requirements in `SPEC.md` files.

New Python source files must start with:

```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
```
