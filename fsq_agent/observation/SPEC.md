# Module: observation

## Purpose

Persist safe Agent progress and diagnostic event timelines under the active workspace's direct run directory. The durable Core execution journal and evidence checkpoints belong to `core.evidence`. Screenshots, UI trees, page sources, and other runtime observations are represented by artifact references produced by active platform runtime services, PlatformTools, CommonTools, or AgentTool artifact helpers.

## Dependencies

- `models`: Uses `RunEvent`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ExecutionLogger`: Writes structured step logs, run-level trace events, and per-run live event timelines.

## Internal Structure

- `__init__.py`: Public exports only.
- `_logger.py`: Structured logging setup and event writing.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: Level 2 Simple Package.
- Public API: `ExecutionLogger` exported through `__init__.py`.
- Internal modules: `_logger.py` owns structured progress persistence.
- Domain boundaries: safe event timeline persistence only; Core Evidence owns the execution ledger and Execution owns Run lifecycle.
- Boundary models: `models.RunEvent`; no duplicate event hierarchy.
- Dependency direction: Agent and composition roots consume Observation; Observation depends only on shared models.
- Rationale: run-local JSONL persistence needs no service layer or repository abstraction.

## Error Handling

Event logging failures are treated as I/O errors from the underlying filesystem. Observation capture failures belong to the platform runtime service, PlatformTool, CommonTool, or AgentTool helper that provided the observation capability.

## Current Invariants

- The observation module does not implement screenshot, UI tree, or page-source capture. Current platform observations should be requested through active PlatformTools or harness runtime services; dynamic historical artifact lookup should use AgentTools. If no active capability exposes an observation type, that observation type is unavailable for the run.
- Live run event timelines are persisted as `<workspace>/.fsq/runs/<platform>/<run-id>/events.jsonl`, equivalent to `output.runs_dir/<run-id>/events.jsonl` after workspace-platform settings composition, so interrupted or long-running tasks can be inspected before final reports are generated.
- `events.jsonl` retains its Agent progress format and is never mixed with `evidence-events.jsonl` or assigned the Core journal's sequence space. Correlated capability progress includes execution identity where known; Observation does not infer or manufacture missing Core execution results.
- `run_started`, `run_completed`, and `run_failed` compatibility progress events do not finalize Run metadata or override the frozen execution conclusion.
- The timeline accepts the safe `dynamic_agent_token_usage` Run event emitted once for a completed Dynamic Agent main execution and persists it as an ordinary JSONL record; Observation does not calculate, estimate, aggregate, or otherwise interpret token usage.
- Event timelines, reports, and tool artifacts must remain inside the unique current run directory, a direct child of the selected platform run root; observation never discovers or constructs workspace paths.
