# FSQ Roadmap

FSQ is building an evidence-first agent harness for replayable, verifiable AI UI automation. Its current product principles and supported behavior are documented in this repository; proposed work remains directional until it is tracked and implemented.

This roadmap communicates direction rather than a release commitment. Scope and timing may change as implementation evidence, maintainer capacity, and community feedback evolve. GitHub Issues and milestones track committed work.

## Product Principles

- Evidence is a first-class output of every automation run.
- AI exploration should produce deterministic, replayable automation assets.
- Verification must be auditable rather than based only on agent self-reporting.
- Web, Android, Windows, and macOS should share a consistent harness and evidence model.
- Harnesses, capabilities, and providers should become practical extension points for the community.

## 2026 Q3: Open Source Foundation

Make the repository trustworthy and practical for external contributors.

- Establish CI for linting, tests, package builds, and Playground builds.
- Complete contributor-facing Issue and pull request workflows.
- Improve installation, quick-start, architecture, and troubleshooting documentation.
- Define the changelog, semantic versioning, and automated release process.
- Make test coverage and compatibility status visible.

## 2026 Q3-Q4: Public Harness SDK

Turn the internal harness architecture into a stable community extension surface.

- Define public contracts for harness plugins, drivers, platforms, capabilities, and artifacts.
- Support third-party registration through Python entry points.
- Move first-party platforms toward the same registration path used by external plugins.
- Publish a harness authoring guide and reference implementation.
- Begin community collaboration on iOS, Linux desktop, and Electron support.

## 2026 Q4: Provider Expansion

Reduce adoption friction by supporting more model providers.

- Add direct OpenAI and Anthropic provider support.
- Add local-model support through Ollama or compatible endpoints.
- Add OpenRouter as a unified provider option.
- Keep provider-specific SDK details behind a stable FSQ provider contract.

## 2027 Q1: Developer Experience

Target a five-minute path from installation to a first successful automation run.

- Publish preconfigured Web and Android container images.
- Add Codespaces or equivalent cloud development setup.
- Add environment diagnostics and harness scaffolding commands.
- Improve interactive recording and Playground workflows.

## 2027 Q1-Q2: Ecosystem

Make FSQ useful as both a tool and a platform.

- Publish an official GitHub Action and CI integration guidance.
- Build a curated registry of reusable FSQ cases and skills.
- Add a compatibility matrix generated from tests and run evidence.
- Expand Playground into a case authoring and contribution workflow.
- Provide an embeddable Python SDK and progress toward a stable 1.0 release.
- Explore a VS Code extension for YAML authoring, evidence inspection, and run management.

## 2027 H2: Technical Frontiers

Advance the reliability and reach of agent-driven automation.

- Multi-agent execution for complex workflows.
- Visual grounding when accessibility data is incomplete.
- Evidence-backed self-healing locator recommendations.
- Remote device farm and cloud harness integrations.
- A public benchmark for UI agent success, replay reliability, and evidence completeness.
- Workflow-level orchestration beyond individual automation tasks.

## How Priorities Are Chosen

Maintainers prioritize work using user impact, alignment with the product principles, implementation evidence, compatibility risk, and available ownership. Near-term reliability and contributor experience take precedence over speculative expansion.

To propose a roadmap change, open a Feature or New Platform/Driver Issue. Significant behavior, public API, or architecture changes follow the repository's spec-driven development process before implementation.

## Maintenance

Maintainers review this document at least monthly and after material strategy changes. Roadmap edits should link relevant Issues or design documents when available. If this document and current public project documentation diverge, maintainers must reconcile them before presenting roadmap work as committed.
