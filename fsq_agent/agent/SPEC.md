# Module: agent

## Purpose

Coordinate dynamic goal/reference testing workflows using OpenAI Agents SDK: load runtime settings, construct or receive dynamic-only AgentTool hosts plus active platform harness/backend bindings, obtain the shared provider session from `providers`, build the validated platform-selected capability registry, build the OpenAI-compatible agent from AgentTools plus registry-backed CommonTool/PlatformTool capabilities, load relevant project knowledge and complete configured skills, derive execution key actions and a final verification goal from a natural-language goal or raw reference content, execute every concrete recordable capability invocation through `StepRunner`, persist safe normalized capability event metadata for post-run recording, derive verification status by checking the final verification goal against execution evidence, and trigger report generation.

## Dependencies

- `models`: Uses all task, plan, structured agent IO, result, tool, report, event, and exception models.
- `config`: Uses runtime settings.
- `providers`: Builds shared Azure OpenAI or GitHub Copilot provider sessions and provider-backed evaluator dependencies.
- `core`: Uses `CapabilityRegistry`, `StepRunner`, `HarnessInterface` implementations, platform CommonTool providers, backend drivers, and shared harness behavior through public core exports supplied by entry/runtime construction.
- `tools`: Builds dynamic-only AgentTool providers/executors and adapts AgentTools into OpenAI Agents SDK tools.
- `observation`: Captures evidence after steps.
- `knowledge`: Loads private knowledge.
- `skills`: Loads configured automation skill instruction bundles.
- `report`: Generates reports and evidence bundles.

The agent module consumes validated capability registry definitions and runner results. It must not import `capabilities` or decorator internals; declaration mechanics are completed before dynamic SDK tool exposure.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `FsqAgent`: Main orchestration class.
- `OpenAIAgentsRuntime`: Builds and runs an OpenAI Agents SDK `Agent` with a provider session supplied by `providers`, registry-generated capability tools, skills, turn limits, tracing policy, and a `StepRunner` execution binding.
- `Verifier`: Parses structured verifier-agent or runner final output and converts task status, evidence, and diagnostics into a `VerificationResult` for the task's single `verification_goal`.

Planned signatures:

- `FsqAgent.from_config(path: str | Path | None = None, workspace: str | Path | None = None) -> FsqAgent`
- `FsqAgent.from_settings(settings: Settings) -> FsqAgent`
- `FsqAgent.run(task: Task, event_sink: RunEventSink | None = None) -> TaskResult`
- `OpenAIAgentsRuntime.run_task(task: Task, knowledge: KnowledgeBundle, skills: list[SkillBundle], run_id: str, event_sink: RunEventSink | None = None) -> list[StepResult]`
- `Verifier.verify(task: Task, results: list[StepResult], events_path: Path | None = None) -> VerificationResult`

## Internal Structure

- `__init__.py`: Public exports only.
- `_core.py`: `FsqAgent` orchestration and lifecycle.
- `_events.py`: Run event emission, sequencing, persistence fan-out, and user-sink dispatch.
- `_openai_runtime.py`: OpenAI Agents SDK runtime assembly using provider sessions from `providers`, AgentTool provider construction or injection, platform-dispatching harness, platform CommonTool provider, and backend driver construction, platform-selected capability registry bootstrap, StepRunner construction with configured post-action delay settings, agent construction, `Runner.run_streamed` invocation, and SDK stream event mapping.
- `_harness_tools.py`: Transitional name for the registry-backed platform capability `FunctionTool` adapter. Target behavior converts active platform CommonTool/PlatformTool schemas into SDK tools, maps SDK JSON arguments into canonical `ExecutableStep` records, delegates execution to `core.StepRunner` configured with runner-owned post-action delay policy, and serializes normalized capability results to bounded model-visible JSON with safe structured status/provenance fields suitable for reports and post-run recording. AgentTool SDK adaptation lives in `tools` and does not receive replay metadata.
- `_pre_plan.py`: Internal prompt instructions and helpers for dynamic goal planning from page knowledge when directly invoked by `FsqAgent.run`.
- `_prompt.py`: Prompt model construction and template rendering for agent instructions and task input.
- `_structured_output.py`: Shared coercion helpers for SDK final output values and compatibility parsing of legacy/raw final JSON strings.
- `_verification_task.py`: Builds an evidence bundle from task context, execution records, event logs, and persisted tool artifacts for a separate evidence-based verification agent task.
- `_verifier.py`: Evidence-based goal verification and failure diagnostics.
- `SPEC.md`: Module design.

## Platform Runtime Blocks

Shared runtime rules:

- `OpenAIAgentsRuntime` builds the active harness through `core.HarnessFactory`, which composes the platform CommonTool provider and config-selected backend driver from `settings.harness.platform` and backend settings.
- SDK tools are generated from dynamic-only AgentTools plus the active platform CommonTool/PlatformTool `action_space()`.
- The runtime remains decoupled from platform decorator internals and backend SDK APIs.

Android runtime:

- Uses `HarnessFactory` to compose the private Android harness, `CommonPlatformTools`, and the config-selected Android driver.
- Startup metadata includes safe Android app id and serial presence.
- Expected platform skill is `android-harness.md` when configured.

Web runtime:

- Uses `HarnessFactory` to compose the private Web harness, `CommonPlatformTools`, and the config-selected Web driver.
- Startup metadata includes safe Web backend, channel, browser executable configured state, headless, and base URL presence.
- Harness construction must not launch a browser. Dynamic Web runs receive `start_browser` and `close_browser` as normal harness tools, and the runtime must not auto-call or auto-inject them.
- Expected platform skill is `web-harness.md` when configured.

macOS runtime:

- Uses `HarnessFactory` to compose the private macOS harness, `CommonPlatformTools`, and the config-selected macOS driver.
- Startup metadata includes only safe macOS fields: platform, backend, Appium server configured state, bundle id presence, app path presence, action timeout seconds, driver class, and configured skill names. It must not log local paths when they are considered sensitive by configuration policy or any secret environment values.
- Harness construction must not connect to Appium or launch a macOS application. Dynamic macOS runs receive `launch_app` and `kill_app` as normal harness tools, and the runtime must not auto-call or auto-inject them.
- Expected platform skill is `macos-harness.md` when configured.

Future platform runtime:

- New platforms must provide harness construction, default capability definitions, skill guidance, and startup metadata before dynamic tool exposure.

## Python Architecture

- Architecture level: 3 Layered Application.
- Public API: `FsqAgent`, `OpenAIAgentsRuntime`, and `Verifier` exported from `__init__.py`.
- Internal modules: all `_*.py` files are private implementation modules.
- Domain boundaries: this module owns dynamic run orchestration, SDK runtime assembly, pre-planning, event persistence, and verification task construction. Recordable capability execution routing lives in `core`; provider/session creation lives in `providers`; dynamic-only AgentTool behavior lives in `tools`; report writing lives in `report`.
- Boundary models: all tasks, final outputs, events, capability metadata, runner results, and report artifacts come from `models`.
- Dependency direction: may depend on `models`, `config`, `providers`, `core`, `tools`, `observation`, `knowledge`, `skills`, and `report`; leaf modules must not import `agent`.
- Rationale: dynamic execution coordinates external SDKs, providers, harnesses, tools, persisted events, and reports, so Level 3 is appropriate without adding repository/unit-of-work patterns.

## Error Handling

Configuration errors are raised before task execution when OpenAI Agents SDK is disabled, required provider credentials are absent, required skills fail to load, harness/platform tool construction fails, AgentTool construction fails, or platform action-space conversion fails. SDK, harness, AgentTool, CommonTool, or PlatformTool runtime exceptions are converted into failed `StepResult` values so report generation can still complete. Synchronous harness construction during main execution startup is bounded by `agent.step_timeout_seconds`; timeout or construction failure emits a run failure event and returns a failed runner `StepResult` instead of waiting silently. Recoverable tool failures should be surfaced through structured final JSON. Verification treats invalid final JSON as inconclusive instead of claiming task success.

Internal goal planning raises configuration errors when OpenAI Agents SDK configuration is unavailable and planning errors when the SDK does not return a valid `GoalPrePlan`. Planning used inside `FsqAgent.run` does not construct platform harnesses, call UI/external action tools, or generate separate reports. Read-only knowledge lookup tool failures are surfaced to the planner as warnings so it can continue when possible.

During `FsqAgent.run`, a dynamic task is internally planned before external UI actions begin. The orchestrator uses the task's explicit planning reference text and kind when present, falling back to legacy goal/description selection only for compatibility, converts returned `GoalKeyAction` values into `Task.key_actions` as execution guidance, copies the returned `GoalPrePlan.verification_goal` into `Task.verification_goal`, and emits planning events on the same run timeline. Generated key actions must not become additional blocking final-verifier requirements. If planning returns no usable key actions or no usable verification goal, the run fails before external UI actions are attempted.

## Design Decisions

- The orchestration module depends on all leaf modules, but leaf modules never depend on `agent`.
- OpenAI Agents SDK is the selected agent runtime and tool-use integration layer for this project.
- Azure OpenAI and GitHub Copilot provider construction is delegated to `providers`. `agent` asks for a configured provider session and uses that session to create the OpenAI Agents SDK provider object for `RunConfig`. Provider authentication, endpoint selection, token caching, Copilot plan detection, and direct Responses-style model invocation are not implemented in `agent`.
- Task execution requires the OpenAI Agents SDK package and provider authentication to be available through `providers`. There is no offline fallback execution path.
- The SDK runner owns tool dispatch and turn continuation. The project should not reimplement the Responses function-call loop.
- SDK tools are generated from validated AgentTool definitions plus active platform CommonTool/PlatformTool `action_space()` schemas. `OpenAIAgentsRuntime` converts dynamic helper tools and recordable platform capabilities into SDK `FunctionTool` objects using canonical names, schemas, and descriptions. Active capability SDK tools use strict JSON schema by default; per-capability schema strictness is not part of capability metadata. Unimplemented backend methods must not appear in `action_space()` because they must not be decorated as capabilities. It creates SDK agents with no external platform tool servers. `assert_with_ai` is a driver-backed PlatformTool exposed by the active backend when an evaluator is configured, not an AgentTool and not a concrete harness method.
- `OpenAIAgentsRuntime` must pass explicit OpenAI Agents SDK `ModelSettings` with `reasoning.effort="medium"` and `verbosity="medium"` to the main execution agent, pre-planner, and verification agent unless a future SPEC adds first-class model-setting configuration. This prevents SDK package upgrades from silently injecting model-family defaults such as disabled reasoning or low verbosity into dynamic UI automation runs.
- `OpenAIAgentsRuntime` constructs the active harness through `HarnessFactory` from `settings.harness.platform`. Driver selection is delegated to `DriverFactory`, which chooses the private concrete backend from config-owned platform backend settings. The runtime must not inspect Playwright APIs, Appium APIs, MCP reference code, or decorator internals when exposing tools; it uses `harness.action_space()` and `StepRunner` like every other platform.
- Web browser lifecycle is task-visible capability behavior. The runtime may construct a Web driver object for tool exposure, but it must not launch a browser until the agent executes `start_browser`, and it must not treat final resource cleanup as evidence that `close_browser` was executed.
- The runtime treats decorators as compile/bootstrap-time declaration mechanics only. It consumes `CapabilityDefinition` values, `CapabilityRegistry` snapshots, and `StepRunner` results, and it must not inspect decorator marker attributes or platform action catalog entries directly.
- Main execution startup is observable before the first SDK planning turn. `OpenAIAgentsRuntime.run_task` emits runtime progress events for startup, harness setup, tool setup, and SDK agent readiness before the existing main `Planning started` event. Harness setup events include only safe metadata such as platform, backend, app id presence, serial presence, Web channel, Web browser executable configured state, headless mode, base URL presence, macOS Appium server configured state, macOS bundle id/app path presence, timeout seconds, configured skill names, and driver class when available.
- Harness construction remains a synchronous platform concern internally, but dynamic main execution wraps it in an async-compatible timeout boundary. The runtime calls the configured harness factory or built-in harness construction through a worker-thread helper and applies `agent.step_timeout_seconds` as the startup timeout. A timed-out worker result is ignored after the runtime has returned a failed runner step; no UI action should be invoked from that timed-out path.
- The capability tool adapter must preserve capability provenance, including canonical capability name, executor kind, step kind, platform, backend, owner, replay policy, sensitivity, and authored-action metadata when present, in run events and tool result metadata. Primary authored strict command names come from `ReplayPolicy(kind="fsq_command").alias` rather than a duplicate capability alias list.
- When the SDK calls a CommonTool or PlatformTool capability, the platform capability adapter parses JSON arguments, builds an `ExecutableStep` with the canonical capability name, and delegates execution to `StepRunner.run_step(run_id, step)` instead of directly invoking platform providers, harnesses, or drivers. The adapter must not own the standard `capture_evidence=True` to screenshot/UI-tree/page-snapshot policy conversion or the post-action delay algorithm; it supplies canonical steps and lets `StepRunner` derive the effective evidence policy and effective post-action delay from capability metadata, explicit step policy, and configured `execution.post_action_delay_seconds` defaults. Dynamic before/after evidence capture and post-action stabilization are therefore shared with strict replay and are derived from `CapabilityDefinition` metadata rather than private action-name allowlists. Capabilities with `capture_evidence=True` receive the standard runner evidence behavior that captures before/after screenshots and active platform observations plus failure artifacts. Capabilities with the default `False`, including read-only, observation, and assertion capabilities such as `assert_visible`, `assert_not_visible`, `assert_state`, `assert_with_ai`, and `ui_tree`, keep the default evidence policy unless their metadata says otherwise.
- A capability failure should normally be returned as a successful SDK tool transport result whose JSON has `status="failed"`, `failure_category`, `error_message`, output preview, artifact refs, and safe capability metadata. Runner-level artifact capture failures must surface as failed capability tool JSON with `failure_category="artifact_error"`. Unexpected adapter failures are converted into structured failed tool JSON or failed `StepResult` records depending on when they occur. Tool output events should include safe structured payload fields for `capability_name`, `executor_kind`, `step_kind`, `platform`, `backend`, `owner`, `replay`, `sensitivity`, effective post-action delay metadata, status, failure category, safe replay params, dependency metadata, and artifact paths when known so CLI recording does not parse truncated previews.
- Capability tool output JSON must preserve existing report/recording compatibility fields where useful, including `tool_name`, `tool_origin`, `platform`, `driver_method`, `fsq_action_name`, `status`, `failure_category`, `error_message`, `duration_ms`, `result`, and `metadata`, while adding authoritative fields `capability_name`, `executor_kind`, `step_kind`, `replay`, `sensitivity`, effective post-action delay metadata, `safe_replay_params`, `runner_step_id`, `runner_result`, and flattened `artifact_refs`.
- Capability registry bootstrap or SDK tool conversion failures are startup configuration errors. The runtime must not silently expose a partial capability list.
- The agent may create an internal plan before external actions, use the pre-plan-derived `verification_goal` as the final success target, execute through AgentTools plus active CommonTool/PlatformTool capabilities, and adapt the plan when tool feedback changes the best path.
- Standalone goal pre-planning is not a public CLI or module API. Any retained pre-planning implementation is internal to normal LLM execution.
- Internal planning receives a structured reference envelope containing `reference_type`, `reference_text`, and a concise active CommonTool/PlatformTool capability summary generated from the active platform registry. It loads the concise page index from `agent_context.knowledge.pre_plan.dir` when configured or from `agent_context.knowledge.root_dir` as a fallback, and returns ordered key actions, one verification goal, relevant page ids, summary, and warnings. It is side-effect-free for the application under test: no UI automation, no lifecycle calls, no verification agent, and no separate report generation.
- For `reference_type="raw_case"`, the pre-planner treats the complete raw case text as advisory source material, not as parsed strict executable input. It should prefer case-level intent signals such as name, metadata, tags, properties, and human-authored goal text when summarizing `verification_goal`; raw YAML steps may support execution planning and fill gaps, but they are not assumed accurate or complete and must not be transformed into final verifier requirements. If step details conflict with case-level intent, the case-level intent wins and the mismatch should appear in warnings. Lifecycle commands such as `launchApp`, `killApp`, `startBrowser`, and `closeBrowser` may be represented as setup/teardown intent instead of ordinary business key actions unless they are semantically central to the case.
- Generated key actions become the execution spine only; final verification checks the pre-plan-derived `verification_goal` against execution evidence.
- Pre-planning is an iterative knowledge loop. The initial model input contains `index.md` only. The pre-plan agent can call read-only local knowledge tools to reload the index or load specific page files from `knowledge/pages/` by page id or relative path. Page-to-page transitions may cause additional page reads until the action chain is complete or no useful next page is available.
- If page knowledge is incomplete, the planner should still produce the best available contiguous key-action chain and a fact-supported verification goal. It may skip at most one consecutive missing action by recording a warning. If it cannot produce useful key actions or a reliable verification goal, it must return empty planning fields and warnings so the orchestrator can fail before external UI actions.
- When a caller supplies ordered key actions, the runtime must use the complete list as the execution spine: preserve their relative order, allow recovery/setup/dialog-handling steps between them, and collect live evidence for the resulting state before reporting success. The public CLI no longer supplies parsed FSQ command-derived key actions for normal LLM `--case-yaml` or `--case-dir` runs.
- Ordered key actions must preserve semantic fidelity. Recovery or fallback actions may restore UI state, but they do not satisfy the original ordered key action unless they perform the same accepted semantic action. Tool usage errors should be corrected for the same semantic action before switching to non-equivalent fallback routes.
- Run identifiers are generated by the orchestration layer as `<task-id>-YYYY-MM-DD_HH-MM-SS` using local time so directories under `output.runs_dir` are easy to read while remaining path-safe on Windows.
- Task runs emit live `RunEvent` values for planning summaries, AgentTool calls, CommonTool/PlatformTool capability calls, runtime-internal progress, tool outputs, failures, and completion. Events are for user-visible progress, reports, and post-run recording metadata, and must not expose hidden model chain-of-thought. Runtime interruptions such as debugger cancellation or keyboard interrupt emit a final `run_failed` event before being re-raised.
- The runtime consumes OpenAI Agents SDK streaming semantic events through `Runner.run_streamed(...).stream_events()` and maps them into `RunEvent` values while preserving the final output path used by verification and reporting.
- The runtime must not let the OpenAI Agents SDK trace exporter repeatedly warn when no OpenAI trace export key is configured. `openai_agents.tracing_enabled` expresses the user/config tracing request, but the SDK run config and SDK global tracing switch must disable SDK tracing when `OPENAI_API_KEY` is absent or blank because the SDK exporter uses that variable even when the model provider is GitHub Copilot or Azure OpenAI.
- The runtime configures the OpenAI Agents SDK `call_model_input_filter` with `ToolOutputTrimmer` plus a project filter that preserves the most recent configured number of function tool outputs by tool-call count. This keeps recent outputs at full fidelity while trimming older large tool outputs before each model call.
- The project filter persists SDK function-call outputs, including AgentTool and platform capability outputs when represented as function-call output items, into the current run's tool artifact directory before replacing historical oversized content with a bounded preview and artifact path.
- Visual assertion image handling is owned by the active backend `assert_with_ai` PlatformTool and provider-backed evaluator, using harness runtime services for screenshot/artifact capture. The main runner does not use a local `submit_visual_assertion` tool or screenshot-to-next-turn attachment filter. When the model needs an authored `assertWithAI`, it calls the active backend `assert_with_ai` PlatformTool; shared backend support captures a screenshot through harness services, calls the injected evaluator, and returns a verdict as tool output evidence.
- Runtime instructions tell the agent that AgentTool outputs may include artifact references and that `search_artifact`/`read_artifact_slice` should be used for targeted recovery rather than full artifact rereads. Artifact search is historical context and should not be treated as proof of current UI state without a fresh tool observation.
- Runtime instructions tell the agent to treat inferred FSQ preconditions as conditional setup obligations. It must inspect live UI/account state first, execute missing setup before ordered key actions, use `get_runtime_secret` only for configured secret names when credentials are required, and never echo secret values in progress events, evidence, or final output.
- Runtime instructions and task input are assembled by first building prompt models, then rendering Jinja template files configured by `openai_agents.prompt.agent_template_path` and `openai_agents.prompt.task_template_path` or the package defaults. Static behavioral prompt text and section wording belong in template files, while configuration injects only scalar variables and optional template paths. There is no custom-instruction prompt channel; project-specific guidance is loaded from knowledge, and reusable execution guidance is loaded from configured skills.
- Model-facing runtime instructions must not include knowledge-loader warnings or skill-loader warnings. Required skill load failures fail before LLM execution. Optional broken skills are skipped with operator-visible diagnostics and are not included in main execution instructions or pre-plan skill input.
- The default `agent_instructions.j2` should stay a compact dynamic execution contract: non-interactive single-task execution, configured tool boundaries, ordered key action semantics, goal-only final verification, source-case mutation boundaries, secret handling, artifact/evidence boundaries, structured-output semantics, and separate blocks for project knowledge and successfully loaded skills.
- Runtime Markdown content under `knowledge/` is part of prompt quality. `knowledge/project.md` should contain only tested-project-specific guidance. Configured skills should contain concise, current, composable execution guidance aligned with exposed AgentTools, CommonTools, and PlatformTools. Page-knowledge Markdown should stay pre-plan-oriented, concise, indexed, and free of stale historical narrative that does not help route planning.
- If the user description is too broad to derive domain-specific checks, the default success standard is that the executable task flow completes without unrecovered errors and with enough evidence to show completion.
- Skills are descriptive guidance. Command execution is not exposed through configured CLI tools or SDK `ShellTool` in this SPEC cycle; execution is performed through AgentTools and active CommonTool/PlatformTool capabilities only.
- Harness- and platform-specific action selection, argument rules, and recovery recipes belong in configured skill Markdown rather than hard-coded agent runtime branches. Android runs should load `android-harness.md`; Web runs should load `web-harness.md`; macOS runs should load `macos-harness.md` alongside common automation guidance. The agent consumes those skills as current runtime policy while remaining decoupled from concrete platform backends.
- The final SDK output must conform to `AgentFinalOutput`. `AgentFinalOutput` is passed to OpenAI Agents SDK through `Agent(output_type=AgentFinalOutput)`, which is the authoritative structured-output schema. The prompt may describe status and goal-verification semantics, but it must not duplicate the full JSON Schema text.
- Final output includes `schema_version` for traceability. Schema selection is not configurable; the runtime owns the current contract.
- The runtime converts `pre_plan` entries from typed final output into `StepResult` records, then appends one SDK runner summary step containing the serialized final output.
- Task input is rendered from an `AgentTaskInput` model so the model-facing task envelope has a stable shape while still allowing template customization.
- SDK stream events are mapped into `RunEvent` values that preserve real capability/tool names, call IDs, redacted arguments, output previews, errors, timing, capability executor kind or AgentTool origin when known (`agent_tool`, `common`, `platform`, `runtime`, or `unknown`), and safe replay/provenance metadata when available. Reports reconstruct real tool calls from these structured events rather than treating plan or runner summary records as tools. CLI post-run recording may consume the same persisted capability events, but `agent` does not decide recording eligibility or write generated case files. AgentTool events are persisted for reports/diagnostics and ignored by the recorder.
- Task execution is non-interactive. Any human-in-the-loop SDK feature must be disabled or backed by deterministic programmatic approval.
- Final result judgment is performed by a separate evidence-based verification agent task after the main automation run. The verification task has no AgentTools, no CommonTool/PlatformTool action tools, and no image inputs; it receives the authoritative pre-plan-derived `verification_goal`, the main agent's structured claims when available, execution records, normalized event/tool-call records, AI assertion verdict metadata, and persisted artifact excerpts. The verification agent must decide success, failure, or inconclusive from supplied execution evidence only.
- Final verification is goal-only. Success requires evidence supporting `Task.verification_goal`; failure requires evidence proving the goal unmet or impossible; inconclusive is used when evidence is insufficient or ambiguous. Key actions are execution guidance and diagnostics, not independent final verifier requirements.
- Visual assertions in the LLM execution loop are judged during the main execution loop when the agent explicitly calls a backend PlatformTool assertion such as `assert_with_ai` and receives the provider-backed verdict as tool output evidence. The verification task does not re-inspect screenshot pixels; it verifies that execution evidence contains the AI assertion result, that the main agent's structured output reports the corresponding result, and that no supplied evidence contradicts that result.
- Deterministic strict-core execution is not an agent capability. Strict entry-layer code may inject a provider-backed evaluator for explicitly authored `assertWithAI`, but `agent` does not own strict execution or construct strict harnesses.
- Dynamic run recording is not an agent capability. `agent` must persist safe event metadata needed by `cli` recording, but must not write `recorded.codex.yaml`, mutate source cases, resolve strict replay refs, or decide whether a run should be recorded.
- The local `Verifier` does not hard-code FSQ key-action formats or Appium command semantics as the final arbiter. It treats a parseable verification-agent status as authoritative, preserving the agent's success, failed, or inconclusive conclusion without local status downgrades. If the verification task is unavailable, it uses parseable runner output as the fallback conclusion; if no agent conclusion is parseable, it falls back to failed-step or inconclusive diagnostics.
