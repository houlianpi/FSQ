# Claude Instructions

This repository uses Python Spec-Driven Development.

Root `SPEC.md` is the project-level source of truth. Relevant module `SPEC.md` files must be read before changes.

For non-trivial work:

1. Use `$requirements-to-design` to clarify requirements and produce a confirmed design document.
2. After the user confirms the design, use `$spec-driven` with the design document path.
3. `$spec-driven` updates SPEC files, waits for SPEC confirmation, implements, verifies, synchronizes, and audits.

Use installed skills when available. For Python architecture decisions, apply `$python-architecture` through the SDD flow.

New Python source files must start with:

```python
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
```

Do not treat this file as a specification. Keep project and module requirements in `SPEC.md` files.
