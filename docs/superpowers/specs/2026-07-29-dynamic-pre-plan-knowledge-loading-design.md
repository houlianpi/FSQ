# Dynamic Pre-Plan Knowledge Loading Design

## Goal

Make pre-plan knowledge loading configuration-driven and file-existence-driven. Dynamic LLM pre-planning should not assume that `index.md` or page graph files always exist. It should load and expose only configured knowledge resources that are present, while still allowing page graph content to enrich planning when available.

The intended behavior is:

- configured skills are loaded as they are today and passed directly into pre-plan input when complete;
- `project.md` is available to pre-plan only when it exists under the configured knowledge root;
- `index.md` is available to pre-plan only when the configured pre-plan knowledge directory is set/resolved and the file exists;
- concrete page Markdown files referenced by `index.md` are read only when pre-plan asks for them by page id or relative file path;
- missing optional knowledge files are operational diagnostics, not model-facing instructions or hard failures.

## Scope

This design covers the internal dynamic pre-plan knowledge context for `FsqAgent.run` and `OpenAIAgentsRuntime.run_pre_plan`.

Affected runtime inputs:

- configured skills from `agent_context.knowledge.skills`;
- normal project knowledge from `agent_context.knowledge.root_dir/project.md`;
- optional page graph index from `agent_context.knowledge.pre_plan.dir/index.md` or the knowledge root fallback;
- optional concrete page files under the pre-plan knowledge directory, normally `pages/*.md` and referenced by `index.md`.

Affected modules:

- `agent`: owns pre-plan orchestration, pre-plan runtime tools, and model-facing pre-plan instructions;
- `knowledge`: owns normal project knowledge file loading semantics;
- `skills`: owns configured skill loading semantics;
- `config`: owns path resolution for knowledge root, skills directory, and pre-plan directory;
- `models`: owns shared `KnowledgeBundle`, `SkillBundle`, page knowledge, and `GoalPrePlan` contracts.

## Non-Goals

- Do not make skills dynamically tool-read during pre-plan. The confirmed behavior is to keep skills loaded before pre-plan and passed in the pre-plan input.
- Do not remove page graph support or the `PageKnowledgeIndex`/`PageKnowledgePage` models.
- Do not parse raw cases into executable strict steps during dynamic LLM runs.
- Do not introduce a public standalone pre-plan API or CLI command.
- Do not expose shell/file-system write capability to pre-plan.
- Do not send missing optional knowledge diagnostics to the model as advisory prompt text.

## Proposed Design

### 1. Preserve Configured Skill Loading

`SkillLoader` remains the owner of configured automation skills. `FsqAgent.run` continues loading `self.settings.skills` before pre-plan, and `build_pre_plan_input` continues including only successfully loaded `SkillBundle` values.

Semantics:

- required missing/broken skills fail fast before pre-plan;
- optional missing/broken skills are skipped with operator-visible diagnostics;
- skipped optional skills are not represented as warning-only prompt content;
- successfully loaded skills remain part of the initial pre-plan input.

This keeps platform and harness guidance stable without adding another pre-plan tool round trip for every run.

### 2. Treat Project Knowledge As Optional Pre-Plan Context

Pre-plan should be allowed to use `project.md` when it exists, but it must not require it. The normal `DirectoryKnowledgeProvider` already reads `project.md` for main execution when present. The pre-plan path should mirror the same optional existence behavior for initial planning context.

Expected behavior:

- if `knowledge.root_dir/project.md` exists, pre-plan input includes it under a stable key such as `project.md`;
- if it is absent, pre-plan continues without project knowledge;
- unreadable `project.md` should follow existing knowledge error policy where appropriate: project knowledge read failures are hard failures when the file exists but cannot be read.

### 3. Treat Page Graph Index As Optional Pre-Plan Context

`index.md` remains page-graph-specific and pre-plan-only. The change is that it is optional and only loaded when present.

Expected behavior:

- resolve the active pre-plan knowledge directory as `agent_context.knowledge.pre_plan.dir` when configured, otherwise `agent_context.knowledge.root_dir`;
- if `<pre-plan-dir>/index.md` exists, include it in initial pre-plan knowledge or make it available through the read-only pre-plan tool;
- if it does not exist, do not emit a model-facing warning like `Knowledge index not found: index.md`;
- operator diagnostics may still record that no page index was loaded, but the model prompt should not treat absence as a planning instruction.

### 4. Keep Concrete Page Files On-Demand

Concrete page files referenced by the page graph index should remain lazy. Pre-plan reads them only when needed to continue the planned action chain.

Expected behavior:

- `read_knowledge_page` accepts a safe relative file path or a `page_id`;
- when called by `page_id`, it resolves the page file from the loaded/existing `index.md` if possible;
- if no index exists or the page id is not indexed, the tool may fall back to the current safe `pages/<page_id>.md` convention;
- missing page files return structured tool errors to the planner, not Python exceptions, so the planner can continue with reference text, skills, project knowledge, and available platform tools;
- path traversal and absolute paths remain rejected.

### 5. Clarify Pre-Plan Prompt Contract

The pre-plan instructions should no longer say that initial context contains the knowledge index only. They should describe the actual dynamic context:

- skills are loaded configured guidance;
- project knowledge may be present when `project.md` exists;
- page graph index may be present when configured and `index.md` exists;
- page details are optional and should be read only when needed;
- missing page/project knowledge should lead to warnings in `GoalPrePlan.warnings` only when it materially affects planning confidence.

The planner should still produce the best useful key-action chain and one verification goal when enough information exists from the user reference, configured skills, project knowledge, page knowledge, and platform tool summary.

## Python Architecture Level

Architecture level: 3 Layered Application.

Rationale: this work changes orchestration behavior across configuration, knowledge loading, skill loading, provider-backed pre-planning, and model-facing runtime tools. It does not introduce a new domain model or persistence abstraction. The existing layered ownership remains sufficient:

- `config` resolves paths and config shape;
- `knowledge` and `skills` load advisory context;
- `agent` orchestrates dynamic pre-plan and exposes read-only pre-plan tools;
- `models` owns shared boundary schemas.

No new repository, unit-of-work, or DDD boundary is justified.

## Module Ownership

### `agent`

Owns pre-plan aggregation policy and read-only runtime tools:

- assemble the pre-plan `KnowledgeBundle` from optional `project.md` and optional `index.md`;
- avoid model-facing missing-index warnings when optional files are absent;
- keep `read_knowledge_index` or an equivalent entry-reading tool read-only;
- keep `read_knowledge_page` bounded to the pre-plan knowledge directory;
- keep generated key actions and verification goal behavior unchanged.

### `knowledge`

Owns normal project knowledge behavior:

- `project.md` is optional and loaded for normal execution when present;
- task `knowledge_refs` remain supported;
- loader diagnostics remain operational metadata.

### `skills`

Owns configured skill loading behavior:

- required skills fail fast;
- optional broken skills are skipped;
- only successful `SkillBundle` instances enter pre-plan input.

### `config`

Owns path resolution:

- `agent_context.knowledge.root_dir` resolves relative to config base;
- `agent_context.knowledge.skills.dir` resolves relative to knowledge root;
- `agent_context.knowledge.pre_plan.dir`, when configured, resolves relative to knowledge root;
- absence of `pre_plan.dir` falls back to the knowledge root for page graph lookup.

### `models`

Continues to own shared schemas:

- `KnowledgeBundle` for loaded planning context and operational warnings;
- `SkillBundle` for skill prompt content;
- `PageKnowledgeIndex` and `PageKnowledgePage` for optional page graph files;
- `GoalPrePlan` for structured pre-plan output.

## Data And Control Flow

1. Platform config resolves knowledge paths.
2. `FsqAgent.run` loads normal task knowledge and configured skills.
3. Before external UI actions, `FsqAgent` builds pre-plan context:
   - include `project.md` if present;
   - include `index.md` if present in the resolved pre-plan directory;
   - include no missing optional file warnings in model-facing knowledge content.
4. `OpenAIAgentsRuntime.run_pre_plan` receives reference text, loaded skills, optional planning knowledge, platform tool summary, and runtime secret names.
5. The pre-plan model may call read-only tools to reload the optional index/project entry or read concrete page files.
6. Pre-plan returns `GoalPrePlan` with ordered key actions, one verification goal, relevant page ids, summary, and warnings.
7. `FsqAgent` injects generated key actions and verification goal into the dynamic task, then main execution proceeds unchanged.

## Public Behavior

The user-visible behavior should be:

- Android config with only `knowledge/project_android_v1/project.md` and no `index.md` can still pre-plan.
- Configs with `index.md` and `pages/*.md` continue to support page-graph-enriched planning.
- Configs without `project.md` and without `index.md` can still pre-plan from the user goal/raw case, skills, and platform tool summary when sufficient.
- Required missing skills still fail before pre-plan; optional missing skills are skipped.
- Missing optional `project.md`, `index.md`, or page files must not be shown to the model as prompt instructions.

## Error Handling And Edge Cases

- Missing `project.md`: continue without project knowledge.
- Missing `index.md`: continue without page graph index.
- Missing page referenced by `index.md`: `read_knowledge_page` returns a structured `{ok: false}` payload; planner may warn and continue.
- Unreadable required skill: fail fast through `SkillLoader`.
- Unreadable optional skill: skip and log diagnostics.
- Unreadable existing project/index file: fail or surface an operational diagnostic according to the owning loader's current error policy; do not silently pass corrupted content.
- Unsafe page path: reject absolute paths and parent traversal.
- Empty knowledge directory: pre-plan still receives reference text, loaded skills, platform tool summary, and runtime secret names.

## Compatibility

The design preserves current page graph compatibility:

- existing `index.md` files still work;
- existing `pages/*.md` files still work;
- page id resolution from index remains supported;
- existing configured skills remain loaded into pre-plan input;
- existing raw-case planning reference behavior remains unchanged.

The main compatibility change is removing the assumption that `index.md` must exist.

## Affected Specs Expected To Change

- Root `SPEC.md`: update dynamic pre-plan and prompt context boundaries to describe optional project/page knowledge instead of mandatory initial `index.md`.
- `fsq_agent/agent/SPEC.md`: update internal pre-plan invariants, tool descriptions, prompt expectations, and error handling for optional project/index/page knowledge.
- `fsq_agent/knowledge/SPEC.md`: clarify that `project.md` is optional normal project knowledge and may also be used by pre-plan when present.
- `fsq_agent/skills/SPEC.md`: likely no behavior change, but may clarify that pre-plan receives only successfully loaded configured skills.
- `fsq_agent/config/SPEC.md`: clarify path resolution and optional pre-plan directory behavior if current wording still implies mandatory page knowledge.
- `fsq_agent/models/SPEC.md`: clarify that page graph models remain optional pre-plan enrichment contracts.

## Verification Expectations

Focused tests should cover:

- pre-plan receives `project.md` when it exists and no `index.md` exists;
- pre-plan does not emit a model-facing missing-index warning when `index.md` is absent;
- pre-plan still reads legacy `index.md` when it exists;
- `read_knowledge_page` resolves page files by page id from `index.md`;
- `read_knowledge_page` returns structured not-found payloads for missing optional pages;
- configured skills are still passed to pre-plan input;
- required missing skills still fail fast and optional missing skills are skipped.

Suggested commands:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent.py -k "pre_plan or preplans or refreshes_provider"
.\.venv\Scripts\python.exe -m pytest tests/test_openai_runtime.py -k "pre_plan or knowledge_index or tool_origin"
.\.venv\Scripts\python.exe -m pytest tests/test_knowledge.py tests/test_skills.py tests/test_config.py -k "knowledge or skill or pre_plan"
```

## Resolved Questions

- Skills should keep the current behavior: configured and successfully loaded skills are included directly in pre-plan input.
- `project.md`, `index.md`, and concrete page files should be dynamic optional knowledge resources gated by configuration/path resolution and file existence.
- Concrete page files should remain on-demand rather than all being loaded into the initial pre-plan prompt.

## Self-Review

- The design keeps scope to one SPEC update cycle focused on pre-plan knowledge context.
- It does not require implementation before SPEC confirmation.
- It preserves existing raw-case, skill, and page graph compatibility.
- It avoids making missing optional knowledge model-facing prompt instructions.
- It keeps Python architecture at the existing Level 3 boundary without adding unnecessary abstractions.
