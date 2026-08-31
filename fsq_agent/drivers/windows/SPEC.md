# Module: drivers.windows

## Purpose

Implement Windows desktop automation through optional pywinauto, including application/window lifecycle, actions, observations, assertions, and safe failure normalization.

## Dependencies

- `core.interfaces.WindowsDriverInterface`, `capabilities`, and Windows parameter/result models.
- Optional pywinauto, imported lazily at runtime.

## Public Interface

Instances satisfy `WindowsDriverInterface`; the concrete backend class is private outside Drivers and composition.

## Internal Structure

- Private pywinauto backend implementation and Windows capability declarations.

## Python Architecture

- Architecture level: Level 2 Simple Package.
- Dependency direction: depends on Core Interfaces; never imports Harnesses or adapters.
- Rationale: one focused backend implementation is sufficient.

## Current Invariants

- Construction and registry discovery do not import pywinauto or launch an application.
- Backend kind remains pywinauto configuration, not a second FSQ backend.
