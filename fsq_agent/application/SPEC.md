# Module: application

## Purpose

Provide the shared, transport-neutral Application layer used by the FSQ CLI, Control Plane, and future Coding Agent APIs. The package exposes application operations grouped by Workspace, Case, Run, Provider, and Environment and coordinates existing module authorities without reimplementing their rules.

## Dependencies

Application may consume public APIs from `models`, `config`, `providers`, `agent`, `execution`, `case_dsl`, `environments`, `core`, and `report`. It must not import adapters, frontend code, Click, HTTP/SSE frameworks, terminal rendering, or concrete UI types. Lower-level modules must not import `application`.

## Public Interface

The package exports transport-neutral operations and their Request, Result, Event, and Error contracts through `__init__.py`. The same symbols are available from their canonical resource modules so callers may depend on the narrow boundary they use. Operations are organized by resource domain rather than exposed through one generic `execute(command)` facade:

- Workspace operations support the shared workspace precondition, platform target resolution, read-only runtime readiness coordination, and workspace initialization needed by adapters.
- Case operations support creating a Case from a Goal, testing an existing Case with optional suggestions, static formatting, and saving generated recordings.
- Run operations support Workspace-scoped multi-platform listing, stable detail lookup, safe structured logs, historical inference, public evidence projection/comparison, artifact resolution, and offline exports.
- Provider operations support user-level Azure OpenAI configuration, GitHub Copilot device authorization/model activation, and active-Provider readiness status. Provider inventory is not an Application operation in the first release.
- Environment operations support listing and diagnostics.
- Doctor supports complete read-only Workspace diagnosis and per-platform command readiness.

Requests contain application inputs, Results contain operation outcomes and safe artifact references, Events describe transport-neutral progress, and Errors contain stable codes plus safe structured details. These contracts contain no Click, HTTP, SSE, terminal, or frontend types. `application.contracts` is the canonical owner of these types and groups them by shared, Workspace, Case, Run, Provider, and Environment concerns. Resource operation modules import those canonical contract objects rather than defining transport-specific or duplicate equivalents.

Canonical resource modules are:

- `application.workspace`: Workspace operations.
- `application.cases`: Case creation, testing, formatting, and generated-recording save operations.
- `application.runs`: persisted Run query, report, artifact, and export operations.
- `application.providers`: Provider operations.
- `application.environments`: Environment operations.
- `application.doctor`: Workspace-level diagnostic orchestration.

`application.runs` owns Workspace-scoped Run query orchestration. CLI requests resolve the exact registered current directory; Control Plane history requests resolve an explicit registered Workspace name. These scope selectors are mutually exclusive and never fall back to another Workspace. History requires a trustworthy readable registered root and platform/Run mapping, not Provider, Driver, application, browser, device, or executable-platform readiness. Application aggregates platform Run roots, detects duplicate IDs, applies filters/order/limits, parses current metadata or bounded historical facts, normalizes safe logs, and supplies resolved inputs to Report. It does not allocate IDs, mutate lifecycle/result facts, render transport output, or open a browser.

Canonical immutable contracts under `application.contracts.runs` include list/show/log/HTML requests and results, `RunSummary`, `RunDetail`, `RunLogEvent`, normalized filters, and Execution-facing metadata. List results contain Workspace identity, queried platforms, filters, counts, truncation, entries, and warnings. Show returns safe summary and relative artifact references without report or log bodies. Logs return validated safe events and selection metadata; original timestamp/title/tool-name fields and normalized time/label/tool fields project consistently. HTML generation returns Run identity, platform, and a Workspace-relative path.

`fsq.run/v2` metadata identifies the Run and lifecycle; the frozen `execution-result.json` owns execution/verification conclusions, independently of evidence completeness and recording/report/suggestion processing. `evidence-events.jsonl` carries `fsq.evidence-event/v1` records, with `fsq.evidence/v2` manifest checkpoints. Application obtains normalized recovered evidence through `execution.RunLifecycleService.read_evidence`, which delegates to Core, and supplies it to Report; neither Application nor Report duplicates journal recovery. Active metadata is reconciled with Execution's read-only owner inspection: confirmed live owners remain active, confirmed dead owners project interrupted, and unknown ownership remains explicitly unknown; missing or stale heartbeat alone never proves interruption. Query does not persist reconciliation.

Historical `fsq.run/v1`, evidence schema `1.0`, and Runs without metadata remain readable through bounded compatibility projection. List isolates a damaged direct-child Run as an error entry; detail/report access permits trustworthy partial history but rejects untrustworthy identity. Missing/conflicting counts, outcomes, artifacts, or measurement provenance produce explicit warnings and unavailable values rather than invented facts. Count summaries derive from canonical action outcomes and retain aggregation scope; dynamic runtime/pre-plan claims are not counted as executed actions. Query never rewrites history.

### Public Run Reports And Exports

- `get_run_report(GetRunReportRequest) -> GetRunReportResult` resolves one Run and optional baseline/related Run IDs within the selected Workspace and platform, then delegates projection and comparison to `report.RunReportService`. The result contains `workspace`, `run_id`, `platform`, `report: models.PublicRunReport`, and warnings. The `fsq.report/v1` report is shared across adapters without casing or semantic copies.
- `export_run_report(ExportRunReportRequest) -> ExportRunReportResult` accepts one `json`, `junit`, `html`, or `bundle` format, optional output path, baseline ID, related IDs, and optional share-profile path. It validates the complete request and destination before delegating to Report with resolved paths and parsed profile data. Results expose Run/platform/export identity, format, output path, export-file inventory, and warnings without replacing the original execution result.
- `resolve_run_artifact(ResolveRunArtifactRequest) -> ResolvedRunArtifact` accepts exactly one typed reference: a source `artifact_id`, or an `export_id` plus `file_id`. It resolves only validated report/manifest entries, rechecks Run/export containment, allowed type, symlinks, size, and recorded hash, and returns a trusted local path plus safe size/MIME metadata for adapter streaming. Browser-supplied file paths are never accepted. The returned host path is an internal adapter capability and must not be serialized to clients.
- `generate_run_html(GenerateRunHtmlRequest) -> GenerateRunHtmlResult` preserves the Run-local `report.html` rebuild used by `runs show --open`, using the same projection and renderer. Browser opening belongs only to the CLI adapter.

Baseline and related IDs resolve in the same Workspace/platform as the primary Run. Report validates stable source comparability, recording mappings, lineage, and hashes; Application does not guess relationships or pair steps by order. Missing or invalid requested relationships return explicit errors. All involved original outcomes remain visible.

Absent an output path, export allocates a unique `exports/<export-id>/` below the primary Run and writes `report.json`, `junit.xml`, `report.html`, or `evidence-bundle.zip` for the selected format plus its export manifest. An explicit output path identifies one destination file; relative paths resolve from the selected Workspace root. Application authorizes only that path and its private temporary output, rejects existing destinations and any path that could overwrite authoritative Run/source files, and supplies that exact destination to Report. No overwrite option is exposed. The `report.html` compatibility rebuild is the sole replacement exception. Export manifest records use contained logical file IDs; export-file resolution cannot enumerate arbitrary sibling paths or serve explicit external CLI destinations.

Share profiles are explicitly selected local inputs. Application validates bounded schema and file identity, then passes profile data to Report. Profiles select artifact IDs, literal text replacements, field removals, and validated screenshot masks; regex, executable templates, credential discovery, secret configuration, commands, and remote inputs are unsupported. Loading a profile never publishes or uploads anything. Default local exports remain local evidence copies, with no claim of anonymity or public suitability. Source Runs and artifacts remain immutable.

Share selection qualifies artifact IDs by Run ID within the resolved report scope. Only the Report allowlist of display text and optional content can be transformed; authoritative identity/outcome/gate/count/reference fields cannot be changed. An optional digest-bound Case review declaration is scoped to the export and explicitly labelled as user-declared, without writing Run/Case approval state. Application applies the Report-owned resource limits and propagates explicit omission, limit, or validation outcomes without inventing different transport budgets.

Export is available for completed, failed, cancelled, interrupted, and trustworthy partial Runs without execution or inference. The public report gate is not passing when completion is untrustworthy or required evidence is missing; original execution/verification outcomes remain distinct from that gate. A preflight error before allocation has no Run ID and does not create a synthetic Run or report. Export errors are separate operation failures and never overwrite a completed test's outcome or exit status.

## Ownership Boundaries

Application owns cross-module orchestration, shared request validation, workspace enforcement, operation-level event production, and consistent results/errors for all adapters. It delegates authoritative behavior to existing modules:

- `agent` owns AI planning, model/tool orchestration, and dynamic verification.
- `execution` owns complete dynamic/deterministic run coordination, Case lifecycle semantics, cancellation/teardown ordering, and candidate Case recording.
- `case_dsl` owns Case parsing, static validation, normalization, canonical serialization, and deterministic-step adaptation.
- `environments` owns host support, read-only runtime readiness, and Web executable discovery.
- `core` owns capability execution, runtime-secret handling, evidence policy, and Harness/Driver routing.
- `report` owns transformation of persisted execution facts into reports and failure analysis.
- concrete drivers own platform automation and backend-error normalization.

Application must not copy, reinterpret, or fork those rules. This specification does not require `case create`, `case test`, and suggestion handling to be three independent internal Use Cases.

Goal-based Case creation requests Run-local recording and supplies the selected platform Case directory as the optional publication destination. An optional `case_name` selects the stable identity; otherwise Execution derives it from platform and normalized Goal. A validated successful recording is published there as `<case-name>.fsq.yaml` with conflict-safe publication. The result exposes the authoritative Run-local candidate, stable name, published path, publication outcome, and safe warnings, including publication conflicts. Recording or publication failure does not replace the completed dynamic execution result.

Case testing always performs one deterministic Execution run. Execution freezes its conclusion before report, recording, or suggestion processing. When suggestion is requested, Application invokes a separate post-execution analysis through an injected read-only collaborator using the parsed source Case and bounded persisted facts. The collaborator has no UI-action authority, cannot rerun the Case, and cannot change its conclusion. Application returns Run-local suggestion/candidate references and their processing status; the source Case and configured Case directory remain unchanged. Suggestion failure is recorded as `case.suggestion_failed` processing diagnostics while retaining the completed result and available report or execution-result reference. It does not replace the test outcome with a top-level execution error.

Workspace initialization accepts a selected current directory, optional workspace name, one platform's target inputs/environment, and controlled-update intent. Application resolves the name case-insensitively through Config's registry. For an unregistered name it delegates final-root selection to Config: an empty selected directory is adopted as the root, while a non-empty selected directory receives an absent `<selected-directory>/<workspace-name>` child. For a registered name it ignores the selected directory for persistence and uses the immutable stored root; an unavailable registered name is not recreated. Before any workspace mutation Application validates the request, resolves the complete target, and asks the platform runtime service to check readiness without installing software. Web target resolution requires an explicit channel and either validates the explicit executable path or discovers exactly one compatible host executable. Application delegates filesystem validation, root selection, platform persistence, registry mutation, idempotency, revision handling, and rollback to Config only after these prerequisites succeed, then returns committed workspace name/root/platform/status plus safe readiness/discovery facts needed by CLI or Control Plane presentation. The shared workspace precondition for non-init commands resolves the exact current directory through Config registry and Workspace truth; a marker directory alone never satisfies it.

Application also exposes transport-neutral workspace create, add-platform, and update-platform operations used by Control Plane. Create accepts a selected directory, name, and complete platform inputs; add and update accept the identity and revision fields required by that mutation. Each operation resolves every target, completes readiness, and only then calls Config persistence. CLI and Control Plane do not call Config workspace mutation operations directly.

Provider operations do not accept or resolve a Workspace. They coordinate the existing public Config and Providers APIs against the user Config root also used by Control Plane and never use process environment, Workspace `.env`, or platform configuration as Provider authority. Azure configuration accepts a complete endpoint, model/deployment name, and API key candidate and delegates validation plus atomic replacement to Config. GitHub configuration exposes transport-neutral device-code request, cancellable completion, eligible-model discovery, and authorization activation operations so an adapter can present and select without receiving persistence authority. Application validates that the selected model came from that authorization's discovered eligible set before activation.

Provider replacement commits a complete candidate before obsolete credentials are removed. Any validation, authentication, discovery, selection, persistence, cancellation, or unexpected failure preserves the previously active Provider and credentials. Results contain only safe Provider type, model, configuration/readiness state, device verification facts where required before activation, and stable safe errors; credentials and raw backend values never enter Application contracts.

The Provider status operation loads the latest user-level Provider snapshot, reports the explicit unconfigured state without manufacturing a default, and delegates non-interactive session readiness to Providers. It may use the documented cached GitHub token refresh but never starts device flow, prompts, sends model inference, or requires a Workspace. Its immutable result contains `status` (`ready` or `unavailable`), `configured`, optional `provider` and `model`, `authenticated`, a safe message, and an optional safe repair action. Expected unavailable states are results rather than exceptions; malformed persisted configuration and unrecoverable orchestration failures remain stable safe Application Errors. Exception messages, tracebacks, API keys, tokens, authorization objects, and raw provider responses are never returned.

Target resolution finishes before readiness check or Config mutation. It rejects cross-platform fields and missing required values; normalizes and validates explicit local paths for existence, regular-file shape, executable eligibility where applicable, and exact Web channel compatibility; and resolves an omitted Web executable only when discovery returns exactly one normalized candidate. Zero or ambiguous candidates are configuration errors and cause no runtime or persistence side effects.
For an explicit Web executable, exact compatibility uses Core's component-aware path identity contract rather than discovery membership or generic substring matching. A non-standard installation root is accepted when the normalized basename and directory or application-bundle components prove the selected product and channel. An ambiguous shared basename without the required channel identity is rejected with safe guidance to omit the path for discovery or provide a channel-identified path.

Application owns the transport-neutral workspace initialization, platform readiness check, and Web executable discovery use cases shared by CLI and Control Plane. It does not implement or invoke package-manager commands, filesystem registry formats, browser path tables, ADB/Appium/backend protocols, or transport wording. Platform runtime services own read-only platform-specific detection; Config owns target validation and persistence. CLI and Control Plane decode inputs and project Application results/errors without reproducing this orchestration.

Application's Doctor operation accepts the exact current directory and returns immutable `DoctorResult`, `DoctorWorkspaceSummary`, `DoctorPlatformResult`, fixed `DoctorChecks`, fixed `DoctorCommands`, `DoctorPrerequisite`, and `DoctorStatusDetail` contracts. Detail and prerequisite status is `ready`, `unavailable`, `error`, or `not_applicable`; platform and overall status is `ready`, `partial`, or `unavailable`. Each platform result contains an ordered prerequisite tuple, empty when the platform exposes no individual prerequisite details. Platforms are diagnosed in Android, Web, Windows, macOS order and only identifiable configured platforms are returned. An identifiable damaged platform produces a configuration error detail without aborting other platforms; an untrustworthy registry, root mapping, or platform inventory raises a Workspace/configuration Application Error.

Doctor delegates component facts through public Config, Environments, Providers, Agent, and Core boundaries, isolates unexpected component exceptions into safe error details, derives command verdicts from a fixed dependency matrix, and returns ordered exact-deduplicated actions. Ordinary `case test` requires configuration, Runtime, Target configuration/availability, and Strict Core readiness. `case test --suggest` additionally requires Provider and suggestion-analyzer readiness. `case create` additionally requires Provider and dynamic-Agent readiness. Doctor does not inspect a particular Case and therefore does not promise readiness for Case-specific syntax, runtime-secret, nested-Case, or `assertWithAI` requirements.

For Android and macOS, Doctor projects Environments-owned prerequisite facts without re-running host commands or interpreting backend output. The existing `target_configuration` and `target_availability` details summarize prerequisite readiness for command dependency evaluation, while the prerequisite tuple explains each independent or blocked host requirement. Actions from prerequisite details participate in the existing ordered exact-deduplicated action list. Stable prerequisite codes are preserved across Human and machine projections.

Doctor requests Config inspection with target-path validation deferred to Environments. A missing or unusable application does not prevent independent host prerequisites from being reported; malformed or identity-mismatched platform documents remain configuration errors and cannot authorize target inspection.

### Registered-platform diagnosis

`diagnose_registered_platform` and its immutable `RegisteredPlatformDoctorRequest` are public Application exports for explicitly selected registered Workspace diagnosis. The request supplies a Workspace name and platform; an optional user-config root is a trusted composition input and is not accepted from browser requests. Application resolves the registered root through Config and returns a `DoctorResult` containing only the requested platform. It shares component checks, ordered prerequisite facts, command dependency rules, and safe errors with CLI Doctor. CLI Doctor retains its exact-current-root, all-configured-platform behavior.

The public `diagnose_platform_settings` operation diagnoses already resolved settings and returns a `DoctorPlatformResult`; registered-platform diagnosis and CLI Doctor use this same implementation after establishing trustworthy configuration. Control Plane macOS run preparation uses it on the settings frozen for that execution attempt. Explore requires the `case_create` verdict; Strict requires `case_test` plus Provider readiness only when the parsed Case requires AI assertions. A browser's earlier ready response is not reusable start authority. Failure prevents Run allocation, model execution, Driver construction, and UI actions.

`DoctorPrerequisite` projects the explicit, default-empty `commands` tuple from Environments facts. Application does not extract commands from explanatory prose or execute remediation. Workspace diagnosis preserves independent check results and safe repair eligibility without returning private configuration values.

### Android selected-device diagnosis

`RegisteredPlatformDoctorRequest` accepts an optional Android-only `target_id` as a transient exact serial. It rejects that field for other platforms, never writes it to Workspace/configuration, and applies it only to a private resolved settings copy. CLI Doctor keeps its all-platform, no-device-selection contract: one online authorized device is unambiguous; multiple online devices produce actionable selection-required diagnosis without inventing a persisted serial setting.

Android platform results expose the effective selected `target_id` (or null) solely to bind device-specific diagnosis to selection. Supplied-but-missing devices do not resolve to another device. The shared readiness dependency matrix is unchanged: Explore requires Provider/dynamic-agent readiness, provider-free Strict does not, and parsed Strict AI assertions additionally require Provider readiness.

Control Plane startup diagnoses the exact Android settings copy after applying the requested device and resolving the effective application identity using the same precedence as execution (Workspace app ID, then supported Case metadata fallback). Existing Strict nested/lifecycle semantics remain unchanged. Installed-app checks use that effective run app rather than a different inferred target. Startup failure occurs before Run allocation, model execution, Driver construction or UI actions. Discovery does not imply app availability. The same diagnosis operation used by CLI provides these prerequisite facts; Application adds no ADB protocol implementation.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: resource-grouped operations and transport-neutral Request, Result, Event, and Error contracts exported from `__init__.py`.
- Dependency direction: CLI and Control Plane adapters depend on Application; Application depends on owning module public APIs; owning modules do not depend on Application.
- Rationale: the package coordinates several existing authorities and presents one consistent application boundary to multiple transports without introducing repositories, a database, a daemon, a queue, or Clean Architecture ceremony.

## Internal Structure

- `__init__.py`: Complete convenience exports for the public Application API.
- `contracts/`: Canonical transport-neutral Request, Result, Event, Error, summary, and machine-record contracts grouped by resource concern.
- `workspace.py`: Public Workspace operation boundary and private Workspace orchestration helpers.
- `cases.py`: Public Case creation, testing, formatting, and generated-recording save boundary.
- `_case_format.py`: Static Case file orchestration and atomic conditional formatting writes.
- `runs.py`: Public persisted Run query/report/export/artifact boundary and Workspace/destination resolution.
- `providers.py`: Public Provider operation boundary.
- `environments.py`: Public Environment operation boundary.
- `doctor.py`: Public Workspace Doctor operation and aggregation boundary.
- Private `_*.py` files may support these public modules but are not imported across package boundaries.

## Error Handling

Application normalizes expected operation failures into stable application Errors and preserves safe structured details. It never exposes secrets, hidden model reasoning, backend objects, transport status codes, or tracebacks. Adapters map Application Errors to exit codes, HTTP statuses, and presentation text.

Report/export errors distinguish unavailable or invalid facts, incompatible baselines, invalid lineage/share profiles, unavailable artifacts, source changes, unsafe/existing destinations, and generation/persistence failure. Identity and relationship errors fail before writes; optional missing evidence remains a report availability state. Export writes commit atomically and never change `run.json`, `execution-result.json`, journals, source artifacts, or an existing destination. Safely reading/exporting a failed Run is a successful query/export operation with a non-passing report gate.

Doctor component failures do not expose exception messages, arguments, tracebacks, raw subprocess/backend output, env values, or credentials and do not abort independent checks. Only an untrustworthy Workspace identity/inventory or an unrecoverable top-level orchestration failure prevents a complete result.

## Current Invariants

- CLI and Control Plane business operations pass through Application.
- CLI and Control Plane use the same Config-owned registered workspace identity and `.fsq` layout; Application contains no legacy marker-based workspace authority.
- Shared runtime readiness and Web executable discovery flow through Application; adapters and Application do not execute installers or maintain browser discovery tables.
- All CLI and Control Plane workspace mutations flow through Application; Config remains the persistence and transaction owner.
- Application is a real Python package and an architectural layer, not a documentation-only label.
- There is no generic command-string facade.
- Application contracts have one canonical definition under `application.contracts`; package-root and resource-module exports reference the same objects.
- Resource modules contain the authoritative implementation for their operation group; compatibility exports do not copy behavior or state.
- Run queries are read-only. Explicit report/export requests may write only derived artifacts at the validated destination; they never execute, authenticate, invoke Providers/Drivers, or rewrite authoritative metadata or results.
- Transport concerns remain in adapters.
- Domain and runtime rules remain in their owning modules.
- Case operations coordinate through public Execution services and do not import package-root or adapter-private execution helpers.
- Suggestion-enabled Case testing separates deterministic execution from read-only post-execution AI analysis; the analysis has no UI-action authority and all generated artifacts remain inside the completed Run directory.
- Doctor is a read-only Application use case; CLI presents its result but does not reproduce diagnostic or command-readiness rules.
- Provider configuration and status are user-level Application use cases shared in persistence authority with Control Plane, require no Workspace, and never recover Provider state from `.env` or process environment.
- The first-release Provider boundary has one active Provider and no listing, profiles, fallback chain, or transport-specific UI models.

## Static Case Formatting And Generated Save

`format_case`, `CaseFormatRequest`, `CaseFormatResult`, and `CaseFormatDiagnostic` are public Application contracts exported through the Case resource and package entries. Requests identify one explicit file path, its current-directory base, and check/diff/write mode. No Workspace registration, platform configuration, Provider readiness, credential resolution, or external runtime construction is required. Platform comes from Case metadata and selects the declarative capability registry, including AI assertion schemas without constructing an evaluator.

The operation delegates content validation and canonical bytes to Case DSL. Cross-file lifecycle resolution and runtime checks are outside its scope and are identified as such in results. Format does not rename files, strip recording metadata, or migrate historical files. Invalid data yields field-addressable safe diagnostics and no write. Successful writes replace atomically only after validating all data, preserve file permission bits, avoid a write when bytes match, and fail if the source changed since it was read rather than knowingly overwriting concurrent edits.

Results include path, mode, `valid`, `formatted`, `changed`, `needs_formatting`, diagnostics, and optional unified diff. `valid` describes static validity; `formatted` describes whether the resulting on-disk file is canonical; `changed` means this invocation actually wrote different bytes; `needs_formatting` describes the original input. Read-only noncanonical input has valid=true, formatted=false, changed=false. Successful normalization writes have valid=true, formatted=true, changed=true. Invalid input has valid=false, formatted=false, changed=false. Diagnostic fields are stable code, safe message, file, optional zero-based command index, and field path; raw rejected values are excluded.

`save_recorded_case`, `CaseSaveRequest`, and `CaseSaveResult` coordinate the supplied frozen candidate/destination/platform/name through Execution's public contained publication boundary. Control Plane owns terminal-run authorization and frozen input selection; Application and Execution own saving semantics.

Suggestion candidates pass shared static validation and canonical serialization before persistence, preserve the parsed source identity and description, and never gain Run provenance in their YAML. Invalid candidates remain unavailable with safe diagnostics; the completed execution result and source bytes are preserved.
