# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import time
from pathlib import Path
from threading import Event, Lock, Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fsq_agent.config import Settings, activate_github_copilot_provider
from fsq_agent.control_plane import ControlPlaneServer, ControlPlaneServerOptions
from fsq_agent.models import ConfigurationError
from fsq_agent.providers import GitHubDeviceCode, ProviderConnectionTestResult


def _server(tmp_path: Path, *, host: str = "127.0.0.1") -> ControlPlaneServer:
    return ControlPlaneServer(
        ControlPlaneServerOptions(
            host=host,
            static_path=tmp_path / "static",
            user_config_root=tmp_path / "user",
            open_browser=False,
        )
    )


def _device_code() -> GitHubDeviceCode:
    return GitHubDeviceCode(
        device_code="device-secret",
        user_code="ABCD-EFGH",
        verification_uri="https://github.com/login/device",
        expires_at=time.time() + 600,
        poll_interval_seconds=5,
    )


def test_config_get_initializes_unconfigured_state_with_no_store(tmp_path: Path) -> None:
    server = _server(tmp_path)

    status, payload, headers = server.handle_get("/api/control-plane/config", peer_host="127.0.0.1")

    assert status == 200
    assert payload == {"configured": False, "provider": None}
    assert headers["Cache-Control"] == "no-store"


def test_config_azure_put_and_get_return_complete_local_projection(tmp_path: Path) -> None:
    server = _server(tmp_path)

    status, saved = server.handle_put(
        "/api/control-plane/config/azure",
        {"baseUrl": "https://example.openai.azure.com", "modelName": "gpt-5.4", "apiKey": "complete-key"},
        peer_host="127.0.0.1",
    )
    read_status, loaded, _ = server.handle_get("/api/control-plane/config", peer_host="127.0.0.1")

    assert status == read_status == 200
    assert saved == loaded
    assert loaded == {
        "configured": True,
        "provider": {
            "type": "azure_openai",
            "modelName": "gpt-5.4",
            "baseUrl": "https://example.openai.azure.com/openai/v1/",
            "apiKey": "complete-key",
        },
    }


def test_config_rejects_nonloopback_bind_peer_and_cross_origin_write(tmp_path: Path) -> None:
    nonloopback_server = _server(tmp_path / "bind", host="0.0.0.0")  # noqa: S104 - validates the rejection gate without binding.
    bind_status, bind_error, _ = nonloopback_server.handle_get("/api/control-plane/config", peer_host="127.0.0.1")
    server = _server(tmp_path / "peer")
    peer_status, peer_error, _ = server.handle_get("/api/control-plane/config", peer_host="192.0.2.10")
    origin_status, origin_error = server.handle_put(
        "/api/control-plane/config/azure",
        {"baseUrl": "https://example.openai.azure.com", "modelName": "model", "apiKey": "key"},
        peer_host="127.0.0.1",
        origin="https://evil.example",
        host="127.0.0.1:8879",
    )

    assert bind_status == peer_status == origin_status == 403
    assert bind_error["code"] == peer_error["code"] == "config_unavailable"
    assert origin_error["code"] == "cross_origin_forbidden"
    assert "key" not in str(origin_error)


def test_device_flow_is_independent_from_run_state_and_cancels_idempotently(tmp_path: Path) -> None:
    server = _server(tmp_path)
    server.state.reserve(workspace_name="checkout", platform="web", target_id="chrome", mode="explore", source={"goal": "active"})
    worker_started = Event()

    def complete(_device_code, *, model, cancel_requested, user_config_root):
        worker_started.set()
        while not cancel_requested():
            worker_started.wait(0.01)
        raise ConfigurationError("GitHub device-code authentication was cancelled.")

    with (
        patch("fsq_agent.control_plane._provider_auth.request_github_copilot_device_code", return_value=_device_code()),
        patch("fsq_agent.control_plane._provider_auth.complete_github_copilot_device_flow", side_effect=complete),
    ):
        status, started = server.handle_post(
            "/api/control-plane/config/github/device-flow",
            {"modelName": "copilot-model"},
            peer_host="127.0.0.1",
        )
        worker_started.wait(1)
        busy_status, busy = server.handle_post(
            "/api/control-plane/config/github/device-flow",
            {"modelName": "other-model"},
            peer_host="127.0.0.1",
        )
        cancel_status, cancelled = server.handle_delete(
            f"/api/control-plane/config/github/device-flow/{started['authRequestId']}",
            peer_host="127.0.0.1",
        )
        repeat_status, repeated = server.handle_delete(
            f"/api/control-plane/config/github/device-flow/{started['authRequestId']}",
            peer_host="127.0.0.1",
        )

    assert status == 202
    assert started["status"] == "waiting"
    assert busy_status == 409
    assert busy["code"] == "device_flow_busy"
    assert cancel_status == repeat_status == 200
    assert cancelled["status"] == repeated["status"] == "cancelled"
    server.stop()


def test_device_flow_success_is_queryable_without_returning_tokens(tmp_path: Path) -> None:
    server = _server(tmp_path)

    def complete(_device_code, *, model, cancel_requested, user_config_root):
        return activate_github_copilot_provider(
            model=model,
            github_token={"access_token": "github-secret"},
            provider_token={"token": "provider-secret", "plan": "individual"},
            user_config_root=user_config_root,
        )

    with (
        patch("fsq_agent.control_plane._provider_auth.request_github_copilot_device_code", return_value=_device_code()),
        patch("fsq_agent.control_plane._provider_auth.complete_github_copilot_device_flow", side_effect=complete),
    ):
        status, started = server.handle_post(
            "/api/control-plane/config/github/device-flow",
            {"modelName": "copilot-model"},
            peer_host="127.0.0.1",
        )
        deadline = time.monotonic() + 1
        auth_payload = None
        while time.monotonic() < deadline:
            _, auth_payload, _ = server.handle_get(
                f"/api/control-plane/config/github/device-flow/{started['authRequestId']}",
                peer_host="127.0.0.1",
            )
            if auth_payload["status"] == "success":
                break
            time.sleep(0.01)

    assert status == 202
    assert auth_payload is not None
    assert auth_payload["status"] == "success"
    assert "secret" not in str(auth_payload)
    _, config, _ = server.handle_get("/api/control-plane/config", peer_host="127.0.0.1")
    assert config["provider"] == {"type": "github_copilot", "modelName": "copilot-model", "authenticated": True}


def test_connection_endpoint_accepts_no_fields_and_returns_saved_result(tmp_path: Path) -> None:
    server = _server(tmp_path)
    result = ProviderConnectionTestResult(provider="azure_openai", model="saved-model", duration_seconds=0.125)

    with patch("fsq_agent.control_plane._config.test_model_provider_connection", return_value=result) as test_connection:
        status, payload = server.handle_post(
            "/api/control-plane/config/test-connection",
            {},
            peer_host="127.0.0.1",
        )
        invalid_status, invalid = server.handle_post(
            "/api/control-plane/config/test-connection",
            {"apiKey": "draft-key"},
            peer_host="127.0.0.1",
        )

    assert status == 200
    assert payload == {"success": True, "provider": "azure_openai", "modelName": "saved-model", "durationMs": 125}
    assert invalid_status == 400
    assert invalid["code"] == "invalid_request"
    test_connection.assert_called_once_with(user_config_root=tmp_path / "user")


def test_control_plane_run_start_loads_latest_provider_from_configured_user_root(tmp_path: Path, monkeypatch) -> None:
    server = _server(tmp_path)
    settings = Settings(harness={"platform": "web"})
    captured: dict[str, object] = {}

    def load(workspace_name, platform, user_config_root=None):
        captured.update(workspace_name=workspace_name, platform=platform, user_config_root=user_config_root)
        return settings

    monkeypatch.setattr("fsq_agent.control_plane._server.load_control_plane_settings", load)
    monkeypatch.setattr("fsq_agent.control_plane._server.prepare_run", lambda **kwargs: kwargs)
    monkeypatch.setattr("fsq_agent.control_plane._server.start_execution", lambda prepared, state: object())

    status, _ = server.handle_post(
        "/api/control-plane/runs",
        {"mode": "explore", "workspaceName": "checkout", "platform": "web", "targetId": "chrome", "goal": "Do it"},
    )

    assert status == 202
    assert captured == {
        "workspace_name": "checkout",
        "platform": "web",
        "user_config_root": tmp_path / "user",
    }


def test_actual_http_config_transport_supports_put_and_rejects_cross_origin(tmp_path: Path) -> None:
    static = tmp_path / "static" / "control-plane"
    static.mkdir(parents=True)
    (static / "index.html").write_text("control plane", encoding="utf-8")
    server = _server(tmp_path)
    server.options = ControlPlaneServerOptions(
        host="127.0.0.1",
        port=0,
        static_path=tmp_path / "static",
        user_config_root=tmp_path / "user",
        open_browser=False,
    )
    server.start()
    payload = b'{"baseUrl":"https://example.openai.azure.com","modelName":"model","apiKey":"local-key"}'
    try:
        request = Request(  # noqa: S310 - URL is the in-process loopback server.
            f"{server.url}/api/control-plane/config/azure",
            method="PUT",
            data=payload,
            headers={"Content-Type": "application/json", "Origin": server.url},
        )
        with urlopen(request, timeout=5) as response:  # noqa: S310 - in-process loopback server.
            saved = response.read()
            cache_control = response.headers["Cache-Control"]
        with urlopen(f"{server.url}/api/control-plane/config", timeout=5) as response:  # noqa: S310 - in-process loopback server.
            loaded = response.read()
        cross_origin = Request(  # noqa: S310 - URL is the in-process loopback server.
            f"{server.url}/api/control-plane/config/azure",
            method="PUT",
            data=payload,
            headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
        )
        try:
            urlopen(cross_origin, timeout=5)  # noqa: S310 - in-process loopback server.
        except HTTPError as exc:
            cross_origin_status = exc.code
            cross_origin_body = exc.read()
    finally:
        server.stop()

    assert saved == loaded
    assert b"local-key" in loaded
    assert cache_control == "no-store"
    assert cross_origin_status == 403
    assert b"cross_origin_forbidden" in cross_origin_body
    assert b"local-key" not in cross_origin_body


def test_concurrent_device_flow_starts_reserve_before_requesting_code(tmp_path: Path) -> None:
    server = _server(tmp_path)
    request_entered = Event()
    release_request = Event()
    count_lock = Lock()
    request_count = 0
    results: list[tuple[int, dict[str, object]]] = []

    def request_code() -> GitHubDeviceCode:
        nonlocal request_count
        with count_lock:
            request_count += 1
        request_entered.set()
        release_request.wait(1)
        return _device_code()

    def start_flow(model: str) -> None:
        results.append(
            server.handle_post(
                "/api/control-plane/config/github/device-flow",
                {"modelName": model},
                peer_host="127.0.0.1",
            )
        )

    with (
        patch("fsq_agent.control_plane._provider_auth.request_github_copilot_device_code", side_effect=request_code),
        patch("fsq_agent.control_plane._provider_auth.complete_github_copilot_device_flow", side_effect=ConfigurationError("cancelled")),
    ):
        first = Thread(target=start_flow, args=("first-model",))
        second = Thread(target=start_flow, args=("second-model",))
        first.start()
        request_entered.wait(1)
        second.start()
        second.join(timeout=0.1)
        release_request.set()
        first.join(timeout=1)
        second.join(timeout=1)

    assert request_count == 1
    assert sorted(status for status, _ in results) == [202, 409]


def test_server_stop_cancels_active_device_flow_worker(tmp_path: Path) -> None:
    server = _server(tmp_path)
    worker_started = Event()
    worker_stopped = Event()

    def complete(_device_code, *, model, cancel_requested, user_config_root):
        worker_started.set()
        while not cancel_requested():
            worker_stopped.wait(0.01)
        worker_stopped.set()
        raise ConfigurationError("cancelled")

    with (
        patch("fsq_agent.control_plane._provider_auth.request_github_copilot_device_code", return_value=_device_code()),
        patch("fsq_agent.control_plane._provider_auth.complete_github_copilot_device_flow", side_effect=complete),
    ):
        server.handle_post(
            "/api/control-plane/config/github/device-flow",
            {"modelName": "model"},
            peer_host="127.0.0.1",
        )
        worker_started.wait(1)
        server.stop()

    assert worker_stopped.is_set()
