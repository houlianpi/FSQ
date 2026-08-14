# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path

from click.testing import CliRunner

from fsq_agent.application import CaseCreateResult, CaseTestResult
from fsq_agent.cli import main


def _workspace(path: Path) -> None:
    root = path / ".fsq-agent-workspace"
    root.mkdir()
    (root / ".fsq-agent-workspace").write_text("fsq-agent workspace\n", encoding="utf-8")


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


def test_supporting_commands_require_current_workspace(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        _workspace(Path.cwd())
        result = runner.invoke(main, ["--output", "json", "providers", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["result"]) == 2


def test_case_create_json_maps_application_result(tmp_path: Path, monkeypatch) -> None:
    async def fake_create(_request, *, event_sink=None):
        return CaseCreateResult(run_id="run-1", task_id="task-1", status="success", summary="passed", report_path=tmp_path / "report.md", candidate_case_path=tmp_path / "recorded.fsq.yaml")

    monkeypatch.setattr("fsq_agent.cli._main.create_case", fake_create)
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["--output", "json", "case", "create", "--platform", "web", "--goal", "Verify search"])
    assert result.exit_code == 0
    assert json.loads(result.output)["result"]["candidate_case_path"].endswith("recorded.fsq.yaml")


def test_case_test_failure_uses_exit_one_and_jsonl_terminal_record(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("fsq_agent.cli._main.test_case", lambda _request: CaseTestResult(run_id="run-1", status="failed", summary="failed", report_path=tmp_path / "core-report.md"))
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


def test_non_interactive_provider_configuration_is_rejected(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        _workspace(Path.cwd())
        result = runner.invoke(main, ["--non-interactive", "providers", "configure", "github_copilot"])
    assert result.exit_code == 2
    assert "interactive terminal" in result.output


def test_runs_logs_jsonl_emits_one_record_per_event(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        _workspace(Path.cwd())
        run = Path.cwd() / ".fsq-agent-workspace" / "output" / "runs" / "run-1"
        run.mkdir(parents=True)
        lines = [json.dumps({"type": "started"}), json.dumps({"type": "completed"})]
        (run / "events.jsonl").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        result = runner.invoke(main, ["--output", "jsonl", "runs", "logs", "run-1"])
    assert result.exit_code == 0
    records = [json.loads(line) for line in result.output.splitlines()]
    assert [record["type"] for record in records] == ["event", "event", "result"]
    assert [record["event"]["type"] for record in records[:-1]] == ["started", "completed"]
    assert records[-1]["result"]["event_count"] == 2
