# Module: core.evidence

## Purpose

Own run-contained artifact storage and normalized execution evidence recording. Evidence persists safe facts and artifact references supplied by Runner and harness observation boundaries; it does not decide execution, transport projection, Case recording, or report presentation.

## Dependencies

- `models`: evidence bundles, runner events/results, artifact references, and safe metadata.
- `core.interfaces`: artifact/evidence sink boundaries where required by callers.

Evidence must not import adapters, Application, Agent, Case DSL, concrete harnesses, concrete drivers, or report renderers.

## Public Interface

- `ArtifactStore`: owns run-local directory containment and artifact writes.
- `EvidenceRecorder`: records normalized events/results and writes the evidence manifest.

Both symbols are exported from `core.evidence` and re-exported from `core` with identical object identity.

## Internal Structure

- `__init__.py`: public exports.
- `_artifact_store.py`: contained artifact paths and writes.
- `_recorder.py`: evidence bundle accumulation and manifest persistence.

## Python Architecture

- Architecture level: Level 2 Simple Package.
- Public API: `ArtifactStore` and `EvidenceRecorder`.
- Internal modules: `_artifact_store.py` and `_recorder.py`.
- Domain boundaries: safe artifact/evidence persistence only.
- Boundary models: evidence and artifact records come from `models`.
- Dependency direction: Runner and Execution consume Evidence; Evidence depends only on shared models and public interfaces.
- Rationale: persistence is focused and run-local, so no repository or Unit of Work is warranted.

## Error Handling

All paths remain contained under the explicit Run directory. IO and serialization failures are reported without leaking secret values or writing outside the Run.

## Current Invariants

- Artifact paths are Run-relative in persisted contracts.
- Callers do not manually construct artifact storage paths.
- Evidence facts remain distinct from transport progress projection and generated Case recording.
