# Module: report

## Purpose

Project persisted Run facts into one public evidence report for CLI, Control Plane, CI, and offline inspection. Own deterministic report projection, evidence comparison, rendering, and contained export. Preserve dynamic and strict Markdown/JSON report APIs and their stored formats.

## Dependencies

- `models`: Owns task, result, evidence, assertion, report, comparison, export, and share-profile contracts, including `PublicRunReport`, `RunReportExportOptions`, and `RunReportExportResult`.

The report module imports no other project modules. It consumes persisted event, result, and evidence data and must not discover Workspaces, parse Cases for execution, inspect decorators, rebuild capability catalogs, invoke Providers/Drivers, inspect live UI, or import adapters. Reports may read historical events containing `tool_origin="harness"`; live capability executor kinds are `common` and `driver`.

## Public Interface

`__init__.py` exports:

- `ReportGenerator`: Generates reports for completed task runs under the configured output runs directory.
- `EvidenceBundler`: Compatibility API for manifests built from dynamic `StepResult` references. It never overwrites a Core-owned `fsq.evidence/v2` manifest; normal execution consumes Core's evidence journal and checkpoints.
- `FailureAnalyzer`: Classifies failures as success, tool usage error, semantic action unmet, execution issue, planning issue, verification issue, or a combined label when multiple rule-assisted signals are present.
- `CoreEvidenceReportGenerator`: Generates Markdown and JSON reports from one deterministic core `evidence-manifest.json` path.
- `resolve_report_path(runs_dir: Path, run_id: str, report_format: Literal["markdown", "json"] = "markdown") -> Path`: Resolves a stored LLM report (`report.md/json`) or strict-core report (`core-report.md/json`) for the requested run id. It returns exactly one matching path or raises `ReportGenerationError` when the report is missing or ambiguous.
- `RunReportService`: `project` converts supplied normalized evidence and explicitly resolved Run facts into `PublicRunReport`; `compare` computes comparable step and UI snapshot differences; `export` renders and atomically writes the requested format using `RunReportExportOptions` and returns `RunReportExportResult`. It receives model-owned values, resolved Run/output paths, and validated share-profile data rather than Workspace names, CLI arguments, or frontend state.
- `generate_static_run_report(run_dir: Path, facts: Mapping[str, object]) -> Path`: Compatibility wrapper over the public projection and HTML renderer that atomically rebuilds the Run-local `report.html`. Current-schema callers include recovered normalized evidence in `facts`; the wrapper does not recover a journal itself. It performs no browser opening and cannot change authoritative Run facts.

The core evidence report API is:

```python
artifact = CoreEvidenceReportGenerator().generate_from_manifest(Path("runs/run-1/evidence-manifest.json"))
```

It writes `core-report.md` and `core-report.json` next to the manifest and returns `ReportArtifact(run_id=..., path=core-report.md, evidence_manifest_path=manifest_path)`.

For strict-core evidence generated from case lifecycle hooks, `CoreEvidenceReportGenerator` must surface persisted lifecycle metadata instead of requiring users to inspect raw manifest JSON. Markdown and JSON reports should distinguish:

- `onCaseStart`: before-case hook work, including nested `runCase` command steps triggered from start hooks and `runShell` start-hook steps.
- `case`: the root case's main command body.
- `onCaseComplete`: after-case hook work, including nested `runCase` command steps triggered from complete hooks and `runShell` complete-hook steps.

Strict-core JSON and Markdown expose the same lifecycle breakdown and preserve passed, failed, skipped, and cancelled step distinctions. Counts derive from result records, use the public report's consistent count definitions, and never classify every non-passed result as failed. Action labels prefer persisted replay aliases, fall back to capability names, and show hook actions with safe context. Nested hook Case steps retain the phase and invocation that triggered them.

### Public Report Projection

`PublicRunReport` uses schema `fsq.report/v1` and the sections defined by `models`. It contains Run/source/runtime identity, original execution and verification outcomes, evidence completeness, post-execution processing status, action and lifecycle results, measured metrics, first blocking failure and secondary diagnostics, ordered logs, artifact inventory, source/recording lineage, and optional comparisons. Public schema ownership belongs to `models`; reports do not create transport-specific copies.

Current Run facts originate from `fsq.run/v2` metadata, the frozen `execution-result.json`, `fsq.evidence-event/v1` records in `evidence-events.jsonl`, and `fsq.evidence/v2` manifest checkpoints. Callers supply the normalized `EvidenceBundle` recovered by Core through Execution's public read boundary; Report never implements journal/checkpoint recovery or imports Core/Execution. Run identity/lifecycle comes from validated metadata; completed execution/verification conclusions come from the frozen result; canonical action conclusions come from normalized runner results. Evidence completeness and report/recording/suggestion failures remain independent facts. An SDK tool transport completing never implies its capability passed. Rule-assisted failure labels supplement structured causes and are marked as inferred rather than replacing them.

Historical `fsq.run/v1`, evidence schema `1.0`, dynamic `report.json`/`report-fallback.json`, strict `core-report.json`, and both persisted event shapes remain readable without rewriting their files. Dynamic action results and artifact references are reconstructed from persisted event payloads, including `runner_result` and `artifact_refs`; `execution.runtime_steps` and pre-plan claims are not treated as real action invocations. A safe projection identifies which sources supplied its fields, reports contradictions and absent facts, and does not silently manufacture a repaired `run.json`. Untrustworthy identity prevents export; partial but trustworthy facts remain inspectable with explicit unavailable sections and a non-passing gate.

Step identity preserves Run-local step/call IDs, stable source keys, Case invocation and lifecycle phase, authored/canonical action, kind, execution status, transport status when relevant, failure category, safe error, and evidence references. Dynamic helper tool invocations remain distinct from recordable capability actions. Root Case totals, action totals, and lifecycle/attempt records have named aggregation scopes and never double-count a parent `runCase` with its child actions. Logs normalize timestamp/title/tool-name and time/label/tool forms, retain source sequence and step identity, and expose safe parse/order/truncation diagnostics instead of dropping data silently.

Metric values carry unit, measurement scope, and availability. Step wall duration, prepare/invoke/settle/finalize durations, screenshot/UI-snapshot capture timing and size, actual attempts, and measured assertion latency are exposed when recorded. Missing, unsupported, unmeasured, and truncated values are `null` with a reason; zero denotes a measured zero. Historical zero phase durations without a measurement marker are unmeasured. Configured maximum attempts are not actual attempts, requested stabilization delay is not measured elapsed delay, and overlapping phase/capture/parent durations are not summed as independent work. Dynamic pre-plan/runtime summaries do not contribute action counts or per-step timing totals. Provider usage retains its recorded scope; main-agent usage is not total Run usage, and tokens/cost are neither estimated nor divided among steps.

Evidence coverage derives from persisted capture expectations for each step kind and capture phase. Available, intentionally uncaptured, missing, failed, truncated, and redacted artifacts remain distinguishable. A missing required capture makes evidence incomplete and prevents a passing report gate while preserving the original execution/verification conclusions. Optional evidence is not required retroactively for historical Runs.

### Comparison And Lineage

Report owns deterministic normalization and line/inline UI snapshot diff data consumed identically by Control Plane and HTML. Each diff identifies source artifact IDs/hashes, normalized format/version, and completeness. Within-step before/after diff describes observed change and is not itself an assertion or proven failure cause. Screenshots are paired visual evidence; pixel differences do not establish a verdict.

Cross-Run baselines require the same platform and a persisted comparable source identity plus stable source step keys, or an explicit recording-command mapping validated against its source/Case hashes. Reports never pair steps by display order, action name alone, or similar prose. Non-comparable, one-sided, missing, truncated, or transformed evidence has an explicit comparison status and cannot be reported as unchanged. Normalization cannot discard a fact used by an assertion without marking that comparison incomplete.

Related Runs are resolved by callers and checked against persisted lineage and artifact/source hashes. A recording, candidate, published Case, and strict replay remain separate objects with separate validation/review/replay status. Related or baseline outcomes never replace the primary Run outcome. Suggested or recovered Cases do not erase the original failed execution; all original outcomes remain visible.

Every cross-Run artifact and step reference is qualified by Run ID; bundle paths are namespaced under `runs/<run_id>/`. A local artifact ID never selects content from another Run. An optional export-scoped Case review declaration identifies the retained Case artifact/digest and is visibly a user declaration, not independent approval or a change to execution lineage. Saving or replaying a Case does not itself supply review evidence.

### Export Formats

- JSON serializes the complete `fsq.report/v1` contract with relative artifact references, schema version, provenance, and warnings. It does not expose absolute host paths, private configuration, or hidden model reasoning.
- JUnit emits one testcase for the primary Run's root Case or Goal invocation. Baseline/related Runs are references and do not add testcase counts. Action, attempt, nested hook, and model-call details are properties, bounded `system-out`, and report anchors. The model-owned `run.gate` maps `passed` to pass, `failed` to `failure`, and both `error` and `incomplete` to `error`. Step skips remain detail rather than a fabricated skipped root testcase. The original FSQ outcome and separate evidence/processing statuses remain properties. Interruption solely after a trustworthy execution freeze follows the shared processing-isolation rule; missing or untrustworthy execution facts never become a passing testcase.
- HTML is a standalone offline file with embedded PNG screenshots, escaped snapshot/source/log text, inline CSS, evidence anchors, and shared normalized diff data. It presents the original verdict and first failure before the step timeline, evidence comparisons, lifecycle details, related strict replay, and diagnostics. Packaged fixed scripts may provide selection/filter/disclosure controls only under hash-based CSP; network requests, eval, inline event handlers, and execution of stored HTML/SVG/JavaScript artifacts are prohibited. Missing/large/partial sections remain visible with their availability reason.
- Bundle is a ZIP containing the standalone HTML, public JSON, JUnit, selected sanitized source/Case and evidence copies, an artifact index, and SHA-256 checksums. Archive names remain contained relative paths and cannot refer to symlinks or external files. The index relates copied/transformed artifacts to source IDs and original hashes and records export/profile versions. Checksums establish content integrity, not authorship or anonymity.

Exports are derived local copies. A default export does not claim that visible application data is safe to publish. An explicit share profile contains an artifact-ID selection, literal text replacements, field removals, and validated screenshot rectangle masks applied to export copies only. Profiles have no regex, script, executable template, remote lookup, or secret-configuration input. Text is transformed before rendering and diffing; image masks are applied to decoded raster copies. Source hashes identify exact retained bytes and are distinct from transformed hashes; no digest is synthesized for omitted private values. Exclusions and transformations remain visible without claiming complete removal of private content. Profile-sensitive values are not reproduced in the export manifest. Source facts and screenshots are never modified.

Profile selections use qualified Run/artifact identities. Text replacement and field removal apply only to allowlisted display text or optional content, with redaction/omission metadata. Schema, identity, outcome, gate, counts, measured quantities, reference structure, source digests, and lineage meaning cannot be altered. Derived digests remain separate. An optional `case_review_declaration` follows the model-owned export-only declaration contract and is reproduced with its export timestamp and explicit attribution.

One Report-owned fixed resource policy applies to API projection and every exporter: at most eight related Runs plus one baseline; a profile is at most 256 KiB and 256 transformation rules; a raster is at most 16 MiB encoded and 40 million decoded pixels; displayed snapshot text is at most 512 KiB per artifact; total inline text is at most 8 MiB and embedded raster content at most 64 MiB per report; a bundle is at most 512 MiB uncompressed. These limits are versioned report metadata, not user-configurable execution policy. Optional display content over budget is explicitly omitted or truncated with its original size and authorized full-artifact reference. Required identity/outcome corruption, an over-limit relationship/profile request, or a bundle exceeding its total budget is an explicit error; no successful export silently drops selected bundle files. Display omission does not change the source execution or evidence gate. Hash/identity checks and complete required result accounting precede a passing report.

`RunReportService` reads only the resolved, contained input artifacts and writes only a caller-authorized export target. Application owns Workspace and destination resolution. Export checks containment, source hashes, file/type/size limits, and destination absence again at the filesystem boundary. Existing files and source facts are never overwritten, except the explicit Run-local `report.html` compatibility rebuild. An export uses one identified persisted snapshot and records its checkpoint/hash boundary; changing inputs cause a retryable error rather than a mixed report.

## Internal Structure

- `__init__.py`: Public exports only.
- `_generator.py`: Markdown and JSON report generation with minimal JSON fallback, typed agent output rendering, execution/verification report shaping, and `ToolCallRecord` reconstruction from structured capability events in `events.jsonl`.
- `_evidence.py`: Evidence manifest and bundle creation.
- `_core_evidence_report.py`: Markdown and JSON report generation from `EvidenceBundle` or a core `evidence-manifest.json` path, including strict lifecycle phase summarization when lifecycle metadata is present.
- `_resolver.py`: Stored report lookup for LLM `report.*` and strict-core `core-report.*` files.
- `_static_html.py`: Offline escaped HTML rendering, contained artifact projection, and atomic `report.html` persistence.
- `_run_report.py`: Public report projection and compatibility input adaptation.
- `_comparison.py`: Stable identity matching, lineage checks, snapshot normalization, and deterministic diff construction.
- `_export.py`: Shared export coordination, destination containment, share-profile transformations, and bundle/index/checksum persistence.
- `_junit.py`: JUnit projection of public Run conclusions and step detail.
- `_failure_analysis.py`: Failure classification helpers.
- `templates/`: Optional report templates.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 2 Simple Package.
- Public API: `RunReportService`, `ReportGenerator`, `EvidenceBundler`, `FailureAnalyzer`, `CoreEvidenceReportGenerator`, `resolve_report_path`, and `generate_static_run_report` exported from `__init__.py`.
- Internal modules: all `_*.py` files are private report implementation modules.
- Domain boundaries: persisted-fact projection, comparison, rendering, safe export, and supplementary failure classification. Execution, result finalization, Case recording eligibility, Workspace discovery, and publication remain outside Report.
- Boundary models: task/result/final-output/evidence/report models and normalized tool call records come from `models`.
- Dependency direction: imports `models` only and must not import `application` or transport adapters. It consumes persisted JSON/JSONL files and paths supplied by Application or other authorized callers.
- Rationale: projection and export are bounded deterministic transformations of caller-resolved files; no application service layer, repository, database, or workflow engine is required.

## Error Handling

If rich Markdown/JSON report generation fails after a task run, `ReportGenerator` attempts to write `report-fallback.json` with `run_id`, `task_id`, `status`, `summary`, and the rich report error. `ReportGenerationError` is raised only when both rich report generation and minimal fallback generation fail.

Stored report lookup raises `ReportGenerationError` when no report exists for the requested run id/format or when both LLM and strict-core report files exist for the same run id/format.

Projection requires trustworthy Run identity and distinguishes unavailable history from an empty successful Run. Unsupported schemas, incompatible baselines, invalid lineage/share profiles, source changes, unsafe paths, existing export destinations, and persistence failures produce bounded `ReportGenerationError` diagnostics. Optional missing artifacts render unavailable sections. Export failure is independent of the original execution result, leaves source facts and existing destinations intact, and removes incomplete temporary outputs.

## Verification Scope

Verification covers equivalent dynamic/strict public projection; historical compatibility and contradiction warnings; measured versus unavailable timing; execution/transport status separation; count and JUnit gate consistency; lifecycle and attempt aggregation; interrupted and partial evidence; stable identity matching; shared diff determinism; lineage/hash checks; contained atomic export; source immutability; profile transformations; and complete offline HTML/bundle rendering without active persisted content.

## Current Invariants

- Markdown and JSON reports are part of the design because they are easy to inspect in CI and IDEs.
- Dynamic internal JSON reports retain `task`, `agent_output`, `execution`, `verification`, and `failure_classification`. The checked `verification_goal` and typed final output remain visible. `execution.tool_calls` contains real AgentTool/CommonTool/PlatformTool invocations reconstructed from persisted metadata, not runtime progress or pre-plan reconstruction. Tool origin comes from structured provenance rather than hard-coded tool-name sets. Step `source` remains provenance rather than a tool name. Public projection preserves execution status independently from the internal transport-completion label.
- Reports treat capability and AgentTool metadata as persisted execution evidence, not as live decorator state. Report generation must not depend on the module that originally declared a capability. Reports may display replay aliases from persisted `ReplayPolicy` metadata, but they must not expect `CapabilityDefinition.aliases` or per-capability schema strictness fields in persisted capability metadata. Automatic and explicit runner evidence uses normalized `ui_snapshot` artifacts across platforms, and reports render those artifacts uniformly.
- Reports must preserve AI assertion evidence emitted by backend PlatformTools. For Android/Web/Windows/macOS `assert_with_ai`/`assertWithAI`, reports should include the prompt summary, verdict status, explanation, provider/model metadata safe for display, latency/token diagnostics when safe, screenshot artifact references, and any evaluator error. Reports must not re-inspect screenshot pixels or include hidden model reasoning.
- Sensitive runtime-secret text input values must be redacted in reports. Reports may show safe metadata such as requested workspace secret name, text source type, allowlist/presence status, capability name, and replay alias, but never private values. Historical `get_runtime_secret` dependency events are not part of the target runtime-secret input path and need not be treated as active recording dependencies.
- Execution-owned reports remain below the direct Run directory. Explicit exports use the Application-authorized destination and never gain arbitrary filesystem discovery or mutation authority.
- LLM and strict-core reports retain their internal shapes; `fsq.report/v1` is their common public projection. Export never replaces the source report or manifest.
- Static HTML is derived only from persisted facts and does not become authoritative evidence or update `run.json`.
- Failure analysis is rule-assisted. Provider-side incomplete response failures such as OpenAI Agents SDK `response.incomplete` with `content_filter` must be classified as provider failures, not tool usage errors.
- Deterministic core execution reports should be generated from persisted evidence manifests rather than live runner objects. This keeps report generation replayable and allows reports to be regenerated after real-device runs.
- Regression comparison reports should be generated after execution from persisted strict and recovery manifests. This keeps self-healing auditable and prevents recovery from masking the original regression signal. AI assertion verdicts in strict evidence remain part of the strict result, while AI-assisted repair attempts belong only to separate recovery evidence.
