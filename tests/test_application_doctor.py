# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
from types import SimpleNamespace

import pytest

from fsq_agent.application import ApplicationError, DoctorRequest, diagnose_workspace
from fsq_agent.models import PlatformRuntimeCheck, WorkspacePlatformStatus, WorkspaceRegistryEntry, WorkspaceStatus


def _platform(platform: str, root: Path, status: str = "available") -> WorkspacePlatformStatus:
    return WorkspacePlatformStatus(
        platform=platform,
        config_path=root / ".fsq" / "config" / f"config.{platform}.yaml",
        status=status,
        message="available" if status == "available" else "damaged",
        action=None if status == "available" else f"Repair config.{platform}.yaml manually.",
    )


def _settings(platform: str):
    return SimpleNamespace(harness=SimpleNamespace(platform=platform))


def _base(monkeypatch: pytest.MonkeyPatch, root: Path, platforms: list[WorkspacePlatformStatus]) -> None:
    monkeypatch.setattr("fsq_agent.application.doctor.list_workspace_registry", lambda: [WorkspaceRegistryEntry(name="checkout", root_path=root)])
    monkeypatch.setattr(
        "fsq_agent.application.doctor.inspect_registered_workspace",
        lambda _name: WorkspaceStatus(name="checkout", root_path=root, status="partial", message="checked", platforms=platforms),
    )
    monkeypatch.setattr("fsq_agent.application.doctor.load_platform_settings", lambda platform, _root: _settings(platform))
    monkeypatch.setattr("fsq_agent.application.doctor.validate_strict_core_settings", lambda _settings: None)
    monkeypatch.setattr("fsq_agent.application.doctor.CapabilityDefinitionFactory.platform_definitions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("fsq_agent.application.doctor.CommonPlatformTools.capability_definitions", list)
    monkeypatch.setattr("fsq_agent.application.doctor.check_dynamic_agent_readiness", lambda _settings: (True, "ready", ""))
    monkeypatch.setattr(
        "fsq_agent.application.doctor.PlatformRuntimeService.check",
        lambda _self, platform: PlatformRuntimeCheck(platform=platform, status="ready", ready=True, message="ready"),
    )
    monkeypatch.setattr("fsq_agent.application.doctor.PlatformRuntimeService.check_target_configuration", lambda *_args: (True, "ready", ""))
    monkeypatch.setattr("fsq_agent.application.doctor.PlatformRuntimeService.check_target_availability", lambda *_args: (True, "ready", ""))
    monkeypatch.setattr("fsq_agent.application.doctor.check_provider_readiness", lambda _settings: (True, "ready", ""))
    monkeypatch.setattr("fsq_agent.application.doctor.check_case_suggestion_readiness", lambda _settings: (True, "ready", ""))


def test_doctor_reports_configured_platforms_in_canonical_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _base(monkeypatch, tmp_path, [_platform("macos", tmp_path), _platform("android", tmp_path), _platform("web", tmp_path)])

    result = diagnose_workspace(DoctorRequest(current_directory=tmp_path))

    assert result.status == "ready"
    assert [item.platform for item in result.platforms] == ["android", "web", "macos"]
    assert all(item.commands.case_test.status == "ready" for item in result.platforms)


def test_provider_failure_keeps_case_test_ready_and_ai_commands_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _base(monkeypatch, tmp_path, [_platform("web", tmp_path)])
    monkeypatch.setattr(
        "fsq_agent.application.doctor.check_provider_readiness",
        lambda _settings: (False, "Provider unavailable.", "Configure Provider."),
    )

    result = diagnose_workspace(DoctorRequest(current_directory=tmp_path))

    platform = result.platforms[0]
    assert result.status == "partial"
    assert platform.commands.case_test.status == "ready"
    assert platform.commands.case_test_suggest.status == "unavailable"
    assert platform.commands.case_create.status == "unavailable"
    assert result.actions == ("Configure Provider.",)


def test_damaged_platform_does_not_abort_other_platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _base(monkeypatch, tmp_path, [_platform("android", tmp_path, "unavailable"), _platform("web", tmp_path)])

    result = diagnose_workspace(DoctorRequest(current_directory=tmp_path))

    assert result.status == "partial"
    assert result.platforms[0].status == "unavailable"
    assert result.platforms[1].status == "ready"


def test_component_exception_is_safe_and_other_checks_continue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _base(monkeypatch, tmp_path, [_platform("web", tmp_path)])

    def fail(_settings):
        raise RuntimeError("secret backend detail")

    monkeypatch.setattr("fsq_agent.application.doctor.check_provider_readiness", fail)
    result = diagnose_workspace(DoctorRequest(current_directory=tmp_path))
    payload = result.model_dump_json()

    assert result.platforms[0].checks.provider.status == "error"
    assert result.platforms[0].checks.strict_core.status == "ready"
    assert "secret backend detail" not in payload


def test_target_configuration_failure_is_error_not_external_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _base(monkeypatch, tmp_path, [_platform("web", tmp_path)])
    monkeypatch.setattr(
        "fsq_agent.application.doctor.PlatformRuntimeService.check_target_configuration",
        lambda *_args: (False, "Target configuration is invalid.", "Repair Target configuration."),
    )

    result = diagnose_workspace(DoctorRequest(current_directory=tmp_path))

    detail = result.platforms[0].checks.target_configuration
    assert detail.status == "error"
    assert detail.code == "doctor.target_configuration_invalid"


def test_doctor_rejects_unregistered_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fsq_agent.application.doctor.list_workspace_registry", list)

    with pytest.raises(ApplicationError) as error:
        diagnose_workspace(DoctorRequest(current_directory=tmp_path))

    assert error.value.code.value == "workspace.not_initialized"


def test_doctor_normalizes_unreadable_registry_as_workspace_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_registry():
        raise ValueError("unsafe registry detail")

    monkeypatch.setattr("fsq_agent.application.doctor.list_workspace_registry", fail_registry)

    with pytest.raises(ApplicationError) as error:
        diagnose_workspace(DoctorRequest(current_directory=tmp_path))

    assert error.value.category.value == "workspace_configuration"
    assert "unsafe registry detail" not in error.value.message


def test_doctor_result_collections_are_immutable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _base(monkeypatch, tmp_path, [_platform("web", tmp_path)])

    result = diagnose_workspace(DoctorRequest(current_directory=tmp_path))

    assert isinstance(result.platforms, tuple)
    assert isinstance(result.actions, tuple)
