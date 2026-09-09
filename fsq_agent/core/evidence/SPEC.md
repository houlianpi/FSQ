# Module: core.evidence

## Purpose

Own run-contained artifact storage, the durable runner evidence journal, atomic evidence checkpoints, and read-only reconstruction of persisted execution facts. Evidence persists safe facts and artifact references supplied by Runner and harness observation boundaries; it does not decide execution, Run lifecycle or liveness, transport projection, Case recording, or report presentation.

## Dependencies

- `models`: evidence bundles, runner events/results, artifact references, and safe metadata.
- `core.interfaces`: artifact/evidence sink boundaries where required by callers.

Evidence must not import adapters, Application, Agent, Case DSL, concrete harnesses, concrete drivers, or report renderers.

## Public Interface

- `ArtifactStore`: owns run-local directory containment, unique artifact allocation, atomic artifact writes, and explicit capture availability records.
- `EvidenceRecorder`: implements the public evidence sink contracts, appends normalized execution facts durably, builds bundles, and atomically checkpoints the manifest. Existing `record_event`, `record_step_result`, `build_bundle`, and `write_manifest` methods remain supported. Its public `recover_bundle(run_dir: Path) -> EvidenceBundle` class operation reconstructs a bundle from a validated checkpoint and acknowledged journal records without invoking execution or rewriting source facts.

Both symbols are exported from `core.evidence` and re-exported from `core` with identical object identity.

## Internal Structure

- `__init__.py`: public exports.
- `_artifact_store.py`: contained unique artifact paths, availability records, and atomic writes.
- `_recorder.py`: journal append, evidence reconstruction, bundle accumulation, and atomic manifest checkpoints.

## Python Architecture

- Architecture level: Level 2 Simple Package.
- Public API: `ArtifactStore` and `EvidenceRecorder`.
- Internal modules: `_artifact_store.py` and `_recorder.py`.
- Domain boundaries: safe artifact/evidence persistence only.
- Boundary models: evidence and artifact records come from `models`.
- Dependency direction: Runner and Execution consume Evidence; Evidence depends only on shared models and public interfaces.
- Rationale: persistence is focused and run-local, so no repository or Unit of Work is warranted.

## Error Handling

All paths remain contained under the explicit Run directory, including resolved symlinks. IO and serialization failures are reported without leaking secret values or writing outside the Run. A failed append or checkpoint never replaces a previously valid checkpoint or silently acknowledges an unpersisted fact.

Recovery preserves complete validated records before an incomplete trailing write and reports the truncated tail explicitly. A malformed complete record, conflicting sequence, or inconsistent identity is an evidence-integrity error; it cannot be silently discarded to manufacture a complete or successful bundle. Missing, unreadable, truncated, deliberately omitted, and not-applicable artifacts are distinguishable from captured artifacts. Unknown values remain null with a reason.

## Current Invariants

- Artifact paths are Run-relative in persisted contracts.
- Callers do not manually construct artifact storage paths.
- Evidence facts remain distinct from transport progress projection and generated Case recording.
- `evidence-events.jsonl` stores `fsq.evidence-event/v1` runner journal records with a strictly increasing Run-local sequence and stable event identity. It is separate from Agent `events.jsonl`; a capability fact is persisted once even when SDK progress events also describe it.
- Step start, phase transitions, external action result, artifact capture outcome, and step completion are appended as they occur, with flush and durable acknowledgement at the boundary that depends on them. Evidence does not wait for the complete step or Run to return before persisting facts.
- `evidence-manifest.json` uses `fsq.evidence/v2`, records its checkpoint sequence and completeness, and is written through same-directory temporary storage, flush, fsync, and atomic replacement. Recovery can expose a partial Run from the checkpoint and journal after a crash.
- Historical core evidence version `1.0` and the supported unversioned dynamic manifest shape remain readable without migration or invented missing fields. New dynamic and strict capability evidence use the same versioned manifest contract.
- Artifact identity includes artifact kind, `step_execution_id`, phase, and capture occurrence. Screenshot and UI snapshot references are distinct; repeated invocations, attempts, and captures never overwrite earlier evidence. Safe artifact content integrity metadata describes the bytes actually persisted; secret values are neither persisted nor hashed as provenance.
- Evidence completeness is derived from required capture outcomes and acknowledged execution facts, independently of action and verification verdicts. Partial evidence cannot silently become complete during report generation.
- `recover_bundle` owns versioned journal/checkpoint reconstruction. Execution exposes this through its read-only evidence boundary; report renderers receive the normalized `models.EvidenceBundle` and do not import Core or implement another journal-replay algorithm.
