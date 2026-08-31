# Module: harnesses

## Purpose

Own concrete runtime gateways that combine inherited CommonTools, one injected platform driver, artifact/evaluator/runtime context, and normalized capability invocation for Core Runner. Harnesses do not own backend automation implementations or transport orchestration.

## Dependencies

- `core.interfaces`: Harness, Driver, observation, evaluator, secret, and factory contracts.
- `core.evidence`: run-local artifact storage.
- `models`: canonical steps, contexts, schemas, artifacts, and results.
- `drivers`: only internal capability metadata composition and driver instances supplied through public interfaces; Harnesses must not import concrete backend modules.

## Public Interface

Concrete Android, Web, Windows, and macOS harness classes remain private. `core.interfaces.HarnessFactory` is the stable public construction boundary and returns `HarnessInterface`.

## Internal Structure

- Private platform harness modules for Android, Web, Windows, and macOS.
- Private CommonTool routing and capability-schema adaptation shared by platform harnesses.
- Private composition implementation behind the public Core factory boundary.

## Python Architecture

- Architecture level: Level 3 Layered Application.
- Public API: `HarnessInterface` and `HarnessFactory` remain owned by `core.interfaces`.
- Internal modules: all concrete platform harnesses and selection/composition helpers.
- Domain boundaries: runtime gateway/context/evidence coordination only.
- Boundary models: shared execution values come from `models`.
- Dependency direction: Harnesses depend on Core Interfaces and receive Drivers through interfaces; Drivers never import Harnesses.
- Rationale: harnesses coordinate several runtime collaborators and side effects, requiring Level 3 without a new domain framework.

## Error Handling

Harnesses classify backend failures through normalized contracts, preserve cancellation, and keep secret values out of contexts, events, and artifacts. Missing observations are explicit safe failures.

## Current Invariants

- CommonTools route to the inherited platform provider; PlatformTools delegate to the injected driver.
- Harnesses do not duplicate driver action bodies.
- Concrete harness selection is lazy and hidden behind `core.interfaces.HarnessFactory`.
- Old `core.harness` imports forward to canonical Drivers, Harnesses, or Core Interfaces without duplicate state.
