# Module: case_dsl

## Purpose

Canonically load and validate FSQ AI Test DSL Cases, lifecycle metadata, goal-only Cases, replay input, and deterministic commands, then convert commands into executable steps using a supplied capability registry snapshot. It does not execute Cases or hooks.

## Dependencies

- `models`: canonical Case, lifecycle, capability snapshot, executable-step, parameter, and error contracts.

The package must not import Core, Capabilities, Execution, Application, adapters, drivers, harnesses, providers, or tools.

## Public Interface

`__init__.py` exports `FSQ_CASE_SUFFIX`, `FsqCaseLoader`, `FsqExecutableStepAdapter`, and `is_fsq_case_file`. The legacy `fsq` package forwards these exact objects and preserves private module identity where repository callers observe it.

## Internal Structure

- `_loader.py`: YAML parsing, Case shape and lifecycle validation, goal-only normalization, and discovery.
- `_step_adapter.py`: registry-backed command resolution, parameter validation, and executable-step conversion.

## Python Architecture

- Architecture level: Level 2 Simple Package.
- Public API: the loader, step adapter, suffix, and filename predicate.
- Internal modules: `_loader.py` and `_step_adapter.py`.
- Domain boundaries: deterministic Case syntax, validation, and normalization only.
- Boundary models: shared values come from `models`.
- Dependency direction: depends only on public Models contracts.
- Rationale: parsing and normalization are focused stateless behavior.

## Error Handling

Invalid YAML, schema versions, lifecycle metadata, command shapes, aliases, replay support, and parameter payloads raise safe `ConfigurationError` values before execution. Goal-only Cases remain valid.

## Current Invariants

- `*.fsq.yaml` remains canonical and `*.codex.yaml` retains its current warning compatibility.
- Registry snapshots determine active commands and parameter validation.
- Lifecycle hooks remain metadata; path resolution, recursion, shell execution, cancellation, and failure policy belong to Execution.
- Runtime-secret references remain unresolved safe names until Core execution.
- Relocation does not alter models, executable steps, warnings, exceptions, or Case behavior.
