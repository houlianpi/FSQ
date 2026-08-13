# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pytest

from fsq_agent.config import Settings
from fsq_agent.control_plane import ControlPlaneServer, ControlPlaneServerOptions
from fsq_agent.control_plane._cases import discover_cases, resolve_case
from fsq_agent.control_plane._evidence import UI_SNAPSHOT_LIMIT_BYTES, EvidenceProjection, read_screenshot, read_ui_snapshot, safe_exception_message, safe_text
from fsq_agent.control_plane._execution import _run_explore, _run_strict, prepare_run
from fsq_agent.control_plane._readiness import provider_readiness, readiness
from fsq_agent.control_plane._server import _RequestHandler
from fsq_agent.control_plane._state import BusyError, ControlPlaneState, TaskCancelledError
from fsq_agent.control_plane._targets import discover_targets
from fsq_agent.models import HarnessActionResult, HarnessArtifactRef, HarnessContext, ReportArtifact, RunEvent, RunnerEvent, TaskResult, VerificationResult


def _settings(tmp_path: Path, platform: str = "android") -> Settings:
    settings = Settings(harness={"platform": platform})
    settings.workspace.root_dir = tmp_path / ".fsq-agent-workspace"
    settings.workspace.root_dir.mkdir(parents=True, exist_ok=True)
    settings.cases.dir = tmp_path / "cases"
    settings.cases.dir.mkdir(exist_ok=True)
    settings.output.root_dir = tmp_path / "output"
    settings.output.root_dir.mkdir(exist_ok=True)
    settings.output.runs_dir = settings.output.root_dir / "runs"
    settings.output.runs_dir.mkdir(exist_ok=True)
    return settings


def _case(path: Path, *, platform: str = "android", command: str = "waitMs:\n    duration_ms: 1", app_id: bool = True) -> None:
    app = "appId: com.example.app\n" if app_id else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"schemaVersion: fsq.ai-test/v1\nname: {path.stem}\nplatform: {platform}\n{app}---\n- {command}\n",
        encoding="utf-8",
    )


def _open_loopback(request: str | Request):
    url = request.full_url if isinstance(request, Request) else request
    parsed = urlparse(url)
    assert parsed.scheme == "http"
    assert parsed.hostname in {"127.0.0.1", "localhost"}
    return urlopen(request, timeout=5)  # noqa: S310 - restricted to this in-process loopback server.


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    request = Request(url, method="POST", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})  # noqa: S310
    with _open_loopback(request) as response:
        return json.loads(response.read())


def _wait_for_terminal(url: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with _open_loopback(url) as response:
            snapshot = json.loads(response.read())
        if snapshot["terminal"]:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("Control Plane run did not reach a terminal state")


@pytest.mark.parametrize("disconnect_error", [ConnectionAbortedError, ConnectionResetError, BrokenPipeError])
def test_request_handler_closes_connection_when_client_disconnects(
    monkeypatch: pytest.MonkeyPatch,
    disconnect_error: type[OSError],
) -> None:
    def raise_disconnect(_handler: BaseHTTPRequestHandler) -> None:
        raise disconnect_error()

    monkeypatch.setattr(BaseHTTPRequestHandler, "handle_one_request", raise_disconnect)
    handler = object.__new__(_RequestHandler)
    handler.close_connection = False

    handler.handle_one_request()

    assert handler.close_connection is True


def test_state_holds_single_active_task_through_cancellation() -> None:
    state = ControlPlaneState()
    request_id = state.reserve(platform="android", target_id="serial", mode="explore", source={"goal": "Do it"})

    snapshot = state.request_cancel(request_id)

    assert snapshot["status"] == "preparing"
    assert snapshot["cancelRequested"] is True
    with pytest.raises(BusyError):
        state.reserve(platform="web", target_id="chrome", mode="explore", source={"goal": "Other"})
    with pytest.raises(TaskCancelledError):
        state.raise_if_cancelled(request_id)

    state.finish(request_id, status="cancelled", summary="Run cancelled.")
    replacement = state.reserve(platform="web", target_id="chrome", mode="explore", source={"goal": "Other"})
    assert replacement != request_id


def test_state_sequences_resumable_snapshots_and_releases_only_after_finalizing() -> None:
    state = ControlPlaneState()
    request_id = state.reserve(platform="web", target_id="chrome", mode="strict", source={"casePath": "a.codex.yaml"})
    state.transition(request_id, "running")
    state.add_event(request_id, {"label": "one"})
    state.add_event(request_id, {"label": "two"})
    state.transition(request_id, "finalizing")

    snapshot = state.snapshot(request_id, after_sequence=1)

    assert [event["label"] for event in snapshot["events"]] == ["two"]
    assert snapshot["status"] == "finalizing"
    with pytest.raises(BusyError):
        state.reserve(platform="android", target_id="device", mode="explore", source={"goal": "blocked"})

    state.finish(request_id, status="success", summary="done", result={"status": "success"})
    assert state.snapshot(request_id)["terminal"] is True


def test_state_cancellation_during_finalizing_overrides_later_success() -> None:
    state = ControlPlaneState()
    request_id = state.reserve(platform="web", target_id="chrome", mode="explore", source={"goal": "Go"})
    state.transition(request_id, "running")
    state.transition(request_id, "finalizing")

    state.request_cancel(request_id)
    state.finish(request_id, status="success", summary="completed", result={"status": "success"}, report_available=True)

    snapshot = state.snapshot(request_id)
    assert snapshot["status"] == "cancelled"
    assert snapshot["summary"] == "Run cancelled."
    assert snapshot["result"] == {"status": "cancelled"}


def test_state_cancel_on_terminal_task_is_idempotent_and_does_not_mutate() -> None:
    state = ControlPlaneState()
    request_id = state.reserve(platform="web", target_id="chrome", mode="explore", source={"goal": "Go"})
    state.finish(request_id, status="success", summary="done", result={"status": "success"}, report_available=True)
    before = state.snapshot(request_id)
    revision = state.revision()

    first = state.request_cancel(request_id)
    second = state.request_cancel(request_id)
    state.finish(request_id, status="failed", summary="late failure")

    assert first == second == before
    assert state.snapshot(request_id) == before
    assert state.revision() == revision


def test_android_target_discovery_normalizes_online_offline_and_unauthorized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    settings.harness.android.serial = "emulator-5554"
    completed = subprocess.CompletedProcess(
        ["adb"],
        0,
        "List of devices attached\nemulator-5554 device product:sdk model:Pixel_8 transport_id:1\noffline-1 offline\nlocked-1 unauthorized\n",
        "",
    )
    monkeypatch.setattr("fsq_agent.control_plane._targets.shutil.which", lambda _name: "C:/tools/adb.exe")
    monkeypatch.setattr("fsq_agent.control_plane._targets.subprocess.run", lambda *args, **kwargs: completed)

    payload = discover_targets(settings)

    assert payload["targetLabel"] == "Device"
    assert [(item["id"], item["status"], item["selectable"]) for item in payload["targets"]] == [
        ("emulator-5554", "ready", True),
        ("offline-1", "offline", False),
        ("locked-1", "unauthorized", False),
    ]
    assert payload["targets"][0]["isDefault"] is True
    assert payload["targets"][0]["metadata"]["model"] == "Pixel_8"


@pytest.mark.parametrize(
    ("exception", "target_id", "status"),
    [
        (FileNotFoundError(), "adb-missing", "missing"),
        (subprocess.TimeoutExpired("adb", 5), "adb-timeout", "timeout"),
        (OSError(), "adb-error", "error"),
    ],
)
def test_android_target_discovery_reports_command_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exception: BaseException, target_id: str, status: str) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("fsq_agent.control_plane._targets.shutil.which", lambda _name: "C:/tools/adb.exe")

    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr("fsq_agent.control_plane._targets.subprocess.run", fail)
    target = discover_targets(settings)["targets"][0]
    assert (target["id"], target["status"], target["selectable"]) == (target_id, status, False)


def test_configured_targets_are_safe_and_config_owned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fsq_agent.control_plane._targets.importlib.util.find_spec", lambda _name: object())
    monkeypatch.setattr("fsq_agent.control_plane._targets.validate_strict_core_settings", lambda _settings: None)
    expected = {"web": ("chrome", "Browser"), "windows": ("windows-app", "Application"), "macos": ("macos-app", "Application")}
    for platform, (target_id, target_label) in expected.items():
        settings = _settings(tmp_path / platform, platform)
        if platform == "windows":
            settings.harness.windows.app_path = Path("C:/secret/location/app.exe")
        elif platform == "macos":
            settings.harness.macos.bundle_id = "com.example.app"
        payload = discover_targets(settings)
        assert payload["targetLabel"] == target_label
        assert payload["targets"][0]["id"] == target_id
        assert "secret/location" not in json.dumps(payload)


def test_case_discovery_is_recursive_sorted_validated_and_platform_filtered(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _case(settings.cases.dir / "z.codex.yaml")
    _case(settings.cases.dir / "nested" / "a.codex.yaml")
    _case(settings.cases.dir / "wrong.codex.yaml", platform="web", app_id=False)
    (settings.cases.dir / "broken.codex.yaml").write_text("not: valid: yaml", encoding="utf-8")

    payload = discover_cases(settings)

    assert [entry["path"] for entry in payload["cases"]] == ["broken.codex.yaml", "nested/a.codex.yaml", "wrong.codex.yaml", "z.codex.yaml"]
    assert payload["cases"][1]["validationStatus"] == "validated"
    assert payload["cases"][1]["commandCount"] == 1
    assert payload["cases"][2]["selectable"] is False
    assert payload["cases"][0]["diagnostics"]


def test_case_discovery_limit_and_contained_resolution(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    for index in range(3):
        _case(settings.cases.dir / f"{index}.codex.yaml")

    payload = discover_cases(settings, limit=2)

    assert len(payload["cases"]) == 2
    assert payload["truncated"] is True
    assert resolve_case(settings, "0.codex.yaml") == (settings.cases.dir / "0.codex.yaml").resolve()
    with pytest.raises(ValueError, match="contained"):
        resolve_case(settings, "../outside.codex.yaml")
    with pytest.raises(ValueError, match="relative"):
        resolve_case(settings, str((settings.cases.dir / "0.codex.yaml").resolve()))


def test_case_discovery_derives_ai_requirement_from_registry_snapshots(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _case(settings.cases.dir / "ai.codex.yaml", command="assertWithAI:\n    prompt: Verify the page")

    entry = discover_cases(settings)["cases"][0]

    assert entry["selectable"] is True
    assert entry["requiresAiAssertion"] is True


def test_provider_readiness_is_noninteractive_and_closes_without_model_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Session:
        def close_sync(self) -> None:
            captured["closed"] = True

    def prepare(_settings):
        captured["prepared"] = True
        return Session()

    monkeypatch.setattr("fsq_agent.control_plane._readiness.prepare_model_provider_session", prepare)

    result = provider_readiness(_settings(tmp_path))

    assert result["status"] == "ready"
    assert captured == {"prepared": True, "closed": True}


def test_explore_preparation_normalizes_goal_and_overrides_only_android_serial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    settings.harness.android.serial = "configured-device"
    calls: list[str] = []
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_target", lambda _settings, target: calls.append(f"target:{target}"))
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_runtime_settings", lambda _settings: calls.append("runtime"))
    monkeypatch.setattr("fsq_agent.control_plane._execution.require_provider", lambda _settings: calls.append("provider"))

    prepared = prepare_run(
        request_id="request-1",
        settings=settings,
        body={"mode": "explore", "platform": "android", "targetId": "selected-device", "goal": "  Verify   settings  "},
    )

    assert prepared.goal == "Verify settings"
    assert prepared.settings.harness.android.serial == "selected-device"
    assert settings.harness.android.serial == "configured-device"
    assert calls == ["target:selected-device", "runtime", "provider"]


def test_strict_preparation_validates_lifecycle_children_before_harness_creation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _case(settings.cases.dir / "child.codex.yaml", platform="web", app_id=False)
    root_path = settings.cases.dir / "root.codex.yaml"
    root_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Root\nplatform: android\nappId: com.example.app\nonCaseStart:\n  runCase: child.codex.yaml\n---\n- waitMs:\n    duration_ms: 1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_target", lambda _settings, _target: None)

    with pytest.raises(ValueError, match="lifecycle child platform"):
        prepare_run(
            request_id="request-1",
            settings=settings,
            body={"mode": "strict", "platform": "android", "targetId": "device", "casePath": "root.codex.yaml"},
        )


def test_strict_preparation_builds_registry_and_resolved_steps_without_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _case(settings.cases.dir / "strict.codex.yaml")
    calls: list[bool] = []
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_target", lambda _settings, _target: None)
    monkeypatch.setattr(
        "fsq_agent.control_plane._execution.validate_strict_core_settings",
        lambda _settings, requires_ai_assertion=False: calls.append(requires_ai_assertion),
    )
    monkeypatch.setattr("fsq_agent.control_plane._execution.require_provider", lambda _settings: pytest.fail("provider must not be required"))

    prepared = prepare_run(
        request_id="request-1",
        settings=settings,
        body={"mode": "strict", "platform": "android", "targetId": "device", "casePath": "strict.codex.yaml"},
    )

    assert prepared.registry_snapshot.resolve("waitMs") is not None
    assert [step.action_name for step in prepared.resolved_steps_by_path[prepared.case_path.resolve()]] == ["wait_ms"]
    assert prepared.requires_ai_assertion is False
    assert calls == [False]


def test_strict_preparation_gates_provider_from_registry_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _case(settings.cases.dir / "ai.codex.yaml", command="assertWithAI:\n    prompt: Verify the page")
    calls: list[str] = []
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_target", lambda _settings, _target: None)
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_strict_core_settings", lambda _settings, requires_ai_assertion=False: calls.append(f"strict:{requires_ai_assertion}"))
    monkeypatch.setattr("fsq_agent.control_plane._execution.require_provider", lambda _settings: calls.append("provider"))

    prepared = prepare_run(
        request_id="request-ai",
        settings=settings,
        body={"mode": "strict", "platform": "android", "targetId": "device", "casePath": "ai.codex.yaml"},
    )

    assert prepared.requires_ai_assertion is True
    assert calls == ["strict:True", "provider"]


def test_strict_execution_composes_real_lifecycle_with_fake_harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _case(settings.cases.dir / "wait.codex.yaml")
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_target", lambda _settings, _target: None)
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_strict_core_settings", lambda *_args, **_kwargs: None)
    prepared = prepare_run(
        request_id="request-strict",
        settings=settings,
        body={"mode": "strict", "platform": "android", "targetId": "device", "casePath": "wait.codex.yaml"},
    )
    state = ControlPlaneState()
    request_id = state.reserve(platform="android", target_id="device", mode="strict", source={"casePath": "wait.codex.yaml"})
    prepared.request_id = request_id

    class FakeHarness:
        def get_context(self):
            return HarnessContext(platform="android", session_id="fake")

        def action_space(self):
            return {}

        def before_action(self, step, context):
            return None

        def invoke_action(self, step, context):
            return HarnessActionResult(status="passed", action_name=step.action_name)

        def after_action(self, step, context, action_result):
            return None

        def capture_artifact(self, kind, reason, context, step_id, phase):
            return HarnessArtifactRef(artifact_id=f"{step_id}-{kind}", kind=kind, path=Path(f"artifacts/{step_id}.{kind}"))

        def classify_error(self, error, phase, step):
            return "unknown"

    monkeypatch.setattr("fsq_agent.control_plane._execution.HarnessFactory.create_harness", lambda *_args, **_kwargs: FakeHarness())

    _run_strict(prepared, state)

    snapshot = state.snapshot(request_id)
    assert snapshot["status"] == "success"
    assert snapshot["reportAvailable"] is True
    assert (settings.output.runs_dir / f"{prepared.case.id}-{request_id[:8]}" / "core-report.json").is_file()


@pytest.mark.asyncio
async def test_explore_execution_delegates_to_agent_and_records_without_changing_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    state = ControlPlaneState()
    request_id = state.reserve(platform="android", target_id="device", mode="explore", source={"goal": "Verify it"})
    prepared = type("Prepared", (), {"settings": settings, "request_id": request_id, "goal": "Verify it"})()
    run_dir = settings.output.runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    report_path = run_dir / "report.md"
    report_path.write_text("report", encoding="utf-8")
    captured: dict[str, object] = {}

    class FakeAgent:
        async def run(self, task, event_sink=None):
            captured["task"] = task
            event_sink(RunEvent(run_id="run-1", task_id=task.id, type="run_started", title="Started"))
            return TaskResult(
                task_id=task.id,
                status="failed",
                steps=[],
                verification=VerificationResult(status="failed", summary="Expected failure"),
                report=ReportArtifact(run_id="run-1", path=report_path),
            )

    monkeypatch.setattr("fsq_agent.control_plane._execution.FsqAgent.from_settings", lambda _settings: FakeAgent())

    def record(**kwargs):
        captured["record"] = kwargs
        raise OSError("recording unavailable")

    monkeypatch.setattr("fsq_agent.control_plane._execution.record_dynamic_run_as_strict_case", record)

    await _run_explore(prepared, state)

    snapshot = state.snapshot(request_id)
    assert snapshot["status"] == "failed"
    assert snapshot["reportAvailable"] is True
    assert captured["task"].planning_reference_kind == "goal"
    assert captured["record"]["allow_failure"] is True
    assert any(event["label"] == "Dynamic recording" for event in snapshot["events"])


def test_evidence_projection_rejects_escape_and_reads_latest_artifacts(tmp_path: Path) -> None:
    state = ControlPlaneState()
    request_id = state.reserve(platform="android", target_id="device", mode="explore", source={"goal": "Go"})
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "run-1"
    screenshot = run_dir / "artifacts" / "screen.png"
    snapshot = run_dir / "artifacts" / "tree.json"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"png-data")
    snapshot.write_text('{"node":"safe"}', encoding="utf-8")
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"secret")
    projection = EvidenceProjection(state, request_id, runs_dir, secret_values=("super-secret",))
    projection.bind_run("run-1")

    projection.project_runner_event(RunnerEvent(run_id="run-1", event_type="artifact_captured", step_id="step-1", payload={"kind": "screenshot", "path": "artifacts/screen.png"}))
    projection.project_runner_event(RunnerEvent(run_id="run-1", event_type="artifact_captured", step_id="step-1", payload={"kind": "ui_snapshot", "path": "artifacts/tree.json"}))
    projection.project_runner_event(RunnerEvent(run_id="run-1", event_type="artifact_captured", payload={"kind": "screenshot", "path": str(outside)}))
    projection.project_run_event(RunEvent(run_id="run-1", task_id="task", type="planning_update", title="Plan", message="token=super-secret"))

    screen_ref, _ = state.artifact(request_id, "screenshot")
    tree_ref, _ = state.artifact(request_id, "ui_snapshot")
    data, headers = read_screenshot(screen_ref)
    tree, _ = read_ui_snapshot(tree_ref)
    assert data == b"png-data"
    assert headers["X-Evidence-Revision"] == "1"
    assert tree["content"] == '{"node":"safe"}'
    assert "super-secret" not in json.dumps(state.snapshot(request_id))


def test_safe_messages_redact_paths_credentials_and_configured_runtime_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_TEST_SECRET", "runtime-secret-value")
    settings = _settings(tmp_path)
    settings.runtime_secrets.allowed_env_names = ["CONTROL_PLANE_TEST_SECRET"]
    message = safe_exception_message(
        ValueError(f"Failed at {tmp_path / 'private' / 'case.yaml'} with Bearer abc123 api_key=key-value and runtime-secret-value"),
        settings=settings,
    )

    assert "abc123" not in message
    assert "key-value" not in message
    assert "runtime-secret-value" not in message
    assert str(tmp_path) not in message
    assert "[local path]" in message
    assert safe_exception_message(RuntimeError("backend repr SecretObject(value='x')"), unexpected=True) == "An unexpected Control Plane error occurred."
    assert len(safe_text("x" * 2000, limit=64)) == 64


def test_case_diagnostics_use_safe_sanitizer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    case_path = settings.cases.dir / "unsafe.codex.yaml"
    case_path.write_text("broken", encoding="utf-8")
    monkeypatch.setattr(
        "fsq_agent.control_plane._cases.FsqCaseLoader.load_case",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError(f"Invalid {tmp_path / 'private.yaml'} token=secret-token")),
    )

    diagnostic = discover_cases(settings)["cases"][0]["diagnostics"][0]

    assert str(tmp_path) not in diagnostic
    assert "secret-token" not in diagnostic


def test_sse_generator_yields_status_only_and_terminal_snapshots() -> None:
    server = ControlPlaneServer(ControlPlaneServerOptions(open_browser=False))
    request_id = server.state.reserve(platform="web", target_id="chrome", mode="explore", source={"goal": "Go"})
    server.state.add_event(request_id, {"label": "one"})
    stream = server.sse_snapshots(request_id, after_sequence=1, timeout=0)

    status_only = next(stream)
    server.state.finish(request_id, status="success", summary="done")
    terminal = next(stream)

    assert status_only["events"] == []
    assert status_only["status"] == "preparing"
    assert terminal["events"] == []
    assert terminal["terminal"] is True


def test_screenshot_endpoint_includes_frozen_platform_header(tmp_path: Path) -> None:
    server = ControlPlaneServer(ControlPlaneServerOptions(workspace_path=tmp_path, static_path=tmp_path))
    request_id = server.state.reserve(platform="windows", target_id="app", mode="explore", source={"goal": "Go"})
    screenshot = tmp_path / "screen.png"
    screenshot.write_bytes(b"png")
    server.state.set_artifact(request_id, "screenshot", {"path": screenshot, "mimeType": "image/png"})

    status, body, headers = server.handle_get(f"/api/control-plane/runs/{request_id}/screen")

    assert (status, body) == (200, b"png")
    assert headers["X-Evidence-Platform"] == "windows"


@pytest.mark.parametrize("platform", ["android", "web", "windows", "macos"])
def test_readiness_covers_all_supported_platforms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    settings = _settings(tmp_path / platform, platform)
    monkeypatch.setattr("fsq_agent.control_plane._readiness.load_control_plane_settings", lambda *_args: settings)
    monkeypatch.setattr("fsq_agent.control_plane._readiness.provider_readiness", lambda _settings: {"status": "ready", "message": "ready", "action": ""})
    monkeypatch.setattr("fsq_agent.control_plane._readiness.target_readiness", lambda _settings: (True, "ready", ""))
    monkeypatch.setattr("fsq_agent.control_plane._readiness.validate_strict_core_settings", lambda _settings: None)

    payload = readiness(platform, settings.workspace.root_dir)

    assert payload["platform"] == platform
    assert {payload[key]["status"] for key in ("workspace", "provider", "target", "strict")} == {"ready"}


def test_readiness_and_case_discovery_do_not_require_cases_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    settings.cases.dir.rmdir()
    monkeypatch.setattr("fsq_agent.control_plane._readiness.load_control_plane_settings", lambda *_args: settings)
    monkeypatch.setattr("fsq_agent.control_plane._readiness.provider_readiness", lambda _settings: {"status": "ready", "message": "ready", "action": ""})
    monkeypatch.setattr("fsq_agent.control_plane._readiness.target_readiness", lambda _settings: (True, "ready", ""))
    monkeypatch.setattr("fsq_agent.control_plane._readiness.validate_strict_core_settings", lambda _settings: None)

    payload = readiness("android", settings.workspace.root_dir)

    assert payload["workspace"] == {"status": "ready", "message": "Workspace is ready.", "action": ""}
    assert payload["strict"]["status"] == "ready"
    assert discover_cases(settings) == {"platform": "android", "cases": [], "truncated": False}
    assert not settings.cases.dir.exists()


def test_ui_snapshot_limit_is_local_to_read(tmp_path: Path) -> None:
    path = tmp_path / "large.txt"
    path.write_bytes(b"x" * (UI_SNAPSHOT_LIMIT_BYTES + 1))
    with pytest.raises(OverflowError, match="512 KiB"):
        read_ui_snapshot({"path": path, "revision": 1})


def test_server_static_fallback_and_traversal_are_control_plane_scoped(tmp_path: Path) -> None:
    static = tmp_path / "static"
    entry = static / "control-plane" / "index.html"
    entry.parent.mkdir(parents=True)
    entry.write_text("control plane", encoding="utf-8")
    (static / "asset.js").write_text("asset", encoding="utf-8")
    server = ControlPlaneServer(ControlPlaneServerOptions(static_path=static, open_browser=False))

    assert server.static_response("/")[:2] == (200, b"control plane")
    assert server.static_response("/devices")[:2] == (200, b"control plane")
    assert server.static_response("/asset.js")[:2] == (200, b"asset")
    assert server.static_response("/../secret.txt")[0] == 404
    assert server.static_response("/missing.js")[0] == 404


def test_server_start_requires_frontend_build(tmp_path: Path) -> None:
    server = ControlPlaneServer(ControlPlaneServerOptions(static_path=tmp_path, open_browser=False))
    with pytest.raises(FileNotFoundError, match=r"npm ci.*npm run build"):
        server.start()


def test_server_bootstrap_and_errors_use_structured_shape(tmp_path: Path) -> None:
    server = ControlPlaneServer(ControlPlaneServerOptions(workspace_path=tmp_path / ".fsq-agent-workspace", static_path=tmp_path))
    status, payload, _ = server.handle_get("/api/control-plane/bootstrap")
    invalid_status, error, _ = server.handle_get("/api/control-plane/readiness", {})

    assert status == 200
    assert payload["apiVersion"] == "1.0"
    assert payload["busy"] is False
    assert [platform["id"] for platform in payload["platforms"]] == ["android", "web", "windows", "macos"]
    assert invalid_status == 400
    assert set(error) == {"code", "message", "action"}


def test_server_error_boundary_redacts_validation_and_hides_unexpected_repr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = ControlPlaneServer(ControlPlaneServerOptions(workspace_path=tmp_path, static_path=tmp_path))
    monkeypatch.setattr(
        "fsq_agent.control_plane._server.load_control_plane_settings",
        lambda *_args: (_ for _ in ()).throw(ValueError(f"Invalid file {tmp_path / 'secret' / 'config.yaml'} api_key=credential-value")),
    )

    status, validation, _ = server.handle_get("/api/control-plane/targets", {"platform": ["web"]})
    monkeypatch.setattr(server.state, "bootstrap", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("BackendObject(secret='raw')")))
    unexpected_status, unexpected, _ = server.handle_get("/api/control-plane/bootstrap")

    assert status == 400
    assert "credential-value" not in validation["message"]
    assert str(tmp_path) not in validation["message"]
    assert unexpected_status == 500
    assert unexpected["message"] == "An unexpected Control Plane error occurred."
    assert "BackendObject" not in json.dumps(unexpected)


def test_server_run_start_busy_cancel_and_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = ControlPlaneServer(ControlPlaneServerOptions(workspace_path=tmp_path / "workspace", static_path=tmp_path))
    settings = _settings(tmp_path)
    captured: dict[str, object] = {}

    class Handle:
        def cancel(self) -> None:
            captured["cancelled"] = True

    monkeypatch.setattr("fsq_agent.control_plane._server.load_control_plane_settings", lambda platform, workspace: settings)
    monkeypatch.setattr("fsq_agent.control_plane._server.prepare_run", lambda **kwargs: kwargs)
    monkeypatch.setattr("fsq_agent.control_plane._server.start_execution", lambda prepared, state: Handle())

    status, payload = server.handle_post("/api/control-plane/runs", {"mode": "explore", "platform": "android", "targetId": "device", "goal": "Do it"})
    busy_status, busy = server.handle_post("/api/control-plane/runs", {"mode": "explore", "platform": "android", "targetId": "device", "goal": "Again"})
    cancel_status, cancelled = server.handle_post(f"/api/control-plane/runs/{payload['requestId']}/cancel", {})
    snapshot_status, snapshot, _ = server.handle_get(f"/api/control-plane/runs/{payload['requestId']}")

    assert status == 202
    assert busy_status == 409
    assert busy["code"] == "busy"
    assert cancel_status == 200
    assert cancelled["cancelRequested"] is True
    assert captured["cancelled"] is True
    assert snapshot_status == 200
    assert snapshot["source"] == {"goal": "Do it"}


def test_server_actual_http_dispatches_json(tmp_path: Path) -> None:
    static = tmp_path / "static"
    entry = static / "control-plane" / "index.html"
    entry.parent.mkdir(parents=True)
    entry.write_text("control plane", encoding="utf-8")
    server = ControlPlaneServer(ControlPlaneServerOptions(port=0, static_path=static, open_browser=False))
    server.start()
    try:
        with urlopen(f"{server.url}/api/control-plane/bootstrap", timeout=5) as response:  # noqa: S310 - loopback test server.
            payload = json.loads(response.read())
        with urlopen(f"{server.url}/", timeout=5) as response:  # noqa: S310 - loopback test server.
            body = response.read()
    finally:
        server.stop()

    assert payload["apiVersion"] == "1.0"
    assert body == b"control plane"


def test_server_actual_http_run_paths_sse_evidence_and_cancellation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    static = tmp_path / "static"
    entry = static / "control-plane" / "index.html"
    entry.parent.mkdir(parents=True)
    entry.write_text("control plane", encoding="utf-8")
    settings = _settings(tmp_path, "web")
    _case(settings.cases.dir / "strict.codex.yaml", platform="web", app_id=False)
    monkeypatch.setattr("fsq_agent.control_plane._server.load_control_plane_settings", lambda *_args: settings)
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_target", lambda *_args: None)
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_runtime_settings", lambda *_args: None)
    monkeypatch.setattr("fsq_agent.control_plane._execution.validate_strict_core_settings", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("fsq_agent.control_plane._execution.require_provider", lambda *_args: None)
    monkeypatch.setattr("fsq_agent.control_plane._execution.record_dynamic_run_as_strict_case", lambda **_kwargs: None)

    class FakeAgent:
        async def run(self, task, event_sink=None):
            run_id = f"explore-{task.id}"
            event_sink(RunEvent(run_id=run_id, task_id=task.id, type="run_started", title="Explore started"))
            if "cancel" in task.description.casefold():
                await asyncio.Event().wait()
            run_dir = settings.output.runs_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            report = run_dir / "report.md"
            report.write_text("report", encoding="utf-8")
            return TaskResult(
                task_id=task.id,
                status="success",
                steps=[],
                verification=VerificationResult(status="success", summary="Explore complete"),
                report=ReportArtifact(run_id=run_id, path=report),
            )

    class FakeHarness:
        def __init__(self, store):
            self.store = store

        def get_context(self):
            return HarnessContext(platform="web", session_id="fake")

        def action_space(self):
            return {}

        def before_action(self, step, context):
            return None

        def invoke_action(self, step, context):
            return HarnessActionResult(status="passed", action_name=step.action_name)

        def after_action(self, step, context, action_result):
            return None

        def capture_artifact(self, kind, reason, context, step_id, phase):
            relative = Path("artifacts") / f"{step_id}-{phase}.{('png' if kind == 'screenshot' else 'json')}"
            path = self.store.run_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if kind == "screenshot":
                path.write_bytes(b"png-evidence")
            else:
                path.write_text('{"role":"window"}', encoding="utf-8")
            return HarnessArtifactRef(artifact_id=f"{step_id}-{kind}-{phase}", kind=kind, path=relative)

        def classify_error(self, error, phase, step):
            return "unknown"

    monkeypatch.setattr("fsq_agent.control_plane._execution.FsqAgent.from_settings", lambda _settings: FakeAgent())
    monkeypatch.setattr(
        "fsq_agent.control_plane._execution.HarnessFactory.create_harness",
        lambda *_args, **kwargs: FakeHarness(kwargs["artifact_store"]),
    )
    server = ControlPlaneServer(ControlPlaneServerOptions(port=0, static_path=static, workspace_path=settings.workspace.root_dir, open_browser=False))
    server.start()
    try:
        explore = _post_json(f"{server.url}/api/control-plane/runs", {"mode": "explore", "platform": "web", "targetId": "chrome", "goal": "Verify available platform"})
        with _open_loopback(f"{server.url}/api/control-plane/runs/{explore['requestId']}/stream") as response:
            sse_lines: list[str] = []
            while not any('"terminal":true' in line for line in sse_lines):
                sse_lines.append(response.readline().decode())
            sse = "".join(sse_lines)
        assert "event: snapshot" in sse
        assert "Explore started" in sse
        assert '"terminal":true' in sse

        strict = _post_json(f"{server.url}/api/control-plane/runs", {"mode": "strict", "platform": "web", "targetId": "chrome", "casePath": "strict.codex.yaml"})
        strict_snapshot = _wait_for_terminal(f"{server.url}/api/control-plane/runs/{strict['requestId']}")
        assert strict_snapshot["status"] == "success"
        assert strict_snapshot["screenshotRevision"] > 0
        assert strict_snapshot["uiSnapshotRevision"] > 0
        with _open_loopback(f"{server.url}/api/control-plane/runs/{strict['requestId']}/screen") as response:
            assert response.read() == b"png-evidence"
            assert response.headers["Content-Type"] == "image/png"
        with _open_loopback(f"{server.url}/api/control-plane/runs/{strict['requestId']}/ui-snapshot") as response:
            assert json.loads(response.read())["content"] == '{"role":"window"}'

        cancelling = _post_json(f"{server.url}/api/control-plane/runs", {"mode": "explore", "platform": "web", "targetId": "chrome", "goal": "Cancel this run"})
        cancelled = _post_json(f"{server.url}/api/control-plane/runs/{cancelling['requestId']}/cancel", {})
        assert cancelled["cancelRequested"] is True
        terminal = _wait_for_terminal(f"{server.url}/api/control-plane/runs/{cancelling['requestId']}")
        assert terminal["status"] == "cancelled"
    finally:
        server.stop()
