# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import subprocess
from pathlib import Path

import pytest

from fsq_agent._capability_bootstrap import build_capability_registry
from fsq_agent._strict_lifecycle import _run_shell_command, collect_strict_lifecycle_cases, run_strict_lifecycle_case
from fsq_agent.config import Settings
from fsq_agent.core import EvidenceRecorder
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import (
    ConfigurationError,
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    PostActionDelaySettings,
    StepPhase,
)


class LifecycleHarness:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def get_context(self) -> HarnessContext:
        return HarnessContext(platform="android", session_id="session-1")

    def action_space(self) -> dict[str, object]:
        return {}

    def before_action(self, step: ExecutableStep, context: HarnessContext) -> None:
        return None

    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        self.actions.append(step.action_name)
        return HarnessActionResult(status="passed", action_name=step.action_name)

    def after_action(
        self,
        step: ExecutableStep,
        context: HarnessContext,
        action_result: HarnessActionResult | None,
    ) -> None:
        return None

    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        return HarnessArtifactRef(
            artifact_id=f"{step_id}-{phase}-{kind}",
            kind=kind,
            path=Path(f"artifacts/raw/{step_id}-{phase}-{reason}.{kind}"),
        )

    def classify_error(self, error: BaseException, phase: StepPhase, step: ExecutableStep) -> FailureCategory:
        return "unknown"


def test_shared_lifecycle_runs_config_case_child_main_and_after_in_one_manifest(tmp_path: Path) -> None:
    child_path = tmp_path / "child.codex.yaml"
    child_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Child\nplatform: android\n---\n- tapOn:\n    target: Child target\n",
        encoding="utf-8",
    )
    root_path = tmp_path / "root.codex.yaml"
    root_path.write_text(
        "schemaVersion: fsq.ai-test/v1\n"
        "name: Root\n"
        "platform: android\n"
        "appId: com.example\n"
        "onCaseStart:\n"
        "- runCase: child.codex.yaml\n"
        "onCaseComplete:\n"
        "- runShell: echo case-after\n"
        "---\n"
        "- launchApp: {}\n",
        encoding="utf-8",
    )
    settings = Settings(
        cases={"dir": tmp_path},
        case_lifecycle={
            "onCaseStart": [{"runShell": "echo config-before"}],
            "onCaseComplete": [{"runShell": "echo config-after"}],
        },
    )
    case = FsqCaseLoader().load_case(root_path)
    registry = build_capability_registry(platform="android")
    harness = LifecycleHarness()
    run_dir = tmp_path / "runs" / "root"
    recorder = EvidenceRecorder(run_id="root", output_dir=run_dir)
    cancellation_checks: list[str] = []

    artifact = run_strict_lifecycle_case(
        case_path=root_path,
        case=case,
        settings=settings,
        harness=harness,
        output_dir=run_dir,
        run_id="root",
        registry=registry,
        registry_snapshot=registry.snapshot(),
        post_action_delay_seconds=PostActionDelaySettings(platform=0, common=0),
        recorder=recorder,
        resolve_steps=lambda steps, _case: steps,
        cancellation_check=lambda: cancellation_checks.append("check"),
    )

    manifest = json.loads(artifact.evidence_manifest_path.read_text(encoding="utf-8"))
    steps = manifest["steps"]
    assert harness.actions == ["tap_on", "launch_app"]
    assert [step["metadata"].get("command") for step in steps if step["metadata"].get("command")] == [
        "echo config-before",
        "echo case-after",
        "echo config-after",
    ]
    assert any(step["metadata"].get("hook_action_name") == "runCase" for step in steps)
    assert any(step.get("source_ref", {}).get("metadata", {}).get("lifecycle_phase") == "case" for step in steps)
    assert len(cancellation_checks) >= 5
    assert artifact.path == run_dir / "core-report.md"


def test_shared_lifecycle_uses_powershell_on_windows(monkeypatch) -> None:
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("fsq_agent._strict_lifecycle.sys.platform", "win32")
    monkeypatch.setattr("fsq_agent._strict_lifecycle.subprocess.run", fake_run)

    command = "Remove-Item -LiteralPath 'C:\\temp\\test1' -Recurse -Force -Confirm:$false"
    result = _run_shell_command(command)

    assert result.returncode == 0
    assert calls[0][0] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]


def test_shared_lifecycle_before_failure_skips_main_but_runs_after(tmp_path: Path, monkeypatch) -> None:
    case_path = tmp_path / "failure.codex.yaml"
    case_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Failure\nplatform: android\nappId: com.example\nonCaseStart:\n- runShell: fail-before\nonCaseComplete:\n- runShell: pass-after\n---\n- launchApp: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "fsq_agent._strict_lifecycle._run_shell_command",
        lambda command: subprocess.CompletedProcess(command, 3 if command == "fail-before" else 0, stdout="", stderr=""),
    )
    settings = Settings(cases={"dir": tmp_path})
    case = FsqCaseLoader().load_case(case_path)
    registry = build_capability_registry(platform="android")
    harness = LifecycleHarness()
    run_dir = tmp_path / "runs" / "failure"

    artifact = run_strict_lifecycle_case(
        case_path=case_path,
        case=case,
        settings=settings,
        harness=harness,
        output_dir=run_dir,
        run_id="failure",
        registry=registry,
        registry_snapshot=registry.snapshot(),
        recorder=EvidenceRecorder(run_id="failure", output_dir=run_dir),
        resolve_steps=lambda steps, _case: steps,
    )

    manifest = json.loads(artifact.evidence_manifest_path.read_text(encoding="utf-8"))
    assert harness.actions == []
    assert [step["metadata"]["command"] for step in manifest["steps"]] == ["fail-before", "pass-after"]
    assert [step["status"] for step in manifest["steps"]] == ["failed", "passed"]


def test_shared_lifecycle_propagates_cancellation_before_actions(tmp_path: Path, monkeypatch) -> None:
    case_path = tmp_path / "cancel.codex.yaml"
    case_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Cancel\nplatform: android\nonCaseStart:\n- runShell: should-not-run\n---\n- launchApp: {}\n",
        encoding="utf-8",
    )
    shell_calls: list[str] = []
    monkeypatch.setattr(
        "fsq_agent._strict_lifecycle._run_shell_command",
        shell_calls.append,
    )
    settings = Settings(cases={"dir": tmp_path})
    case = FsqCaseLoader().load_case(case_path)
    registry = build_capability_registry(platform="android")

    with pytest.raises(RuntimeError, match="cancelled"):
        run_strict_lifecycle_case(
            case_path=case_path,
            case=case,
            settings=settings,
            harness=LifecycleHarness(),
            output_dir=tmp_path / "runs" / "cancel",
            run_id="cancel",
            registry=registry,
            registry_snapshot=registry.snapshot(),
            resolve_steps=lambda steps, _case: steps,
            cancellation_check=lambda: (_ for _ in ()).throw(RuntimeError("cancelled")),
        )

    assert shell_calls == []


def test_shared_lifecycle_preflight_rejects_recursive_run_case(tmp_path: Path) -> None:
    case_path = tmp_path / "recursive.codex.yaml"
    case_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Recursive\nplatform: android\nonCaseStart:\n- runCase: recursive.codex.yaml\n---\n- launchApp: {}\n",
        encoding="utf-8",
    )
    settings = Settings(cases={"dir": tmp_path})
    case = FsqCaseLoader().load_case(case_path)

    with pytest.raises(ConfigurationError, match="Recursive lifecycle hook runCase detected"):
        collect_strict_lifecycle_cases(case_path=case_path, case=case, settings=settings)


def test_shared_lifecycle_preserves_repeated_shell_order_and_continues_after_failures(tmp_path: Path, monkeypatch) -> None:
    case_path = tmp_path / "repeated.codex.yaml"
    case_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Repeated\nplatform: android\nonCaseComplete:\n- runShell: first\n- runShell: second\n---\n- launchApp: {}\n",
        encoding="utf-8",
    )
    calls: list[str] = []

    def run_shell(command: str):
        calls.append(command)
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="")

    monkeypatch.setattr("fsq_agent._strict_lifecycle._run_shell_command", run_shell)
    settings = Settings(cases={"dir": tmp_path})
    case = FsqCaseLoader().load_case(case_path)
    registry = build_capability_registry(platform="android")
    run_dir = tmp_path / "runs" / "repeated"

    run_strict_lifecycle_case(
        case_path=case_path,
        case=case,
        settings=settings,
        harness=LifecycleHarness(),
        output_dir=run_dir,
        run_id="repeated",
        registry=registry,
        registry_snapshot=registry.snapshot(),
        resolve_steps=lambda steps, _case: steps,
    )

    manifest = json.loads((run_dir / "evidence-manifest.json").read_text(encoding="utf-8"))
    assert calls == ["first", "second"]
    assert [step["status"] for step in manifest["steps"][-2:]] == ["failed", "failed"]


def test_shared_lifecycle_uses_system_shell_off_windows(monkeypatch) -> None:
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("fsq_agent._strict_lifecycle.sys.platform", "linux")
    monkeypatch.setattr("fsq_agent._strict_lifecycle.subprocess.run", fake_run)

    _run_shell_command("echo ready")

    assert calls == [("echo ready", {"shell": True, "capture_output": True, "text": True, "check": False})]


def test_shared_lifecycle_records_shell_startup_failure(tmp_path: Path, monkeypatch) -> None:
    case_path = tmp_path / "startup-failure.codex.yaml"
    case_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Startup Failure\nplatform: android\nonCaseStart:\n- runShell: broken\n---\n- launchApp: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "fsq_agent._strict_lifecycle._run_shell_command",
        lambda command: (_ for _ in ()).throw(OSError("cannot start shell")),
    )
    settings = Settings(cases={"dir": tmp_path})
    case = FsqCaseLoader().load_case(case_path)
    registry = build_capability_registry(platform="android")
    run_dir = tmp_path / "runs" / "startup-failure"

    run_strict_lifecycle_case(
        case_path=case_path,
        case=case,
        settings=settings,
        harness=LifecycleHarness(),
        output_dir=run_dir,
        run_id="startup-failure",
        registry=registry,
        registry_snapshot=registry.snapshot(),
        resolve_steps=lambda steps, _case: steps,
    )

    manifest = json.loads((run_dir / "evidence-manifest.json").read_text(encoding="utf-8"))
    assert manifest["steps"][0]["status"] == "failed"
    assert "cannot start shell" in manifest["steps"][0]["error_message"]


def test_shared_lifecycle_uses_pre_resolved_steps_without_lazy_resolution(tmp_path: Path) -> None:
    case_path = tmp_path / "resolved.codex.yaml"
    case_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Resolved\nplatform: android\n---\n- launchApp: {}\n",
        encoding="utf-8",
    )
    settings = Settings(cases={"dir": tmp_path})
    case = FsqCaseLoader().load_case(case_path)
    registry = build_capability_registry(platform="android")
    resolved_steps = FsqExecutableStepAdapter(registry_snapshot=registry.snapshot()).to_executable_steps(case)
    harness = LifecycleHarness()

    run_strict_lifecycle_case(
        case_path=case_path,
        case=case,
        settings=settings,
        harness=harness,
        output_dir=tmp_path / "runs" / "resolved",
        run_id="resolved",
        registry=registry,
        registry_snapshot=registry.snapshot(),
        resolve_steps=lambda steps, _case: (_ for _ in ()).throw(AssertionError("lazy resolver called")),
        resolved_steps_by_path={case_path.resolve(): resolved_steps},
    )

    assert harness.actions == ["launch_app"]


def test_shared_lifecycle_uses_preloaded_child_snapshot_and_encloses_child_events(tmp_path: Path) -> None:
    child_path = tmp_path / "snapshot-child.codex.yaml"
    child_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Snapshot Child\nplatform: android\n---\n- tapOn:\n    target: Child\n",
        encoding="utf-8",
    )
    root_path = tmp_path / "snapshot-root.codex.yaml"
    root_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Snapshot Root\nplatform: android\nonCaseStart:\n- runCase: snapshot-child.codex.yaml\n---\n- launchApp: {}\n",
        encoding="utf-8",
    )
    settings = Settings(cases={"dir": tmp_path})
    root_case = FsqCaseLoader().load_case(root_path)
    child_case = FsqCaseLoader().load_case(child_path)
    registry = build_capability_registry(platform="android")
    adapter = FsqExecutableStepAdapter(registry_snapshot=registry.snapshot())
    resolved = {
        root_path.resolve(): adapter.to_executable_steps(root_case),
        child_path.resolve(): adapter.to_executable_steps(child_case),
    }
    recorder = EvidenceRecorder(run_id="snapshot-root", output_dir=tmp_path / "runs" / "snapshot-root")
    events: list[tuple[str, str | None]] = []
    original_record_event = recorder.record_event

    def record_event(event):
        events.append((event.event_type, event.step_id))
        original_record_event(event)

    recorder.record_event = record_event  # type: ignore[method-assign]
    child_path.unlink()
    harness = LifecycleHarness()

    run_strict_lifecycle_case(
        case_path=root_path,
        case=root_case,
        settings=settings,
        harness=harness,
        output_dir=tmp_path / "runs" / "snapshot-root",
        run_id="snapshot-root",
        registry=registry,
        registry_snapshot=registry.snapshot(),
        recorder=recorder,
        resolve_steps=lambda steps, _case: (_ for _ in ()).throw(AssertionError("lazy resolution")),
        resolved_steps_by_path=resolved,
        cases_by_path={root_path.resolve(): root_case, child_path.resolve(): child_case},
    )

    parent_id = next(step_id for event_type, step_id in events if event_type == "step_start" and step_id and "hook-run-case" in step_id)
    child_id = next(step_id for event_type, step_id in events if event_type == "step_start" and step_id and step_id.startswith("snapshot-child-case-step"))
    parent_start = events.index(("step_start", parent_id))
    parent_phase_start = events.index(("phase_start", parent_id))
    child_start = events.index(("step_start", child_id))
    parent_phase_finish = events.index(("phase_finish", parent_id))
    parent_finish = events.index(("step_finish", parent_id))
    assert parent_start < parent_phase_start < child_start < parent_phase_finish < parent_finish
    assert harness.actions == ["tap_on", "launch_app"]


@pytest.mark.parametrize("cancel_boundary", ["child", "main"])
def test_shared_lifecycle_cancels_at_child_and_main_boundaries(tmp_path: Path, cancel_boundary: str) -> None:
    child_path = tmp_path / "cancel-child.codex.yaml"
    child_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Cancel Child\nplatform: android\n---\n- tapOn:\n    target: Child\n",
        encoding="utf-8",
    )
    root_path = tmp_path / "cancel-root.codex.yaml"
    before = "onCaseStart:\n- runCase: cancel-child.codex.yaml\n" if cancel_boundary == "child" else ""
    root_path.write_text(
        f"schemaVersion: fsq.ai-test/v1\nname: Cancel Root\nplatform: android\n{before}---\n- launchApp: {{}}\n",
        encoding="utf-8",
    )
    settings = Settings(cases={"dir": tmp_path})
    root_case = FsqCaseLoader().load_case(root_path)
    registry = build_capability_registry(platform="android")
    checks = 0
    harness = LifecycleHarness()

    def cancel() -> None:
        nonlocal checks
        checks += 1
        threshold = 3 if cancel_boundary == "child" else 2
        if checks >= threshold:
            raise RuntimeError(f"cancelled at {cancel_boundary}")

    with pytest.raises(RuntimeError, match=f"cancelled at {cancel_boundary}"):
        run_strict_lifecycle_case(
            case_path=root_path,
            case=root_case,
            settings=settings,
            harness=harness,
            output_dir=tmp_path / "runs" / f"cancel-{cancel_boundary}",
            run_id=f"cancel-{cancel_boundary}",
            registry=registry,
            registry_snapshot=registry.snapshot(),
            resolve_steps=lambda steps, _case: steps,
            cancellation_check=cancel,
        )

    assert harness.actions == []
