import json
from pathlib import Path

import yaml

from fsq_agent.cli._strict_case_recording import record_dynamic_run_as_strict_case
from fsq_agent.config._settings import Settings
from fsq_agent.models import AndroidHarnessSettings, HarnessSettings, OutputSettings, ReportArtifact, RunEvent, Task, TaskResult, VerificationResult


def _write_event(path: Path, event: RunEvent) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json() + "\n")


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
            type="tool_call_completed",
            title="Tool call completed",
            tool_name="get_runtime_secret",
            payload={
                "tool_origin": "common",
                "replay": {"kind": "dependency", "alias": "runtimeSecret"},
                "runtime_secret_name": "TEST_ACCOUNT_PASSWORD",
                "sensitive": True,
            },
        ),
    )
    _write_event(
        events_path,
        RunEvent(
            run_id="recorded-run",
            task_id="task-1",
            type="tool_call_started",
            title="Tool call started",
            tool_name="input_text",
            tool_call_id="call-1",
            tool_arguments={"text": "***", "target": "Password field"},
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
    docs = list(yaml.safe_load_all((run_dir / "recorded.codex.yaml").read_text(encoding="utf-8")))
    assert docs[0]["properties"]["recording"]["required_runtime_secret_names"] == ["TEST_ACCOUNT_PASSWORD"]
    assert docs[1] == [
        {"inputText": {"text": {"runtimeSecret": "TEST_ACCOUNT_PASSWORD"}, "target": "Password field"}},
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
    docs = list(yaml.safe_load_all((run_dir / "recorded.codex.yaml").read_text(encoding="utf-8")))
    assert docs[0]["platform"] == "web"
    assert "appId" not in docs[0]
    assert docs[1] == [{"clickOn": {"target": "Search"}}]


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
    docs = list(yaml.safe_load_all((run_dir / "recorded.codex.yaml").read_text(encoding="utf-8")))
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
    docs = list(yaml.safe_load_all((run_dir / "recorded.codex.yaml").read_text(encoding="utf-8")))
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
