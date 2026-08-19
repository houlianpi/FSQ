# Module: adapters.coding_agent

## Purpose

Implement public SDK-neutral Agent runtime protocols through OpenAI Agents SDK. This adapter owns SDK agent/session construction, provider-to-SDK adaptation, SDK FunctionTool/schema conversion, streamed event conversion, structured output extraction, context trimming, and SDK failure normalization. It does not own dynamic planning policy, verification policy, Application use cases, execution recording, or platform automation.

## Dependencies

- `agent`: public runtime protocols and the public `CodingAgentPolicy` SDK-neutral facade.
- `models`: settings and runtime boundary values.
- `providers`: provider sessions and SDK provider construction inputs.
- `tools`: AgentTool definitions and execution adapters.
- `core`: capability registry, StepRunner, and public harness/factory contracts.
- External OpenAI Agents SDK and OpenAI client packages, imported lazily.

The adapter must not be imported by Application, Agent, Execution, Core, Case DSL, Drivers, Harnesses, Environments, Config, Models, or other inward packages.

## Public Interface

`create_coding_agent_runtime(settings, *, harness_factory=None)` is the stable composition factory and returns `CodingAgentRuntime`. `OpenAIAgentsRuntime` remains exported only for compatibility and references the canonical concrete runtime class. Concrete SDK tool adapters are private.

The runtime implements required public `run_task`, `run_pre_plan`, and `run_verification` operations. It receives or constructs `CodingAgentPolicy` through the public Agent API and does not import Agent-private modules.

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
- Dependency direction: composition roots and compatibility forwarders may depend on this adapter. Inward packages never do during normal orchestration; the only temporary exception is the lazy default-factory import in legacy `FsqAgent.from_config()`, scheduled for Batch 8 retirement.
- Cross-module boundary: adapter implementation imports Agent-owned behavior only from `fsq_agent.agent`; imports from `fsq_agent.agent._*` are forbidden.
- Rationale: SDK runtime assembly coordinates provider sessions, tools, streaming, structured output, and external failures without a DI container.

## Error Handling

Missing SDK packages remain runtime configuration errors rather than import-time failures. SDK, provider, tool conversion, streaming, content filtering, timeout, and structured-output failures preserve current safe normalized results and events.

## Current Invariants

- Main execution, pre-plan, and verification preserve current SDK behavior, model settings, tracing, context trimming, event metadata, and structured output contracts.
- Capability calls continue through Core `StepRunner`; AgentTool calls continue through Tools-owned behavior.
- Harness construction remains lazy and browser/application lifecycle remains explicit capability behavior.
- CLI, Control Plane, and Playground inject the same runtime factory at composition boundaries.
- Relocation does not change CLI, HTTP/SSE, reports, evidence, provider configuration, workspace behavior, or `fsq runs`.
