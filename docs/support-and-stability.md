# Support, Stability, and Privacy

FSQ v0.1.0 is an alpha release for evaluation and early contribution, not a 1.0 compatibility commitment.

## Stability

- CLI details, Workspace layout, Case authoring, Python APIs, and Control Plane transport may evolve before 1.0.
- Breaking changes are described in release notes and the changelog once published.
- Generated candidate Cases are review inputs, not automatically trusted regression assets.

## Supported environment

Package metadata supports Python 3.11, 3.12, and 3.13. CI currently tests Python 3.11 on Linux and Python 3.13 on Linux, macOS, and Windows; Python 3.12 is supported but does not have a dedicated CI matrix cell. Web, Android, Windows, and macOS require external applications, devices, or services. The current Providers are GitHub Copilot and Azure OpenAI.

## Local data and privacy

FSQ stores Workspace configuration, Cases, knowledge, Run evidence, logs, metadata, suggestions, and reports locally. User-level Provider configuration and authentication state are stored below `~/.fsq`. Model-backed operations send the inputs required for the operation to the configured Provider; consult that Provider's data policy.

Evidence may capture visible application content, UI text, screenshots, local paths, or target metadata. Inspect artifacts before sharing them. Never use production credentials or private personal data in public demonstrations.

FSQ does not claim that a passing AI judgment proves application correctness. Review evidence, Case logic, target state, and verification policy in context.

For help, open a redacted GitHub Issue. Report vulnerabilities privately through [SECURITY.md](../SECURITY.md).
