# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import json
import mimetypes
import time
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from fsq_agent.models import FsqAgentError

from ._cases import discover_cases
from ._evidence import EvidenceProjection, read_replay_frames, read_screenshot, read_step_artifacts, read_ui_snapshot, safe_exception_message, safe_text
from ._execution import ExecutionHandle, prepare_run, start_execution
from ._readiness import load_control_plane_settings, readiness
from ._replay import read_replay_video, replay_video_metadata, store_replay_video
from ._state import BusyError, ControlPlaneState, RequestNotFoundError
from ._targets import discover_targets

_API_PREFIX = "/api/control-plane"
_JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"}
_MAX_BODY_BYTES = 36 * 1024 * 1024


class _RunNotTerminalError(RuntimeError):
    pass


@dataclass(frozen=True)
class ControlPlaneServerOptions:
    host: str = "127.0.0.1"
    port: int = 8879
    open_browser: bool = True
    workspace_path: Path = field(default_factory=lambda: Path.cwd() / ".fsq-agent-workspace")
    static_path: Path | None = None


class ControlPlaneServer:
    def __init__(self, options: ControlPlaneServerOptions | None = None) -> None:
        self.options = options or ControlPlaneServerOptions()
        self.state = ControlPlaneState()
        self._static_root = (self.options.static_path or Path(__file__).parent / "static").resolve()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._handles: dict[str, ExecutionHandle] = {}

    @property
    def port(self) -> int:
        return int(self._httpd.server_address[1]) if self._httpd is not None else self.options.port

    @property
    def url(self) -> str:
        return f"http://{self.options.host}:{self.port}"

    def start(self) -> None:
        if self._httpd is not None:
            return
        if self._entry_path() is None:
            raise FileNotFoundError(f"Control Plane frontend build not found under {self._static_root}. Run npm ci and npm run build.")
        self._httpd = _ControlPlaneHTTPServer((self.options.host, self.options.port), _RequestHandler, self)
        self._thread = Thread(target=self._httpd.serve_forever, name="fsq-control-plane-server", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        if httpd is None:
            return
        httpd.shutdown()
        httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    def handle_get(self, path: str, query: dict[str, list[str]] | None = None) -> tuple[int, Any, dict[str, str]]:
        query = query or {}
        try:
            if path == f"{_API_PREFIX}/bootstrap":
                initialized = self.options.workspace_path.is_dir() and (self.options.workspace_path / ".fsq-agent-workspace").is_file()
                return 200, self.state.bootstrap(self.options.workspace_path.name, initialized=initialized), dict(_JSON_HEADERS)
            if path == f"{_API_PREFIX}/readiness":
                platform = _platform_query(query)
                return 200, readiness(platform, self.options.workspace_path), dict(_JSON_HEADERS)
            if path == f"{_API_PREFIX}/targets":
                settings = load_control_plane_settings(_platform_query(query), self.options.workspace_path)
                return 200, discover_targets(settings), dict(_JSON_HEADERS)
            if path == f"{_API_PREFIX}/cases":
                settings = load_control_plane_settings(_platform_query(query), self.options.workspace_path)
                return 200, discover_cases(settings), dict(_JSON_HEADERS)
            request_id, suffix = _run_route(path)
            if suffix == "":
                if self.state.snapshot(request_id).get("terminal"):
                    self._hydrate_evidence(request_id)
                return 200, self.state.snapshot(request_id), dict(_JSON_HEADERS)
            if suffix == "/screen":
                self._hydrate_evidence(request_id)
                artifact, _ = self.state.artifact(request_id, "screenshot")
                data, headers = read_screenshot(artifact)
                frozen_platform = str(self.state.snapshot(request_id)["platform"])
                return 200, data, {**headers, "X-Evidence-Platform": frozen_platform, "Cache-Control": "no-store"}
            if suffix == "/ui-snapshot":
                self._hydrate_evidence(request_id)
                artifact, _ = self.state.artifact(request_id, "ui_snapshot")
                payload, headers = read_ui_snapshot(artifact)
                return 200, payload, {**_JSON_HEADERS, **headers}
            if suffix.startswith("/step-artifacts/"):
                run_dir = self._terminal_run_dir(request_id)
                step_id = unquote(suffix.removeprefix("/step-artifacts/")).strip()
                return 200, read_step_artifacts(run_dir, step_id), dict(_JSON_HEADERS)
            if suffix == "/replay":
                return 200, read_replay_frames(self._terminal_run_dir(request_id)), dict(_JSON_HEADERS)
            if suffix == "/replay-video":
                video_url = f"{_API_PREFIX}/runs/{request_id}/replay-video/file"
                return 200, replay_video_metadata(self._terminal_run_dir(request_id), video_url), dict(_JSON_HEADERS)
            if suffix == "/stream":
                return 400, _error("sse_required", "Use an SSE client for the stream endpoint.", "Connect with EventSource."), dict(_JSON_HEADERS)
            return 404, _error("not_found", "Control Plane endpoint not found.", "Check the API path."), dict(_JSON_HEADERS)
        except RequestNotFoundError:
            return 404, _error("request_not_found", "Run request not found.", "Reload Control Plane to find the active request."), dict(_JSON_HEADERS)
        except FileNotFoundError as exc:
            return 404, _error("evidence_unavailable", str(exc), "Wait for evidence capture or select another evidence view."), dict(_JSON_HEADERS)
        except OverflowError as exc:
            return 413, _error("evidence_too_large", str(exc), "Inspect the persisted artifact outside the Control Plane display."), dict(_JSON_HEADERS)
        except _RunNotTerminalError as exc:
            return 409, _exception_error("run_not_terminal", exc, "Wait for the run to finish."), dict(_JSON_HEADERS)
        except (ValueError, FsqAgentError) as exc:
            return 400, _exception_error("invalid_request", exc, "Correct the request and retry."), dict(_JSON_HEADERS)
        except OSError as exc:
            return 503, _exception_error("unavailable", exc, "Verify local platform configuration and retry."), dict(_JSON_HEADERS)
        except Exception as exc:  # noqa: BLE001 - HTTP boundary does not expose tracebacks.
            return 500, _exception_error("internal_error", exc, "Retry or inspect the local server logs.", unexpected=True), dict(_JSON_HEADERS)

    def handle_post(self, path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if path == f"{_API_PREFIX}/runs":
            return self._start_run(body)
        try:
            request_id, suffix = _run_route(path)
            if suffix == "/replay-video":
                stored = store_replay_video(self._terminal_run_dir(request_id), body.get("mimeType"), body.get("videoBase64"))
                return 200, {**stored, "videoUrl": f"{_API_PREFIX}/runs/{request_id}/replay-video/file"}
            if suffix != "/cancel":
                return 404, _error("not_found", "Control Plane endpoint not found.", "Check the API path.")
            snapshot = self.state.request_cancel(request_id)
            handle = self._handles.get(request_id)
            if handle is not None:
                handle.cancel()
        except RequestNotFoundError:
            return 404, _error("request_not_found", "Run request not found.", "Reload Control Plane to find the active request.")
        except ValueError as exc:
            return 400, _exception_error("invalid_request", exc, "Correct the request and retry.")
        except OverflowError as exc:
            return 413, _exception_error("body_too_large", exc, "Upload a smaller replay video.")
        except _RunNotTerminalError as exc:
            return 409, _exception_error("run_not_terminal", exc, "Wait for the run to finish.")
        else:
            return 200, snapshot

    def handle_replay_video_file(self, request_id: str, range_header: str | None) -> tuple[int, bytes, dict[str, str]]:
        return read_replay_video(self._terminal_run_dir(request_id), range_header)

    def sse_snapshots(self, request_id: str, *, after_sequence: int = 0, timeout: float = 15.0):
        revision = -1
        sequence = max(0, after_sequence)
        while True:
            snapshot, revision = self.state.wait_for_update(request_id, after_sequence=sequence, revision=revision, timeout=timeout)
            events = snapshot.get("events") or []
            if events:
                sequence = max(sequence, *(int(event.get("sequence", 0)) for event in events))
            yield snapshot
            if snapshot.get("terminal"):
                return

    def static_response(self, request_path: str) -> tuple[int, bytes, str]:
        decoded = unquote(urlsplit(request_path).path)
        relative = PurePosixPath(decoded.lstrip("/"))
        if any(part in {"..", "."} for part in relative.parts):
            return 404, b"Not found", "text/plain; charset=utf-8"
        candidate = (self._static_root / Path(*relative.parts)).resolve()
        if _is_relative_to(candidate, self._static_root) and candidate.is_file():
            return 200, candidate.read_bytes(), mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if relative.suffix:
            return 404, b"Not found", "text/plain; charset=utf-8"
        entry = self._entry_path()
        if entry is None:
            return 404, b"Control Plane frontend build not found. Run npm ci and npm run build.", "text/plain; charset=utf-8"
        return 200, entry.read_bytes(), "text/html; charset=utf-8"

    def _start_run(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        platform = body.get("platform")
        target_id = body.get("targetId")
        mode = body.get("mode")
        if not isinstance(platform, str) or not isinstance(target_id, str) or not isinstance(mode, str):
            return 400, _error("invalid_run", "mode, platform, and targetId are required.", "Complete the run form and retry.")
        source = {"goal": body["goal"]} if isinstance(body.get("goal"), str) else {"casePath": body["casePath"]} if isinstance(body.get("casePath"), str) else {}
        settings = None
        try:
            request_id = self.state.reserve(platform=platform, target_id=target_id, mode=mode, source=source)
        except BusyError as exc:
            return 409, _exception_error("busy", exc, "Wait for the active run to finish or cancel it.")
        try:
            settings = load_control_plane_settings(platform, self.options.workspace_path)
            prepared = prepare_run(request_id=request_id, settings=settings, body=body)
            self._handles[request_id] = start_execution(prepared, self.state)
        except (TypeError, ValueError, FsqAgentError, OSError) as exc:
            self.state.abandon_preparation(request_id)
            return 400, _exception_error("run_validation_failed", exc, "Refresh readiness, targets, and cases, then retry.", settings=settings)
        except Exception as exc:  # noqa: BLE001
            self.state.abandon_preparation(request_id)
            return 500, _exception_error("run_start_failed", exc, "Inspect local configuration and retry.", unexpected=True)
        else:
            return 202, {"requestId": request_id}

    def _hydrate_evidence(self, request_id: str) -> None:
        artifact, run_id = self.state.artifact(request_id, "screenshot")
        ui_artifact, _ = self.state.artifact(request_id, "ui_snapshot")
        if not run_id:
            return
        run_dir = self.state.run_directory(request_id)
        if not isinstance(run_dir, Path):
            return
        projection = EvidenceProjection(self.state, request_id, run_dir.parent)
        projection.bind_run(run_id)
        if not (artifact and ui_artifact):
            projection.load_persisted_manifest()
        projection.load_persisted_step_ids()

    def _terminal_run_dir(self, request_id: str) -> Path:
        snapshot = self.state.snapshot(request_id)
        if not snapshot.get("terminal"):
            raise _RunNotTerminalError("Run evidence is available after the run reaches a terminal state.")
        run_id = snapshot.get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise FileNotFoundError("Run artifacts are unavailable.")
        run_dir = self.state.run_directory(request_id)
        if not isinstance(run_dir, Path) or not run_dir.is_dir():
            raise FileNotFoundError("Run artifacts are unavailable.")
        return run_dir

    def _entry_path(self) -> Path | None:
        candidates = (self._static_root / "control-plane" / "index.html", self._static_root / "index.html")
        return next((path for path in candidates if path.is_file()), None)


class _ControlPlaneHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, control_plane: ControlPlaneServer) -> None:
        self.control_plane = control_plane
        super().__init__(address, handler)


class _RequestHandler(BaseHTTPRequestHandler):
    server: _ControlPlaneHTTPServer

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if parsed.path.startswith(_API_PREFIX):
            request_id, suffix = _run_route_or_empty(parsed.path)
            if request_id and suffix == "/stream":
                self._send_sse(request_id, query)
                return
            if request_id and suffix == "/replay-video/file":
                try:
                    status, body, headers = self.server.control_plane.handle_replay_video_file(request_id, self.headers.get("Range"))
                    self._send(status, body, headers)
                except RequestNotFoundError:
                    self._send(404, _error("request_not_found", "Run request not found.", "Reload Control Plane."), _JSON_HEADERS)
                except FileNotFoundError as exc:
                    self._send(404, _error("evidence_unavailable", str(exc), "Wait for replay generation."), _JSON_HEADERS)
                except (_RunNotTerminalError, ValueError) as exc:
                    self._send(409 if isinstance(exc, _RunNotTerminalError) else 416, _error("invalid_range", str(exc), "Retry with a valid range after completion."), _JSON_HEADERS)
                return
            status, body, headers = self.server.control_plane.handle_get(parsed.path, query)
            self._send(status, body, headers)
            return
        status, body, content_type = self.server.control_plane.static_response(self.path)
        self._send(status, body, {"Content-Type": content_type})

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > _MAX_BODY_BYTES:
                self._send(413, _error("body_too_large", "Request body is too large.", "Send a smaller JSON request."), _JSON_HEADERS)
                return
            body = _decode_json_body(self.rfile.read(length))
        except (TypeError, ValueError, json.JSONDecodeError):
            self._send(400, _error("invalid_json", "Request body must be a JSON object.", "Correct the request body."), _JSON_HEADERS)
            return
        status, payload = self.server.control_plane.handle_post(parsed.path, body)
        self._send(status, payload, _JSON_HEADERS)

    def log_message(self, format_string: str, *args: Any) -> None:
        return

    def _send_sse(self, request_id: str, query: dict[str, list[str]]) -> None:
        try:
            after = _after_sequence(query)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            for snapshot in self.server.control_plane.sse_snapshots(request_id, after_sequence=after):
                events = snapshot.get("events") or []
                sequence = max((int(event.get("sequence", 0)) for event in events), default=after)
                payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
                self.wfile.write(f"id: {sequence}\nevent: snapshot\ndata: {payload}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except (RequestNotFoundError, ValueError) as exc:
            if not self.wfile.closed:
                payload = json.dumps(_exception_error("stream_error", exc, "Reload the active run."), separators=(",", ":"))
                self.wfile.write(f"event: error\ndata: {payload}\n\n".encode())

    def _send(self, status: int, body: Any, headers: dict[str, str]) -> None:
        if isinstance(body, bytes):
            encoded = body
        else:
            encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_control_plane(options: ControlPlaneServerOptions) -> None:
    server = ControlPlaneServer(options)
    server.start()
    try:
        print(f"Control Plane: {server.url}")
        if options.open_browser:
            webbrowser.open(server.url)
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return
    finally:
        server.stop()


def _platform_query(query: dict[str, list[str]]) -> str:
    values = query.get("platform") or []
    if len(values) != 1 or values[0] not in {"android", "web", "windows", "macos"}:
        raise ValueError("platform must be one of android, web, windows, or macos.")
    return values[0]


def _decode_json_body(raw: bytes) -> dict[str, Any]:
    body = json.loads(raw or b"{}")
    if not isinstance(body, dict):
        raise TypeError("Request body must be a JSON object.")
    return body


def _after_sequence(query: dict[str, list[str]]) -> int:
    values = query.get("afterSequence") or ["0"]
    if len(values) != 1:
        raise ValueError("afterSequence must be one non-negative integer.")
    value = int(values[0])
    if value < 0:
        raise ValueError("afterSequence must be non-negative.")
    return value


def _run_route(path: str) -> tuple[str, str]:
    prefix = f"{_API_PREFIX}/runs/"
    if not path.startswith(prefix):
        raise ValueError("Invalid run endpoint.")
    remainder = unquote(path.removeprefix(prefix))
    request_id, separator, suffix = remainder.partition("/")
    if not request_id:
        raise ValueError("request id is required.")
    return request_id, f"/{suffix}" if separator else ""


def _run_route_or_empty(path: str) -> tuple[str | None, str | None]:
    try:
        return _run_route(path)
    except ValueError:
        return None, None


def _error(code: str, message: str, action: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": safe_text(message), "action": safe_text(action, limit=500)}
    if details:
        payload["details"] = _safe_details(details)
    return payload


def _exception_error(code: str, exc: BaseException, action: str, *, settings: Any | None = None, unexpected: bool = False) -> dict[str, Any]:
    return _error(code, safe_exception_message(exc, settings=settings, unexpected=unexpected, limit=1000), action)


def _safe_details(value: Any, *, depth: int = 0) -> Any:
    if depth >= 4:
        return "[details omitted]"
    if isinstance(value, dict):
        return {safe_text(key, limit=100): _safe_details(item, depth=depth + 1) for key, item in list(value.items())[:50]}
    if isinstance(value, list):
        return [_safe_details(item, depth=depth + 1) for item in value[:50]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return safe_text(value, limit=500)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


__all__ = ["ControlPlaneServer", "ControlPlaneServerOptions", "run_control_plane"]
