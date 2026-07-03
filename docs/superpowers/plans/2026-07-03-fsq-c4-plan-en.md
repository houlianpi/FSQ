# FSQ2.0 C4 Plan

## 1. Goal

This plan defines the C4 delivery scope for FSQ2.0. C4 is planned as six Scrum iterations, with each Scrum lasting two weeks. The first four Scrum iterations focus on platform adaptation, S5 focuses on code cleanup and refactoring, and S6 is reserved as a buffer for carry-over work, stabilization, and closeout.

This plan is intended for two audiences:

- Business and management stakeholders who are not familiar with FSQ and need a concise explanation of what FSQ is and why FSQ2.0 matters.
- FSQ engineering and testing contributors who need clear Scrum deliverables, acceptance criteria, and risk boundaries.

## 2. FSQ Overview

FSQ is an AI test automation system centered on the FSQ YAML test DSL and a shared execution architecture. It supports two complementary workflows:

- Regression execution flow: reviewed FSQ YAML can run as stable regression tests without requiring an Agent to reinterpret the test intent every time.
- Exploration and generation flow: natural-language goals can be planned, executed, repaired, and refined by models, then converted into reusable FSQ YAML test cases.

The key FSQ2.0 design is to make these two flows share the same execution core, platform Harness layer, evidence model, verifier, report system, debug artifacts, and knowledge system. This prevents AI-generated tests and manually maintained regression tests from becoming two disconnected systems. Instead, they converge on a unified action protocol, execution evidence model, and quality judgment standard.

The architecture diagram below comes from `docs/fsq-agent-architecture-v2.md`:

![FSQ-Agent Architecture](../../assets/fsq-agent-architecture-v2.png)

## 3. Why FSQ2.0

FSQ2.0 is an iteration designed to address FSQ1.0 limitations in reproducibility, platform expansion, evidence quality, debugging efficiency, and long-term maintainability.

The main FSQ2.0 characteristics are:

- Dual-loop architecture: deterministic YAML regression execution and AI-assisted exploration/test generation are both first-class capabilities.
- Shared execution core: YAML replay, dynamic planning, step execution, retry policy, event recording, evidence capture, verification, and reporting use the same execution path wherever possible.
- Platform-oriented Harness layer: Android, Windows, iOS, and macOS adaptation is organized through platform Harness contracts, avoiding scattered platform-specific logic across the execution flow.
- Evidence-driven verification: screenshots, UI Tree, UI Snapshot, tool logs, assertion records, and verifier judgments are stored as debugging and quality judgment artifacts.
- Debuggable failure model: failures can be traced through step timelines, screenshots, UI hierarchy, tool-call logs, assertion evidence, and verifier decisions.
- Knowledge system: successful cases, page/screen transitions, stable locator candidates, failure patterns, and repair recipes can be reused by both regression execution and exploration generation.
- Model/Provider abstraction: the Planner and Verifier are not tied to a single model provider, leaving room for future model upgrades or provider changes.

## 4. C4 Overall Goal

By the end of C4, FSQ2.0 should complete adaptation validation for Android, Windows, iOS, and macOS. The converted test cases and stable execution metrics should demonstrate that the FSQ2.0 architecture can support real regression testing scenarios.

Platform-level acceptance criteria:

- Convert at least 100 test cases per platform.
- Achieve a stable execution success rate above 95% per platform.

For this plan, stable execution success rate means the converted test cases can run repeatedly in the agreed lab or CI environment and reach at least 95% success after excluding clearly documented non-FSQ causes such as environment outages, unavailable devices, expired accounts or credentials, and target application service issues.

## 5. C4 Scrum Plan

| Scrum | Duration | Theme | Core Goal | Acceptance Criteria |
|---|---:|---|---|---|
| S1 | 2 weeks | Android platform adaptation | Complete Android adaptation for the C4 target test case set. | Convert at least 100 Android test cases; stable execution success rate >= 95%; failed cases have evidence and classification. |
| S2 | 2 weeks | Windows platform adaptation | Complete Windows desktop platform adaptation. | Convert at least 100 Windows test cases; stable execution success rate >= 95%; Windows environment assumptions and setup requirements are documented. |
| S3 | 2 weeks | iOS platform adaptation | Complete iOS platform adaptation, or complete the minimum viable iOS Harness path required for test case conversion. | Convert at least 100 iOS test cases; stable execution success rate >= 95%; if new public platform contracts are required, SPEC confirmation must happen first. |
| S4 | 2 weeks | macOS platform adaptation | Complete macOS desktop platform adaptation. | Convert at least 100 macOS test cases; stable execution success rate >= 95%; macOS Appium/Mac2 environment assumptions are documented. |
| S5 | 2 weeks | Code cleanup and refactoring | Consolidate duplicated logic and temporary implementations introduced during the first four platform adaptations. | Cross-platform action patterns and capability metadata are more consistent; duplicated adaptation logic is reduced; completed platform regressions do not degrade. |
| S6 | 2 weeks | Buffer and stabilization | Absorb carry-over work, fix high-priority stability issues, and complete C4 closeout. | Blocking issues are closed or explicitly documented; final C4 metrics are collected; C4 readiness summary is delivered. |

## 6. Scrum Deliverables

### S1: Android Platform Adaptation

S1 proves that the FSQ2.0 regression execution flow and shared execution core can support Android test execution at scale.

Main deliverables:

- At least 100 converted Android test cases.
- Execution evidence for converted cases, including screenshots, UI Tree artifacts, tool logs, and assertion records.
- Failure classification for unstable cases, separating test case issues, Harness issues, target application issues, and environment issues.
- Repair records for high-value unstable cases.

Acceptance targets:

- Android converted test cases >= 100.
- Stable execution success rate >= 95%.
- Remaining failures have evidence and responsibility classification.

### S2: Windows Platform Adaptation

S2 validates whether the FSQ2.0 platform capability registry, desktop Harness, and UI Snapshot evidence model can support Windows desktop automation.

Main deliverables:

- At least 100 converted Windows test cases.
- Windows runtime environment documentation, including application path, backend type, launch arguments, window title matching, and related dependencies.
- Evidence artifacts based on Windows UI Snapshot conventions.
- Coverage validation for desktop actions across the converted cases.

Acceptance targets:

- Windows converted test cases >= 100.
- Stable execution success rate >= 95%.
- Environment assumptions and setup requirements are clear and reproducible.

### S3: iOS Platform Adaptation

S3 completes iOS platform adaptation. Because iOS is currently treated as a future platform direction in the root project specification, S3 must first confirm the iOS platform block, capability surface, Harness contract, driver backend, and evidence naming through the repository SDD flow if new public platform contracts are required.

Main deliverables:

- If new public platform capabilities are required, complete iOS-related design and SPEC confirmation first.
- At least 100 converted iOS test cases.
- An iOS Harness path capable of deterministic replay for the converted cases.
- Evidence capture and failure classification aligned with the FSQ2.0 shared execution model.

Acceptance targets:

- iOS converted test cases >= 100.
- Stable execution success rate >= 95%.
- New platform decisions are recorded in SPEC files before they are used as implementation authority.

### S4: macOS Platform Adaptation

S4 validates the macOS desktop automation path, with emphasis on the Appium/Mac2 runtime flow, desktop action capabilities, and UI Snapshot evidence model.

Main deliverables:

- At least 100 converted macOS test cases.
- macOS runtime environment documentation, including Appium server URL, bundle id, app path, and related dependencies.
- Evidence artifacts based on macOS UI Snapshot conventions.
- Validation of key action flows such as launch, interaction, assertion, screenshot, and uiSnapshot.

Acceptance targets:

- macOS converted test cases >= 100.
- Stable execution success rate >= 95%.
- Environment assumptions and setup requirements are clear and reproducible.

### S5: Code Cleanup and Refactoring

S5 consolidates duplicated logic, temporary implementations, and cross-platform inconsistencies discovered during the first four platform adaptation Scrum iterations. The goal is not to introduce a new architecture, but to improve maintainability without breaking completed platform capabilities.

Main deliverables:

- Reduce avoidable duplication in platform adapters, Harness initialization, evidence capture, and report flows.
- Standardize shared naming, capability metadata, error classification, and action patterns where appropriate.
- Keep platform-specific behavior in platform parameter models, action catalogs, Harnesses, drivers, config blocks, and skill Markdown.
- If implementation exposes SPEC gaps, update the relevant specifications through the SDD flow.

Acceptance targets:

- Completed platform test cases still meet the success-rate targets.
- Relevant `SPEC.md` files remain aligned with code behavior.
- Refactoring does not introduce platform regressions.

### S6: Buffer and Stabilization

S6 absorbs carry-over work from S1-S5, resolves high-priority stability issues, and prepares the C4 closeout package. This Scrum should prioritize evidence-backed stabilization and blocking issues instead of expanding new feature scope.

Main deliverables:

- Fix or document remaining blocking issues from S1-S5.
- Re-run each platform test case set and collect final conversion and success-rate metrics.
- Close high-impact flaky cases or complete clear issue attribution.
- Produce a C4 readiness summary covering platform status, known risks, and next-cycle recommendations.

Acceptance targets:

- Final C4 metrics are available for all four platforms.
- Remaining risks have owners, impact descriptions, and recommended next steps.
- C4 closeout report is ready for review.

## 7. Cross-Scrum Execution Rules

- Public behavior, platform contracts, or architecture changes must follow the repository SDD flow.
- Root `SPEC.md` is the project-level source of truth; module-level `SPEC.md` files own module contracts.
- Test case conversion should happen in batches and be run continuously, instead of waiting until the end of a Scrum.
- Every failed or flaky case should have evidence before triage.
- Do not rely only on aggregate success rate; separately track test case defects, Harness defects, application defects, and environment defects.
- Prefer capability metadata and evidence policy to drive behavior, and avoid hard-coded platform action-name branches in the execution flow.

## 8. Metrics Tracking

Each platform should continuously track:

- Number of converted test cases.
- Number of executable test cases.
- Stable execution success rate.
- Number of flaky cases.
- Top failure categories.
- Average time to classify a failure.
- Number of repaired or stabilized test cases.
- Number of open platform/Harness defects.

Recommended Scrum reporting table:

| Platform | Converted | Executable | Stable Success Rate | Flaky | Blocking Defects | Notes |
|---|---:|---:|---:|---:|---:|---|
| Android | 100+ | Measure in S1 | >= 95% target | Measure in S1 | Measure in S1 | S1 owner |
| Windows | 100+ | Measure in S2 | >= 95% target | Measure in S2 | Measure in S2 | S2 owner |
| iOS | 100+ | Measure in S3 | >= 95% target | Measure in S3 | Measure in S3 | S3 owner |
| macOS | 100+ | Measure in S4 | >= 95% target | Measure in S4 | Measure in S4 | S4 owner |

## 9. Key Risks

- iOS may require platform SPEC and Harness contract work before the implementation boundary is clear.
- Platform environment instability can distort success-rate metrics unless exclusion rules and evidence records are explicit.
- Test case conversion may produce cases that can run once but are not stable enough for regression usage.
- S5 refactoring can introduce platform regressions if cross-platform regression verification is incomplete.
- S6 buffer can be consumed by earlier carry-over work, so each platform Scrum should reserve stabilization time within its own two-week window.

## 10. C4 Exit Criteria

C4 is successful when:

- Android, Windows, iOS, and macOS each have at least 100 converted test cases.
- Each platform achieves a stable execution success rate above 95%.
- Platform failures have evidence, classification, and owners.
- FSQ2.0 architecture benefits are visible in practice: shared execution, shared evidence, reusable verification/reporting, and platform Harness isolation.
- S5 code cleanup does not regress completed platform work.
- The C4 readiness summary can support next-cycle planning.
