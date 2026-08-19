# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from fsq_agent.core import PlatformRuntimeService
from fsq_agent.models import PlatformRuntimeCheck, web_executable_matches_channel

CHANNEL_PATHS = {
    "chromium": ("Chromium/Application", "chrome.exe"),
    "chrome": ("Google/Chrome/Application", "chrome.exe"),
    "chrome-beta": ("Google/Chrome Beta/Application", "chrome.exe"),
    "chrome-dev": ("Google/Chrome Dev/Application", "chrome.exe"),
    "chrome-canary": ("Google/Chrome SxS/Application", "chrome.exe"),
    "msedge": ("Microsoft/Edge/Application", "msedge.exe"),
    "msedge-beta": ("Microsoft/Edge Beta/Application", "msedge.exe"),
    "msedge-dev": ("Microsoft/Edge Dev/Application", "msedge.exe"),
    "msedge-canary": ("Microsoft/Edge SxS/Application", "msedge.exe"),
}


def test_runtime_check_requires_consistent_explicit_status() -> None:
    with pytest.raises(ValidationError):
        PlatformRuntimeCheck(platform="web", ready=True, message="ready")
    with pytest.raises(ValidationError):
        PlatformRuntimeCheck(platform="web", status="ready", ready=False, message="bad")


def test_web_discovery_returns_exact_channel_candidates(tmp_path: Path, monkeypatch) -> None:
    chrome = tmp_path / "Google Chrome"
    edge = tmp_path / "Microsoft Edge Canary"
    monkeypatch.setattr("fsq_agent.core._platform_runtime._web_candidate_paths", lambda _channel: [chrome, edge])
    monkeypatch.setattr(Path, "is_file", lambda self: self in {chrome, edge})

    assert PlatformRuntimeService().discover_web_executables("msedge-canary") == [edge.resolve()]


def test_web_discovery_checks_windows_install_locations(tmp_path: Path, monkeypatch) -> None:
    edge = tmp_path / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_text("", encoding="utf-8")
    monkeypatch.setattr("fsq_agent.core._platform_runtime.platform.system", lambda: "Windows")
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert PlatformRuntimeService().discover_web_executables("msedge") == [edge.resolve()]


def test_runtime_check_reports_unsupported_host_before_module_lookup(monkeypatch) -> None:
    monkeypatch.setattr("fsq_agent.core._platform_runtime.platform.system", lambda: "Linux")
    monkeypatch.setattr("fsq_agent.core._platform_runtime.importlib.util.find_spec", lambda _module: object())

    check = PlatformRuntimeService().check("windows")

    assert check.status == "unsupported"
    assert check.ready is False
    assert check.action == "Run Windows platform tests on a Windows host."


def test_runtime_install_does_not_invoke_pip_on_unsupported_host(monkeypatch) -> None:
    monkeypatch.setattr("fsq_agent.core._platform_runtime.platform.system", lambda: "Windows")
    monkeypatch.setattr("fsq_agent.core._platform_runtime.subprocess.run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("pip must not run")))

    check = PlatformRuntimeService().install("macos")

    assert check.status == "unsupported"


def test_explicit_nonstandard_web_path_can_match_selected_channel(tmp_path: Path) -> None:
    chrome = tmp_path / "portable" / "Google Chrome" / "chrome.exe"
    firefox = tmp_path / "portable" / "firefox.exe"

    service = PlatformRuntimeService()

    assert service.web_executable_matches_channel("chrome", chrome) is True
    assert service.web_executable_matches_channel("chrome", firefox) is False
    assert service.web_executable_matches_channel("chrome", tmp_path / "arbitrary" / "chrome.exe") is False
    assert service.web_executable_matches_channel("msedge", tmp_path / "arbitrary" / "msedge.exe") is False


@pytest.mark.parametrize("selected_channel", CHANNEL_PATHS)
def test_channel_identity_matrix_is_exact_and_shared(tmp_path: Path, selected_channel: str) -> None:
    directory, executable = CHANNEL_PATHS[selected_channel]
    selected_path = tmp_path / "portable" / directory / executable
    service = PlatformRuntimeService()

    for requested_channel in CHANNEL_PATHS:
        expected = requested_channel == selected_channel
        assert web_executable_matches_channel(requested_channel, selected_path) is expected
        assert service.web_executable_matches_channel(requested_channel, selected_path) is expected


@pytest.mark.parametrize(
    ("channel", "path"),
    [
        ("chrome", "arbitrary/chrome.exe"),
        ("msedge", "arbitrary/msedge.exe"),
        ("chromium", "arbitrary/chrome.exe"),
        ("chrome", "Microsoft/Edge/Application/chrome.exe"),
        ("msedge", "Google/Chrome/Application/msedge.exe"),
        ("chrome", "Google/Chrome Beta/Application/chrome.exe"),
        ("msedge", "Microsoft/Edge SxS/Application/msedge.exe"),
        ("chrome-beta", "Google/Chrome/Application/chrome.exe"),
        ("msedge-dev", "Microsoft/Edge/Application/msedge.exe"),
    ],
)
def test_channel_identity_rejects_ambiguous_wrong_product_and_wrong_channel(tmp_path: Path, channel: str, path: str) -> None:
    selected = tmp_path / "portable" / path

    assert web_executable_matches_channel(channel, selected) is False
    assert PlatformRuntimeService().web_executable_matches_channel(channel, selected) is False


@pytest.mark.parametrize(
    ("channel", "directory", "executable"),
    [
        ("chromium", "Chromium", "chrome.exe"),
        ("chrome", "Google Chrome", "chrome.exe"),
        ("chrome-beta", "Google Chrome Beta", "chrome.exe"),
        ("chrome-dev", "Google Chrome Dev", "chrome.exe"),
        ("chrome-canary", "Chrome SxS", "chrome.exe"),
        ("msedge", "Microsoft Edge", "msedge.exe"),
        ("msedge-beta", "Microsoft Edge Beta", "msedge.exe"),
        ("msedge-dev", "Microsoft Edge Dev", "msedge.exe"),
        ("msedge-canary", "Edge SxS", "msedge.exe"),
    ],
)
def test_explicit_web_path_uses_exact_channel_components(tmp_path: Path, channel: str, directory: str, executable: str) -> None:
    service = PlatformRuntimeService()
    selected = tmp_path / "portable" / directory / "Application" / executable

    assert service.web_executable_matches_channel(channel, selected) is True
    for other in ("chrome-beta", "chrome-dev", "chrome-canary", "msedge-beta", "msedge-dev", "msedge-canary"):
        if other != channel and executable in {"chrome.exe", "msedge.exe"}:
            assert service.web_executable_matches_channel(other, selected) is False


@pytest.mark.parametrize(
    ("channel", "relative"),
    [
        ("chromium", "Chromium/Application/chrome.exe"),
        ("chrome", "Google/Chrome/Application/chrome.exe"),
        ("chrome-beta", "Google/Chrome Beta/Application/chrome.exe"),
        ("chrome-dev", "Google/Chrome Dev/Application/chrome.exe"),
        ("chrome-canary", "Google/Chrome SxS/Application/chrome.exe"),
        ("msedge", "Microsoft/Edge/Application/msedge.exe"),
        ("msedge-beta", "Microsoft/Edge Beta/Application/msedge.exe"),
        ("msedge-dev", "Microsoft/Edge Dev/Application/msedge.exe"),
        ("msedge-canary", "Microsoft/Edge SxS/Application/msedge.exe"),
    ],
)
def test_windows_discovery_covers_every_supported_channel(tmp_path: Path, monkeypatch, channel: str, relative: str) -> None:
    executable = tmp_path / relative
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr("fsq_agent.core._platform_runtime.platform.system", lambda: "Windows")
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert PlatformRuntimeService().discover_web_executables(channel) == [executable.resolve()]


@pytest.mark.parametrize(("installed", "status"), [(True, "ready"), (False, "missing")])
def test_runtime_check_reports_ready_or_missing(monkeypatch, installed: bool, status: str) -> None:
    monkeypatch.setattr("fsq_agent.core._platform_runtime.platform.system", lambda: "Linux")
    monkeypatch.setattr("fsq_agent.core._platform_runtime.importlib.util.find_spec", lambda _module: object() if installed else None)

    check = PlatformRuntimeService().check("web")

    assert check.status == status
    assert check.ready is installed
    assert "stdout" not in check.model_dump()
    assert "stderr" not in check.model_dump()


def test_runtime_install_success_uses_fixed_bounded_command_and_rechecks(monkeypatch) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    monkeypatch.setattr("fsq_agent.core._platform_runtime.platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "fsq_agent.core._platform_runtime.subprocess.run",
        lambda command, **kwargs: calls.append((command, kwargs)) or subprocess.CompletedProcess(command, 0),
    )
    monkeypatch.setattr(PlatformRuntimeService, "check", lambda self, platform: PlatformRuntimeCheck(platform=platform, status="ready", ready=True, message="ready"))

    check = PlatformRuntimeService().install("web")

    assert check.status == "ready"
    assert calls == [
        (
            [__import__("sys").executable, "-m", "pip", "install", "fsq-agent[web]"],
            {"check": False, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "timeout": 300},
        )
    ]


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.TimeoutExpired(["pip"], 300, output=b"secret-output", stderr=b"secret-error"),
        OSError("secret launch failure"),
        subprocess.CompletedProcess(["pip"], 9, stdout=b"secret-output", stderr=b"secret-error"),
    ],
)
def test_runtime_install_failures_are_missing_and_do_not_disclose_output(monkeypatch, failure: BaseException | subprocess.CompletedProcess) -> None:
    monkeypatch.setattr("fsq_agent.core._platform_runtime.platform.system", lambda: "Linux")

    def fail(*args, **kwargs):
        if isinstance(failure, BaseException):
            raise failure
        return failure

    monkeypatch.setattr("fsq_agent.core._platform_runtime.subprocess.run", fail)

    check = PlatformRuntimeService().install("web")

    assert check.status == "missing"
    assert check.ready is False
    assert "secret" not in check.message
    assert "secret" not in (check.action or "")
