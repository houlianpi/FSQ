# Module: observation

## Purpose

Persist run-level event timelines under the fsq-agent output directory. Screenshots, UI trees, page sources, and other runtime observations are not captured by the observation module itself; they are represented by artifact references produced by active platform runtime services, PlatformTools, CommonTools, or AgentTool artifact helpers.

## Dependencies

- `models`: Uses `RunEvent`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ExecutionLogger`: Writes structured step logs, run-level trace events, and per-run live event timelines.

## Internal Structure

- `__init__.py`: Public exports only.
- `_logger.py`: Structured logging setup and event writing.
- `SPEC.md`: Module design.

## Error Handling

Event logging failures are treated as I/O errors from the underlying filesystem. Observation capture failures belong to the platform runtime service, PlatformTool, CommonTool, or AgentTool helper that provided the observation capability.

## Current Invariants

- The observation module does not implement screenshot, UI tree, or page-source capture. Current platform observations should be requested through active PlatformTools or harness runtime services; dynamic historical artifact lookup should use AgentTools. If no active capability exposes an observation type, that observation type is unavailable for the run.
- Live run event timelines are persisted as `output.runs_dir/<run-id>/events.jsonl` so interrupted or long-running tasks can be inspected before final reports are generated.
- Event timelines, reports, and tool artifacts must be written under the configured output directories so installed CLI usage does not scatter artifacts across user directories.
