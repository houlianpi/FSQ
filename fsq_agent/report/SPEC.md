# Module: report

## Purpose

Generate human-readable and machine-readable reports inside the selected workspace platform's unique direct run directory from dynamic LLM task results and strict-core evidence manifests, including the checked dynamic `verification_goal`, strict lifecycle phase summaries, structured capability provenance, AgentTool/CommonTool/PlatformTool execution metadata, replay metadata, sensitivity-safe previews, and provider-backed AI assertion verdict metadata. Provide one lookup path so CLI can print a stored LLM or strict-core report by run id from that platform's run root.

## Dependencies

- `models`: Uses `Task`, `AgentFinalOutput`, `ToolCallRecord`, `StepResult`, `VerificationResult`, `ReportArtifact`, `EvidenceBundle`, `AIAssertionResult`, and `ReportGenerationError`.

The report module consumes persisted event, result, and evidence data. It must not import `capabilities`, inspect decorators, or rebuild platform action catalogs. Reports may read historical events that contain compatibility labels such as `tool_origin="harness"`, but live capability executor kinds are only `common` and `driver`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ReportGenerator`: Generates reports for completed task runs under the configured output runs directory.
- `EvidenceBundler`: Creates a manifest for evidence references supplied by execution steps, including paths or snapshots produced by capability execution.
- `FailureAnalyzer`: Classifies failures as success, tool usage error, semantic action unmet, execution issue, planning issue, verification issue, or a combined label when multiple rule-assisted signals are present.
- `CoreEvidenceReportGenerator`: Generates Markdown and JSON reports from one deterministic core `evidence-manifest.json` path.
- `resolve_report_path(runs_dir: Path, run_id: str, report_format: Literal["markdown", "json"] = "markdown") -> Path`: Resolves a stored LLM report (`report.md/json`) or strict-core report (`core-report.md/json`) for the requested run id. It returns exactly one matching path or raises `ReportGenerationError` when the report is missing or ambiguous.

The core evidence report API is:

```python
artifact = CoreEvidenceReportGenerator().generate_from_manifest(Path("runs/run-1/evidence-manifest.json"))
```

It writes `core-report.md` and `core-report.json` next to the manifest and returns `ReportArtifact(run_id=..., path=core-report.md, evidence_manifest_path=manifest_path)`.

For strict-core evidence generated from case lifecycle hooks, `CoreEvidenceReportGenerator` must surface persisted lifecycle metadata instead of requiring users to inspect raw manifest JSON. Markdown and JSON reports should distinguish:

- `onCaseStart`: before-case hook work, including nested `runCase` command steps triggered from start hooks and `runShell` start-hook steps.
- `case`: the root case's main command body.
- `onCaseComplete`: after-case hook work, including nested `runCase` command steps triggered from complete hooks and `runShell` complete-hook steps.

The strict-core JSON summary should include lifecycle counts by phase: total, passed, failed, and status. The Markdown summary should include the same lifecycle breakdown in a concise table. The Markdown steps table should include lifecycle phase, source case name or path, action label, step id, status, failure category, and error. Action labels should prefer persisted replay aliases such as `tapOn`/`launchApp` when available, fall back to capability names, and show hook actions such as `runCase` or `runShell` with safe target/command context. Nested hook case steps should be labeled under the hook phase that triggered them, not only under their child case body phase.

## Internal Structure

- `__init__.py`: Public exports only.
- `_generator.py`: Markdown and JSON report generation with minimal JSON fallback, typed agent output rendering, execution/verification report shaping, and `ToolCallRecord` reconstruction from structured capability events in `events.jsonl`.
- `_evidence.py`: Evidence manifest and bundle creation.
- `_core_evidence_report.py`: Markdown and JSON report generation from `EvidenceBundle` or a core `evidence-manifest.json` path, including strict lifecycle phase summarization when lifecycle metadata is present.
- `_resolver.py`: Stored report lookup for LLM `report.*` and strict-core `core-report.*` files.
- `_failure_analysis.py`: Failure classification helpers.
- `templates/`: Optional report templates.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 2 Simple Package.
- Public API: `ReportGenerator`, `EvidenceBundler`, `FailureAnalyzer`, `CoreEvidenceReportGenerator`, and `resolve_report_path` exported from `__init__.py`.
- Internal modules: all `_*.py` files are private report implementation modules.
- Domain boundaries: report owns rendering, stored report lookup, evidence manifest report generation, and failure classification from persisted facts. It does not execute capabilities, read live device state, call providers, parse FSQ YAML for execution, or decide recording eligibility.
- Boundary models: task/result/final-output/evidence/report models and normalized tool call records come from `models`.
- Dependency direction: imports `models` only. It consumes persisted JSON/JSONL files and paths supplied by callers.
- Rationale: report generation is focused transformation from persisted data into Markdown/JSON output, so Level 2 is sufficient.

## Error Handling

If rich Markdown/JSON report generation fails after a task run, `ReportGenerator` attempts to write `report-fallback.json` with `run_id`, `task_id`, `status`, `summary`, and the rich report error. `ReportGenerationError` is raised only when both rich report generation and minimal fallback generation fail.

Stored report lookup raises `ReportGenerationError` when no report exists for the requested run id/format or when both LLM and strict-core report files exist for the same run id/format.

## Current Invariants

- Markdown and JSON reports are part of the design because they are easy to inspect in CI and IDEs.
- JSON reports are structured by lifecycle concern: `task`, `agent_output`, `execution`, `verification`, and `failure_classification`. The `task` and `verification` sections should make the single checked dynamic `verification_goal` visible for LLM runs. The `agent_output` section contains the typed `AgentFinalOutput` when available. The `execution.tool_calls` collection contains normalized `ToolCallRecord` values for real AgentTool, CommonTool, and PlatformTool invocations reconstructed from run events. Tool origin is derived first from structured metadata (`agent_tool`, `common`, `platform`, `runtime`, capability name, platform/backend/owner, and compatibility `tool_origin` when present), not hard-coded tool-name sets. Runtime-only records such as progress events, pre-plan reconstruction, provider setup, and SDK runner summaries are not represented as real tool calls. Step records use `source` for runtime/provenance labels rather than overloading it as a tool name. Failure classification may use both verification output and normalized real tool-call output previews so tool usage failures can be distinguished from planning failures.
- Reports treat capability and AgentTool metadata as persisted execution evidence, not as live decorator state. Report generation must not depend on the module that originally declared a capability. Reports may display replay aliases from persisted `ReplayPolicy` metadata, but they must not expect `CapabilityDefinition.aliases` or per-capability schema strictness fields in persisted capability metadata. Automatic and explicit runner evidence uses normalized `ui_snapshot` artifacts across platforms, and reports render those artifacts uniformly.
- Reports must preserve AI assertion evidence emitted by backend PlatformTools. For Android/Web/Windows/macOS `assert_with_ai`/`assertWithAI`, reports should include the prompt summary, verdict status, explanation, provider/model metadata safe for display, latency/token diagnostics when safe, screenshot artifact references, and any evaluator error. Reports must not re-inspect screenshot pixels or include hidden model reasoning.
- Sensitive runtime-secret text input values must be redacted in reports. Reports may show safe metadata such as requested workspace secret name, text source type, allowlist/presence status, capability name, and replay alias, but never private values. Historical `get_runtime_secret` dependency events are not part of the target runtime-secret input path and need not be treated as active recording dependencies.
- Report artifacts are stored below `<workspace>/.fsq/runs/<platform>/<run-id>`, equivalent to `output.runs_dir/<run-id>` after workspace-platform settings composition. Report does not discover workspace layout or write in an arbitrary caller directory.
- LLM and strict-core reports intentionally keep separate internal shapes. CLI unifies only lookup and printing through `resolve_report_path`.
- HTML report generation is intentionally out of scope.
- Failure analysis is rule-assisted. Provider-side incomplete response failures such as OpenAI Agents SDK `response.incomplete` with `content_filter` must be classified as provider failures, not tool usage errors.
- Deterministic core execution reports should be generated from persisted evidence manifests rather than live runner objects. This keeps report generation replayable and allows reports to be regenerated after real-device runs.
- Regression comparison reports should be generated after execution from persisted strict and recovery manifests. This keeps self-healing auditable and prevents recovery from masking the original regression signal. AI assertion verdicts in strict evidence remain part of the strict result, while AI-assisted repair attempts belong only to separate recovery evidence.
