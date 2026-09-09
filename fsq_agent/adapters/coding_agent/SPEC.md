# Module: adapters.coding_agent

## Purpose

Implement public SDK-neutral Agent runtime protocols through OpenAI Agents SDK. This adapter owns SDK agent/session construction, provider-to-SDK adaptation, SDK FunctionTool/schema conversion, streamed event conversion, structured output extraction, context trimming, and SDK failure normalization. It does not own dynamic planning policy, verification policy, Application use cases, execution recording, or platform automation.

## Dependencies

- `agent`: public runtime protocols and the public `CodingAgentPolicy` SDK-neutral facade.
- `models`: settings and runtime boundary values.
- `config`: the public `Settings` runtime boundary and runtime-settings validation; provider/configuration persistence remains Config-owned.
- `providers`: provider sessions and SDK provider construction inputs.
- `tools`: AgentTool definitions and execution adapters.
- `core`: capability registry, StepRunner, and public harness/factory contracts.
- External OpenAI Agents SDK and OpenAI client packages, imported lazily.

The adapter must not be imported by Application, Agent, Execution, Core, Case DSL, Drivers, Harnesses, Environments, Config, Models, or other inward packages.

## Public Interface

`create_coding_agent_runtime(settings, *, harness_factory=None)` is the stable composition factory and returns `CodingAgentRuntime`. `OpenAIAgentsRuntime` remains exported only for compatibility and references the canonical concrete runtime class. Concrete SDK tool adapters are private.

The runtime implements required public `run_task`, `run_pre_plan`, and `run_verification` operations. It receives or constructs `CodingAgentPolicy` through the public Agent API and does not import Agent-private modules.

Runtime composition accepts the Execution-allocated safe context and explicit Core evidence-journal and execution-identity collaborators. `create_coding_agent_runtime` retains its existing settings and optional harness-factory inputs; injected runtime collaborators supply durable capability evidence without an import of Execution. The adapter does not allocate Runs, update owner records, freeze execution conclusions, generate final reports, or transition `run.json`.

## Internal Structure

- `__init__.py`: public factory and compatibility export.
- `_openai_runtime.py`: SDK runtime, provider/session wiring, main/pre-plan/verification calls, and stream/result conversion.
- `_harness_tools.py`: capability-to-SDK FunctionTool conversion and StepRunner-backed invocation.

## Python Architecture

- Architecture level: Level 3 Layered Application adapter.
- Public API: runtime factory plus temporary concrete-runtime compatibility export.
- Internal modules: all `_*.py` implementation files.
- Domain boundaries: external Coding Agent SDK adaptation only.
- Boundary models: cross-module values come from `models` or public Agent protocols.
- Dependency direction: composition roots depend on this adapter; inward packages never do.
- Cross-module boundary: adapter implementation imports Agent-owned behavior only from `fsq_agent.agent`; imports from `fsq_agent.agent._*` are forbidden.
- Rationale: SDK runtime assembly coordinates provider sessions, tools, streaming, structured output, and external failures without a DI container.

## Error Handling

Missing SDK packages remain runtime configuration errors rather than import-time failures. SDK, provider, tool conversion, streaming, content filtering, timeout, and structured-output failures preserve current safe normalized results and events.

## Current Invariants

- Main execution, pre-plan, and verification preserve current SDK behavior, model settings, tracing, context trimming, event metadata, and structured output contracts.
- After the streamed main execution reaches a terminal outcome, the adapter reads the OpenAI Agents SDK Run context's aggregated Provider usage and emits exactly one SDK-neutral `dynamic_agent_token_usage` event. Its safe payload contains the configured provider and model plus SDK-reported request, input, output, total, cached-input, and reasoning token counts. It does not estimate missing usage, inspect prompts or responses, include pre-plan or verification usage, write Run files directly, or mutate `run.json`.
- Capability calls continue through Core `StepRunner`; AgentTool calls continue through Tools-owned behavior. Every real capability invocation receives stable source identity and a unique execution identity before external action, including repeated SDK calls and recovery attempts. Compatibility `runner_step_id` and result `step_id` alias `step_execution_id` for new records.
- Core journal acknowledgements persist capability start, action outcome, and artifact outcomes independently of SDK stream completion, final tool JSON, and output trimming. SDK `RunEvent` records correlate to this identity and are progress projections, not a second durable capability ledger. AgentTool SDK events retain their existing independent event ownership and are excluded from strict capability and replay counts.
- `runner_result` and structured capability metadata preserve measured phase timing, action outcome, primary failure, secondary evidence errors, artifact availability, and identity fields before any display truncation. A shortened model-facing output or dropped SDK stream item cannot erase Core evidence; unavailable fields use null with a reason rather than an invented zero.
- Pre-plan entries and SDK runner summary records remain runtime compatibility records and never inflate executed capability counts or imply additional actions. Main-execution token usage remains scoped to the existing SDK aggregate; unavailable per-step usage is not estimated.
- Harness construction remains lazy and browser/application lifecycle remains explicit capability behavior.
- CLI and Control Plane inject the same runtime factory at composition boundaries.
- SDK adaptation does not decide Run lifecycle, recording eligibility, report schema, or provenance policy.
