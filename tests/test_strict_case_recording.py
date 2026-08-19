# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path

import yaml

from fsq_agent.config._settings import Settings
from fsq_agent.execution.recording import record_dynamic_run_as_strict_case
from fsq_agent.models import AndroidHarnessSettings, ConfigurationError, HarnessSettings, OutputSettings, ReportArtifact, RunEvent, Task, TaskResult, VerificationResult


def _write_event(path: Path, event: RunEvent) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json() + "\n")


def _recordable_web_run(
    tmp_path: Path,
    *,
    planning_reference_kind: str = "goal",
    status: str = "success",
    replay_alias: str = "clickOn",
) -> tuple[Path, Task, TaskResult, Settings]:
    run_id = "goal-recording-run"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    task = Task(
        id="task-1",
        name="Search",
        description="Search the web",
        planning_reference_kind=planning_reference_kind,
        planning_reference_text="Search the web",
    )
    result = TaskResult(
        task_id=task.id,
        status=status,
        steps=[],
        verification=VerificationResult(status=status, summary=status),
        report=ReportArtifact(run_id=run_id, path=run_dir / "report.md"),
    )
    output_settings = OutputSettings()
    output_settings.runs_dir = tmp_path / "runs"
    settings = Settings(output=output_settings, harness=HarnessSettings(platform="web"))
    settings.cases.dir = tmp_path / "workspace" / "cases" / "web"
    events_path = run_dir / "events.jsonl"
    _write_event(
        events_path,
        RunEvent(
            run_id=run_id,
            task_id=task.id,
            type="tool_call_started",
            title="Tool call started",
            tool_name="click_on",
            tool_call_id="call-1",
            tool_arguments={"target": "Search"},
            payload={"tool_origin": "platform", "capability_name": "click_on", "replay": {"kind": "fsq_command", "alias": replay_alias}},
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id=run_id,
            task_id=task.id,
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="click_on",
            tool_call_id="call-1",
            payload={
                "tool_origin": "platform",
                "capability_name": "click_on",
                "replay": {"kind": "fsq_command", "alias": replay_alias},
                "status": "passed",
            },
        ),
    )
    return run_dir, task, result, settings


def test_record_dynamic_run_writes_strict_yaml_with_runtime_secret_and_wait(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "recorded-run"
    run_dir.mkdir(parents=True)
    events_path = run_dir / "events.jsonl"
    task = Task(id="task-1", name="Login", description="Log in")
    result = TaskResult(
        task_id="task-1",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="ok"),
        report=ReportArtifact(run_id="recorded-run", path=run_dir / "report.md"),
    )
    output_settings = OutputSettings()
    output_settings.runs_dir = tmp_path / "runs"
    android_settings = AndroidHarnessSettings()
    android_settings.app_id = "com.example"
    settings = Settings(output=output_settings, harness=HarnessSettings(android=android_settings))

    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-run",
            task_id="task-1",
            type="tool_call_started",
            title="Tool call started",
            tool_name="input_text",
            tool_call_id="call-1",
            tool_arguments={"text": "TEST_ACCOUNT_PASSWORD", "textType": "runtimeSecret", "target": "Password field"},
            payload={"tool_origin": "platform", "capability_name": "input_text", "replay": {"kind": "fsq_command", "alias": "inputText"}},
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-run",
            task_id="task-1",
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="input_text",
            tool_call_id="call-1",
            payload={"tool_origin": "platform", "capability_name": "input_text", "replay": {"kind": "fsq_command", "alias": "inputText"}, "status": "passed"},
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-run",
            task_id="task-1",
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="wait_ms",
            payload={"tool_origin": "common", "replay": {"kind": "fsq_command", "alias": "waitMs"}, "duration_ms": 1, "reason": "settle"},
        ),
    )

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    assert recording.status == "recorded"
    assert recording.validation_status == "passed"
    docs = list(yaml.safe_load_all((run_dir / "recorded.fsq.yaml").read_text(encoding="utf-8")))
    assert docs[0]["properties"]["recording"]["required_runtime_secret_names"] == ["TEST_ACCOUNT_PASSWORD"]
    assert docs[1] == [
        {"inputText": {"text": "TEST_ACCOUNT_PASSWORD", "textType": "runtimeSecret", "target": "Password field"}},
        {"waitMs": {"duration_ms": 1, "reason": "settle"}},
    ]
    manifest = json.loads((run_dir / "recording.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "recorded"
    assert manifest["command_count"] == 2


def test_record_dynamic_web_run_validates_against_web_registry(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "recorded-web-run"
    run_dir.mkdir(parents=True)
    events_path = run_dir / "events.jsonl"
    task = Task(id="task-1", name="Search", description="Search the web")
    result = TaskResult(
        task_id="task-1",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="ok"),
        report=ReportArtifact(run_id="recorded-web-run", path=run_dir / "report.md"),
    )
    output_settings = OutputSettings()
    output_settings.runs_dir = tmp_path / "runs"
    settings = Settings(output=output_settings, harness=HarnessSettings(platform="web"))

    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-web-run",
            task_id="task-1",
            type="tool_call_started",
            title="Tool call started",
            tool_name="click_on",
            tool_call_id="call-1",
            tool_arguments={"target": "Search"},
            payload={"tool_origin": "platform", "capability_name": "click_on", "replay": {"kind": "fsq_command", "alias": "clickOn"}},
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-web-run",
            task_id="task-1",
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="click_on",
            tool_call_id="call-1",
            payload={"tool_origin": "platform", "capability_name": "click_on", "replay": {"kind": "fsq_command", "alias": "clickOn"}, "status": "passed"},
        ),
    )

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    assert recording.status == "recorded"
    assert recording.validation_status == "passed"
    docs = list(yaml.safe_load_all((run_dir / "recorded.fsq.yaml").read_text(encoding="utf-8")))
    assert docs[0]["platform"] == "web"
    assert "appId" not in docs[0]
    assert docs[1] == [{"clickOn": {"target": "Search"}}]


def test_record_dynamic_run_does_not_infer_replay_from_fsq_action_name(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "recorded-missing-replay-run"
    run_dir.mkdir(parents=True)
    events_path = run_dir / "events.jsonl"
    task = Task(id="task-1", name="Tap", description="Tap a target")
    result = TaskResult(
        task_id="task-1",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="ok"),
        report=ReportArtifact(run_id="recorded-missing-replay-run", path=run_dir / "report.md"),
    )
    output_settings = OutputSettings()
    output_settings.runs_dir = tmp_path / "runs"
    android_settings = AndroidHarnessSettings()
    android_settings.app_id = "com.example"
    settings = Settings(output=output_settings, harness=HarnessSettings(android=android_settings))

    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-missing-replay-run",
            task_id="task-1",
            type="tool_call_started",
            title="Tool call started",
            tool_name="tap_on",
            tool_call_id="call-1",
            tool_arguments={"target": "Login"},
            payload={"tool_origin": "platform", "capability_name": "tap_on", "fsq_action_name": "tapOn"},
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-missing-replay-run",
            task_id="task-1",
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="tap_on",
            tool_call_id="call-1",
            payload={"tool_origin": "platform", "capability_name": "tap_on", "fsq_action_name": "tapOn", "status": "passed"},
        ),
    )

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    assert recording.status == "failed"
    assert not (run_dir / "recorded.fsq.yaml").exists()
    assert recording.skipped_tool_calls == [{"tool_name": "tap_on", "reason": "platform tool did not include fsq_command replay metadata"}]


def test_record_dynamic_run_skips_observation_capabilities(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "recorded-observation-run"
    run_dir.mkdir(parents=True)
    events_path = run_dir / "events.jsonl"
    task = Task(id="task-1", name="Tap and observe", description="Tap then inspect UI tree")
    result = TaskResult(
        task_id="task-1",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="ok"),
        report=ReportArtifact(run_id="recorded-observation-run", path=run_dir / "report.md"),
    )
    output_settings = OutputSettings()
    output_settings.runs_dir = tmp_path / "runs"
    android_settings = AndroidHarnessSettings()
    android_settings.app_id = "com.example"
    settings = Settings(output=output_settings, harness=HarnessSettings(android=android_settings))

    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-observation-run",
            task_id="task-1",
            type="tool_call_started",
            title="Tool call started",
            tool_name="tap_on",
            tool_call_id="call-1",
            tool_arguments={"target": "Login"},
            payload={
                "tool_origin": "platform",
                "capability_name": "tap_on",
                "step_kind": "action",
                "replay": {"kind": "fsq_command", "alias": "tapOn"},
            },
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-observation-run",
            task_id="task-1",
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="tap_on",
            tool_call_id="call-1",
            payload={
                "tool_origin": "platform",
                "capability_name": "tap_on",
                "step_kind": "action",
                "replay": {"kind": "fsq_command", "alias": "tapOn"},
                "status": "passed",
            },
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-observation-run",
            task_id="task-1",
            type="tool_call_started",
            title="Tool call started",
            tool_name="ui_snapshot",
            tool_call_id="call-2",
            tool_arguments={},
            payload={
                "tool_origin": "platform",
                "capability_name": "ui_snapshot",
                "step_kind": "observation",
                "replay": {"kind": "fsq_command", "alias": "uiTree"},
            },
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-observation-run",
            task_id="task-1",
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="ui_snapshot",
            tool_call_id="call-2",
            payload={
                "tool_origin": "platform",
                "capability_name": "ui_snapshot",
                "step_kind": "observation",
                "replay": {"kind": "fsq_command", "alias": "uiTree"},
                "status": "passed",
            },
        ),
    )

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    assert recording.status == "recorded"
    docs = list(yaml.safe_load_all((run_dir / "recorded.fsq.yaml").read_text(encoding="utf-8")))
    assert docs[0]["properties"]["recording"]["warnings"] == []
    assert docs[1] == [{"tapOn": {"target": "Login"}}]
    assert recording.skipped_tool_calls == [{"tool_name": "ui_snapshot", "reason": "observation tool is not recorded"}]
    manifest = json.loads((run_dir / "recording.json").read_text(encoding="utf-8"))
    assert manifest["warnings"] == []
    assert manifest["skipped_tool_calls"] == [{"tool_name": "ui_snapshot", "reason": "observation tool is not recorded"}]


def test_record_dynamic_android_tap_at_includes_reference_screen_size(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "recorded-tap-at-run"
    run_dir.mkdir(parents=True)
    events_path = run_dir / "events.jsonl"
    task = Task(id="task-1", name="Tap coordinate", description="Tap a coordinate")
    result = TaskResult(
        task_id="task-1",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="ok"),
        report=ReportArtifact(run_id="recorded-tap-at-run", path=run_dir / "report.md"),
    )
    output_settings = OutputSettings()
    output_settings.runs_dir = tmp_path / "runs"
    android_settings = AndroidHarnessSettings()
    android_settings.app_id = "com.example"
    settings = Settings(output=output_settings, harness=HarnessSettings(android=android_settings))

    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-tap-at-run",
            task_id="task-1",
            type="tool_call_started",
            title="Tool call started",
            tool_name="tap_at",
            tool_call_id="call-1",
            tool_arguments={"point": {"x": 100, "y": 200}},
            payload={"tool_origin": "platform", "capability_name": "tap_at", "replay": {"kind": "fsq_command", "alias": "tapAt"}},
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-tap-at-run",
            task_id="task-1",
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="tap_at",
            tool_call_id="call-1",
            payload={
                "tool_origin": "platform",
                "capability_name": "tap_at",
                "replay": {"kind": "fsq_command", "alias": "tapAt"},
                "status": "passed",
                "safe_replay_params": {
                    "point": {"x": 100, "y": 200},
                    "reference_screen_size": {"width": 1080, "height": 2400},
                },
            },
        ),
    )

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    assert recording.status == "recorded"
    assert recording.validation_status == "passed"
    docs = list(yaml.safe_load_all((run_dir / "recorded.fsq.yaml").read_text(encoding="utf-8")))
    assert docs[1] == [
        {
            "tapAt": {
                "point": {"x": 100, "y": 200},
                "reference_screen_size": {"width": 1080, "height": 2400},
            }
        }
    ]


def test_record_dynamic_android_point_swipe_includes_reference_screen_size(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "recorded-swipe-run"
    run_dir.mkdir(parents=True)
    events_path = run_dir / "events.jsonl"
    task = Task(id="task-1", name="Swipe coordinate", description="Swipe by coordinates")
    result = TaskResult(
        task_id="task-1",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="ok"),
        report=ReportArtifact(run_id="recorded-swipe-run", path=run_dir / "report.md"),
    )
    output_settings = OutputSettings()
    output_settings.runs_dir = tmp_path / "runs"
    android_settings = AndroidHarnessSettings()
    android_settings.app_id = "com.example"
    settings = Settings(output=output_settings, harness=HarnessSettings(android=android_settings))

    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-swipe-run",
            task_id="task-1",
            type="tool_call_started",
            title="Tool call started",
            tool_name="swipe",
            tool_call_id="call-1",
            tool_arguments={"start": {"x": 800, "y": 1900}, "end": {"x": 200, "y": 1900}, "duration": 1000},
            payload={"tool_origin": "platform", "capability_name": "swipe", "replay": {"kind": "fsq_command", "alias": "swipe"}},
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-swipe-run",
            task_id="task-1",
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="swipe",
            tool_call_id="call-1",
            payload={
                "tool_origin": "platform",
                "capability_name": "swipe",
                "replay": {"kind": "fsq_command", "alias": "swipe"},
                "status": "passed",
                "safe_replay_params": {
                    "start": {"x": 800, "y": 1900},
                    "end": {"x": 200, "y": 1900},
                    "duration": 1000,
                    "reference_screen_size": {"width": 1080, "height": 2400},
                },
            },
        ),
    )

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    assert recording.status == "recorded"
    assert recording.validation_status == "passed"
    docs = list(yaml.safe_load_all((run_dir / "recorded.fsq.yaml").read_text(encoding="utf-8")))
    assert docs[1] == [
        {
            "swipe": {
                "start": {"x": 800, "y": 1900},
                "end": {"x": 200, "y": 1900},
                "duration": 1000,
                "reference_screen_size": {"width": 1080, "height": 2400},
            }
        }
    ]


def test_record_dynamic_goal_publishes_validated_case_to_platform_cases_dir(tmp_path: Path) -> None:
    run_dir, task, result, settings = _recordable_web_run(tmp_path)

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    expected_path = settings.cases.dir / "goal-recording-run.fsq.yaml"
    assert recording.status == "recorded"
    assert recording.validation_status == "passed"
    assert recording.published_case_path == expected_path
    assert expected_path.read_bytes() == (run_dir / "recorded.fsq.yaml").read_bytes()
    manifest = json.loads((run_dir / "recording.json").read_text(encoding="utf-8"))
    assert manifest["published_case_path"] == str(expected_path)
    assert manifest["warnings"] == []


def test_record_dynamic_goal_atomically_overwrites_published_case_with_valid_draft(tmp_path: Path) -> None:
    run_dir, task, result, settings = _recordable_web_run(tmp_path, status="failed")
    published_path = settings.cases.dir / "goal-recording-run.fsq.yaml"
    published_path.parent.mkdir(parents=True)
    published_path.write_text("stale", encoding="utf-8")

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings, allow_failure=True)

    assert recording.status == "recorded"
    assert recording.draft is True
    assert recording.published_case_path == published_path
    assert published_path.read_bytes() == (run_dir / "recorded.fsq.yaml").read_bytes()
    docs = list(yaml.safe_load_all(published_path.read_text(encoding="utf-8")))
    assert docs[0]["properties"]["recording"]["draft"] is True


def test_record_dynamic_raw_case_does_not_publish(tmp_path: Path) -> None:
    run_dir, task, result, settings = _recordable_web_run(tmp_path, planning_reference_kind="raw_case")

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    assert recording.status == "recorded"
    assert recording.published_case_path is None
    assert not settings.cases.dir.exists()
    manifest = json.loads((run_dir / "recording.json").read_text(encoding="utf-8"))
    assert manifest["published_case_path"] is None


def test_record_dynamic_goal_does_not_publish_when_generated_case_validation_fails(tmp_path: Path, monkeypatch) -> None:
    run_dir, task, result, settings = _recordable_web_run(tmp_path)

    def fail_validation(*_args, **_kwargs):
        raise ConfigurationError("invalid generated case")

    monkeypatch.setattr("fsq_agent.execution.recording.FsqExecutableStepAdapter.to_executable_steps", fail_validation)

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    assert recording.status == "failed"
    assert recording.validation_status == "failed"
    assert recording.published_case_path is None
    assert not settings.cases.dir.exists()


def test_record_dynamic_goal_publication_failure_preserves_recording_and_existing_case(tmp_path: Path, monkeypatch) -> None:
    run_dir, task, result, settings = _recordable_web_run(tmp_path)
    published_path = settings.cases.dir / "goal-recording-run.fsq.yaml"
    published_path.parent.mkdir(parents=True)
    published_path.write_text("existing", encoding="utf-8")

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("fsq_agent.execution.recording.os.replace", fail_replace)

    recording = record_dynamic_run_as_strict_case(run_dir=run_dir, task=task, result=result, settings=settings)

    assert recording.status == "recorded"
    assert recording.validation_status == "passed"
    assert recording.published_case_path is None
    assert published_path.read_text(encoding="utf-8") == "existing"
    assert list(settings.cases.dir.iterdir()) == [published_path]
    assert any("publish" in warning.lower() for warning in recording.warnings)
    manifest = json.loads((run_dir / "recording.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "recorded"
    assert manifest["validation_status"] == "passed"
    assert manifest["published_case_path"] is None
    assert manifest["warnings"] == recording.warnings
