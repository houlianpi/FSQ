# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

import pytest

from fsq_agent.application import configure_provider, list_runs, read_run_logs, show_run


def _workspace(root: Path) -> None:
    workspace = root / ".fsq-agent-workspace"
    workspace.mkdir()
    (workspace / ".fsq-agent-workspace").write_text("fsq-agent workspace\n", encoding="utf-8")


def test_run_queries_list_show_and_stream_logs(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run = runs / "run-1"
    run.mkdir(parents=True)
    (run / "report.md").write_text("report", encoding="utf-8")
    (run / "events.jsonl").write_text('{"type":"started"}\n{"type":"completed"}\n', encoding="utf-8")

    assert [item.run_id for item in list_runs(runs)] == ["run-1"]
    assert show_run(runs, "run-1")["artifacts"] == ["events.jsonl", "report.md"]
    assert [item["type"] for item in read_run_logs(runs, "run-1")] == ["started", "completed"]


@pytest.mark.parametrize("run_id", ["../escape", "missing"])
def test_run_queries_reject_escape_and_missing_runs(tmp_path: Path, run_id: str) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    with pytest.raises(FileNotFoundError):
        show_run(runs, run_id)


def test_configure_provider_preserves_unrelated_env_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.application._provider.require_initialized_workspace",
        lambda _request: type("Workspace", (), {"workspace": tmp_path})(),
    )
    env = tmp_path / ".env"
    env.write_text("OTHER=value\nFSQ_LLM_PROVIDER=github_copilot\n", encoding="utf-8")

    result = configure_provider(tmp_path, "azure_openai")

    assert result.name == "azure_openai"
    assert result.selected is True
    assert env.read_text(encoding="utf-8") == "OTHER=value\nFSQ_LLM_PROVIDER=azure_openai\n"
