# GitHub Contribution Templates and Code Ownership Design

**Status:** Confirmed
**Date:** 2026-08-03

## Goal

Give the public repository consistent contribution intake, explicit SDD review prompts, and default review ownership. Bug reports and feature requests should arrive with enough information to act on, pull requests should show how design and SPEC requirements were handled, and every changed path should have a recognized code owner.

## Context

The repository currently has no Issue templates, pull request template, or CODEOWNERS file. `CONTRIBUTING.md` asks contributors to open or join an Issue before larger changes and distinguishes behavior-changing work from documentation and repository-metadata changes. Root `SPEC.md` defines the current SDD contract: confirmed SPEC files are the implementation source of truth, non-trivial behavior changes require confirmed SPEC updates before implementation, and behavior-preserving bug fixes may omit a design document when the relevant SPEC files remain accurate. `SECURITY.md` requires vulnerabilities to be reported privately.

The repository already has GitHub Issues enabled and has the `bug` and `enhancement` labels. The confirmed code-owner accounts are:

- `@zhengdawang443`
- `@houlianpi`
- `@tongyu70020`

## Scope

Add these repository metadata files:

```text
.github/
├── CODEOWNERS
├── ISSUE_TEMPLATE/
│   ├── bug_report.yml
│   ├── config.yml
│   ├── feature_request.yml
│   └── new_platform.yml
└── PULL_REQUEST_TEMPLATE.md
```

The change includes:

- Structured Bug, Feature, and New Platform/Driver Issue Forms in English.
- An Issue chooser that disables blank Issues for normal contributors and directs security reports to the repository Security Policy.
- One English pull request template with SDD, verification, documentation, evidence, and sensitive-data checks.
- One global CODEOWNERS rule naming all three maintainers.
- A documented post-merge GitHub ruleset configuration that requires review for normal contributors while permitting repository administrators to merge through a pull request without another approval.

## Non-Goals

- CI, release automation, bots, or automated enforcement of pull request template fields.
- New labels, automatic assignees, milestones, or project-board routing.
- Separate Issue Forms for documentation or questions.
- Per-directory or per-module code ownership.
- Changes to `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, Python source, frontend source, or SPEC files.
- Direct-push bypass to the default branch.

## Approaches Considered

### Structured Issue Forms, One PR Template, Global Ownership

Use YAML Issue Forms for validated inputs, including a dedicated New Platform/Driver proposal, one Markdown pull request template, and one global CODEOWNERS rule. This provides consistent Issue data without adding unnecessary PR categories or ownership mappings. This is the selected approach.

### Markdown Issue Templates

Markdown Issue templates would be simpler to author, but contributors could delete prompts or omit required environment and reproduction details. They would not provide controlled platform and affected-area choices. This was rejected because FSQ Issues need predictable platform-specific context.

### Structured Issue Forms and Multiple PR Templates

Multiple PR templates could separate code, documentation, and platform contributions. This was rejected for the initial repository workflow because contributors would have to choose between overlapping PR categories and the SDD checks would be duplicated across files.

## Architecture and Ownership

This is repository metadata and does not enter the Python package dependency graph. Python architecture levels and public API boundaries do not apply. GitHub owns form rendering, label application, template insertion, CODEOWNERS recognition, and ruleset enforcement.

The `.github` directory owns the new files. No `fsq_agent` module gains a responsibility or dependency.

## Issue Intake Design

### Bug Form

`.github/ISSUE_TEMPLATE/bug_report.yml` will:

- Use the name `Bug report` and title prefix `[Bug]: `.
- Apply the existing `bug` label.
- Start with guidance that security vulnerabilities must not be reported publicly and link to the Security Policy.
- Require these fields:
  - What happened.
  - Steps to reproduce.
  - Expected behavior.
  - FSQ version or source revision.
  - Active platform: Android, Web, Windows, macOS, Cross-platform, or Other.
  - Operating system and version.
  - Python version.
- Provide optional fields for sanitized logs/evidence and additional context.
- Require confirmation that the reporter searched existing Issues.
- Require confirmation that credentials, tokens, account data, personal data, and other sensitive values were removed.

The form will not require the latest FSQ version because reports against pinned or older supported revisions may still be valid.

### Feature Form

`.github/ISSUE_TEMPLATE/feature_request.yml` will:

- Use the name `Feature request` and title prefix `[Feature]: `.
- Apply the existing `enhancement` label.
- Require the problem or use case, desired outcome, and one or more affected areas.
- Offer affected-area choices for agent runtime, strict replay/FSQ DSL, Android, Web, Windows, macOS, CLI, Playground, providers, Harness SDK/existing drivers, documentation/build/tooling, and Other.
- Provide optional fields for alternatives, compatibility or rollout risks, additional context, and willingness to contribute.
- Require confirmation that the requester searched existing Issues.

Improvements to the Harness SDK or existing drivers remain Feature requests. New platform, Driver, or backend proposals use the dedicated form below.

### New Platform/Driver Form

`.github/ISSUE_TEMPLATE/new_platform.yml` will:

- Use the name `New platform or driver proposal` and title prefix `[Platform]: `.
- Apply the existing `enhancement` label.
- Require the target platform, proposed Driver/backend, user need and use cases, initial capability scope, evidence and strict replay approach, and maintenance commitment.
- Provide optional fields for dependencies and constraints and for prior art or references.
- Require confirmation that the requester searched for an equivalent platform or Driver proposal.
- Require acknowledgement that implementation cannot begin until the required design document and relevant SPEC changes are confirmed.
- Direct improvements to an existing implementation to the general Feature form.

### Issue Chooser

`.github/ISSUE_TEMPLATE/config.yml` will:

- Set `blank_issues_enabled: false`.
- Expose only the Bug, Feature, and New Platform/Driver forms as public Issue creation paths for contributors with Read or Triage access. GitHub still shows a `Maintainers only` blank Issue option to users with Write, Maintain, or Admin access.
- Add a `Security vulnerability` contact link to `https://github.com/microsoft/FSQ/security/policy`.

Questions do not receive a separate contact route because GitHub Discussions is not enabled and the confirmed scope contains only Bug, Feature, and New Platform/Driver intake.

## Pull Request Design

`.github/PULL_REQUEST_TEMPLATE.md` will use concise Markdown sections and HTML comments for author guidance. The policy requires each section to be completed, although GitHub does not technically validate Markdown template completion.

### Required Sections

- `Summary`: describe the problem and outcome.
- `Related issue`: use `Closes #...` or explain why an Issue is not required. Behavior and public-contract changes must link an existing Issue. Small documentation, repository-metadata, or behavior-preserving fixes may explain the exception.
- `Design document`: link the confirmed design document. If no design document exists, state the reason. Accepted categories are behavior-preserving bug fixes whose relevant SPEC files remain accurate, and documentation or repository-metadata changes exempted by the contribution policy.
- `SPEC updates`: list every root or module SPEC updated and confirmed before implementation. If no SPEC changed, state which relevant SPEC files were reviewed, why no current fact changed, and why those SPEC files remain accurate.
- `Changes`: summarize the implementation or metadata changes.
- `Verification`: list exact commands and manual checks with outcomes.
- `Evidence`: provide screenshots, reports, or other user-visible evidence when relevant; otherwise state `N/A` with a reason.

### Author Checklist

The author must attest that:

- Root `SPEC.md` and every relevant module `SPEC.md` were reviewed.
- Required design and SPEC confirmation gates occurred before implementation.
- The implementation, tests, and documentation agree with current confirmed SPEC files.
- The design document was not treated as the implementation source of truth.
- Focused tests and required formatting or lint checks were run, or an explicit reason is supplied.
- User-facing documentation was updated when behavior or setup changed.
- No credentials, tokens, account data, personal data, local `.env` files, generated logs, reports, screenshots, or workspace output were committed.

The template makes the SDD decision visible but does not replace human review or future automated policy checks.

## Code Ownership and Review Policy

`.github/CODEOWNERS` will contain one effective rule:

```text
* @zhengdawang443 @houlianpi @tongyu70020
```

All three accounts are global code owners. For a pull request subject to required Code Owner review, one approval from any listed owner satisfies a one-approval requirement. The pull request author cannot approve their own pull request.

Each listed account must have `write` access for GitHub to recognize it as a code owner. Account existence has been confirmed, but repository permission must be verified after the file reaches the default branch.

The maintainers explicitly chose to allow repository administrators to merge their own pull requests. After the files are merged, configure an active branch ruleset targeting the default branch with:

- `Require a pull request before merging` enabled.
- One required approval.
- `Require review from Code Owners` enabled.
- The `Repository administrators` bypass actor configured as `For pull requests only`.

This configuration keeps a pull request and audit trail mandatory while allowing an administrator to choose to bypass review and merge. It does not grant direct-push bypass through this ruleset. Because the bypass actor is a role, future repository administrators will receive the same ability. An administrator can also bypass an external pull request's review requirement; normal policy is to approve such a pull request as a code owner instead of bypassing it.

CODEOWNERS alone does not enforce approval. Until the ruleset is active, the file only causes review requests and ownership display.

## Control Flow

### Issue Creation

1. A contributor opens the New Issue chooser.
2. GitHub offers Bug, Feature, New Platform/Driver, and the private Security Policy link. Normal contributors receive no blank Issue option; users with Write or higher access may use GitHub's `Maintainers only` blank option.
3. GitHub validates required form fields and checklist confirmations.
4. A submitted Bug, Feature, or New Platform/Driver proposal receives its existing repository label.
5. Maintainers triage the structured Issue normally.

### Pull Request Creation and Review

1. A contributor opens a pull request and GitHub inserts the PR template.
2. The author links or explains the Issue, design document, and SPEC disposition, then records verification and evidence.
3. The CODEOWNERS rule requests owner review for every changed path.
4. For normal contributors, any one of the three recognized owners can satisfy the required owner review.
5. A repository administrator may use the pull-request-only bypass to merge without another approval, while retaining the PR audit trail.

## Error Handling and Edge Cases

- Each Issue Form field must have a unique stable `id`; invalid YAML or duplicate IDs must be fixed before merge.
- `Other` and free-text context prevent the forms from blocking an unanticipated platform or subsystem.
- Evidence fields warn contributors to sanitize data before submission. Public Issues must never become a security-reporting path.
- Labels are limited to the already verified `bug` and `enhancement` labels so form submission does not depend on label creation.
- No default assignee is configured because report intake does not imply scheduling or ownership of the work.
- If a CODEOWNER lacks `write` access, GitHub may not recognize that owner. The repository permissions or rule must be corrected before relying on required review.
- If another branch protection rule or organization ruleset also targets `main`, GitHub combines the rules and applies the most restrictive result. Post-merge verification must inspect the effective rules, not only this repository ruleset.
- Markdown PR fields and checkboxes are policy prompts, not machine-enforced required inputs. Automated SDD validation is deferred to a separate CI design.

## Security and Privacy

The Bug form and PR checklist explicitly prohibit credentials, tokens, account data, personal data, and local runtime artifacts. The Issue chooser sends vulnerability reports to the existing private Microsoft security process. No form asks for email addresses, account identifiers, or secrets.

## Affected Specifications

No root or module SPEC is expected to change. This design changes GitHub contribution metadata, not FSQ runtime behavior, public interfaces, configuration contracts, module ownership, or dependency direction. During implementation, root `SPEC.md` must be rechecked; if implementation reveals a changed current fact, work stops until the relevant SPEC update is confirmed.

## Resolved Questions

- Issue scope: Bug, Feature, and a dedicated New Platform/Driver proposal.
- Blank Issues: disabled for normal contributors; GitHub's built-in maintainer-only blank option remains available to users with Write or higher access.
- Language: English.
- Issue format: YAML Issue Forms rather than Markdown Issue templates.
- Pull request format: one Markdown template rather than multiple category templates.
- Issue relationship: required for behavior/public-contract changes; justified exceptions are allowed for small non-behavior changes.
- SDD visibility: every PR states its design-document and SPEC disposition and includes explicit SDD attestations.
- Ownership: all three named accounts own all paths; any one owner can satisfy normal required review.
- Administrator review: repository administrators may bypass review only through a pull request and may merge their own PRs.

## Verification Expectations

### Before Merge

- Parse all four YAML files successfully.
- Validate Issue Form top-level keys, unique field IDs, required fields, dropdown options, checkbox requirements, and existing label names.
- Confirm `config.yml` disables blank Issues and uses the expected absolute Security Policy URL.
- Confirm the PR template contains Related issue, Design document, SPEC updates, Changes, Verification, Evidence, and every SDD attestation.
- Confirm CODEOWNERS has exactly the intended global rule and three exact handles.
- Confirm no unresolved placeholder markers remain.
- Review the final diff and verify that no SPEC or implementation file changed.

### After Merge to the Default Branch

- As a non-maintainer, open the New Issue chooser and verify only Bug, Feature, and New Platform/Driver forms plus the Security Policy link are available. A maintainer may additionally see GitHub's `Maintainers only` blank option.
- Open each form and verify required-field behavior, platform/area options, sensitive-data guidance, and automatic `bug` or `enhancement` labeling.
- Open a draft pull request and verify the complete PR template is inserted.
- Confirm GitHub recognizes all three CODEOWNER handles and requests ownership review for a changed file.
- Activate and inspect the default-branch ruleset with one required Code Owner approval and pull-request-only administrator bypass.
- Use a normal test pull request to verify one owner approval satisfies the review requirement.
- Use an administrator-authored test pull request to verify the administrator can merge through bypass without another approval but cannot use the ruleset bypass for a direct push.