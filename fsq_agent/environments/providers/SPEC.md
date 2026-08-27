# Module: environments.providers

## Purpose

Own private Android, Web, Windows, and macOS host/runtime providers used by `PlatformRuntimeService`. These are not LLM providers and do not perform platform automation.

## Dependencies

Providers use standard-library host, import, and filesystem facilities plus public Models contracts. They must not invoke package managers or import adapters, Application, Config persistence, concrete drivers or harnesses, Execution, or top-level LLM `providers`.

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

Providers perform read-only checks and return safe normalized outcomes. They never install or modify Python packages, system dependencies, services, targets, applications, devices, emulators, or virtual machines.
