# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fsq_agent.application import ApplicationError, ApplicationErrorCode, ExportRunReportRequest, GetRunReportRequest, export_run_report, get_run_report, runs
from fsq_agent.execution import RunLifecycleService, RunSource, allocate_run
from fsq_agent.models import EvidenceBundle, RunnerStepResult


def _scope(root: Path, monkeypatch):
    monkeypatch.setattr(runs, "list_workspace_registry", lambda: [SimpleNamespace(name="demo", root_path=root)])
    monkeypatch.setattr(runs, "inspect_registered_workspace", lambda _name, *args, **kwargs: SimpleNamespace(platforms=[SimpleNamespace(platform="web")]))
    metadata = allocate_run(workspace=root, workspace_name="demo", platform="web", source_id="search", mode="strict", source=RunSource(kind="case", case_id="search"))
    directory = root / ".fsq/runs/web" / metadata.run_id
    service = RunLifecycleService()
    metadata = service.snapshot_sources(directory, metadata, sources={"case": b"name: search\n"})
    frozen = service.freeze(
        directory,
        metadata,
        bundle=EvidenceBundle(bundle_id="e", run_id=metadata.run_id, steps=[RunnerStepResult(step_id="one", status="failed", failure_category="assertion_error", error_message="Missing heading")]),
    )
    service.finalize(directory, metadata, execution_result=frozen)
    return metadata, directory


def test_failed_run_export_preserves_facts_and_needs_no_provider(tmp_path, monkeypatch):
    metadata, directory = _scope(tmp_path, monkeypatch)
    before = (directory / "run.json").read_bytes()
    report = get_run_report(GetRunReportRequest(workspace_name="demo", run_id=metadata.run_id, platform="web"))
    assert report.report.run["gate"]["status"] != "passed"
    result = export_run_report(ExportRunReportRequest(current_directory=tmp_path, run_id=metadata.run_id, format="json"))
    assert result.output_path.is_file()
    assert json.loads(result.output_path.read_text())["schema_version"] == "fsq.report/v1"
    assert (directory / "run.json").read_bytes() == before


def test_untrustworthy_source_export_maps_to_report_unavailable(tmp_path, monkeypatch):
    metadata, directory = _scope(tmp_path, monkeypatch)
    persisted = json.loads((directory / "run.json").read_text())
    (directory / persisted["source"]["snapshot_path"]).unlink()
    with pytest.raises(ApplicationError) as error:
        export_run_report(ExportRunReportRequest(current_directory=tmp_path, run_id=metadata.run_id, format="json"))
    assert error.value.code == ApplicationErrorCode.RUN_REPORT_UNAVAILABLE
    assert error.value.details["reason"] == "source_identity_unavailable"


def test_export_does_not_overwrite_explicit_destination(tmp_path, monkeypatch):
    metadata, _ = _scope(tmp_path, monkeypatch)
    output = tmp_path / "keep.json"
    output.write_text("unchanged")
    with pytest.raises(Exception, match="exists"):
        export_run_report(ExportRunReportRequest(current_directory=tmp_path, run_id=metadata.run_id, format="json", output_path=output))
    assert output.read_text() == "unchanged"


def test_scope_requires_exactly_one_selector():
    with pytest.raises(ValueError, match="exactly one"):
        GetRunReportRequest(current_directory=Path(), workspace_name="demo", run_id="run")
