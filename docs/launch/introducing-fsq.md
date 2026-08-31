# Introducing FSQ: Evidence-First AI UI Automation You Can Replay

AI can operate a user interface, but “the agent said it finished” is not enough for a trustworthy test. Teams need to inspect what happened and repeat successful behavior without asking a model to rediscover every step.

FSQ is an open-source, evidence-first agent harness built for that workflow.

## From a goal to inspectable facts

Give FSQ a user-visible goal. During execution it records screenshots, normalized UI snapshots, ordered events, metadata, and a report in one local Run. Verification consumes evidence rather than relying only on the agent's narrative.

When exploration succeeds, FSQ can produce a reviewable YAML Case from the actual actions. That Case can be replayed through the same platform Harness to produce fresh regression evidence.

## One model across four platforms

FSQ uses Playwright for Web, uiautomator2 for Android, pywinauto for Windows, and Appium Mac2 for macOS. These libraries perform platform interaction. FSQ adds a shared Case format, lifecycle, evidence model, verification, Run history, readiness diagnostics, and local Control Plane.

## Local-first operation

Workspace files and Run evidence stay local. Provider configuration is stored under the user's FSQ configuration directory and shared by the CLI and Control Plane. Model-backed operations use the configured GitHub Copilot or Azure OpenAI Provider.

## Try the alpha

```bash
python -m pip install fsq-agent
mkdir fsq-web-demo && cd fsq-web-demo
fsq init --platform web --browser-channel chrome
fsq doctor
```

The v0.1.0 release is alpha software. It is an invitation to evaluate the model, inspect the architecture, report gaps, and help define a dependable path to 1.0.

Read the [getting-started guide](../getting-started.md), explore the [architecture](../architecture.md), and join through the [contribution guide](../../CONTRIBUTING.md).
