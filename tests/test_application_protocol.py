# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json

import pytest
from click.testing import CliRunner

from fsq_agent.application import (
    ApplicationError,
    ApplicationErrorCategory,
    ApplicationErrorCode,
    ProviderStatusResult,
    event_record,
    normalize_application_error,
    result_record,
)
from fsq_agent.cli import main
from fsq_agent.models import ConfigurationError


def test_protocol_records_have_stable_discriminators() -> None:
    event = event_record({"sequence": 1}, operation="case.create")
    result = result_record({"status": "success"}, operation="case.create")
    assert event["type"] == "event"
    assert event["event"] == {"sequence": 1}
    assert result["type"] == "result"
    assert result["result"] == {"status": "success"}
    for record in (event, result):
        assert record["schema_version"] == "fsq.machine/v1"
        assert record["operation"] == "case.create"
        assert record["timestamp"]
    error = ApplicationError(
        code=ApplicationErrorCode.PROVIDER_UNAVAILABLE,
        category=ApplicationErrorCategory.UNAVAILABLE,
        message="offline",
    )
    assert error.to_record()["type"] == "error"


def test_configuration_error_is_normalized_without_traceback() -> None:
    error = normalize_application_error(ConfigurationError("Bad config", context={"field": "provider"}))
    assert error.code == ApplicationErrorCode.CONFIGURATION_INVALID
    assert error.category == ApplicationErrorCategory.CONFIGURATION
    assert error.details == {"field": "provider"}


@pytest.mark.parametrize(
    ("category", "expected_exit"),
    [
        (ApplicationErrorCategory.REQUEST_VALIDATION, 2),
        (ApplicationErrorCategory.WORKSPACE_CONFIGURATION, 3),
        (ApplicationErrorCategory.CONFIGURATION, 3),
        (ApplicationErrorCategory.UNAVAILABLE, 4),
        (ApplicationErrorCategory.INTERNAL, 5),
    ],
)
def test_machine_error_category_maps_to_exit_code(monkeypatch, category, expected_exit) -> None:
    code = ApplicationErrorCode.INTERNAL_ERROR
    if category == ApplicationErrorCategory.UNAVAILABLE:
        code = ApplicationErrorCode.PROVIDER_UNAVAILABLE
    monkeypatch.setattr(
        "fsq_agent.adapters.cli._main.test_case",
        lambda _request: (_ for _ in ()).throw(ApplicationError(code=code, category=category, message="failure")),
    )
    result = CliRunner().invoke(main, ["--output", "json", "case", "test", "--platform", "web", "case.fsq.yaml"])
    assert result.exit_code == expected_exit
    record = json.loads(result.output)
    assert record["type"] == "error"
    assert record["error"]["category"] == category.value
    assert "Traceback" not in result.output


@pytest.mark.parametrize("output", ["json", "jsonl"])
def test_machine_usage_error_is_a_terminal_error_record(output: str) -> None:
    result = CliRunner().invoke(main, ["--output", output, "case", "test"])
    assert result.exit_code == 2
    records = [json.loads(line) for line in result.output.splitlines()]
    assert records[-1]["type"] == "error"
    assert records[-1]["error"]["category"] == "request_validation"
    assert "Usage:" not in result.output


def test_unexpected_command_exception_is_safe_internal_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.adapters.cli._main.provider_status",
        lambda: (_ for _ in ()).throw(RuntimeError("sensitive implementation detail")),
    )
    result = CliRunner().invoke(main, ["--output", "json", "providers", "status"])
    assert result.exit_code == 5
    record = json.loads(result.output)
    assert record["error"]["code"] == "internal.error"
    assert "sensitive implementation detail" not in result.output
    assert "Traceback" not in result.output


def test_jsonl_command_without_progress_emits_one_terminal_result(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "fsq_agent.adapters.cli._main.provider_status",
        lambda: ProviderStatusResult(
            status="ready",
            configured=True,
            provider="azure_openai",
            model="gpt-5",
            authenticated=True,
            message="Ready.",
        ),
    )
    result = CliRunner().invoke(main, ["--output", "jsonl", "providers", "status"])
    assert result.exit_code == 0
    records = [json.loads(line) for line in result.output.splitlines()]
    assert len(records) == 1
    assert records[0]["type"] == "result"
    assert records[0]["operation"] == "providers.status"
