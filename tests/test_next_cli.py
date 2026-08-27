# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path

from click.testing import CliRunner

from fsq_agent.application import CaseCreateResult, CaseTestResult, WorkspaceInitializeResult
from fsq_agent.cli import main


def _workspace(path: Path, monkeypatch=None) -> None:
    if monkeypatch is not None:
        monkeypatch.setattr("fsq_agent.adapters.cli._main.require_initialized_workspace", lambda _request: type("Workspace", (), {"workspace": path.resolve()})())


def test_public_command_tree() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    for command in ("init", "doctor", "case", "ui", "providers", "runs", "environments"):
        assert command in result.output
    for removed in ("run", "report", "playground", "control-plane"):
        assert f"  {removed} " not in result.output


def test_workspace_error_is_machine_readable(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["--output", "json", "doctor"])
    assert result.exit_code == 3
    payload = json.loads(result.output)
    assert payload["type"] == "error"
    assert payload["error"]["code"] == "workspace.not_initialized"


def test_case_test_exposes_suggest_option() -> None:
    result = CliRunner().invoke(main, ["case", "test", "--help"])
    assert result.exit_code == 0
    assert "--suggest" in result.output


def test_supporting_commands_require_current_workspace(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        _workspace(Path.cwd(), monkeypatch)
        result = runner.invoke(main, ["--output", "json", "providers", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["result"]) == 2


def test_case_create_json_maps_application_result(tmp_path: Path, monkeypatch) -> None:
    async def fake_create(_request, *, event_sink=None, agent_factory=None):
        return CaseCreateResult(run_id="run-1", task_id="task-1", status="success", summary="passed", report_path=tmp_path / "report.md", candidate_case_path=tmp_path / "recorded.fsq.yaml")

    monkeypatch.setattr("fsq_agent.adapters.cli._main.create_case", fake_create)
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["--output", "json", "case", "create", "--platform", "web", "--goal", "Verify search"])
    assert result.exit_code == 0
    assert json.loads(result.output)["result"]["candidate_case_path"].endswith("recorded.fsq.yaml")


def test_case_test_failure_uses_exit_one_and_jsonl_terminal_record(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("fsq_agent.adapters.cli._main.test_case", lambda _request: CaseTestResult(run_id="run-1", status="failed", summary="failed", report_path=tmp_path / "core-report.md"))
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["--output", "jsonl", "case", "test", "--platform", "web", "search.fsq.yaml"])
    assert result.exit_code == 1
    terminal = json.loads(result.output)
    assert terminal["type"] == "result"
    assert terminal["result"]["status"] == "failed"


def test_legacy_commands_are_rejected_as_usage_errors() -> None:
    for command in ("run", "replay", "report", "playground", "control-plane"):
        result = CliRunner().invoke(main, [command])
        assert result.exit_code == 2
        assert "No such command" in result.output


def test_non_interactive_provider_configuration_is_rejected(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        _workspace(Path.cwd(), monkeypatch)
        result = runner.invoke(main, ["--non-interactive", "providers", "configure", "github_copilot"])
    assert result.exit_code == 2
    assert "interactive terminal" in result.output


def test_ui_starts_control_plane_from_non_workspace_directory(tmp_path: Path, monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr("fsq_agent.adapters.cli._main.run_control_plane", lambda options: captured.update(options=options))

    def fail_if_workspace_required(_request) -> None:
        raise AssertionError("fsq ui must not require the current directory to be a workspace")

    monkeypatch.setattr("fsq_agent.adapters.cli._main.require_initialized_workspace", fail_if_workspace_required)
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        assert not (Path.cwd() / ".fsq").exists()
        result = runner.invoke(main, ["ui", "--host", "127.0.0.2", "--port", "9000", "--no-open-browser"])
    assert result.exit_code == 0
    options = captured["options"]
    assert options.host == "127.0.0.2"
    assert options.port == 9000
    assert options.open_browser is False


def test_internal_error_human_output_exposes_only_safe_exception_type(monkeypatch) -> None:
    def fail() -> None:
        raise RuntimeError("secret backend detail")

    monkeypatch.setattr("fsq_agent.adapters.cli._main.list_providers", fail)
    monkeypatch.setattr("fsq_agent.adapters.cli._main.require_initialized_workspace", lambda _request: type("Workspace", (), {"workspace": Path.cwd()})())
    result = CliRunner().invoke(main, ["providers", "list"])
    assert result.exit_code == 5
    assert "Diagnostic: RuntimeError" in result.output
    assert "secret backend detail" not in result.output
    assert "Traceback" not in result.output


def test_internal_error_machine_output_contains_only_safe_exception_type(monkeypatch) -> None:
    def fail() -> None:
        raise RuntimeError("secret backend detail")

    monkeypatch.setattr("fsq_agent.adapters.cli._main.list_providers", fail)
    monkeypatch.setattr("fsq_agent.adapters.cli._main.require_initialized_workspace", lambda _request: type("Workspace", (), {"workspace": Path.cwd()})())
    for output in ("json", "jsonl"):
        result = CliRunner().invoke(main, ["--output", output, "providers", "list"])
        assert result.exit_code == 5
        payload = json.loads(result.output)
        assert payload["error"]["details"] == {"exception_type": "RuntimeError"}
        assert "secret backend detail" not in result.output
        assert "Traceback" not in result.output


def test_runs_logs_jsonl_emits_one_record_per_event(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        _workspace(Path.cwd(), monkeypatch)
        run = Path.cwd() / ".fsq" / "runs" / "run-1"
        run.mkdir(parents=True)
        monkeypatch.setattr("fsq_agent.adapters.cli._main._runs_dir", lambda: Path.cwd() / ".fsq" / "runs")
        lines = [json.dumps({"type": "started"}), json.dumps({"type": "completed"})]
        (run / "events.jsonl").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        result = runner.invoke(main, ["--output", "jsonl", "runs", "logs", "run-1"])
    assert result.exit_code == 0
    records = [json.loads(line) for line in result.output.splitlines()]
    assert [record["type"] for record in records] == ["event", "event", "result"]
    assert [record["event"]["type"] for record in records[:-1]] == ["started", "completed"]
    assert records[-1]["result"]["event_count"] == 2


def test_runs_use_canonical_platform_directory(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        workspace = Path.cwd()
        _workspace(workspace, monkeypatch)
        config_dir = workspace / ".fsq" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "config.web.yaml").write_text("version: 2\n", encoding="utf-8")
        run = workspace / ".fsq" / "runs" / "web" / "run-1"
        run.mkdir(parents=True)

        result = runner.invoke(main, ["--output", "json", "runs", "list"])

    assert result.exit_code == 0
    assert json.loads(result.output)["result"][0]["run_id"] == "run-1"


def test_init_maps_web_options_to_application(monkeypatch, tmp_path: Path) -> None:
    captured = {}
    monkeypatch.setattr(
        "fsq_agent.adapters.cli._main.initialize_workspace",
        lambda request: (
            captured.update(request=request)
            or WorkspaceInitializeResult(status="initialized", name="project", root_path=tmp_path, platform="web", driver_status="ready", browser_executable_path=tmp_path / "chrome")
        ),
    )
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "--platform", "web", "--browser-channel", "chrome"])
    assert result.exit_code == 0
    assert captured["request"].browser_channel == "chrome"
    assert captured["request"].browser_executable_path is None


def test_init_rejects_install_driver_option() -> None:
    result = CliRunner().invoke(main, ["init", "--platform", "web", "--browser-channel", "chrome", "--install-driver"])

    assert result.exit_code == 2
    assert "No such option: --install-driver" in result.output
