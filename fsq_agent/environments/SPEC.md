# Module: environments

## Purpose

Own host/runtime discovery, support classification, read-only readiness checks, and target discovery. Platform automation, package installation, and Workspace persistence are outside this module.

## Dependencies

- `models`: runtime status facts and pure Web channel identity contracts.
- Python standard-library host, filesystem, import, and subprocess facilities.

The module must not import Application, adapters, Config persistence, concrete drivers or harnesses, LLM providers, or Execution.

## Public Interface

`PlatformRuntimeService` is the stable service for read-only Runtime `check`, exact-channel Web executable discovery, explicit executable validation, and platform Target configuration/availability diagnosis from resolved settings. Target diagnosis returns safe normalized status facts without env values, unrestricted local target details, raw subprocess output, or backend objects. `PlatformRuntimeCheck` remains owned by Models. Core's legacy export references the canonical service class.

## Internal Structure

- `__init__.py`: public exports only.
- `_service.py`: platform-neutral dispatch and normalized result coordination.
- `providers/`: private Android, Web, Windows, and macOS runtime mechanics.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: `PlatformRuntimeService`.
- Internal modules: service implementation and platform providers.
- Domain boundaries: host support/readiness and target discovery only.
- Boundary models: normalized status facts come from `models`.
- Dependency direction: Application depends on Environments; Environments depends on Models, never Application or adapters.
- Rationale: the service coordinates host-specific discovery and normalized readiness failures.

## Error Handling

Readiness checks never install or modify software. Missing Python platform dependencies identify an incomplete `fsq-agent` installation and provide safe reinstall/repair guidance. Missing external host services or system prerequisites provide safe provisioning guidance without executing it.

Target configuration diagnosis validates required identities and local path/channel shape. Target availability uses read-only discovery for current candidates, including Android online/authorized device and application discovery, without installing applications, changing device state, starting a browser/application, or creating a Driver/Appium session.

## Current Invariants

- Current host support behavior remains unchanged.
- Windows discovery covers Chromium and Chrome/Edge stable, beta, dev, and canary through exact paths.
- Explicit Web validation delegates to the pure Models identity contract and never trusts a shared basename or generic substring.
- Candidates are normalized, deduplicated, ordered, and never selected when multiple distinct matches exist.
- The module does not provision targets, start services, authenticate, mutate Workspaces, or expose subprocess output.
- Environment diagnosis does not inspect Provider readiness; Workspace Doctor composes Environment facts with other public readiness boundaries.
