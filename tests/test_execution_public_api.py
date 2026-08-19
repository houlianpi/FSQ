# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import importlib
from dataclasses import FrozenInstanceError

import pytest

from fsq_agent import execution


def test_lifecycle_compatibility_module_is_canonical_module() -> None:
    canonical = importlib.import_module("fsq_agent.execution.lifecycle")
    legacy = importlib.import_module("fsq_agent._strict_lifecycle")

    assert legacy is canonical
    assert execution.run_strict_lifecycle_case is canonical.run_strict_lifecycle_case
    assert execution.collect_strict_lifecycle_cases is canonical.collect_strict_lifecycle_cases


def test_recording_compatibility_module_is_canonical_module() -> None:
    canonical = importlib.import_module("fsq_agent.execution.recording")
    legacy = importlib.import_module("fsq_agent._strict_case_recording")

    assert legacy is canonical
    assert execution.StrictCaseRecording is canonical.StrictCaseRecording
    assert execution.record_dynamic_run_as_strict_case is canonical.record_dynamic_run_as_strict_case


def test_cli_deterministic_compatibility_module_is_canonical_module() -> None:
    canonical = importlib.import_module("fsq_agent.execution.deterministic")
    legacy = importlib.import_module("fsq_agent.cli._core_execution")

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
        skipped_tool_calls=(),
        errors=(),
        validation_status="passed",
        draft=False,
    )

    with pytest.raises(FrozenInstanceError):
        result.status = "failed"
