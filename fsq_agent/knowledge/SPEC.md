# Module: knowledge

## Purpose

Load private testing knowledge, recorded UI-element notes, application-specific notes, and plain-text/image knowledge assets. Provide relevant project knowledge context to the OpenAI Agents SDK agent without coupling the agent runtime to storage layout or a single upstream data source, while keeping loader diagnostics out of model-facing prompt text.

## Dependencies

- `models`: Uses `Task`, `KnowledgeBundle`, and shared exception types when knowledge loading fails.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `KnowledgeProvider`: Protocol for adapters that can supply relevant knowledge for a task.
- `DirectoryKnowledgeProvider`: Default adapter for the configured workspace knowledge directory. It reads optional workspace `project.md`, task-referenced text/YAML/JSON files, and discovers image assets for knowledge providers. Loader diagnostics are returned as operational warnings rather than prompt instructions.
- `PrivateKnowledgeLoader`: Loads task-referenced knowledge from configured knowledge directories.
- `KnowledgeBundle`: Re-exported shared model from `models` for callers that work through the knowledge module.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: Knowledge provider protocol, directory-backed provider, file discovery, and loader aggregation.
- `SPEC.md`: Module design.

## Error Handling

Missing optional knowledge references are recorded as operational diagnostics. Invalid required knowledge files raise `FsqAgentError` subclasses from `models` with the failing path and reference name. Knowledge loader diagnostics must be logged or surfaced through runtime diagnostics rather than rendered into model-facing execution prompts.

## Current Invariants

- Knowledge is advisory context, not executable authority.
- Loader diagnostics are not advisory knowledge and should not be sent to LLM prompts.
- Knowledge loading is provider-based. `PrivateKnowledgeLoader` aggregates one or more `KnowledgeProvider` implementations so alternate upstreams can supply plain files, generated indexes, image manifests, databases, or service-backed knowledge without changing the agent runtime.
- The default `DirectoryKnowledgeProvider` reads `project.md` from the workspace knowledge root only when it exists and contains non-whitespace text. Missing, empty, and whitespace-only files all mean no project knowledge and do not produce a `project.md` item for normal execution or pre-plan.
- `index.md` is reserved for the optional page-knowledge graph index consumed by internal dynamic goal planning. It is loaded only when present under the resolved pre-plan knowledge directory and is not automatically loaded into normal task execution by `DirectoryKnowledgeProvider`.
- Task-specific `Task.knowledge_refs` remain supported and are resolved relative to the configured knowledge directory.
- Plain text and Markdown are loaded as strings. JSON and YAML are parsed into structured values. Image files are discovered as assets, but this implementation does not attach image pixels to the model prompt.
- Project knowledge storage lives under the selected workspace platform's `knowledge/<platform>/` root. Reusable automation skills remain repository preset resources and are loaded by the separate `skills` module.
- Skill loading is owned by the separate `skills` module so private knowledge and reusable automation skills can evolve independently.
