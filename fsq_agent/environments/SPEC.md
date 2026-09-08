# Module: environments

## Purpose

Own host/runtime discovery, support classification, read-only readiness checks, and target discovery. Platform automation, package installation, and Workspace persistence are outside this module.

## Dependencies

- `models`: runtime status facts and pure Web channel identity contracts.
- Python standard-library host, filesystem, import, and subprocess facilities.

The module must not import Application, adapters, Config persistence, concrete drivers or harnesses, LLM providers, or Execution.

## Public Interface

`PlatformRuntimeService` is the stable service for read-only Runtime `check`, exact-channel Web executable discovery, explicit executable validation, platform Target configuration/availability diagnosis from resolved settings, and ordered platform prerequisite diagnosis. Target and prerequisite diagnosis return safe normalized status facts without env values, unrestricted local target details, raw subprocess output, or backend objects. `PlatformRuntimeCheck` and `PlatformPrerequisiteCheck` remain owned by Models. Core's legacy export references the canonical service class.

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

macOS prerequisite diagnosis performs bounded read-only host inspection and returns details in this order: `xcode_installation`, `xcode_developer_directory`, `appium_cli`, `appium_mac2_driver`, `appium_endpoint`, `application_path`, and `bundle_identifier`. It distinguishes a full Xcode application from Command Line Tools, verifies that the active developer directory belongs to full Xcode, resolves the Appium executable without changing `PATH`, queries installed Appium drivers with fixed non-interactive arguments and a bounded timeout, probes only the configured endpoint's status availability, validates the configured application bundle or executable path, and checks that a configured bundle identifier resolves consistently with the configured application when both are present. A prerequisite blocked by an earlier prerequisite is `not_applicable` with safe guidance rather than a fabricated ready result.

A valid active full-Xcode developer directory proves installation even outside standard application folders. Each host probe isolates unexpected errors into its own safe `error` fact and preserves other independent results. Invalid or non-dictionary application plists fail bundle identity verification without falling back to another installed application. For an executable within an application bundle, that enclosing bundle supplies its identity; path-only targets do not require a separate bundle identifier.

macOS prerequisite facts include explicit copyable repair commands only where a safe, applicable command can be supplied. Custom Xcode installations and non-default Appium endpoints receive guidance that respects their configured values; a default-path command must not be presented as the exact fix for a different configuration. Commands never contain credentials or private target values and are never executed by diagnosis. Android, Web, and Windows prerequisite checks are not extended by the Control Plane integration.

## Current Invariants

- Current host support behavior remains unchanged.
- Windows discovery covers Chromium and Chrome/Edge stable, beta, dev, and canary through exact paths.
- Explicit Web validation delegates to the pure Models identity contract and never trusts a shared basename or generic substring.
- Candidates are normalized, deduplicated, ordered, and never selected when multiple distinct matches exist.
- The module does not provision targets, start services, authenticate, mutate Workspaces, or expose subprocess output.
- macOS checks never install Xcode, accept its license, run first-launch setup, change `xcode-select`, install npm packages or Appium drivers, grant Accessibility/Automation permissions, start Appium, launch the target application, or create an Appium session.
- Environment diagnosis does not inspect Provider readiness; Workspace Doctor composes Environment facts with other public readiness boundaries.
