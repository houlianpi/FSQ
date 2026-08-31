# Module: drivers.macos

## Purpose

Implement macOS desktop automation through optional Appium Mac2, including explicit session/application lifecycle, actions, compact semantic observations, assertions, and safe failure normalization.

## Dependencies

- `core.interfaces.MacOSDriverInterface`, `capabilities`, and macOS parameter/result models.
- Optional Appium/Selenium, imported lazily at runtime.

## Public Interface

Instances satisfy `MacOSDriverInterface`; the concrete backend class is private outside Drivers and composition.

## Internal Structure

- Private Appium Mac2 backend implementation and macOS capability declarations.

## Python Architecture

- Architecture level: Level 2 Simple Package.
- Dependency direction: depends on Core Interfaces; never imports Harnesses or adapters.
- Rationale: one focused backend implementation is sufficient.

## Current Invariants

- Construction and registry discovery do not import Appium/Selenium, connect to Appium, or launch an application.
- Session creation remains explicit through application lifecycle capabilities.
