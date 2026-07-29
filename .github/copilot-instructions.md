# Copilot Instructions

This repository uses Python Spec-Driven Development.

Root `SPEC.md` is the source of truth. Relevant module `SPEC.md` files must be read before changes.

For non-trivial work, do not jump directly to implementation:

1. Use `.github/prompts/requirements-to-design.prompt.md` to clarify requirements and create a confirmed design document.
2. Use `.github/prompts/spec-driven.prompt.md` with that design document path to update SPEC files, implement, verify, synchronize, and audit.

Canonical workflow and architecture guidance lives in `skills/`. Prefer reading those files instead of duplicating rules here.

New Python source files must start with:

```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
```

Do not treat this file as a project specification. Keep project and module requirements in `SPEC.md` files.
