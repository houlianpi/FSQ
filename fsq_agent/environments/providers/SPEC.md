# Module: environments.providers

## Purpose

Own private Android, Web, Windows, and macOS host/runtime providers used by `PlatformRuntimeService`. These are not LLM providers and do not perform platform automation.

## Dependencies

Providers use standard-library host, import, filesystem, and subprocess facilities plus public Models contracts. They must not import adapters, Application, Config persistence, concrete drivers or harnesses, Execution, or top-level LLM `providers`.

## Public Interface

No public package API. Providers are selected internally by `environments`.

## Internal Structure

- Private Android, Web, Windows, and macOS provider modules.

## Python Architecture

- Architecture level: Level 2 Simple Package.
- Public API: none outside `environments`.
- Internal modules: all platform provider modules.
- Domain boundaries: host/runtime mechanics only.
- Boundary models: shared values come from Models.
- Dependency direction: consumed only by the parent Environments service.
- Rationale: each provider is focused infrastructure.

## Error Handling

Providers bound commands, time, and captured output and return safe normalized outcomes. Unsupported providers do not install.
