# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fsq_agent.application import ApplicationError, ApplicationErrorCode, CaseTestRequest
from fsq_agent.application import _case_test as case_test_module


@pytest.mark.parametrize("platform", ["android", "web", "windows", "macos"])
def test_case_test_request_supports_all_public_platforms(platform: str, tmp_path: Path) -> None:
    request = CaseTestRequest(current_directory=tmp_path, platform=platform, case_path=Path("case.fsq.yaml"))
    assert request.platform == platform


def test_case_test_rejects_missing_case_with_stable_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / ".fsq-agent-workspace"
    workspace.mkdir()
    (workspace / ".fsq-agent-workspace").write_text("fsq-agent workspace\n", encoding="utf-8")
    settings = SimpleNamespace(cases=SimpleNamespace(dir=tmp_path / "cases"))
    monkeypatch.setattr(case_test_module, "load_platform_settings", lambda *_args: settings)

    with pytest.raises(ApplicationError) as error:
        case_test_module.test_case(CaseTestRequest(current_directory=tmp_path, platform="web", case_path=Path("missing.fsq.yaml")))

    assert error.value.code == ApplicationErrorCode.CASE_NOT_FOUND


def test_suggestion_artifact_is_fact_based_and_source_immutable(tmp_path: Path) -> None:
    source = tmp_path / "search.fsq.yaml"
    original = "schemaVersion: fsq.ai-test/v1\n"
    source.write_text(original, encoding="utf-8")

    suggestion = case_test_module._write_suggestion(tmp_path, source, "failed", "Case failed with 1 failed step.")
    payload = json.loads(suggestion.read_text(encoding="utf-8"))

    assert payload["source_case_immutable"] is True
    assert payload["suggestions"]
    assert payload["suggestions"][0]["evidence"] == "core-report.json"
    assert source.read_text(encoding="utf-8") == original


def test_deprecated_suffix_warning_is_machine_visible() -> None:
    from fsq_agent.application import CaseTestResult

    result = CaseTestResult(
        run_id="run-1",
        status="success",
        summary="passed",
        report_path=Path("report.md"),
        warnings=["case.suffix_deprecated: rename this Case to *.fsq.yaml"],
    )
    assert result.model_dump(mode="json")["warnings"][0].startswith("case.suffix_deprecated")
