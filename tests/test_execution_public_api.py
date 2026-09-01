# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import importlib
from dataclasses import FrozenInstanceError

import pytest

from fsq_agent import execution


def test_lifecycle_public_module_is_canonical() -> None:
    canonical = importlib.import_module("fsq_agent.execution.lifecycle")
    assert execution.run_strict_lifecycle_case is canonical.run_strict_lifecycle_case
    assert execution.collect_strict_lifecycle_cases is canonical.collect_strict_lifecycle_cases


def test_recording_exposes_only_service_and_immutable_result() -> None:
    assert execution.RecordingService.__module__ == "fsq_agent.execution.recording"
    assert execution.RecordingResult.__module__ == "fsq_agent.execution.recording"
    assert not hasattr(execution.RecordingResult, "from_recording")
    assert not hasattr(execution, "StrictCaseRecording")
    assert not hasattr(execution, "record_dynamic_run_as_strict_case")


def test_cli_uses_canonical_deterministic_module() -> None:
    canonical = importlib.import_module("fsq_agent.execution.deterministic")
    legacy = importlib.import_module("fsq_agent.adapters.cli._core_execution")

    assert legacy is canonical
    assert execution.run_fsq_core_case is canonical.run_fsq_core_case
    assert execution.run_strict_fsq_core_case is canonical.run_strict_fsq_core_case


def test_recording_result_is_immutable(tmp_path) -> None:
    result = execution.RecordingResult(
        status="recorded",
        recording_path=tmp_path / "recording.json",
        recorded_case_path=None,
        published_case_path=None,
        command_count=0,
        required_runtime_secret_names=(),
        warnings=(),
        skipped_tool_calls=({"reason": "not replayable"},),
        errors=(),
        validation_status="passed",
        draft=False,
    )

    with pytest.raises(FrozenInstanceError):
        result.status = "failed"

    with pytest.raises(TypeError):
        result.skipped_tool_calls[0]["reason"] = "changed"
