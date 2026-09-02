# Platform Prerequisites

`pip install fsq-agent` installs supported Python Driver/Runtime packages. FSQ does not install, start, or modify browsers, applications, devices, ADB, Appium servers, or other host services.

## Web

Provide an installed Chromium-family browser. Supported channels are `chromium`, Chrome stable/beta/dev/canary, and Microsoft Edge stable/beta/dev/canary. `fsq init` discovers an exact channel match when there is one; pass `--browser-executable-path` when discovery is ambiguous or the installation uses a non-standard location. Firefox and WebKit are outside the current Web target contract. FSQ does not install or start the browser during readiness checks.

## Android

ADB must be on `PATH`, an online authorized device must be visible, and the target application must already be installed. Device connection and authorization remain operator responsibilities; FSQ does not connect, authorize, or install devices or applications during readiness checks.

## Windows

Run on Windows with an existing application path and an interactive desktop session that can expose the target UI. The package includes pywinauto; application installation, startup prerequisites, permissions, and desktop-session availability remain operator responsibilities.

## macOS

Run on macOS with an existing application bundle id or application path and a compatible, already reachable Appium Mac2 service. FSQ validates the configured target and service URL but does not install the application or install, configure, or start Appium.

Run `fsq doctor` from the exact registered Workspace root. Doctor does not authenticate interactively, invoke a model, launch a target, create an external session, or repair the host.
