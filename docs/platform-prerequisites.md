# Platform Prerequisites

`pip install fsq-agent` installs supported Python Driver/Runtime packages. FSQ does not install, start, or modify browsers, applications, devices, ADB, Appium servers, or other host services.

## Web

Use an installed Chromium-family channel. Pass `--browser-executable-path` when discovery is ambiguous. Firefox and WebKit are outside the current target contract.

## Android

ADB must be on `PATH`, an online authorized device must be visible, and the target application must already be installed. FSQ does not connect, authorize, or install it during readiness checks.

## Windows

Run on Windows with an existing application path. The package includes pywinauto; application installation and desktop session availability remain external.

## macOS

Run on macOS with an existing application identity and a compatible, already reachable Appium Mac2 service. FSQ does not install or start Appium.

Run `fsq doctor` from the exact registered Workspace root. Doctor does not authenticate interactively, invoke a model, launch a target, create an external session, or repair the host.
