# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from fsq_agent._strict_case_recording import StrictCaseRecording
from fsq_agent.cli._android_devices import select_android_serial
from fsq_agent.cli._main import _task_from_goal, _task_from_raw_case_source, main
from fsq_agent.cli._task_loader import discover_case_yaml_paths, read_raw_text_file, resolve_case_yaml_path
from fsq_agent.config import PLATFORM_CONFIG_PATHS, Settings
from fsq_agent.models import AndroidDevice, AndroidDeviceDiscoveryResult, ConfigurationError, ReportArtifact, Task, TaskResult, VerificationResult

FSQ_CASE = """
schemaVersion: fsq.ai-test/v1
name: Strict CLI Case
platform: android
appId: com.microsoft.emmx
---
- launchApp
"""


WEB_FSQ_CASE = """
schemaVersion: fsq.ai-test/v1
name: Strict Web CLI Case
platform: web
---
- startBrowser
- navigateTo:
    url: https://www.bing.com
- uiSnapshot
- closeBrowser
"""


MACOS_FSQ_CASE = """
schemaVersion: fsq.ai-test/v1
name: Strict macOS CLI Case
platform: macos
---
- launchApp
- clickOn:
        point:
            x: 100
            y: 200
- assertElementsOrder:
        elements:
            - target: File
            - target: Edit
- killApp
"""


WINDOWS_FSQ_CASE = """
schemaVersion: fsq.ai-test/v1
name: Strict Windows CLI Case
platform: windows
---
- launchApp
- uiSnapshot
- killApp
"""


def _config(tmp_path: Path, body: str = "", platform: str = "android") -> Path:
    cases_dir = tmp_path / "cases" / platform
    cases_dir.mkdir(parents=True, exist_ok=True)
    target: str
    if platform == "android":
        target = "  app_id: com.example.config"
    elif platform == "web":
        browser_path = tmp_path / "chrome.exe"
        browser_path.write_text("", encoding="utf-8")
        browser_path.chmod(0o755)
        target = f"  browser_executable_path: {browser_path.as_posix()}"
    elif platform == "windows":
        app_path = tmp_path / "windows-app.exe"
        app_path.write_text("", encoding="utf-8")
        target = f'  app_path: {app_path.as_posix()}\n  window_title_re: .*Legacy App\n  launch_args: --flag "two words"'
    else:
        target = "  bundle_id: com.example.MacApp"
    fsq_dir = tmp_path / ".fsq" / "config"
    fsq_dir.mkdir(parents=True, exist_ok=True)
    (fsq_dir / f"config.{platform}.yaml").write_text(
        f"""
version: 2
name: test-workspace
root_path: {tmp_path.as_posix()}
platform: {platform}
target:
{target}
env: {{}}
""",
        encoding="utf-8",
    )
    user_config_root = Path.home() / ".fsq"
    user_config_root.mkdir(parents=True, exist_ok=True)
    (user_config_root / "config.yaml").write_text(
        f"""
version: 3
provider: null
workspaces:
  - name: test-workspace
    root_path: {json.dumps(str(tmp_path.resolve()))}
""",
        encoding="utf-8",
    )
    config_path = tmp_path / f"config.{platform}.yaml"
    preset = (
        body
        or f"""
harness:
  platform: {platform}
  {platform}:
    backend: {"uiautomator2" if platform == "android" else "playwright" if platform == "web" else "pywinauto" if platform == "windows" else "appium_mac2"}
"""
    )
    config_path.write_text(
        preset,
        encoding="utf-8",
    )
    return config_path


def test_case_input_helpers_reject_paths_outside_workspace_cases(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    outside = tmp_path / "outside.fsq.yaml"
    outside.write_text(FSQ_CASE, encoding="utf-8")
    outside_dir = tmp_path / "outside-cases"
    outside_dir.mkdir()
    (outside_dir / "external.fsq.yaml").write_text(FSQ_CASE, encoding="utf-8")

    for source in (outside, Path("..") / outside.name):
        with pytest.raises(ConfigurationError, match="workspace cases"):
            resolve_case_yaml_path(source, cases_dir)
        with pytest.raises(ConfigurationError, match="workspace cases"):
            read_raw_text_file(source, cases_dir)
    with pytest.raises(ConfigurationError, match="workspace cases"):
        discover_case_yaml_paths(outside_dir, cases_dir)

    link = cases_dir / "linked.fsq.yaml"
    try:
        link.symlink_to(outside)
    except OSError:
        return
    with pytest.raises(ConfigurationError, match="workspace cases"):
        resolve_case_yaml_path(link, cases_dir)


def _write_fake_core_report(output_dir: Path, run_id: str, status: str = "passed") -> ReportArtifact:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "core-report.md"
    json_report_path = output_dir / "core-report.json"
    manifest_path = output_dir / "evidence-manifest.json"
    report_path.write_text("report", encoding="utf-8")
    json_report_path.write_text(
        json.dumps({"summary": {"status": status, "failed_steps": 0 if status == "passed" else 1}}),
        encoding="utf-8",
    )
    manifest_path.write_text("{}", encoding="utf-8")
    return ReportArtifact(run_id=run_id, path=report_path, evidence_manifest_path=manifest_path)


@pytest.fixture(autouse=True)
def _isolate_user_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for platform in PLATFORM_CONFIG_PATHS:
        monkeypatch.setitem(PLATFORM_CONFIG_PATHS, platform, tmp_path / f"config.{platform}.yaml")
    user_home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setenv("USERPROFILE", str(user_home))
    monkeypatch.setattr(
        "fsq_agent.cli._android_devices.AndroidDeviceDiscovery.discover",
        lambda _self: AndroidDeviceDiscoveryResult(devices=[AndroidDevice(serial="device-1", state="device")]),
    )
    for name in ("FSQ_LLM_PROVIDER", "AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_MODEL", "AZURE_OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_only_public_commands_are_registered() -> None:
    assert set(main.commands) == {"init", "run", "report", "playground", "control-plane"}


def test_control_plane_command_has_no_platform_or_implicit_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_control_plane(options) -> None:
        captured.update(
            host=options.host,
            port=options.port,
            open_browser=options.open_browser,
        )

    monkeypatch.setattr("fsq_agent.cli._main.run_control_plane", fake_run_control_plane)

    result = CliRunner().invoke(main, ["control-plane", "--host", "localhost", "--port", "9000", "--no-open-browser"])

    assert result.exit_code == 0, result.output
    assert captured == {
        "host": "localhost",
        "port": 9000,
        "open_browser": False,
    }
    rejected = CliRunner().invoke(main, ["control-plane", "--platform", "android"])
    assert rejected.exit_code != 0
    assert "No such option: --platform" in rejected.output


@pytest.mark.parametrize("error", [ConfigurationError("invalid workspace"), OSError("bind failed")])
def test_control_plane_command_normalizes_startup_errors(
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_startup(_options) -> None:
        raise error

    monkeypatch.setattr("fsq_agent.cli._main.run_control_plane", fail_startup)

    result = CliRunner().invoke(main, ["control-plane", "--no-open-browser"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Aborted!" in result.output


def test_init_rejects_provider_before_provider_or_workspace_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config(tmp_path)
    user_root = tmp_path / "user"
    monkeypatch.setenv("HOME", str(user_root))
    monkeypatch.setenv("USERPROFILE", str(user_root))

    result = CliRunner().invoke(main, ["init", "--platform", "android", "--provider", "github_copilot"])

    assert result.exit_code != 0
    assert "No such option: --provider" in result.output
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / ".fsq-agent-workspace").exists()
    assert not (user_root / ".fsq").exists()


def test_init_without_provider_does_not_update_env_or_use_interactive_auth(
    tmp_path: Path,
) -> None:
    _config(tmp_path)

    result = CliRunner().invoke(main, ["init", "--platform", "android"])

    assert result.exit_code != 0
    assert "Create a new workspace in Control Plane" in result.output
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / ".fsq-agent-workspace").exists()


def test_removed_setup_command_fails() -> None:
    result = CliRunner().invoke(main, ["setup", "llm", "--provider", "github_copilot"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_run_rejects_missing_or_conflicting_sources(tmp_path: Path) -> None:
    _config(tmp_path)
    runner = CliRunner()

    selection = ["--workspace", "test-workspace", "--platform", "android"]
    missing = runner.invoke(main, ["run", *selection])
    conflicting = runner.invoke(main, ["run", *selection, "--goal", "Do it", "--case-yaml", "case.fsq.yaml"])
    strict_goal = runner.invoke(main, ["run", *selection, "--strict", "--goal", "Do it"])
    record_on_failure_without_record = runner.invoke(main, ["run", *selection, "--goal", "Do it", "--record-on-failure"])
    strict_record = runner.invoke(main, ["run", *selection, "--strict", "--case-yaml", "case.fsq.yaml", "--record"])

    assert missing.exit_code != 0
    assert "Exactly one" in missing.output
    assert conflicting.exit_code != 0
    assert strict_goal.exit_code != 0
    assert record_on_failure_without_record.exit_code != 0
    assert strict_record.exit_code != 0


def test_run_rejects_removed_config_option() -> None:
    result = CliRunner().invoke(main, ["run", "--config", "config.yaml", "--goal", "Do it"])

    assert result.exit_code != 0
    assert "No such option: --config" in result.output


def test_select_android_serial_uses_only_online_device() -> None:
    settings = Settings()

    selected = select_android_serial(settings, None)

    assert selected == "device-1"
    assert settings.harness.android.serial == "device-1"


def test_select_android_serial_rejects_multiple_online_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    monkeypatch.setattr(
        "fsq_agent.cli._android_devices.AndroidDeviceDiscovery.discover",
        lambda _self: AndroidDeviceDiscoveryResult(devices=[AndroidDevice(serial="device-1", state="device"), AndroidDevice(serial="device-2", state="device")]),
    )

    with pytest.raises(ConfigurationError, match=r"Multiple online Android devices.*--android-serial"):
        select_android_serial(settings, None)


def test_select_android_serial_rejects_no_online_device(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    monkeypatch.setattr(
        "fsq_agent.cli._android_devices.AndroidDeviceDiscovery.discover",
        lambda _self: AndroidDeviceDiscoveryResult(devices=[AndroidDevice(serial="device-1", state="offline")]),
    )

    with pytest.raises(ConfigurationError, match="No online Android devices"):
        select_android_serial(settings, None)


def test_select_android_serial_rejects_explicit_offline_device(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    monkeypatch.setattr(
        "fsq_agent.cli._android_devices.AndroidDeviceDiscovery.discover",
        lambda _self: AndroidDeviceDiscoveryResult(devices=[AndroidDevice(serial="device-1", state="offline")]),
    )

    with pytest.raises(ConfigurationError, match=r"device-1.*not online.*offline"):
        select_android_serial(settings, "device-1")


def test_select_android_serial_rejects_option_for_non_android_without_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    settings.harness.platform = "web"
    monkeypatch.setattr(
        "fsq_agent.cli._android_devices.AndroidDeviceDiscovery.discover",
        lambda _self: pytest.fail("ADB discovery must not run for a non-Android workspace"),
    )

    with pytest.raises(ConfigurationError, match="only supported for Android"):
        select_android_serial(settings, "device-1")


@pytest.mark.parametrize(
    ("source_args", "execution_name"),
    [
        (["--goal", "Do it"], "dynamic"),
        (["--strict", "--case-yaml", "case.fsq.yaml"], "strict"),
    ],
)
def test_run_selects_explicit_android_serial_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_args: list[str],
    execution_name: str,
) -> None:
    _config(tmp_path)
    events: list[tuple[str, str | None]] = []

    def fake_select(_settings: Settings, requested_serial: str | None) -> str:
        events.append(("select", requested_serial))
        return requested_serial or "device-1"

    def fake_dynamic(_settings: Settings, **_kwargs) -> None:
        events.append(("dynamic", None))

    def fake_strict(_settings: Settings, **_kwargs) -> None:
        events.append(("strict", None))

    monkeypatch.setattr("fsq_agent.cli._main.select_android_serial", fake_select)
    monkeypatch.setattr("fsq_agent.cli._main._run_dynamic", fake_dynamic)
    monkeypatch.setattr("fsq_agent.cli._main._run_strict", fake_strict)

    result = CliRunner().invoke(
        main,
        ["run", "--workspace", "test-workspace", "--platform", "android", "--android-serial", "device-2", *source_args],
    )

    assert result.exit_code == 0, result.output
    assert events == [("select", "device-2"), (execution_name, None)]


@pytest.mark.parametrize(
    "args",
    [
        ["run", "--goal", "Do it"],
        ["report", "--run-id", "run-1"],
        ["playground", "--no-open-browser"],
    ],
)
def test_workspace_commands_require_workspace_name(args: list[str]) -> None:
    result = CliRunner().invoke(main, args)

    assert result.exit_code != 0
    assert "Missing option '--workspace'" in result.output


def test_run_resolves_registered_workspace_case_insensitively_without_using_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "registered-workspace"
    workspace.mkdir()
    _config(workspace)
    invocation_dir = tmp_path / "invocation"
    invocation_dir.mkdir()
    monkeypatch.chdir(invocation_dir)
    captured: dict[str, object] = {}
    sentinel_settings = Settings()

    def fake_load_workspace_settings(workspace_path: Path, platform: str):
        captured["workspace_path"] = workspace_path
        captured["platform"] = platform
        return sentinel_settings

    def fake_run_dynamic(settings, **_kwargs) -> None:
        captured["settings"] = settings

    monkeypatch.setattr("fsq_agent.cli._main.load_workspace_platform_settings", fake_load_workspace_settings)
    monkeypatch.setattr("fsq_agent.cli._main._run_dynamic", fake_run_dynamic)

    result = CliRunner().invoke(main, ["run", "--workspace", "TEST-WORKSPACE", "--platform", "android", "--goal", "Do it"])

    assert result.exit_code == 0, result.output
    assert captured == {
        "workspace_path": workspace.resolve(),
        "platform": "android",
        "settings": sentinel_settings,
    }


def test_run_rejects_unregistered_workspace_before_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    executed = False
    errors: list[str] = []

    def fail_execution(*_args, **_kwargs) -> None:
        nonlocal executed
        executed = True

    monkeypatch.setattr("fsq_agent.cli._main._run_dynamic", fail_execution)
    monkeypatch.setattr("fsq_agent.cli._main._log_cli_error", lambda message, *args: errors.append(message % args))

    result = CliRunner().invoke(main, ["run", "--workspace", "missing", "--platform", "android", "--goal", "Do it"])

    assert result.exit_code != 0
    assert executed is False
    assert any("not registered" in error for error in errors)


def test_run_requires_platform_option() -> None:
    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--goal", "Do it"])

    assert result.exit_code != 0
    assert "Missing option '--platform'" in result.output


def test_run_help_stream_format_defaults_to_concise_without_rich_alias() -> None:
    result = CliRunner().invoke(main, ["run", "--help"])

    assert result.exit_code == 0, result.output
    assert "[default: concise]" in result.output
    assert "[concise|jsonl]" in result.output
    assert "rich" not in result.output


def test_run_case_yaml_uses_raw_file_content_without_fsq_parsing(tmp_path: Path, monkeypatch) -> None:
    _config(tmp_path)
    case_path = tmp_path / "cases" / "android" / "raw.fsq.yaml"
    raw_content = "not: [valid yaml"
    case_path.write_text(raw_content, encoding="utf-8")
    captured: dict[str, object] = {}

    class FakeAgent:
        async def run(self, task: Task, event_sink=None) -> TaskResult:
            captured["task"] = task
            return TaskResult(
                task_id=task.id,
                status="success",
                steps=[],
                verification=VerificationResult(status="success", summary="ok"),
                report=ReportArtifact(run_id="raw-run", path=tmp_path / "report.md"),
            )

    class RaisingLoader:
        def __init__(self) -> None:
            raise AssertionError("dynamic case-yaml must not construct FsqCaseLoader")

    def fake_agent_from_settings(settings):
        captured["tracing_enabled"] = settings.openai_agents.tracing_enabled
        return FakeAgent()

    monkeypatch.setattr("fsq_agent.cli._main.FsqAgent.from_settings", fake_agent_from_settings)
    monkeypatch.setattr("fsq_agent.cli._main.FsqCaseLoader", RaisingLoader)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--case-yaml", "raw.fsq.yaml", "--no-stream", "--no-tracing"])

    assert result.exit_code == 0, result.output
    assert captured["tracing_enabled"] is False
    task = captured["task"]
    assert isinstance(task, Task)
    assert task.name == "Case reference: raw.fsq.yaml"
    assert raw_content in task.description
    assert "The CLI has not parsed" in task.description
    assert task.key_actions == []


def test_run_case_yaml_rejects_wrong_suffix_before_dynamic_execution(tmp_path: Path, monkeypatch) -> None:
    _config(tmp_path)
    (tmp_path / "cases" / "android" / "case.yaml").write_text(FSQ_CASE, encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr("fsq_agent.cli._main._run_dynamic_task", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("fsq_agent.cli._main._log_cli_error", lambda message, *args: errors.append(message % args))

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--case-yaml", "case.yaml", "--no-stream", "--no-tracing"])

    assert result.exit_code != 0
    assert any(".fsq.yaml" in error for error in errors)


def test_run_goal_record_invokes_strict_case_recorder(tmp_path: Path, monkeypatch) -> None:
    _config(tmp_path)
    captured: dict[str, object] = {}

    class FakeAgent:
        async def run(self, task: Task, event_sink=None) -> TaskResult:
            return TaskResult(
                task_id=task.id,
                status="success",
                steps=[],
                verification=VerificationResult(status="success", summary="ok"),
                report=ReportArtifact(run_id="recorded-run", path=tmp_path / "report.md"),
            )

    def fake_record_dynamic_run_as_strict_case(**kwargs):
        captured.update(kwargs)
        recording_path = kwargs["run_dir"] / "recording.json"
        recorded_path = kwargs["run_dir"] / "recorded.fsq.yaml"
        return StrictCaseRecording(status="recorded", recording_path=recording_path, recorded_case_path=recorded_path)

    monkeypatch.setattr("fsq_agent.cli._main.FsqAgent.from_settings", lambda _settings: FakeAgent())
    monkeypatch.setattr("fsq_agent.cli._main.record_dynamic_run_as_strict_case", fake_record_dynamic_run_as_strict_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--goal", "Do it", "--record", "--no-stream"])

    assert result.exit_code == 0, result.output
    assert captured["run_dir"] == tmp_path / ".fsq" / "runs" / "android" / "recorded-run"
    assert captured["allow_failure"] is False
    assert "Recorded strict case" in result.output


def test_run_strict_case_builds_android_harness_from_workspace_and_reports_paths(tmp_path: Path, monkeypatch) -> None:
    _config(
        tmp_path,
        """
harness:
    platform: android
    android:
        backend: uiautomator2
execution:
    post_action_delay_seconds:
        platform: 0.25
        common: 0
""",
    )
    case_path = tmp_path / "cases" / "android" / "strict_cli.fsq.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")
    calls = {}

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str | None) -> None:
            self.app_id = app_id
            self.serial = serial
            calls["driver"] = {"app_id": app_id, "serial": serial}

    def fake_run_strict_fsq_core_case(**kwargs):
        calls["strict"] = kwargs
        return _write_fake_core_report(kwargs["output_dir"], kwargs["run_id"])

    monkeypatch.setattr("fsq_agent.core.harness._factory.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--strict", "--case-yaml", "strict_cli.fsq.yaml"])

    assert result.exit_code == 0, result.output
    assert calls["driver"] == {"app_id": "com.example.config", "serial": "device-1"}
    assert calls["strict"]["case_path"] == case_path.resolve()
    assert calls["strict"]["run_id"].startswith("strict_cli-")
    assert calls["strict"]["output_dir"] == tmp_path / ".fsq" / "runs" / "android" / calls["strict"]["run_id"]
    assert calls["strict"]["output_dir"].parent == tmp_path / ".fsq" / "runs" / "android"
    assert calls["strict"]["post_action_delay_seconds"].platform == 0.25
    assert calls["strict"]["post_action_delay_seconds"].common == 0
    assert "core-report.md" in result.output
    assert "evidence-manifest.json" in result.output


def test_run_strict_case_with_lifecycle_hooks_uses_lifecycle_helper(tmp_path: Path, monkeypatch) -> None:
    _config(
        tmp_path,
        """
harness:
  platform: android
  android:
    backend: uiautomator2
""",
    )
    hook_path = tmp_path / "cases" / "android" / "hooks" / "setup.fsq.yaml"
    hook_path.parent.mkdir(parents=True)
    hook_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Setup Hook
platform: android
---
- tapOn:
    target: Setup
""",
        encoding="utf-8",
    )
    case_path = tmp_path / "cases" / "android" / "strict_hooked.fsq.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Strict Hooked Case
platform: android
appId: com.example.root
onCaseStart:
  runCase: hooks/setup.fsq.yaml
---
- launchApp
""",
        encoding="utf-8",
    )
    calls = {}

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str | None) -> None:
            calls["driver"] = {"app_id": app_id, "serial": serial}

    def fake_run_strict_fsq_core_case(**_kwargs):
        raise AssertionError("plain strict core helper should not run lifecycle cases")

    def fake_run_strict_fsq_lifecycle_case(**kwargs):
        calls["lifecycle"] = kwargs
        return _write_fake_core_report(kwargs["output_dir"], kwargs["run_id"])

    monkeypatch.setattr("fsq_agent.core.harness._factory.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_lifecycle_case", fake_run_strict_fsq_lifecycle_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--strict", "--case-yaml", "strict_hooked.fsq.yaml"])

    assert result.exit_code == 0, result.output
    assert calls["driver"] == {"app_id": "com.example.config", "serial": "device-1"}
    assert calls["lifecycle"]["case_path"] == case_path.resolve()
    assert calls["lifecycle"]["case"].config.on_case_start
    assert calls["lifecycle"]["run_id"].startswith("strict_hooked-")
    assert "core-report.md" in result.output


def test_run_strict_single_case_exits_nonzero_when_report_fails(tmp_path: Path, monkeypatch) -> None:
    _config(
        tmp_path,
        """
harness:
  platform: android
  android:
    backend: uiautomator2
""",
    )
    case_path = tmp_path / "cases" / "android" / "strict_fail.fsq.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str | None) -> None:
            self.app_id = app_id
            self.serial = serial

    def fake_run_strict_fsq_core_case(**kwargs):
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        report_path = kwargs["output_dir"] / "core-report.md"
        json_report_path = kwargs["output_dir"] / "core-report.json"
        manifest_path = kwargs["output_dir"] / "evidence-manifest.json"
        report_path.write_text("report", encoding="utf-8")
        json_report_path.write_text(json.dumps({"summary": {"status": "failed", "failed_steps": 1}}), encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return ReportArtifact(run_id=kwargs["run_id"], path=report_path, evidence_manifest_path=manifest_path)

    monkeypatch.setattr("fsq_agent.core.harness._factory.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--strict", "--case-yaml", str(case_path)])

    assert result.exit_code == 1, result.output
    assert "core-report.md" in result.output


def test_run_strict_case_prefers_workspace_app_id(tmp_path: Path, monkeypatch) -> None:
    _config(
        tmp_path,
        """
harness:
  platform: android
  android:
    backend: uiautomator2
""",
    )
    case_path = tmp_path / "cases" / "android" / "strict_cli.fsq.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")
    calls = {}

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str | None) -> None:
            calls["driver"] = {"app_id": app_id, "serial": serial}

    def fake_run_strict_fsq_core_case(**kwargs):
        return _write_fake_core_report(kwargs["output_dir"], kwargs["run_id"])

    monkeypatch.setattr("fsq_agent.core.harness._factory.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--strict", "--case-yaml", str(case_path)])

    assert result.exit_code == 0, result.output
    assert calls["driver"] == {"app_id": "com.example.config", "serial": "device-1"}


def test_run_strict_case_requires_config_or_case_app_id_before_driver_construction(tmp_path: Path, monkeypatch) -> None:
    _config(tmp_path)
    (tmp_path / ".fsq" / "config" / "config.android.yaml").write_text(
        f"""
version: 2
name: test-workspace
root_path: {tmp_path.as_posix()}
platform: android
target: {{}}
env: {{}}
""",
        encoding="utf-8",
    )
    case_path = tmp_path / "cases" / "android" / "missing_app.fsq.yaml"
    case_path.write_text(FSQ_CASE.replace("appId: com.microsoft.emmx\n", ""), encoding="utf-8")

    def fail_driver(**_kwargs):
        raise AssertionError("driver should not be constructed")

    monkeypatch.setattr("fsq_agent.core.harness._factory.UiAutomator2AndroidDriver", fail_driver)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--strict", "--case-yaml", str(case_path)])

    assert result.exit_code != 0


def test_run_strict_web_case_builds_web_harness_without_android_app_id(tmp_path: Path, monkeypatch) -> None:
    chrome_path = tmp_path / "chrome.exe"
    chrome_path.write_text("", encoding="utf-8")
    chrome_path.chmod(0o755)
    _config(
        tmp_path,
        """
harness:
  platform: web
  web:
    backend: playwright
    channel: chrome
    headless: true
    base_url: https://www.bing.com
    viewport_width: 1280
    viewport_height: 720
""",
        platform="web",
    )
    case_path = tmp_path / "cases" / "web" / "strict_web.fsq.yaml"
    case_path.write_text(WEB_FSQ_CASE, encoding="utf-8")
    calls = {}

    class FakeWebDriver:
        def __init__(self, **kwargs) -> None:
            calls["driver"] = kwargs

    def fake_run_strict_fsq_core_case(**kwargs):
        calls["strict"] = kwargs
        return _write_fake_core_report(kwargs["output_dir"], kwargs["run_id"])

    monkeypatch.setattr("fsq_agent.core.harness._factory.PlaywrightWebDriver", FakeWebDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "web", "--strict", "--case-yaml", "strict_web.fsq.yaml"])

    assert result.exit_code == 0, result.output
    assert calls["driver"] == {
        "channel": "chrome",
        "executable_path": chrome_path,
        "headless": True,
        "base_url": "https://www.bing.com",
        "viewport": (1280, 720),
    }
    assert calls["strict"]["case_path"] == case_path.resolve()
    assert calls["strict"]["run_id"].startswith("strict_web-")
    assert [step.action_name for step in calls["strict"]["steps"]] == ["start_browser", "navigate_to", "ui_snapshot", "close_browser"]
    assert calls["strict"]["registry"].resolve("uiSnapshot") is not None
    assert calls["strict"]["registry"].resolve("startBrowser") is not None
    assert calls["strict"]["registry"].resolve("tapOn") is None


def test_run_strict_macos_case_builds_macos_harness_from_preset_without_android_app_id(tmp_path: Path, monkeypatch) -> None:
    _config(
        tmp_path,
        """
harness:
  platform: macos
  macos:
    backend: appium_mac2
    appium_server_url: http://127.0.0.1:4723
    page_source_max_depth: 7
    action_timeout_seconds: 11
""",
        platform="macos",
    )
    case_path = tmp_path / "cases" / "macos" / "strict_macos.fsq.yaml"
    case_path.write_text(MACOS_FSQ_CASE, encoding="utf-8")
    calls = {}

    class FakeMacOSDriver:
        def __init__(self, **kwargs) -> None:
            calls["driver"] = kwargs

    def fake_run_strict_fsq_core_case(**kwargs):
        calls["strict"] = kwargs
        return _write_fake_core_report(kwargs["output_dir"], kwargs["run_id"])

    monkeypatch.setattr("fsq_agent.core.harness._factory.AppiumMac2Driver", FakeMacOSDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "macos", "--strict", "--case-yaml", "strict_macos.fsq.yaml"])

    assert result.exit_code == 0, result.output
    assert calls["driver"] == {
        "server_url": "http://127.0.0.1:4723",
        "bundle_id": "com.example.MacApp",
        "app_path": None,
        "page_source_max_depth": 7,
        "action_timeout_seconds": 11,
        "new_command_timeout_seconds": 300,
    }
    assert calls["strict"]["case_path"] == case_path.resolve()
    assert calls["strict"]["run_id"].startswith("strict_macos-")
    assert [step.action_name for step in calls["strict"]["steps"]] == [
        "launch_app",
        "click_on",
        "assert_elements_order",
        "kill_app",
    ]
    assert calls["strict"]["registry"].resolve("assertElementsOrder") is not None
    assert calls["strict"]["registry"].resolve("tapOn") is None


def test_run_strict_windows_case_builds_windows_harness_from_preset_without_android_app_id(tmp_path: Path, monkeypatch) -> None:
    app_path = tmp_path / "windows-app.exe"
    _config(
        tmp_path,
        """
harness:
  platform: windows
  windows:
    backend: pywinauto
    backend_kind: win32
""",
        platform="windows",
    )
    case_path = tmp_path / "cases" / "windows" / "strict_windows.fsq.yaml"
    case_path.write_text(WINDOWS_FSQ_CASE, encoding="utf-8")
    calls = {}

    class FakeWindowsDriver:
        def __init__(self, **kwargs) -> None:
            calls["driver"] = kwargs

    def fake_run_strict_fsq_core_case(**kwargs):
        calls["strict"] = kwargs
        return _write_fake_core_report(kwargs["output_dir"], kwargs["run_id"])

    monkeypatch.setattr("fsq_agent.core.harness._factory.PywinautoWindowsDriver", FakeWindowsDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "windows", "--strict", "--case-yaml", "strict_windows.fsq.yaml"])

    assert result.exit_code == 0, result.output
    assert calls["driver"] == {
        "app_path": app_path,
        "backend_kind": "win32",
        "window_title_re": ".*Legacy App",
        "launch_args": ["--flag", "two words"],
    }
    assert calls["strict"]["case_path"] == case_path.resolve()
    assert calls["strict"]["run_id"].startswith("strict_windows-")
    assert [step.action_name for step in calls["strict"]["steps"]] == ["launch_app", "ui_snapshot", "kill_app"]
    assert calls["strict"]["registry"].resolve("uiSnapshot") is not None


def test_run_strict_rejects_case_platform_mismatch_before_driver_construction(tmp_path: Path, monkeypatch) -> None:
    _config(
        tmp_path,
        """
harness:
  platform: web
""",
        platform="web",
    )
    case_path = tmp_path / "cases" / "web" / "android_case.fsq.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")
    constructed = False

    def fail_driver(**_kwargs):
        nonlocal constructed
        constructed = True
        raise AssertionError("driver should not be constructed")

    monkeypatch.setattr("fsq_agent.core.harness._factory.PlaywrightWebDriver", fail_driver)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "web", "--strict", "--case-yaml", "android_case.fsq.yaml"])

    assert result.exit_code != 0
    assert constructed is False


def test_run_strict_case_dir_continues_and_writes_summary(tmp_path: Path, monkeypatch) -> None:
    _config(
        tmp_path,
        """
harness:
  platform: android
  android:
    backend: uiautomator2
""",
    )
    cases_dir = tmp_path / "cases" / "android"
    (cases_dir / "first.fsq.yaml").write_text(FSQ_CASE.replace("Strict CLI Case", "First Case"), encoding="utf-8")
    (cases_dir / "second.fsq.yaml").write_text(FSQ_CASE.replace("Strict CLI Case", "Second Case"), encoding="utf-8")
    calls = []

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str | None) -> None:
            self.app_id = app_id
            self.serial = serial

    def fake_run_strict_fsq_core_case(**kwargs):
        calls.append(kwargs)
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        report_path = kwargs["output_dir"] / "core-report.md"
        json_report_path = kwargs["output_dir"] / "core-report.json"
        manifest_path = kwargs["output_dir"] / "evidence-manifest.json"
        case_status = "failed" if kwargs["case_path"].name == "second.fsq.yaml" else "passed"
        report_path.write_text("report", encoding="utf-8")
        json_report_path.write_text(
            json.dumps({"summary": {"status": case_status, "failed_steps": 1 if case_status == "failed" else 0}}),
            encoding="utf-8",
        )
        manifest_path.write_text("{}", encoding="utf-8")
        return ReportArtifact(run_id=kwargs["run_id"], path=report_path, evidence_manifest_path=manifest_path)

    monkeypatch.setattr("fsq_agent.core.harness._factory.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--strict", "--case-dir", str(cases_dir)])

    assert result.exit_code == 1, result.output
    assert [call["case_path"].name for call in calls] == ["first.fsq.yaml", "second.fsq.yaml"]
    summary_paths = list((tmp_path / ".fsq" / "runs" / "android").glob("strict-core-batch-*/strict-core-batch-summary.json"))
    assert len(summary_paths) == 1
    summary_path = summary_paths[0]
    markdown_path = summary_path.with_suffix(".md")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert [case["status"] for case in summary["cases"]] == ["passed", "failed"]
    assert "failed_steps=1" in summary["cases"][1]["error"]
    assert "first.fsq.yaml" in markdown_path.read_text(encoding="utf-8")


def test_run_strict_case_dir_excludes_hook_dependencies_from_top_level_summary(tmp_path: Path, monkeypatch) -> None:
    _config(
        tmp_path,
        """
harness:
  platform: android
  android:
    backend: uiautomator2
""",
    )
    cases_dir = tmp_path / "cases" / "android"
    (cases_dir / "root.fsq.yaml").write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Root Case
platform: android
onCaseStart:
  runCase: setup.fsq.yaml
---
- launchApp
""",
        encoding="utf-8",
    )
    (cases_dir / "setup.fsq.yaml").write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Setup Case
platform: android
---
- tapOn:
    target: Setup
""",
        encoding="utf-8",
    )
    calls = []

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str | None) -> None:
            self.app_id = app_id
            self.serial = serial

    def fake_run_strict_fsq_lifecycle_case(**kwargs):
        calls.append(kwargs)
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        report_path = kwargs["output_dir"] / "core-report.md"
        json_report_path = kwargs["output_dir"] / "core-report.json"
        manifest_path = kwargs["output_dir"] / "evidence-manifest.json"
        report_path.write_text("report", encoding="utf-8")
        json_report_path.write_text(json.dumps({"summary": {"status": "passed", "failed_steps": 0}}), encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return ReportArtifact(run_id=kwargs["run_id"], path=report_path, evidence_manifest_path=manifest_path)

    monkeypatch.setattr("fsq_agent.core.harness._factory.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_lifecycle_case", fake_run_strict_fsq_lifecycle_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--strict", "--case-dir", str(cases_dir)])

    assert result.exit_code == 0, result.output
    assert [call["case_path"].name for call in calls] == ["root.fsq.yaml"]
    summary_paths = list((tmp_path / ".fsq" / "runs" / "android").glob("strict-core-batch-*/strict-core-batch-summary.json"))
    assert len(summary_paths) == 1
    summary = json.loads(summary_paths[0].read_text(encoding="utf-8"))
    assert summary["total"] == 1
    assert summary["cases"][0]["case_path"].endswith("root.fsq.yaml")


def test_run_strict_case_dir_excludes_config_hook_dependencies_from_top_level_summary(tmp_path: Path, monkeypatch) -> None:
    _config(
        tmp_path,
        """
harness:
  platform: android
  android:
    backend: uiautomator2
caseLifecycle:
  onCaseStart:
    runCase: setup.fsq.yaml
""",
    )
    cases_dir = tmp_path / "cases" / "android"
    (cases_dir / "root.fsq.yaml").write_text(FSQ_CASE.replace("Strict CLI Case", "Root Case"), encoding="utf-8")
    (cases_dir / "setup.fsq.yaml").write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Setup Case
platform: android
---
- tapOn:
    target: Setup
""",
        encoding="utf-8",
    )
    calls = []

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str | None) -> None:
            self.app_id = app_id
            self.serial = serial

    def fake_run_strict_fsq_lifecycle_case(**kwargs):
        calls.append(kwargs)
        return _write_fake_core_report(kwargs["output_dir"], kwargs["run_id"])

    monkeypatch.setattr("fsq_agent.core.harness._factory.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_lifecycle_case", fake_run_strict_fsq_lifecycle_case)

    result = CliRunner().invoke(main, ["run", "--workspace", "test-workspace", "--platform", "android", "--strict", "--case-dir", str(cases_dir)])

    assert result.exit_code == 0, result.output
    assert [call["case_path"].name for call in calls] == ["root.fsq.yaml"]


def test_report_command_resolves_llm_and_strict_reports(tmp_path: Path) -> None:
    _config(tmp_path)
    runs_dir = tmp_path / ".fsq" / "runs" / "android"
    llm_dir = runs_dir / "llm-run"
    strict_dir = runs_dir / "strict-run"
    llm_dir.mkdir(parents=True)
    strict_dir.mkdir(parents=True)
    (llm_dir / "report.md").write_text("llm report", encoding="utf-8")
    (strict_dir / "core-report.md").write_text("strict report", encoding="utf-8")
    runner = CliRunner()

    llm_result = runner.invoke(main, ["report", "--workspace", "test-workspace", "--platform", "android", "--run-id", "llm-run"])
    strict_result = runner.invoke(main, ["report", "--workspace", "test-workspace", "--platform", "android", "--run-id", "strict-run"])

    assert llm_result.exit_code == 0, llm_result.output
    assert "llm report" in llm_result.output
    assert strict_result.exit_code == 0, strict_result.output
    assert "strict report" in strict_result.output


def test_playground_command_loads_registered_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _config(tmp_path)
    captured: dict[str, object] = {}

    def fake_run_playground(settings, options) -> None:
        captured.update(
            workspace_path=settings.workspace.root_dir,
            host=options.host,
            port=options.port,
            open_browser=options.open_browser,
        )

    monkeypatch.setattr("fsq_agent.cli._main.run_playground", fake_run_playground)

    result = CliRunner().invoke(
        main,
        ["playground", "--workspace", "TEST-WORKSPACE", "--platform", "android", "--host", "localhost", "--port", "9001", "--no-open-browser"],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "workspace_path": tmp_path.resolve(),
        "host": "localhost",
        "port": 9001,
        "open_browser": False,
    }


def test_task_from_goal_creates_goal_only_task() -> None:
    task = _task_from_goal("  Access Downloads through the overflow menu.  ")

    assert task.id == "access-downloads-through-the-overflow-menu"
    assert task.name == "Access Downloads through the overflow menu."
    assert task.planning_reference_kind == "goal"
    assert task.planning_reference_text == "Access Downloads through the overflow menu."
    assert task.key_actions == []
    assert task.verification_goal is None


def test_task_from_raw_case_source_preserves_full_content_as_planning_reference(tmp_path: Path) -> None:
    case_path = tmp_path / "verify_settings.fsq.yaml"
    content = """schemaVersion: fsq.ai-test/v1
name: Verify Settings
---
- launchApp
- tapOn: Microsoft services
"""

    task = _task_from_raw_case_source(case_path, content)

    assert task.planning_reference_kind == "raw_case"
    assert task.planning_reference_text is not None
    assert f"Source path: {case_path}" in task.planning_reference_text
    assert content in task.planning_reference_text
    assert "Microsoft services" in task.planning_reference_text
    assert task.verification_goal is None
