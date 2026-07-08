import base64
import asyncio
import json
from pathlib import Path
from urllib.request import urlopen

from fsq_agent.config import Settings
from fsq_agent.models import HarnessContext, ReportArtifact, RunEvent, RunnerEvent, TaskResult, VerificationResult
from fsq_agent.playground._android import AndroidTarget, parse_adb_devices, resolve_auto_session
from fsq_agent.playground._execution import PlaygroundExecutionHandle, _PlaygroundEvidenceRecorder, _event_sink, _run_dynamic_task, task_from_case_yaml, task_from_goal
from fsq_agent.playground._server import STEP_ARTIFACT_TEXT_SIZE_LIMIT_BYTES, YAML_DISPLAY_SIZE_LIMIT_BYTES, PlaygroundServer, PlaygroundServerOptions
from fsq_agent.playground._state import BusyError, PlaygroundState


def test_parse_adb_devices_discovers_default_device() -> None:
    output = """List of devices attached
emulator-5554 device product:sdk_gphone64_x86_64 model:sdk_gphone64_x86_64 device:emu64xa transport_id:1
offline-1 offline
"""

    targets = parse_adb_devices(output)

    assert len(targets) == 1
    assert targets[0].id == "emulator-5554"
    assert targets[0].is_default is True
    assert "sdk gphone64 x86 64" in targets[0].description


def test_task_from_goal_matches_dynamic_goal_contract() -> None:
    task = task_from_goal("  Open rewards panel  ")

    assert task.id == "open-rewards-panel"
    assert task.name == "Open rewards panel"
    assert task.planning_reference_kind == "goal"
    assert task.planning_reference_text == "Open rewards panel"
    assert task.verification_goal is None


def test_task_from_case_yaml_preserves_raw_reference(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    case_path = cases_dir / "sample.codex.yaml"
    content = "schemaVersion: fsq.ai-test/v1\nname: Sample\n---\n- launchApp\n"
    case_path.write_text(content, encoding="utf-8")
    settings = Settings()
    settings.cases.dir = cases_dir

    task = task_from_case_yaml("sample.codex.yaml", settings)

    assert task.name == "Case reference: sample.codex.yaml"
    assert task.planning_reference_kind == "raw_case"
    assert task.planning_reference_text is not None
    assert str(case_path.resolve()) in task.planning_reference_text
    assert content in task.planning_reference_text


def test_auto_session_uses_configured_serial_when_online(monkeypatch) -> None:
    settings = Settings()
    settings.harness.android.serial = "device-2"
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: (
            [
                AndroidTarget(id="device-1", label="device-1", is_default=True),
                AndroidTarget(id="device-2", label="device-2"),
            ],
            None,
        ),
    )

    session, info = resolve_auto_session(settings)

    assert session is not None
    assert session.device_id == "device-2"
    assert info["reason"] == "configured_serial"


def test_auto_session_reports_configured_serial_offline(monkeypatch) -> None:
    settings = Settings()
    settings.harness.android.serial = "missing-device"
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: ([AndroidTarget(id="device-1", label="device-1", is_default=True)], None),
    )

    session, info = resolve_auto_session(settings)

    assert session is None
    assert info["reason"] == "configured_serial_offline"
    assert info["configuredSerial"] == "missing-device"


def test_auto_session_uses_single_online_device(monkeypatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: ([AndroidTarget(id="device-1", label="device-1", is_default=True)], None),
    )

    session, info = resolve_auto_session(Settings())

    assert session is not None
    assert session.device_id == "device-1"
    assert info["reason"] == "single_device"


def test_auto_session_requires_manual_selection_for_multiple_devices(monkeypatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: (
            [
                AndroidTarget(id="device-1", label="device-1", is_default=True),
                AndroidTarget(id="device-2", label="device-2"),
            ],
            None,
        ),
    )

    session, info = resolve_auto_session(Settings())

    assert session is None
    assert info["reason"] == "multiple_devices"


def test_auto_session_reports_no_devices(monkeypatch) -> None:
    monkeypatch.setattr("fsq_agent.playground._android.discover_adb_targets", lambda: ([], None))

    session, info = resolve_auto_session(Settings())

    assert session is None
    assert info["reason"] == "no_devices"


def test_playground_state_locks_concurrent_tasks(tmp_path: Path) -> None:
    state = PlaygroundState()
    state.create_session("device-1")
    request_id = state.start_task("Do it")

    try:
        state.start_task("Do something else")
    except BusyError as exc:
        assert "already running" in str(exc)
    else:
        raise AssertionError("Expected BusyError")

    result = TaskResult(
        task_id="task",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="ok"),
        report=ReportArtifact(run_id="run-1", path=tmp_path / "report.md"),
    )
    state.add_event(
        request_id,
        RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"),
    )
    state.finish_task(request_id, result)

    progress = state.get_task(request_id)
    assert progress is not None
    assert progress["runId"] == "run-1"
    assert progress["status"] == "success"
    assert progress["result"]["runId"] == "run-1"
    assert state.current_request_id is None


def test_playground_server_static_path_rejects_traversal(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("hello", encoding="utf-8")
    server = PlaygroundServer(Settings(), PlaygroundServerOptions(static_path=static_dir))

    status, body, content_type = server.static_response("/../secret.txt")

    assert status == 200
    assert body == b"hello"
    assert content_type.startswith("text/html")


def test_playground_server_report_endpoint_returns_content(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    report_dir = settings.output.runs_dir / "run-1"
    report_dir.mkdir(parents=True)
    (report_dir / "report.md").write_text("# report", encoding="utf-8")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/reports/run-1", {})

    assert status == 200
    assert payload["runId"] == "run-1"
    assert payload["content"] == "# report"


def test_playground_server_yaml_input_endpoint_returns_content(tmp_path: Path) -> None:
    settings = Settings()
    settings.cases.dir = tmp_path / "cases"
    settings.cases.dir.mkdir()
    case_path = settings.cases.dir / "sample.codex.yaml"
    case_path.write_text("schemaVersion: fsq.ai-test/v1\nname: Sample\nplatform: android\ndescription: Open sample\ntags: [smoke]\n---\n- launchApp\n", encoding="utf-8")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/input", {"path": ["sample.codex.yaml"]})

    assert status == 200
    assert payload["kind"] == "input"
    assert payload["path"] == "sample.codex.yaml"
    assert payload["resolvedPath"] == str(case_path.resolve())
    assert payload["sizeBytes"] == case_path.stat().st_size
    assert "launchApp" in payload["content"]
    assert payload["display"]["metadata"]["title"] == "Sample"
    assert payload["display"]["metadata"]["platform"] == "android"
    assert payload["display"]["metadata"]["tags"] == ["smoke"]
    assert payload["display"]["metadata"]["fields"] == [
        {"key": "platform", "label": "Platform", "value": "android"},
        {"key": "schemaVersion", "label": "Schema", "value": "fsq.ai-test/v1"},
        {"key": "description", "label": "Description", "value": "Open sample"},
        {"key": "path", "label": "Path", "value": "sample.codex.yaml"},
    ]
    assert payload["display"]["steps"] == [
        {"index": 1, "action": "launchApp", "kind": "setup", "badges": [], "params": []}
    ]


def test_playground_server_yaml_input_endpoint_reports_missing_file(tmp_path: Path) -> None:
    settings = Settings()
    settings.cases.dir = tmp_path / "cases"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/input", {"path": ["missing.codex.yaml"]})

    assert status == 404
    assert payload["available"] is False
    assert "Case YAML not found" in payload["error"]


def test_playground_server_yaml_input_endpoint_reports_directory(tmp_path: Path) -> None:
    settings = Settings()
    settings.cases.dir = tmp_path / "cases"
    (settings.cases.dir / "folder.codex.yaml").mkdir(parents=True)
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/input", {"path": ["folder.codex.yaml"]})

    assert status == 400
    assert payload["available"] is False
    assert "directory" in payload["error"]


def test_playground_server_yaml_input_endpoint_limits_display_size(tmp_path: Path) -> None:
    settings = Settings()
    settings.cases.dir = tmp_path / "cases"
    settings.cases.dir.mkdir()
    case_path = settings.cases.dir / "large.codex.yaml"
    case_path.write_text("x" * (YAML_DISPLAY_SIZE_LIMIT_BYTES + 1), encoding="utf-8")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/input", {"path": ["large.codex.yaml"]})

    assert status == 413
    assert payload["available"] is False
    assert payload["limitBytes"] == YAML_DISPLAY_SIZE_LIMIT_BYTES


def test_playground_server_yaml_input_endpoint_reports_display_parse_errors(tmp_path: Path) -> None:
    settings = Settings()
    settings.cases.dir = tmp_path / "cases"
    settings.cases.dir.mkdir()
    case_path = settings.cases.dir / "broken.codex.yaml"
    case_path.write_text("schemaVersion: [\n", encoding="utf-8")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/input", {"path": ["broken.codex.yaml"]})

    assert status == 400
    assert payload["available"] is False
    assert payload["error"]


def test_playground_server_recorded_yaml_endpoint_returns_content(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    recorded_path = run_dir / "recorded.codex.yaml"
    recorded_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Recorded\nplatform: android\n---\n- inputText:\n    text:\n      runtimeSecret: TEST_PASSWORD\n    target: Password\n    locator:\n      resourceId: com.example:id/password\n      text: null\n",
        encoding="utf-8",
    )
    (run_dir / "recording.json").write_text(
        json.dumps(
            {
                "status": "recorded",
                "recorded_case_path": str(recorded_path),
                "command_count": 1,
                "validation_status": "passed",
                "draft": False,
                "required_runtime_secret_names": [],
                "warnings": [],
                "skipped_tool_calls": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Recorded")
    server.state.bind_run_id(request_id, "run-1")

    status, payload = server.handle_get(f"/yaml/recorded/{request_id}", {})

    assert status == 200
    assert payload["kind"] == "recorded"
    assert payload["runId"] == "run-1"
    assert payload["status"] == "recorded"
    assert payload["validationStatus"] == "passed"
    assert payload["commandCount"] == 1
    assert payload["recordedCasePath"] == str(recorded_path)
    assert "inputText" in payload["content"]
    assert payload["display"]["metadata"]["title"] == "Recorded"
    assert {field["key"]: field["value"] for field in payload["display"]["metadata"]["fields"]}["path"] == str(recorded_path)
    assert payload["display"]["steps"][0]["action"] == "inputText"
    assert payload["display"]["steps"][0]["params"] == [
        {"key": "text", "value": "TEST_PASSWORD", "kind": "secret"},
        {"key": "target", "value": "Password", "kind": "scalar"},
        {
            "key": "locator",
            "value": "",
            "kind": "object",
            "fields": [
                {"key": "resourceId", "value": "com.example:id/password", "kind": "scalar"},
                {"key": "text", "value": "null", "kind": "null"},
            ],
        },
    ]


def test_playground_server_recorded_yaml_endpoint_returns_skipped_metadata(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "recording.json").write_text(
        json.dumps(
            {
                "status": "skipped",
                "recorded_case_path": None,
                "command_count": 0,
                "validation_status": "not_run",
                "draft": True,
                "warnings": ["No replayable commands found."],
                "skipped_tool_calls": [{"tool": "helper"}],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/recorded/run-1", {})

    assert status == 200
    assert payload["status"] == "skipped"
    assert payload["draft"] is True
    assert payload["content"] is None
    assert payload["warnings"] == ["No replayable commands found."]
    assert payload["skippedToolCalls"] == [{"tool": "helper"}]


def test_playground_server_recorded_yaml_endpoint_returns_failed_metadata(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "recording.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "recorded_case_path": None,
                "command_count": 0,
                "validation_status": "failed",
                "draft": False,
                "warnings": [],
                "errors": ["validation failed"],
            }
        ),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/recorded/run-1", {})

    assert status == 200
    assert payload["status"] == "failed"
    assert payload["validationStatus"] == "failed"
    assert payload["content"] is None
    assert payload["errors"] == ["validation failed"]


def test_playground_server_recorded_yaml_endpoint_reports_missing_run(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/recorded/missing-run", {})

    assert status == 404
    assert payload["available"] is False
    assert payload["runId"] == "missing-run"


def test_playground_server_recorded_yaml_endpoint_reports_missing_metadata(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "recorded.codex.yaml").write_text("schemaVersion: fsq.ai-test/v1\n", encoding="utf-8")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/recorded/run-1", {})

    assert status == 404
    assert payload["available"] is False
    assert "Recording metadata not found" in payload["error"]


def test_playground_server_recorded_yaml_endpoint_reports_invalid_metadata(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "recording.json").write_text("[]", encoding="utf-8")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/recorded/run-1", {})

    assert status == 400
    assert payload["available"] is False
    assert "JSON object" in payload["error"]


def test_playground_server_recorded_yaml_endpoint_reports_non_utf8_case(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    recorded_path = run_dir / "recorded.codex.yaml"
    recorded_path.write_bytes(b"\xff")
    (run_dir / "recording.json").write_text(
        json.dumps({"status": "recorded", "recorded_case_path": str(recorded_path)}),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/recorded/run-1", {})

    assert status == 400
    assert payload["available"] is False
    assert "UTF-8" in payload["error"]


def test_playground_server_recorded_yaml_endpoint_rejects_escaped_case_path(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "recording.json").write_text(
        json.dumps({"status": "recorded", "recorded_case_path": "../outside.codex.yaml"}),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/yaml/recorded/run-1", {})

    assert status == 400
    assert payload["available"] is False
    assert "outside" in payload["error"]


def test_playground_server_step_artifacts_endpoint_returns_manifest_artifacts(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    screenshot_dir = run_dir / "artifacts" / "screenshots"
    tree_dir = run_dir / "artifacts" / "ui-trees"
    screenshot_dir.mkdir(parents=True)
    tree_dir.mkdir(parents=True)
    (screenshot_dir / "run-1-step-001-prepare-before-action.png").write_bytes(b"before")
    (screenshot_dir / "run-1-step-001-finalize-after-action.png").write_bytes(b"after")
    (tree_dir / "run-1-step-001-finalize-after-action.json").write_text(
        json.dumps({"xml": '<hierarchy><node text="Login" /></hierarchy>'}),
        encoding="utf-8",
    )
    (run_dir / "evidence-manifest.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_type": "artifact_captured",
                        "timestamp": "2026-07-07T00:00:01+00:00",
                        "payload": {
                            "kind": "screenshot",
                            "path": "artifacts/screenshots/run-1-step-001-prepare-before-action.png",
                            "reason": "before-action",
                            "phase": "prepare",
                        },
                    },
                    {
                        "event_type": "artifact_captured",
                        "timestamp": "2026-07-07T00:00:02+00:00",
                        "payload": {
                            "kind": "screenshot",
                            "path": "artifacts/screenshots/run-1-step-001-finalize-after-action.png",
                            "reason": "after-action",
                            "phase": "finalize",
                        },
                    },
                    {
                        "event_type": "artifact_captured",
                        "timestamp": "2026-07-07T00:00:03+00:00",
                        "payload": {
                            "kind": "ui_tree",
                            "path": "artifacts/ui-trees/run-1-step-001-finalize-after-action.json",
                            "reason": "after-action",
                            "phase": "finalize",
                        },
                    },
                ],
                "artifacts": [
                    {
                        "kind": "screenshot",
                        "step_id": "run-1-step-001",
                        "path": "artifacts/screenshots/run-1-step-001-prepare-before-action.png",
                    },
                    {
                        "kind": "screenshot",
                        "step_id": "run-1-step-001",
                        "path": "artifacts/screenshots/run-1-step-001-finalize-after-action.png",
                    },
                    {
                        "kind": "ui_tree",
                        "step_id": "run-1-step-001",
                        "path": "artifacts/ui-trees/run-1-step-001-finalize-after-action.json",
                        "mime_type": "application/json",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/step-artifacts/run-1/1", {})

    assert status == 200
    assert payload["available"] is True
    assert payload["runId"] == "run-1"
    assert payload["stepIndex"] == 1
    assert [artifact["kind"] for artifact in payload["artifacts"]] == ["screenshot", "screenshot", "ui_tree"]
    assert [artifact["reason"] for artifact in payload["artifacts"]] == ["before-action", "after-action", "after-action"]
    assert payload["artifacts"][0]["contentBase64"] == base64.b64encode(b"before").decode("ascii")
    assert payload["artifacts"][1]["contentBase64"] == base64.b64encode(b"after").decode("ascii")
    assert payload["artifacts"][2]["mimeType"] == "application/xml"
    assert payload["artifacts"][2]["content"] == '<hierarchy><node text="Login" /></hierarchy>'


def test_playground_server_step_artifacts_endpoint_returns_no_artifacts(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "evidence-manifest.json").write_text(json.dumps({"artifacts": []}), encoding="utf-8")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/step-artifacts/run-1/1", {})

    assert status == 200
    assert payload["available"] is False
    assert payload["artifacts"] == []
    assert "No artifacts" in payload["message"]


def test_playground_server_step_artifacts_endpoint_maps_recorded_index_to_dynamic_event_output(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    events = [
        {
            "type": "tool_call_completed",
            "timestamp": "2026-07-07T00:00:01+00:00",
            "tool_name": "launch_app",
            "payload": {
                "tool_origin": "platform",
                "status": "passed",
                "replay": {"kind": "fsq_command", "alias": "launchApp"},
                "runner_step_id": "agent-launch_app-1",
                "artifact_refs": [],
            },
        },
        {
            "type": "tool_call_completed",
            "timestamp": "2026-07-07T00:00:02+00:00",
            "tool_name": "ui_tree",
            "payload": {
                "tool_origin": "platform",
                "status": "passed",
                "fsq_action_name": "uiTree",
                "replay": {"kind": "fsq_command", "alias": "uiTree"},
                "runner_step_id": "agent-ui_tree-2",
                "runner_result": {
                    "step_id": "agent-ui_tree-2",
                    "phase_reports": [
                        {
                            "phase": "invoke",
                            "metadata": {
                                "harness_output": {"xml": '<hierarchy><node text="Recorded" /></hierarchy>'}
                            },
                        }
                    ],
                },
                "artifact_refs": [],
            },
        },
    ]
    (run_dir / "events.jsonl").write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/step-artifacts/run-1/2", {})

    assert status == 200
    assert payload["available"] is True
    assert len(payload["artifacts"]) == 1
    artifact = payload["artifacts"][0]
    assert artifact["kind"] == "ui_tree"
    assert artifact["path"] == ""
    assert artifact["phase"] == "invoke"
    assert artifact["reason"] == "output"
    assert isinstance(artifact["timestamp"], int)
    assert artifact["mimeType"] == "application/xml"
    assert artifact["content"] == '<hierarchy><node text="Recorded" /></hierarchy>'


def test_playground_server_step_artifacts_endpoint_reports_missing_run(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/step-artifacts/missing-run/1", {})

    assert status == 404
    assert payload["available"] is False
    assert payload["runId"] == "missing-run"


def test_playground_server_step_artifacts_endpoint_rejects_escaped_artifact_path(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "evidence-manifest.json").write_text(
        json.dumps({"artifacts": [{"kind": "screenshot", "step_id": "run-1-step-001", "path": "../outside.png"}]}),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/step-artifacts/run-1/1", {})

    assert status == 400
    assert payload["available"] is False
    assert "outside" in payload["error"]


def test_playground_server_step_artifacts_endpoint_skips_missing_files(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "evidence-manifest.json").write_text(
        json.dumps({"artifacts": [{"kind": "screenshot", "step_id": "run-1-step-001", "path": "artifacts/screenshots/missing.png"}]}),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/step-artifacts/run-1/1", {})

    assert status == 200
    assert payload["available"] is False
    assert payload["artifacts"] == []


def test_playground_server_step_artifacts_endpoint_limits_text_size(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    tree_dir = run_dir / "artifacts" / "ui-trees"
    tree_dir.mkdir(parents=True)
    (tree_dir / "too-large.json").write_text("x" * (STEP_ARTIFACT_TEXT_SIZE_LIMIT_BYTES + 1), encoding="utf-8")
    (run_dir / "evidence-manifest.json").write_text(
        json.dumps({"artifacts": [{"kind": "ui_tree", "step_id": "run-1-step-001", "path": "artifacts/ui-trees/too-large.json"}]}),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/step-artifacts/run-1/1", {})

    assert status == 413
    assert payload["available"] is False
    assert payload["limitBytes"] == STEP_ARTIFACT_TEXT_SIZE_LIMIT_BYTES


def test_playground_server_task_progress_filters_events_after_sequence(tmp_path: Path) -> None:
    server = PlaygroundServer(Settings(), PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Incremental progress")
    for sequence in range(1, 4):
        server.state.add_event(
            request_id,
            RunEvent(
                run_id="run-1",
                task_id="task",
                type="planning_update",
                title=f"Event {sequence}",
                sequence=sequence,
            ),
        )
    result = TaskResult(
        task_id="task",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="ok"),
        report=ReportArtifact(run_id="run-1", path=tmp_path / "report.md"),
    )
    server.state.finish_task(request_id, result)

    full_status, full_payload = server.handle_get(f"/task-progress/{request_id}", {})
    incremental_status, incremental_payload = server.handle_get(
        f"/task-progress/{request_id}",
        {"after_sequence": ["2"]},
    )

    assert full_status == 200
    assert [event["sequence"] for event in full_payload["events"]] == [1, 2, 3]
    assert incremental_status == 200
    assert [event["sequence"] for event in incremental_payload["events"]] == [3]
    assert incremental_payload["status"] == "success"
    assert incremental_payload["result"]["runId"] == "run-1"


def test_playground_state_assigns_sequence_for_unsequenced_events() -> None:
    state = PlaygroundState()
    request_id = state.start_task("Strict progress")

    state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Start"))
    state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_completed", title="Done"))

    full_progress = state.get_task(request_id)
    incremental_progress = state.get_task(request_id, after_sequence=1)

    assert full_progress is not None
    assert [event["sequence"] for event in full_progress["events"]] == [1, 2]
    assert incremental_progress is not None
    assert [event["sequence"] for event in incremental_progress["events"]] == [2]


def test_playground_strict_recorder_emits_step_progress_events(tmp_path: Path) -> None:
    state = PlaygroundState()
    request_id = state.start_task("Strict progress")
    recorder = _PlaygroundEvidenceRecorder(run_id="strict_case", output_dir=tmp_path, state=state, request_id=request_id)

    recorder.record_event(RunnerEvent(event_type="step_start", run_id="strict_case", step_id="strict_case-step-002"))
    recorder.record_event(RunnerEvent(event_type="step_finish", run_id="strict_case", step_id="strict_case-step-002"))

    progress = state.get_task(request_id)

    assert progress is not None
    assert [event["type"] for event in progress["events"]] == ["tool_call_started", "tool_call_completed"]
    assert [event["title"] for event in progress["events"]] == ["Strict YAML step started", "Strict YAML step completed"]
    assert [event["payload"]["step_id"] for event in progress["events"]] == ["strict_case-step-002", "strict_case-step-002"]
    assert [event["payload"]["step_index"] for event in progress["events"]] == [2, 2]


def test_playground_state_cancel_request_marks_task_cancelled() -> None:
    state = PlaygroundState()
    request_id = state.start_task("Cancelable")

    payload = state.request_cancel(request_id)

    assert payload is not None
    assert payload["status"] == "cancelled"
    assert payload["cancelRequested"] is True
    assert state.is_cancel_requested(request_id) is True
    assert state.current_request_id is None


def test_playground_server_cancel_endpoint_cancels_current_task(tmp_path: Path) -> None:
    server = PlaygroundServer(Settings(), PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Cancelable")

    class FakeHandle:
        def __init__(self) -> None:
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

    handle = FakeHandle()
    server._execution_handles[request_id] = handle  # type: ignore[assignment]

    status, payload = server.handle_post(f"/cancel/{request_id}", {})

    assert status == 200
    assert payload["status"] == "cancelled"
    assert payload["cancelRequested"] is True
    assert handle.cancelled is True
    assert server.state.current_request_id is None


def test_playground_event_sink_ignores_events_after_cancel() -> None:
    state = PlaygroundState()
    request_id = state.start_task("Cancelable")
    sink = _event_sink(state, request_id)

    sink(RunEvent(run_id="run-1", task_id="task", type="run_started", title="Started"))
    state.request_cancel(request_id)
    sink(RunEvent(run_id="run-1", task_id="task", type="planning_update", title="Late event"))

    progress = state.get_task(request_id)
    assert progress is not None
    assert progress["status"] == "cancelled"
    assert [event["title"] for event in progress["events"]] == ["Started"]


def test_playground_server_persists_replay_frames(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Replay me")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))

    server._record_replay_frame(
        request_id,
        {"available": True, "screenshot": base64.b64encode(b"frame-1").decode("ascii"), "timestamp": 1000},
    )
    server._record_replay_frame(
        request_id,
        {"available": True, "screenshot": base64.b64encode(b"frame-2").decode("ascii"), "timestamp": 1800},
    )

    status, payload = server.handle_get(f"/replay/{request_id}", {})
    progress = server.state.get_task(request_id)

    assert status == 200
    assert [frame["timestamp"] for frame in payload["frames"]] == [1000, 1800]
    assert [frame["index"] for frame in payload["frames"]] == [1, 2]
    assert [frame["path"] for frame in payload["frames"]] == ["frame-0001-1000.png", "frame-0002-1800.png"]
    assert base64.b64decode(payload["frames"][0]["screenshot"]) == b"frame-1"
    assert (settings.output.runs_dir / "run-1" / "playground-replay" / "replay-manifest.json").exists()
    assert progress is not None
    assert progress["replay"]["runId"] == "run-1"
    assert progress["replay"]["frameCount"] == 2
    assert "manifestPath" not in progress["replay"]


def test_playground_server_replay_uses_evidence_screenshots(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    screenshot_dir = run_dir / "artifacts" / "screenshots"
    screenshot_dir.mkdir(parents=True)
    (screenshot_dir / "step-1.png").write_bytes(b"evidence-frame")
    (run_dir / "evidence-manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "events": [
                    {
                        "event_type": "artifact_captured",
                        "timestamp": "2026-06-17T10:49:07Z",
                        "payload": {"kind": "screenshot", "path": "artifacts/screenshots/step-1.png"},
                    }
                ],
                "artifacts": [
                    {"kind": "screenshot", "path": "artifacts/screenshots/step-1.png"},
                ],
            }
        ),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/replay/run-1", {})

    assert status == 200
    assert payload["runId"] == "run-1"
    assert isinstance(payload["frames"][0]["timestamp"], int)
    assert payload["frames"][0]["index"] == 1
    assert payload["frames"][0]["path"] == "artifacts/screenshots/step-1.png"
    assert base64.b64decode(payload["frames"][0]["screenshot"]) == b"evidence-frame"


def test_playground_server_replay_falls_back_to_event_screenshots(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    screenshot_dir = run_dir / "artifacts" / "screenshots"
    screenshot_dir.mkdir(parents=True)
    (screenshot_dir / "step-1.png").write_bytes(b"event-frame")
    (run_dir / "evidence-manifest.json").write_text(json.dumps({"run_id": "run-1", "steps": []}), encoding="utf-8")
    (run_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "type": "tool_call_completed",
                "timestamp": "2026-06-17T10:49:07Z",
                "payload": {
                    "artifact_refs": [
                        {"kind": "screenshot", "path": "artifacts/screenshots/step-1.png"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/replay/run-1", {})

    assert status == 200
    assert payload["runId"] == "run-1"
    assert isinstance(payload["frames"][0]["timestamp"], int)
    assert payload["frames"][0]["index"] == 1
    assert payload["frames"][0]["path"] == "artifacts/screenshots/step-1.png"
    assert base64.b64decode(payload["frames"][0]["screenshot"]) == b"event-frame"


def test_playground_static_progress_summarizes_replay_frames() -> None:
    static_dir = Path(__file__).parents[1] / "fsq_agent" / "playground" / "static"
    script = (static_dir / "playground.js").read_text(encoding="utf-8")
    styles = (static_dir / "playground.css").read_text(encoding="utf-8")

    assert "appendReplayFramesProgress" in script
    assert "replayFrameSummaries" in script
    assert "renderReplayFrameGallery" not in script
    assert "progress-frame-gallery" not in styles
    assert "src: `data:image/png;base64,${frame.screenshot}`" in script
    assert "path: frame.path || ''" in script


def test_playground_static_run_button_can_cancel() -> None:
    static_dir = Path(__file__).parents[1] / "fsq_agent" / "playground" / "static"
    script = (static_dir / "playground.js").read_text(encoding="utf-8")
    styles = (static_dir / "playground.css").read_text(encoding="utf-8")

    assert "cancelExecution" in script
    assert "setRunButtonCancel" in script
    assert "setRunButtonIdle" in script
    assert "Cancel" in script
    assert "els.runSelected.classList.add('secondary-button')" in script
    assert "els.runSelected.classList.remove('secondary-button')" in script
    assert "button.cancel" not in styles
    assert "button.secondary-button" in styles
    assert "#run-selected" in styles
    assert "min-width: 80px" in styles


def test_playground_server_preview_endpoint_returns_latest_screenshot(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    screenshot_path = settings.output.runs_dir / "run-1" / "artifacts" / "screenshots" / "step-1.png"
    screenshot_path.parent.mkdir(parents=True)
    screenshot_path.write_bytes(b"preview")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Strict")
    server.state.set_preview(
        request_id,
        {
            "runId": "run-1",
            "path": "artifacts/screenshots/step-1.png",
            "timestamp": "2026-06-17T10:49:07+00:00",
            "token": "run-1:step-1",
        },
    )

    status, payload = server.handle_get(f"/preview/{request_id}", {})

    assert status == 200
    assert payload["token"] == "run-1:step-1"
    assert base64.b64decode(payload["screenshot"]) == b"preview"


def test_playground_server_resets_replay_dir_once_per_request(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    replay_dir = settings.output.runs_dir / "run-1" / "playground-replay"
    replay_dir.mkdir(parents=True)
    (replay_dir / "old-frame.png").write_bytes(b"old")
    (replay_dir / "replay.webm").write_bytes(b"old-video")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Replay me")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))

    server._record_replay_frame(
        request_id,
        {"available": True, "screenshot": base64.b64encode(b"frame-1").decode("ascii"), "timestamp": 1000},
    )
    server._record_replay_frame(
        request_id,
        {"available": True, "screenshot": base64.b64encode(b"frame-2").decode("ascii"), "timestamp": 1800},
    )

    assert not (replay_dir / "old-frame.png").exists()
    assert not (replay_dir / "replay.webm").exists()
    assert sorted(path.name for path in replay_dir.glob("frame-*.png")) == [
        "frame-0001-1000.png",
        "frame-0002-1800.png",
    ]


def test_playground_server_stores_uploaded_replay_video(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Replay me")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))

    status, payload = server.handle_post(
        f"/replay-video/{request_id}",
        {"mimeType": "video/webm", "videoBase64": base64.b64encode(b"webm").decode("ascii")},
    )
    video_status, video_bytes, content_type, headers = server.handle_replay_video_file(f"/replay-video-file/{request_id}")

    assert status == 200
    assert payload["videoUrl"] == "/replay-video-file/run-1"
    assert (settings.output.runs_dir / "run-1" / "playground-replay" / "replay.webm").read_bytes() == b"webm"
    assert video_status == 200
    assert video_bytes == b"webm"
    assert content_type == "video/webm"
    assert headers == {"Accept-Ranges": "bytes"}


def test_playground_server_accepts_webm_upload_with_codecs(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Replay me")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))

    status, payload = server.handle_post(
        f"/replay-video/{request_id}",
        {"mimeType": "video/webm;codecs=vp8", "videoBase64": base64.b64encode(b"webm").decode("ascii")},
    )

    assert status == 200
    assert payload["videoUrl"] == "/replay-video-file/run-1"


def test_playground_execute_requires_session() -> None:
    server = PlaygroundServer(Settings())

    status, payload = server.handle_post("/execute", {"goal": "Do it"})

    assert status == 409
    assert "No active" in payload["error"]


def test_playground_web_platform_does_not_require_android_session(monkeypatch) -> None:
    settings = Settings(harness={"platform": "web"})
    captured = {}

    def fake_start_dynamic_goal_execution(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("fsq_agent.playground._server.start_dynamic_goal_execution", fake_start_dynamic_goal_execution)
    server = PlaygroundServer(settings)

    status, payload = server.handle_post("/execute", {"goal": "Do it"})

    assert status == 202
    assert payload["requestId"]
    assert captured["device_id"] is None


def test_playground_macos_platform_does_not_require_android_session(monkeypatch) -> None:
    settings = Settings(harness={"platform": "macos"})
    settings.harness.macos.appium_server_url = "http://127.0.0.1:4723"
    settings.harness.macos.bundle_id = "com.example.MacApp"
    captured = {}

    def fake_start_dynamic_goal_execution(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("fsq_agent.playground._server.start_dynamic_goal_execution", fake_start_dynamic_goal_execution)
    server = PlaygroundServer(settings)

    status, payload = server.handle_post("/execute", {"goal": "Do it"})

    assert status == 202
    assert payload["requestId"]
    assert captured["device_id"] is None


def test_playground_web_platform_session_endpoints_are_unavailable() -> None:
    chrome_path = Path("C:/Chrome/chrome.exe")
    settings = Settings(
        harness={
            "platform": "web",
            "web": {"backend": "playwright", "channel": "chrome", "headless": False, "base_url": "https://example.test"},
        }
    )
    settings.harness.web.browser_executable_path = chrome_path
    server = PlaygroundServer(settings)

    session_status, session_payload = server.handle_get("/session", {})
    setup_status, setup_payload = server.handle_get("/session/setup", {})
    auto_status, auto_payload = server.handle_post("/session/auto", {})
    runtime_status, runtime_payload = server.handle_get("/runtime-info", {})

    assert session_status == 200
    assert session_payload["available"] is False
    assert setup_status == 200
    assert setup_payload["available"] is False
    assert auto_status == 409
    assert auto_payload["available"] is False
    assert runtime_status == 200
    assert runtime_payload["platformId"] == "web"
    assert runtime_payload["metadata"]["backend"] == "playwright"
    assert runtime_payload["metadata"]["channel"] == "chrome"
    assert runtime_payload["metadata"]["browserExecutableConfigured"] is True
    assert runtime_payload["metadata"]["headless"] is False
    assert runtime_payload["metadata"]["baseUrlPresent"] is True

def test_playground_windows_platform_does_not_require_android_session(monkeypatch) -> None:
    settings = Settings(harness={"platform": "windows", "windows": {"app_path": "C:/App/app.exe"}})
    captured = {}

    def fake_start_dynamic_goal_execution(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("fsq_agent.playground._server.start_dynamic_goal_execution", fake_start_dynamic_goal_execution)
    server = PlaygroundServer(settings)

    status, payload = server.handle_post("/execute", {"goal": "Do it"})

    assert status == 202
    assert payload["requestId"]
    assert captured["device_id"] is None


def test_playground_windows_platform_runtime_info_and_session_endpoints() -> None:
    settings = Settings(
        harness={
            "platform": "windows",
            "windows": {"app_path": "C:/App/app.exe", "window_title_re": ".*Edge Beta", "launch_args": ["--x"]},
        }
    )
    server = PlaygroundServer(settings)

    session_status, session_payload = server.handle_get("/session", {})
    auto_status, _auto_payload = server.handle_post("/session/auto", {})
    runtime_status, runtime_payload = server.handle_get("/runtime-info", {})

    assert session_status == 200
    assert session_payload["available"] is False
    assert auto_status == 409
    assert runtime_status == 200
    assert runtime_payload["platformId"] == "windows"
    assert runtime_payload["metadata"]["backend"] == "pywinauto"
    assert runtime_payload["metadata"]["appPathConfigured"] is True
    assert runtime_payload["metadata"]["windowTitleRePresent"] is True
    assert runtime_payload["metadata"]["launchArgsCount"] == 1


def test_playground_macos_platform_runtime_info_and_session_endpoints() -> None:
    settings = Settings(harness={"platform": "macos", "macos": {"action_timeout_seconds": 11}})
    settings.harness.macos.appium_server_url = "http://127.0.0.1:4723"
    settings.harness.macos.bundle_id = "com.example.MacApp"
    server = PlaygroundServer(settings)

    session_status, session_payload = server.handle_get("/session", {})
    setup_status, setup_payload = server.handle_get("/session/setup", {})
    auto_status, auto_payload = server.handle_post("/session/auto", {})
    delete_status, delete_payload = server.handle_delete("/session")
    runtime_status, runtime_payload = server.handle_get("/runtime-info", {})

    assert session_status == 200
    assert session_payload["available"] is False
    assert "macos" in session_payload["message"]
    assert setup_status == 200
    assert setup_payload["available"] is False
    assert auto_status == 409
    assert auto_payload["available"] is False
    assert delete_status == 409
    assert delete_payload["available"] is False
    assert "macos" in delete_payload["message"]
    assert runtime_status == 200
    assert runtime_payload["platformId"] == "macos"
    assert runtime_payload["metadata"]["backend"] == "appium_mac2"
    assert runtime_payload["metadata"]["appiumServerConfigured"] is True
    assert runtime_payload["metadata"]["bundleIdPresent"] is True
    assert runtime_payload["metadata"]["appPathConfigured"] is False
    assert runtime_payload["metadata"]["actionTimeoutSeconds"] == 11


def test_playground_web_screenshot_uses_active_harness(tmp_path: Path) -> None:
    class FakeWebHarness:
        def get_context(self) -> HarnessContext:
            return HarnessContext(platform="web", metadata={"browser_started": True})

        def screenshot(self) -> bytes:
            return b"png"

    settings = Settings(harness={"platform": "web"})
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Web preview")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))
    handle = PlaygroundExecutionHandle(request_id=request_id)
    handle.bind_harness(FakeWebHarness())
    server._execution_handles[request_id] = handle

    status, payload = server.handle_get("/screenshot", {})

    assert status == 200
    assert payload["available"] is True
    assert payload["platform"] == "web"
    assert base64.b64decode(payload["screenshot"]) == b"png"
    frames = sorted((settings.output.runs_dir / "run-1" / "playground-replay").glob("frame-*.png"))
    assert len(frames) == 1
    assert frames[0].read_bytes() == b"png"


def test_playground_macos_screenshot_uses_active_harness(tmp_path: Path) -> None:
    class FakeMacOSHarness:
        def get_context(self) -> HarnessContext:
            return HarnessContext(platform="macos", session_id="mac2:session")

        def screenshot(self) -> bytes:
            return b"mac-png"

    settings = Settings(harness={"platform": "macos"})
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("macOS preview")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))
    handle = PlaygroundExecutionHandle(request_id=request_id)
    handle.bind_harness(FakeMacOSHarness())
    server._execution_handles[request_id] = handle

    status, payload = server.handle_get("/screenshot", {})

    assert status == 200
    assert payload["available"] is True
    assert payload["platform"] == "macos"
    assert base64.b64decode(payload["screenshot"]) == b"mac-png"


def test_playground_macos_screenshot_requires_launched_session(tmp_path: Path) -> None:
    class FakeMacOSHarness:
        def get_context(self) -> HarnessContext:
            return HarnessContext(platform="macos")

        def screenshot(self) -> bytes:
            raise AssertionError("screenshot should not be called before launch")

    settings = Settings(harness={"platform": "macos"})
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("macOS preview")
    handle = PlaygroundExecutionHandle(request_id=request_id)
    handle.bind_harness(FakeMacOSHarness())
    server._execution_handles[request_id] = handle

    status, payload = server.handle_get("/screenshot", {})

    assert status == 200
    assert payload["available"] is False
    assert payload["platform"] == "macos"
    assert "launchApp" in payload["error"]


def test_playground_web_screenshot_reports_not_started(tmp_path: Path) -> None:
    class FakeWebHarness:
        def get_context(self) -> HarnessContext:
            return HarnessContext(platform="web", metadata={"browser_started": False})

        def screenshot(self) -> bytes:
            raise AssertionError("screenshot should not be called before startBrowser")

    settings = Settings(harness={"platform": "web"})
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Web preview")
    handle = PlaygroundExecutionHandle(request_id=request_id)
    handle.bind_harness(FakeWebHarness())
    server._execution_handles[request_id] = handle

    status, payload = server.handle_get("/screenshot", {})

    assert status == 200
    assert payload == {
        "available": False,
        "platform": "web",
        "error": "Browser is not started. Call startBrowser before Web page actions.",
    }


def test_playground_execute_requires_exactly_one_source() -> None:
    server = PlaygroundServer(Settings())
    server.state.create_session("device-1")

    missing_status, missing_payload = server.handle_post("/execute", {})
    both_status, both_payload = server.handle_post("/execute", {"goal": "Do it", "caseYamlPath": "case.codex.yaml"})
    strict_both_status, strict_both_payload = server.handle_post("/execute", {"caseYamlPath": "case.codex.yaml", "strictCaseYamlPath": "case.codex.yaml"})

    assert missing_status == 400
    assert "Exactly one" in missing_payload["error"]
    assert both_status == 400
    assert "Exactly one" in both_payload["error"]
    assert strict_both_status == 400
    assert "Exactly one" in strict_both_payload["error"]


def test_playground_execute_starts_strict_yaml(monkeypatch) -> None:
    captured = {}

    def fake_start_dynamic_goal_execution(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("fsq_agent.playground._server.start_dynamic_goal_execution", fake_start_dynamic_goal_execution)
    server = PlaygroundServer(Settings())
    server.state.create_session("device-1")

    status, payload = server.handle_post("/execute", {"strictCaseYamlPath": "case.codex.yaml"})

    assert status == 202
    assert payload["requestId"]
    assert captured["goal"] is None
    assert captured["case_yaml_path"] is None
    assert captured["strict_case_yaml_path"] == "case.codex.yaml"
    assert captured["record"] is True
    assert captured["record_on_failure"] is True


def test_playground_execute_passes_recording_options(monkeypatch) -> None:
    captured = {}

    def fake_start_dynamic_goal_execution(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("fsq_agent.playground._server.start_dynamic_goal_execution", fake_start_dynamic_goal_execution)
    server = PlaygroundServer(Settings(), PlaygroundServerOptions(record=False, record_on_failure=False))
    server.state.create_session("device-1")

    status, payload = server.handle_post("/execute", {"goal": "Do it"})

    assert status == 202
    assert payload["requestId"]
    assert captured["record"] is False
    assert captured["record_on_failure"] is False


def test_playground_dynamic_goal_records_with_failure_drafts(tmp_path: Path, monkeypatch) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    state = PlaygroundState()
    request_id = state.start_task("Do it")
    captured = {}

    class FakeAgent:
        async def run(self, task, event_sink=None):
            captured["task"] = task
            return TaskResult(
                task_id=task.id,
                status="failed",
                steps=[],
                verification=VerificationResult(status="failed", summary="not done"),
                report=ReportArtifact(run_id="run-1", path=tmp_path / "report.md"),
            )

    class FakeRecording:
        def __init__(self, recording_path: Path) -> None:
            self.recording_path = recording_path

        def to_json(self):
            return {"status": "skipped", "recording_path": str(self.recording_path), "draft": True}

    def fake_record_dynamic_run_as_strict_case(**kwargs):
        captured.update(kwargs)
        return FakeRecording(kwargs["run_dir"] / "recording.json")

    monkeypatch.setattr("fsq_agent.playground._execution.validate_runtime_settings", lambda _settings: None)
    monkeypatch.setattr("fsq_agent.playground._execution.FsqAgent.from_settings", lambda _settings: FakeAgent())
    monkeypatch.setattr("fsq_agent.playground._recording._record_dynamic_run_as_strict_case", fake_record_dynamic_run_as_strict_case)

    _run_dynamic_task(
        settings=settings,
        state=state,
        request_id=request_id,
        goal="Do it",
        case_yaml_path=None,
        strict_case_yaml_path=None,
        device_id=None,
        record=True,
        record_on_failure=True,
    )

    progress = state.get_task(request_id)
    assert progress is not None
    assert captured["task"].planning_reference_kind == "goal"
    assert captured["allow_failure"] is True
    assert progress["result"]["recording"]["draft"] is True


def test_playground_dynamic_goal_does_not_overwrite_cancelled_task(tmp_path: Path, monkeypatch) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    state = PlaygroundState()
    request_id = state.start_task("Do it")

    class FakeAgent:
        async def run(self, task, event_sink=None):
            state.request_cancel(request_id)
            if event_sink is not None:
                event_sink(RunEvent(run_id="run-1", task_id=task.id, type="planning_update", title="Late event"))
            return TaskResult(
                task_id=task.id,
                status="success",
                steps=[],
                verification=VerificationResult(status="success", summary="done"),
                report=ReportArtifact(run_id="run-1", path=tmp_path / "report.md"),
            )

    monkeypatch.setattr("fsq_agent.playground._execution.validate_runtime_settings", lambda _settings: None)
    monkeypatch.setattr("fsq_agent.playground._execution.FsqAgent.from_settings", lambda _settings: FakeAgent())

    _run_dynamic_task(
        settings=settings,
        state=state,
        request_id=request_id,
        goal="Do it",
        case_yaml_path=None,
        strict_case_yaml_path=None,
        device_id=None,
        record=True,
        record_on_failure=True,
    )

    progress = state.get_task(request_id)
    assert progress is not None
    assert progress["status"] == "cancelled"
    assert progress["result"] is None
    assert progress["events"] == []


def test_playground_execute_clears_strict_replay_dir_at_start(tmp_path: Path, monkeypatch) -> None:
    settings = Settings()
    settings.cases.dir = tmp_path / "cases"
    settings.output.runs_dir = tmp_path / "runs"
    settings.cases.dir.mkdir()
    case_path = settings.cases.dir / "strict_case.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Strict Case
platform: android
---
- launchApp
- waitMs:
    duration_ms: 1
    reason: settle
""",
        encoding="utf-8",
    )
    replay_dir = settings.output.runs_dir / "strict_case" / "playground-replay"
    replay_dir.mkdir(parents=True)
    (replay_dir / "old-frame.png").write_bytes(b"old")
    monkeypatch.setattr("fsq_agent.playground._server.start_dynamic_goal_execution", lambda **_kwargs: None)
    server = PlaygroundServer(settings)
    server.state.create_session("device-1")

    status, _payload = server.handle_post("/execute", {"strictCaseYamlPath": "strict_case.codex.yaml"})

    assert status == 202
    assert not replay_dir.exists()


def test_playground_strict_yaml_execution_uses_standard_step_adapter(tmp_path: Path, monkeypatch) -> None:
    settings = Settings()
    settings.cases.dir = tmp_path / "cases"
    settings.output.runs_dir = tmp_path / "runs"
    settings.harness.android.serial = "device-1"
    settings.cases.dir.mkdir()
    case_path = settings.cases.dir / "strict_case.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Strict Case
platform: android
appId: com.microsoft.emmx
---
- launchApp
- waitMs:
    duration_ms: 1
    reason: settle
""",
        encoding="utf-8",
    )
    state = PlaygroundState()
    request_id = state.start_task("Strict")
    captured = {}

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str | None) -> None:
            captured["driver"] = {"app_id": app_id, "serial": serial}

    def fake_run_strict_core_steps(**kwargs):
        captured["steps"] = kwargs["steps"]
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "core-report.md"
        json_path = output_dir / "core-report.json"
        manifest_path = output_dir / "evidence-manifest.json"
        report_path.write_text("report", encoding="utf-8")
        json_path.write_text('{"summary":{"status":"passed","failed_steps":0}}', encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return ReportArtifact(run_id=kwargs["run_id"], path=report_path, evidence_manifest_path=manifest_path)

    monkeypatch.setattr("fsq_agent.playground._execution.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.playground._execution._run_strict_core_steps", fake_run_strict_core_steps)

    _run_dynamic_task(
        settings=settings,
        state=state,
        request_id=request_id,
        goal=None,
        case_yaml_path=None,
        strict_case_yaml_path="strict_case.codex.yaml",
        device_id=None,
        record=True,
        record_on_failure=True,
    )

    progress = state.get_task(request_id)
    assert progress is not None
    assert progress["result"]["status"] == "success"
    assert captured["driver"] == {"app_id": "com.microsoft.emmx", "serial": "device-1"}
    assert captured["steps"][0].action_name == "launch_app"
    assert captured["steps"][0].metadata["authored_action_name"] == "launchApp"


def test_playground_strict_web_yaml_execution_uses_web_harness(tmp_path: Path, monkeypatch) -> None:
    chrome_path = tmp_path / "chrome.exe"
    chrome_path.write_text("", encoding="utf-8")
    chrome_path.chmod(0o755)
    settings = Settings(
        harness={
            "platform": "web",
            "web": {
                "backend": "playwright",
                "channel": "chrome",
                "headless": True,
                "base_url": "https://example.test",
                "viewport_width": 1280,
                "viewport_height": 720,
            },
        }
    )
    settings.harness.web.browser_executable_path = chrome_path
    settings.cases.dir = tmp_path / "cases"
    settings.output.runs_dir = tmp_path / "runs"
    settings.cases.dir.mkdir()
    case_path = settings.cases.dir / "strict_web.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Strict Web Case
platform: web
---
- startBrowser
- navigateTo:
    url: /search
- clickOn:
    target: Search
- closeBrowser
""",
        encoding="utf-8",
    )
    state = PlaygroundState()
    request_id = state.start_task("Strict Web")
    captured = {}

    class FakeWebDriver:
        def __init__(self, **kwargs):
            captured["driver"] = kwargs

    def fake_run_strict_core_steps(**kwargs):
        captured["steps"] = kwargs["steps"]
        captured["registry"] = kwargs["registry"]
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "core-report.md"
        json_path = output_dir / "core-report.json"
        manifest_path = output_dir / "evidence-manifest.json"
        report_path.write_text("report", encoding="utf-8")
        json_path.write_text('{"summary":{"status":"passed","failed_steps":0}}', encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return ReportArtifact(run_id=kwargs["run_id"], path=report_path, evidence_manifest_path=manifest_path)

    monkeypatch.setattr("fsq_agent.playground._execution.PlaywrightWebDriver", FakeWebDriver)
    monkeypatch.setattr("fsq_agent.playground._execution._run_strict_core_steps", fake_run_strict_core_steps)

    _run_dynamic_task(
        settings=settings,
        state=state,
        request_id=request_id,
        goal=None,
        case_yaml_path=None,
        strict_case_yaml_path="strict_web.codex.yaml",
        device_id=None,
        record=True,
        record_on_failure=True,
    )

    progress = state.get_task(request_id)
    assert progress is not None
    assert progress["result"]["status"] == "success"
    assert captured["driver"] == {
        "channel": "chrome",
        "executable_path": chrome_path,
        "headless": True,
        "base_url": "https://example.test",
        "viewport": (1280, 720),
    }
    assert captured["registry"].resolve("pageSnapshot") is not None
    assert captured["registry"].resolve("startBrowser") is not None
    assert captured["registry"].resolve("tapOn") is None
    assert [step.action_name for step in captured["steps"]] == ["start_browser", "navigate_to", "click_on", "close_browser"]
    assert captured["steps"][0].metadata["authored_action_name"] == "startBrowser"
    assert captured["steps"][-1].metadata["authored_action_name"] == "closeBrowser"


def test_playground_strict_windows_yaml_execution_uses_windows_harness(tmp_path: Path, monkeypatch) -> None:
    app_path = tmp_path / "windows-app.exe"
    app_path.write_text("", encoding="utf-8")
    settings = Settings(
        harness={
            "platform": "windows",
            "windows": {
                "backend": "pywinauto",
                "backend_kind": "win32",
                "window_title_re": ".*Legacy App",
                "launch_args": ["--flag", "two words"],
            },
        }
    )
    settings.harness.windows.app_path = app_path
    settings.cases.dir = tmp_path / "cases"
    settings.output.runs_dir = tmp_path / "runs"
    settings.cases.dir.mkdir()
    case_path = settings.cases.dir / "strict_windows.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Strict Windows Case
platform: windows
---
- launchApp
- uiSnapshot
- killApp
""",
        encoding="utf-8",
    )
    state = PlaygroundState()
    request_id = state.start_task("Strict Windows")
    captured = {}

    class FakeWindowsDriver:
        def __init__(self, **kwargs):
            captured["driver"] = kwargs

    def fake_run_strict_core_steps(**kwargs):
        captured["steps"] = kwargs["steps"]
        captured["registry"] = kwargs["registry"]
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "core-report.md"
        json_path = output_dir / "core-report.json"
        manifest_path = output_dir / "evidence-manifest.json"
        report_path.write_text("report", encoding="utf-8")
        json_path.write_text('{"summary":{"status":"passed","failed_steps":0}}', encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return ReportArtifact(run_id=kwargs["run_id"], path=report_path, evidence_manifest_path=manifest_path)

    monkeypatch.setattr("fsq_agent.playground._execution.PywinautoWindowsDriver", FakeWindowsDriver)
    monkeypatch.setattr("fsq_agent.playground._execution._run_strict_core_steps", fake_run_strict_core_steps)

    _run_dynamic_task(
        settings=settings,
        state=state,
        request_id=request_id,
        goal=None,
        case_yaml_path=None,
        strict_case_yaml_path="strict_windows.codex.yaml",
        device_id=None,
        record=True,
        record_on_failure=True,
    )

    progress = state.get_task(request_id)
    assert progress is not None
    assert progress["result"]["status"] == "success"
    assert captured["driver"] == {
        "app_path": app_path,
        "backend_kind": "win32",
        "window_title_re": ".*Legacy App",
        "launch_args": ["--flag", "two words"],
    }
    assert captured["registry"].resolve("uiSnapshot") is not None
    assert captured["registry"].resolve("pageSnapshot") is None
    assert [step.action_name for step in captured["steps"]] == ["launch_app", "ui_snapshot", "kill_app"]
    assert captured["steps"][0].metadata["authored_action_name"] == "launchApp"
    assert captured["steps"][-1].metadata["authored_action_name"] == "killApp"


def test_playground_strict_yaml_runs_outside_async_event_loop(monkeypatch) -> None:
    settings = Settings()
    state = PlaygroundState()
    request_id = state.start_task("Strict")
    captured = {}

    def fake_run_strict_case_yaml(_settings, _state, _request_id, path_text):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            captured["running_loop"] = False
        else:
            captured["running_loop"] = True
        captured["path_text"] = path_text
        return TaskResult(
            task_id="strict",
            status="success",
            steps=[],
            verification=VerificationResult(status="success", summary="ok"),
            report=ReportArtifact(run_id="run-1", path=Path("core-report.md")),
        )

    monkeypatch.setattr("fsq_agent.playground._execution._run_strict_case_yaml", fake_run_strict_case_yaml)

    _run_dynamic_task(
        settings=settings,
        state=state,
        request_id=request_id,
        goal=None,
        case_yaml_path=None,
        strict_case_yaml_path="strict_case.codex.yaml",
        device_id=None,
        record=True,
        record_on_failure=True,
    )

    progress = state.get_task(request_id)
    assert progress is not None
    assert progress["status"] == "success"
    assert captured == {"running_loop": False, "path_text": "strict_case.codex.yaml"}


def test_playground_auto_session_route_creates_single_device_session(monkeypatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: ([AndroidTarget(id="device-1", label="device-1", is_default=True)], None),
    )
    server = PlaygroundServer(Settings())

    status, payload = server.handle_post("/session/auto", {})

    assert status == 200
    assert payload["session"]["deviceId"] == "device-1"
    assert payload["autoCreate"]["reason"] == "single_device"


def test_playground_auto_session_route_requires_manual_selection(monkeypatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: (
            [
                AndroidTarget(id="device-1", label="device-1", is_default=True),
                AndroidTarget(id="device-2", label="device-2"),
            ],
            None,
        ),
    )
    server = PlaygroundServer(Settings())

    status, payload = server.handle_post("/session/auto", {})

    assert status == 409
    assert payload["reason"] == "multiple_devices"
    assert len(payload["targets"]) == 2


def test_playground_server_serves_status_over_http(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("hello", encoding="utf-8")
    server = PlaygroundServer(Settings(), PlaygroundServerOptions(port=0, static_path=static_dir, open_browser=False))
    server.start()
    try:
        with urlopen(f"{server.url}/status", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.stop()

    assert payload["status"] == "ok"
    assert payload["busy"] is False


def test_playground_static_progress_is_right_side_tab_and_numbered() -> None:
    static_dir = Path(__file__).parents[1] / "fsq_agent" / "playground" / "static"
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    script = (static_dir / "playground.js").read_text(encoding="utf-8")
    styles = (static_dir / "playground.css").read_text(encoding="utf-8")
    clear_page_body = script[script.index("function clearPage()"):script.index("async function refreshStatus()")]
    start_execution_body = script[script.index("async function startExecution(payload)"):script.index("async function cancelExecution()")]

    assert 'class="section progress-section"' not in html
    assert html.index('id="yaml-input-tab"') < html.index('id="yaml-recorded-tab"') < html.index('id="yaml-progress-tab"')
    assert html.index('id="preview-tab"') < html.index('id="report-tab"')
    assert html.index('id="progress-pane"') < html.index('<section class="section">')
    assert "FSQ-Agent Playground" in html
    assert "status-pill status-connecting" in html
    assert "preview-tab" in html
    assert 'id="progress-tab"' not in html
    assert "yaml-progress-tab" in html
    assert "report-tab" in html
    assert "report-content" in html
    assert "preview-pane" in html
    assert "step-artifact-preview" in html
    assert "progress-pane" in html
    assert "panel-resizer" in html
    assert "role=\"separator\"" in html
    assert "aria-orientation=\"vertical\"" in html
    assert "replay-screenshots" not in html
    assert 'id="replay-video" controls' in html
    assert 'id="replay-video-play"' not in html
    assert 'aria-label="Play replay video"' not in html
    assert "Use Selected" not in html
    assert "Disconnect" not in html
    assert "createSession" not in script
    assert "destroySession" not in script
    assert '<button id="refresh" class="secondary-button" type="button">Clear</button>' in html
    assert "progress-run-id" in html
    assert "handleProgressRunIdClick" in script
    assert "selectProgressRunId" in script
    assert "clearSelectedProgressRunId" in script
    assert "clearSelectedProgressItem();\n  selectProgressRunId();" in script
    assert "els.progressRunId.addEventListener('click', handleProgressRunIdClick)" in script
    assert "els.progressRunId.dataset.runId = runId" in script
    assert "delete els.progressRunId.dataset.runId" in script
    assert "progressSequence" in script
    assert "lastProgressSequence" in script
    assert "modeStates" in script
    assert "highlightRunStartSummary" in script
    assert "if (state.currentExecutionMode !== 'strict-yaml') return" in script
    assert "const title = els.yamlInputViewer.querySelector('.yaml-case-title-row')" in script
    assert "selectYamlRegion(title)" in script
    assert "createRunModeState" in script
    assert "saveRunModeState" in script
    assert "restoreRunModeState" in script
    assert "switchRunMode" in script
    assert "resetRunModeStates" in script
    assert "stripTransientModeClasses" in script
    assert "bindProgressDetailToggles" in script
    assert "finishingRun" in script
    assert "const PROGRESS_POLL_INTERVAL_MS = 750;" in script
    assert "YAML_STEP_CENTER_TOLERANCE_RATIO" in script
    assert "window.setInterval(refreshProgress, PROGRESS_POLL_INTERVAL_MS)" in script
    assert "after_sequence=${state.lastProgressSequence}" in script
    assert "function updateLastProgressSequence" in script
    assert "setServerStatus" in script
    assert "status-pill status-${status}" in script
    assert "progressDetailOpenState" in script
    assert "selectedProgressItem" in script
    assert "activeProgressItem" in script
    assert "activeProgressItemClearTimer" in script
    assert "screenshotTimer" not in script
    assert "screenshotInFlight" not in script
    assert "state.replayTimer" not in script
    assert "state.replayIndex" not in script
    assert "replayRequestId" in script
    assert "previewToken" in script
    assert "pendingReplayVideoCleanup" in script
    assert "replayVideoInFlight" in script
    assert "CONTROL_PANEL_WIDTH_STORAGE_KEY" in script
    assert "initPanelResizer" in script
    assert "applyControlPanelWidth" in script
    assert "localStorage.setItem(CONTROL_PANEL_WIDTH_STORAGE_KEY" in script
    assert "ArrowLeft" in script
    assert "ArrowRight" in script
    assert "function makeReplaySeekable" in script
    assert "makeMetadataSeekable" in script
    assert "const REPLAY_FAST_ACTION_DELAY_MS = 900;" in script
    assert "const REPLAY_FAST_MAX_DELAY_MS = 1500;" in script
    assert "const REPLAY_FAST_FALLBACK_DELAY_MS = 500;" in script
    assert "const REPLAY_FAST_FINAL_FRAME_HOLD_MS = 700;" in script
    assert "const REPLAY_FAST_TIME_SCALE = 10;" in script
    assert "REPLAY_FAST_FINAL_FRAME_HOLD_MS" in script
    assert "requestCanvasFrame();" in script
    assert "await waitMs(REPLAY_FAST_FINAL_FRAME_HOLD_MS);" in script
    assert script.index("await waitMs(REPLAY_FAST_FINAL_FRAME_HOLD_MS);") < script.index("recorder.stop();")
    assert "liveVideoRecorder" not in script
    assert "liveVideoChunks" not in script
    assert "function clearPage()" in script
    assert "if (state.currentRequestId) return" in clear_page_body
    assert "els.refresh.addEventListener('click', clearPage)" in script
    assert "els.refresh.disabled = true" in script
    assert "els.refresh.disabled = false" in script
    assert "els.deviceSelect.disabled = true" in script
    assert "els.deviceSelect.disabled = false" in script
    assert "els.deviceSelect.disabled = Boolean(state.currentRequestId || state.finishingRun || status.busy)" in script
    assert "showRightTab('progress')" not in start_execution_body
    assert script.index("setRunButtonIdle();", script.index("ensureReplayVideoGenerated")) < script.index("els.refresh.disabled = false", script.index("ensureReplayVideoGenerated"))
    assert "window.clearInterval(state.progressTimer)" in script
    assert "stopLiveScreenshotPolling" not in script
    assert "stopReplay" not in script
    assert "clearRunId();" in clear_page_body
    assert "resetRunModeStates();" in clear_page_body
    assert "els.progress.innerHTML = ''" in script
    assert "els.reportContent.textContent = ''" in script
    assert "clearPreview();" in clear_page_body
    assert "clearPreview('Loading live preview...')" in script
    assert "highlightRunStartSummary();" in script
    assert "function clearPreview" in script
    assert "els.screenshot.removeAttribute('src')" in script
    assert "refreshStatus();" in clear_page_body
    assert "els.sessionMessage.textContent = ''" not in clear_page_body
    assert "els.deviceSelect.innerHTML = ''" not in clear_page_body
    assert "captureProgressDetailState" in script
    assert "data-detail-key" in script
    assert "event.sequence" in script
    assert "syncYamlStepWithProgressEvent(event)" in script
    assert "backendSequence" in script
    assert "tool_arguments" in script
    assert "tool_output_preview" in script
    assert "event.payload" in script
    assert "eventDetails" in script
    assert 'name="run-mode"' in html
    assert "strict-yaml" in html
    assert "caseYaml" in script
    assert "runYaml" in script
    assert "runSelected" in script
    assert "currentRunMode() === 'strict-yaml'" in script
    assert "currentRunMode" in script
    assert "updateRunMode" in script
    assert "caseYamlPath" in script
    assert "strictCaseYamlPath" in script
    assert "loadReport" in script
    assert "?format=markdown" in script
    assert "renderMarkdown" in script
    assert "escapeHtml" in script
    assert "showRightTab" in script
    assert "showRightTab('progress')" not in script
    assert "showYamlView('progress')" in script
    assert "renderProgressText" in script
    assert "handleProgressItemClick" in script
    assert "if (state.currentRequestId || state.finishingRun) return" in script
    assert "activateProgressItem(item)" in script
    assert "scheduleClearActiveProgressItem" in script
    assert "selectProgressItem" in script
    assert "clearSelectedProgressRunId();\n    selectProgressItem(item);" in script
    assert "clearSelectedProgressItem" in script
    assert "document.addEventListener('click', handleProgressItemClick)" in script
    assert "toolName" in script
    assert "progressRunId" in script
    assert "function setRunId(runId)" in script
    assert "function clearRunId()" in script
    assert "setRunId(event.run_id || event.runId)" in script
    assert "setRunId(progress.result.runId)" in script
    assert "event.type === 'run_started'" in script
    assert "function syncYamlStepWithProgressEvent" in script
    assert "if (state.currentExecutionMode !== 'strict-yaml') return" in script
    assert "function yamlStepCardForEvent" in script
    assert "function yamlStepIndexFromEvent" in script
    assert "function yamlStepIndexFromStepId" in script
    assert "function activateYamlStepCard" in script
    assert "function centerYamlStepCard" in script
    assert "scheduleClearActiveYamlStepCard" in script
    assert "cancelActiveYamlStepClearTimer" in script
    assert "stepCard.scrollIntoView({ block: 'center', behavior: 'smooth' })" in script
    assert "Run ID: ${runId}" in script
    assert "refreshPreviewFromReplay" in script
    assert "refreshPreview" in script
    assert "api(`/preview/${encodeURIComponent(requestId)}`)" in script
    assert "stepArtifactPreview" in script
    assert "stepArtifactPreviewActive" in script
    assert "showCompletedRunReplayPreview" in script
    assert "loadStepArtifactsForCard" in script
    assert "api(`/step-artifacts/${encodeURIComponent(runId)}/${encodeURIComponent(stepIdentifier)}`)" in script
    assert "const shouldShowLoading = els.stepArtifactPreview.hidden || !els.stepArtifactPreview.hasChildNodes()" in script
    assert "preloadStepArtifactScreenshots" in script
    assert "stepArtifactImageSrc" in script
    assert "renderStepArtifactPreview" in script
    assert "renderStepArtifactScreenshots" in script
    assert "renderStepArtifactTextArtifacts" in script
    assert "completedRunId" in script
    assert "startLiveScreenshotPolling" not in script
    assert "refreshScreenshot({ preservePrevious: true })" not in script
    assert "preloadImage" in script
    assert "showReplayFrame" in script
    assert "loadReplayFrames" in script
    assert "loadReplayVideo" in script
    assert "showReplayVideoPreview" in script
    assert "async function showReplayVideoPreview(videoUrl)" in script
    assert "await waitForReplayVideoReady()" in script
    assert "function waitForReplayVideoReady()" in script
    assert "els.replayVideo.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA" in script
    assert "function cancelPendingReplayVideoReadyWait()" in script
    assert "startReplay" not in script
    assert "replayVideoEnded" not in script
    assert "replayVideoStarted" not in script
    assert "replayVideoPaused" not in script
    assert "normalizeReplayVideoDuration" not in script
    assert "generateReplayVideo" in script
    assert "recordLiveReplayFrame" not in script
    assert "finalizeLiveReplayVideo" not in script
    assert "appendReplayVideoGeneratingProgress" in script
    assert "Generating replay video..." in script
    assert "Replay video saved" in script
    assert "Replay video was not generated:" in script
    assert "MediaRecorder produced an empty video" in script
    assert "no replay frames found" in script
    assert "discardLiveReplayVideo" not in script
    assert "ensureReplayVideoGenerated" in script
    assert "setRunButtonCancel({ disabled: true })" in script
    assert "state.finishingRun = true" in script
    assert "state.finishingRun = false" in script
    assert script.index("ensureReplayVideoGenerated") < script.index("clearSelectedYamlRegion()", script.index("ensureReplayVideoGenerated"))
    assert "!state.currentRequestId && !state.finishingRun" in script
    assert "} else if (state.finishingRun)" in script
    assert script.index("setRunButtonCancel({ disabled: true })") < script.index("ensureReplayVideoGenerated")
    assert script.index("ensureReplayVideoGenerated") < script.index("setRunButtonIdle();", script.index("ensureReplayVideoGenerated"))
    assert "replayVideoMimeType" in script
    assert "MediaRecorder.isTypeSupported" in script
    assert "uploadReplayVideo" in script
    assert "blobToBase64" in script
    assert "const seekable = await makeReplaySeekable(videoBlob, durationMs);" in script
    assert "Replay video is not seekable" in script
    assert "Failed to rewrite WebM index" in script
    assert "els.replayVideo.addEventListener('loadedmetadata', normalizeReplayVideoDuration)" not in script
    assert "finishDurationFix" not in script
    assert "els.replayVideo.currentTime = 1e101" not in script
    assert "await showReplayVideoPreview(replayVideo.videoUrl)" in script
    assert "showRightTab('preview')" in script
    assert "api(`/replay-video/${encodeURIComponent(requestId)}`)" in script
    assert "method: 'POST'" in script
    assert "recorder.start();" in script
    assert "replayVideo.videoUrl" in script
    assert "replayFrameDelay" in script
    assert "[replay-video] draw screenshot" in script
    assert "replayFrameDisplayDuration" in script
    assert "durationMs" in script
    assert "api(`/replay/${encodeURIComponent(requestId)}`)" in script
    assert "next.timestamp - current.timestamp" in script
    assert "window.setTimeout" in script
    assert "window.clearTimeout" not in script
    assert "No replay frames yet." not in script
    assert "No replay run yet." not in script
    assert "Unable to load replay" not in script
    assert "eventStatus" in script
    assert "statusFromValue" in script
    assert "progress-status-${status}" in script
    assert "/session/auto" in script
    assert "ensureSession" in script
    assert "padStart(3, '0')" in script
    assert "progress-number" in styles
    assert "#replay-video" in styles
    assert "status-pill" in styles
    assert "status-ready" in styles
    assert "status-running" in styles
    assert "status-error" in styles
    assert "progress-run-id" in styles
    assert ".progress-run-id:hover" in styles
    assert ".progress-run-id.progress-run-id-selected" in styles
    assert "flex: 0 0 auto" in styles
    assert "progress-title" in styles
    assert ".progress-item:hover" in styles
    assert ".progress-item.progress-item-active" in styles
    assert ".progress-item.progress-item-selected" in styles
    assert "background: #dbeafe" in styles
    assert "box-shadow: inset 3px 0 0 #2563eb" in styles
    assert "box-shadow: inset 3px 0 0 #60a5fa" in styles
    assert "cursor: pointer" in styles
    assert "progress-message" in styles
    assert "progress-tool" in styles
    assert "progress-detail" in styles
    assert "progress-status-dot" in styles
    assert "progress-status-success" in styles
    assert ".replay-video-play" not in styles
    assert ".replay-video-progress" not in styles
    assert "progress-status-failed" in styles
    assert "screenshot-refresh" not in styles
    assert "#22c55e" in styles
    assert "#ef4444" in styles
    assert ".progress-pane" in styles
    assert "grid-template-rows: auto minmax(0, 1fr) auto auto" not in styles
    assert "grid-template-rows: auto minmax(420px, 62vh) auto auto" not in styles
    assert "run-mode-row" in styles
    assert "report-pane" in styles
    assert "report-content" in styles
    assert "tab-button.active" in styles
    assert "[hidden]" in styles


def test_playground_static_yaml_section_is_left_side_context() -> None:
    static_dir = Path(__file__).parents[1] / "fsq_agent" / "playground" / "static"
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    script = (static_dir / "playground.js").read_text(encoding="utf-8")
    styles = (static_dir / "playground.css").read_text(encoding="utf-8")
    run_start = html.index('class="section run-section"')
    run_section = html[run_start:html.index("</section>", run_start)]
    yaml_section = html[html.index('id="yaml-section"'):html.index('</section>\n\n        <section class="section">')]

    assert html.index('id="yaml-section"') < html.index("<h2>Session</h2>")
    assert html.index('id="case-yaml"') > html.index('class="section run-section"')
    assert 'id="case-yaml"' in run_section
    assert 'id="yaml-path-row"' in run_section
    assert 'class="run-input-row"' in run_section
    assert 'id="case-yaml"' not in yaml_section
    assert "yaml-input-tab" in html
    assert "yaml-recorded-tab" in html
    assert "yaml-input-pane" in html
    assert "yaml-recorded-pane" in html
    assert "yaml-refresh" not in html
    assert "yaml-copy" not in html
    assert "yaml-input-viewer" in html
    assert "yaml-recorded-viewer" in html
    assert "yaml-placeholder" not in html
    assert "loadInputYaml" in script
    assert "loadRecordedYaml" in script
    assert "showYamlView" in script
    assert "copyActiveYaml" not in script
    assert "renderYamlDisplay" in script
    assert "renderYamlContent" not in script
    assert "highlightYamlLine" not in script
    assert "renderYamlCaseTitle" in script
    assert "renderYamlCaseSummary" in script
    assert "[metadata.platform, metadata.schemaVersion]" not in script
    assert "renderYamlSteps" in script
    assert "renderYamlStep" in script
    assert "card.dataset.yamlStepIndex" in script
    assert "card.dataset.yamlAction" in script
    assert "card.dataset.yamlActionKey" in script
    assert "normalizeYamlActionName" in script
    assert "renderYamlParams" in script
    assert "renderYamlNestedParams" in script
    assert "formatYamlValue" in script
    assert "setRecordedYamlNoContent" in script
    assert "api(`/yaml/input?path=${encodeURIComponent(path)}`)" in script
    assert "setYamlInputStatus('', 'success')" in script
    assert "message === 'No YAML loaded.' ? '' : message" in script
    assert "clearYamlInput('YAML path is required.')" not in script
    assert "renderYamlEmpty(els.yamlInputViewer, error.message)" not in script
    assert "renderYamlEmpty(els.yamlInputViewer, '')" in script
    assert "if (!message) return" in script
    assert "yaml.resolvedPath || path" not in script
    assert "element.hidden = !message" in script
    assert "api(`/yaml/recorded/${encodeURIComponent(runId)}`)" in script
    assert "await loadRecordedYaml(progress.result.runId, progress.result.recording || null)" in script
    assert "recordedYamlLoaded" not in script
    assert "return Boolean(yaml.content)" not in script
    assert "setYamlRecordedStatus(recordingStatusSummary" not in script
    assert "setYamlRecordedStatus('No recorded YAML yet.'" not in script
    assert "state.yamlInputContent" in script
    assert "state.yamlRecordedContent" in script
    assert "state.yamlInputLastPreviewPath" in script
    assert "selectedYamlRegion" in script
    assert "selectedYamlStepCard" in script
    assert "selectedYamlCaseSummary" in script
    assert "selectedYamlCaseTitle" in script
    assert "activeYamlStepCard" in script
    assert "activeYamlStepClearTimer" in script
    assert "YAML_SELECTABLE_REGION_SELECTOR" in script
    assert "yamlPathRow" in script
    assert "yamlSection" in script
    assert "yamlTabs" in script
    assert "els.yamlSection.hidden = false" in script
    assert "els.yamlCopy" not in script
    assert "els.yamlInputTab.hidden = true" in script
    assert "els.yamlRecordedTab.hidden = false" in script
    assert "els.yamlInputTab.hidden = false" in script
    assert "els.yamlRecordedTab.hidden = true" in script
    assert "const progressAvailable = !els.yamlProgressTab.hidden" in script
    assert "if (viewName === 'progress' && progressAvailable) selectedView = 'progress'" in script
    assert "els.progressPane.hidden = !showProgress" in script
    assert "els.yamlPathRow.hidden = !hasInputYaml" in script
    assert "els.caseYaml.disabled = !hasInputYaml || Boolean(state.currentRequestId)" in script
    assert "yamlRefresh" not in script
    assert "els.yamlInputTab.hidden = true" in script
    assert "els.yamlInputTab.hidden = false" in script
    assert "if (mode === 'goal')" in script
    assert "showYamlView('progress')" in script
    assert "function syncYamlTabOrder(mode)" in script
    assert "mode === 'goal' || mode === 'yaml'" in script
    assert "? [els.yamlProgressTab, els.yamlInputTab, els.yamlRecordedTab]" in script
    assert ": [els.yamlInputTab, els.yamlRecordedTab, els.yamlProgressTab]" in script
    assert "showYamlView('recorded')" in script
    assert "Input YAML inactive in Goal mode" not in script
    assert "loadInputYaml();" in script
    assert "clipboard" not in script
    assert "execCommand('copy')" not in script
    assert "clearSelectedYamlRegion" in script
    assert "clearActiveYamlStepCard" in script
    assert "function clearActiveYamlStepCard(root = null)" in script
    assert "function clearSelectedYamlRegion(root = null)" in script
    assert "if (root && !root.contains(state.activeYamlStepCard)) return" in script
    assert "if (root && state.selectedYamlRegion && !root.contains(state.selectedYamlRegion)) return" in script
    assert "clearStepArtifactPreview" in script
    assert "selectYamlRegion" in script
    assert "handleYamlRegionClick" in script
    assert "document.addEventListener('click', handleYamlRegionClick)" in script
    assert "if (state.currentRequestId || state.finishingRun) return" in script
    assert script.count("if (state.currentRequestId || state.finishingRun) return") >= 3
    assert "if (els.yamlInputViewer.contains(region) && currentRunMode() !== 'strict-yaml') return" in script
    assert "if (!runId) return" in script
    assert "els.yamlRecordedViewer.contains(region)" in script
    assert "const stepCard = region.closest('.yaml-step-card')" in script
    assert "const caseSummary = region.closest('.yaml-case-summary')" in script
    assert "const caseTitle = region.closest('.yaml-case-title-row')" in script
    assert "if (stepCard && stepCard !== region) stepCard.classList.add('yaml-region-selected')" in script
    assert "if (caseSummary && caseSummary !== region) caseSummary.classList.add('yaml-region-selected')" in script
    assert "state.selectedYamlCaseTitle.classList.add('yaml-region-selected')" in script
    assert "yaml-section" in styles
    assert "flex: 1 1 auto" in styles
    assert "min-height: 260px" in styles
    assert "--control-panel-width: clamp(320px, 32vw, 520px)" in styles
    assert "grid-template-columns: minmax(300px, var(--control-panel-width)) 8px minmax(0, 1fr)" in styles
    assert "panel-resizer" in styles
    assert "cursor: col-resize" in styles
    assert "yaml-tabs" in styles
    assert "width: fit-content" in styles
    assert "border-bottom: 1px solid #d8dee8" in styles
    assert ".yaml-tab-button.active::after" in styles
    assert "box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12)" not in styles
    assert "run-input-row" in styles
    assert "grid-template-columns: minmax(0, 1fr) auto" in styles
    assert ".run-input-row .yaml-path-row" in styles
    assert ".run-input-row #run-selected" in styles
    assert "grid-column: 1 / -1" in styles
    assert "justify-self: end" in styles
    assert "height: calc(100vh - 24px)" in styles
    assert "yaml-viewer" in styles
    assert "yaml-placeholder" not in styles
    assert "max-height: min(32vh, 330px)" not in styles
    assert "yaml-code-row" not in styles
    assert "yaml-line-number" not in styles
    assert "yaml-case-summary" in styles
    assert ".yaml-case-summary:hover" in styles
    assert ".yaml-case-summary.yaml-region-selected" in styles
    assert "yaml-case-title-row" in styles
    assert ".yaml-case-title-row:hover" in styles
    assert ".yaml-case-title-row.yaml-region-selected" in styles
    assert "background: #d7eaff" in styles
    assert "box-shadow: inset 3px 0 0 #93c5fd" in styles
    assert "position: sticky" in styles
    assert "top: 0" in styles
    assert "z-index: 1" in styles
    assert "border-bottom: 1px solid #d8e8fb" in styles
    assert "background: #eef6ff" in styles
    assert "color: #0f4c81" in styles
    assert "yaml-metadata-grid" in styles
    assert ".yaml-metadata-item:hover" in styles
    assert ".yaml-metadata-item.yaml-region-selected" in styles
    assert "yaml-chip" in styles
    assert "yaml-step-card" in styles
    assert ".yaml-step-card:hover" in styles
    assert ".yaml-step-card:focus-within" in styles
    assert ".yaml-step-card.yaml-step-card-active" in styles
    assert ".yaml-step-card.yaml-region-selected" in styles
    assert "yaml-step-header" in styles
    assert ".yaml-step-card:hover .yaml-step-header" in styles
    assert ".yaml-step-card.yaml-step-card-active .yaml-step-header" in styles
    assert ".yaml-step-card.yaml-region-selected .yaml-step-header" in styles
    assert ".yaml-step-card.yaml-region-selected .yaml-step-index" in styles
    assert ".yaml-step-card.yaml-step-card-active .yaml-step-index" in styles
    assert "color: #0f3f8a" in styles
    assert "font-size: 13px" in styles
    assert "step-artifact-preview" in styles
    assert "step-artifact-screenshot-row" in styles
    assert "step-artifact-compare" in styles
    assert "step-artifact-text-card" in styles
    assert "isXmlStepArtifact" in script
    assert "step-artifact-xml" in script
    assert 'payload.get("xml")' in (Path(__file__).parents[1] / "fsq_agent" / "playground" / "_server.py").read_text(encoding="utf-8")
    assert "pre.step-artifact-xml" in styles
    assert "border-left-color: #86efac" in styles
    assert "step-artifact-connector" in styles
    assert "before / after" not in script
    assert ".step-artifact-connector::before" in styles
    assert ".step-artifact-connector::after" in styles
    assert "rotate(45deg)" in styles
    assert "step-artifact-arrow" not in styles
    assert "border-radius: 999px" in styles
    assert "arrow.textContent = '->'" not in script
    assert "border-left: 3px solid #bfdbfe" in styles
    assert "white-space: pre" in styles
    assert "tab-size: 2" in styles
    assert "background: #0f172a" not in styles
    assert "cursor: pointer" in styles
    assert "yaml-action-name" in styles
    assert "width: fit-content" in styles
    assert "border-radius: 6px" in styles
    assert "yaml-action-name-setup" in styles
    assert "yaml-action-name-action" in styles
    assert "yaml-action-name-assertion" in styles
    assert "yaml-action-name-teardown" in styles
    assert "yaml-step-kind" not in styles
    assert "yaml-step-kind" not in script
    assert "yaml-param-row" in styles
    assert ".yaml-param-row:hover" in styles
    assert ".yaml-param-row.yaml-region-selected" in styles
    assert "yaml-param-nested" in styles
    assert "yaml-param-row-nested" in styles
    assert "yaml-param-value-null" in styles
    assert "font-style: italic" in styles
    assert "yaml-param-value-secret" in styles


def test_playground_progress_prefers_sse_with_polling_fallback() -> None:
    static_dir = Path(__file__).parents[1] / "fsq_agent" / "playground" / "static"
    script = (static_dir / "playground.js").read_text(encoding="utf-8")
    assert "window.EventSource" in script
    assert "new EventSource(`/task-stream/${encodeURIComponent(requestId)}`)" in script
    assert "state.progressStream" in script
    assert "stream.onmessage" in script
    assert "function applyProgress(progress)" in script
    assert "function stopProgressUpdates()" in script
    assert "window.setInterval(refreshProgress, PROGRESS_POLL_INTERVAL_MS)" in script