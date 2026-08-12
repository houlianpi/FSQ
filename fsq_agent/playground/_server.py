# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import base64
import json
import mimetypes
import re
import shutil
import time
import webbrowser
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, unquote, urlparse

import yaml

from fsq_agent.fsq import FsqCaseLoader
from fsq_agent.models import ConfigurationError
from fsq_agent.playground._android import build_android_setup_schema, capture_android_screenshot, resolve_auto_session
from fsq_agent.playground._execution import PlaygroundExecutionHandle, refresh_execution_settings, start_dynamic_goal_execution
from fsq_agent.playground._state import BusyError, PlaygroundState
from fsq_agent.playground._yaml_lifecycle import (
    YamlLifecycleConflictError,
    YamlLifecycleValidationError,
    YamlLifecycleWriteError,
    lifecycle_display,
    save_lifecycle,
    yaml_revision,
)
from fsq_agent.report import resolve_report_path

if TYPE_CHECKING:
    from fsq_agent.config import Settings

YAML_DISPLAY_SIZE_LIMIT_BYTES = 512 * 1024
STEP_ARTIFACT_TEXT_SIZE_LIMIT_BYTES = 512 * 1024
_YAML_COMMAND_CONTROL_KEYS = {"optional", "timeout", "timeout_ms", "evidence", "evidencePolicy"}
_YAML_SETUP_ACTIONS = {"launchApp", "startBrowser"}
_YAML_TEARDOWN_ACTIONS = {"killApp", "closeBrowser"}
_YAML_ASSERTION_ACTIONS = {"assert", "assertVisible", "assertNotVisible", "assertText", "assertElementsOrder", "assertWithAI"}
_YAML_OBSERVATION_ACTIONS = {"takeScreenshot", "startRecording", "stopRecording", "uiSnapshot"}
_STEP_TEXT_ARTIFACT_KINDS = {"ui_tree", "ui_snapshot"}
_RUN_RESULT_MARKERS = {
    "report.md",
    "report.json",
    "core-report.md",
    "core-report.json",
    "evidence-manifest.json",
    "events.jsonl",
    "recording.json",
    "recorded.codex.yaml",
}


class _StepArtifactTextTooLargeError(Exception):
    def __init__(self, *, size_bytes: int, limit_bytes: int) -> None:
        super().__init__(f"Step artifact text is too large to display ({size_bytes} bytes).")
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes


def _parse_xml_safely(source: str) -> ET.Element:
    normalized = source.upper()
    if "<!DOCTYPE" in normalized or "<!ENTITY" in normalized:
        raise ET.ParseError("DTD and entity declarations are not allowed.")
    # DTD and entity declarations are rejected above, preventing attacker-controlled entity expansion.
    return ET.fromstring(source)  # noqa: S314


@dataclass(frozen=True)
class PlaygroundServerOptions:
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True
    static_path: Path | None = None
    record: bool = True
    record_on_failure: bool = True


class PlaygroundServer:
    def __init__(self, settings: Settings, options: PlaygroundServerOptions | None = None) -> None:
        self.settings = settings
        self.options = options or PlaygroundServerOptions()
        self.state = PlaygroundState()
        self._httpd: _PlaygroundHTTPServer | None = None
        self._thread: Thread | None = None
        self._execution_handles: dict[str, PlaygroundExecutionHandle] = {}
        self._static_root = (self.options.static_path or Path(__file__).parent / "static").resolve()

    @property
    def url(self) -> str:
        return f"http://{self.options.host}:{self.port}"

    @property
    def port(self) -> int:
        if self._httpd is not None:
            return int(self._httpd.server_address[1])
        return self.options.port

    def start(self) -> None:
        if self._httpd is not None:
            return
        if self._static_entry_path() is None:
            raise FileNotFoundError(f"Playground frontend build not found under {self._static_root}. Run npm ci and npm run build.")
        self._httpd = _PlaygroundHTTPServer((self.options.host, self.options.port), _RequestHandler, self)
        self._thread = Thread(target=self._httpd.serve_forever, name="fsq-playground-server", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None

    def serve_forever(self) -> None:
        self.start()
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return
        finally:
            self.stop()

    def handle_get(self, path: str, query: dict[str, list[str]]) -> tuple[int, object]:
        if path == "/status":
            return 200, self.state.status()
        if path == "/session":
            if self.settings.harness.platform != "android":
                return 200, self._android_unavailable(f"Android session selection is unavailable for the active {self.settings.harness.platform} platform.")
            return 200, self.state.session.to_json()
        if path == "/session/setup":
            if self.settings.harness.platform != "android":
                return 200, self._android_unavailable(f"Android setup is unavailable for the active {self.settings.harness.platform} platform.")
            return 200, build_android_setup_schema(self.settings)
        if path == "/runtime-info":
            return 200, self._runtime_info()
        if path == "/yaml/input":
            return self._yaml_input_response(query)
        if path.startswith("/yaml/recorded/"):
            yaml_id = unquote(path.removeprefix("/yaml/recorded/")).strip()
            return self._yaml_recorded_response(yaml_id)
        if path.startswith("/runs/") and path.endswith("/progress"):
            run_id = unquote(path.removeprefix("/runs/").removesuffix("/progress")).strip("/").strip()
            return self._loaded_run_progress_response(run_id)
        if path == "/screenshot":
            if self.settings.harness.platform != "android":
                return self._web_screenshot_response()
            if not self.state.session.connected:
                return 200, {"available": False, "error": "No active session."}
            try:
                payload = capture_android_screenshot(self.settings, self.state.session.device_id)
                if payload.get("available") is True and self.state.current_request_id:
                    self._record_replay_frame(self.state.current_request_id, payload)
            except Exception as exc:  # noqa: BLE001 - API returns structured errors.
                return 500, {"available": False, "error": str(exc) or exc.__class__.__name__}
            else:
                return 200, payload
        if path.startswith("/replay/"):
            request_id = unquote(path.removeprefix("/replay/")).strip()
            return self._replay_response(request_id)
        if path.startswith("/replay-video/"):
            replay_id = unquote(path.removeprefix("/replay-video/")).strip()
            return self._replay_video_response(replay_id)
        if path.startswith("/step-artifacts/"):
            parts = path.removeprefix("/step-artifacts/").split("/", 1)
            if len(parts) != 2:
                return 400, {"available": False, "error": "Step artifact id and step id or index are required."}
            artifact_id = unquote(parts[0]).strip()
            step_id_or_index = unquote(parts[1]).strip()
            return self._step_artifacts_response(artifact_id, step_id_or_index)
        if path.startswith("/task-progress/"):
            request_id = unquote(path.removeprefix("/task-progress/")).strip()
            task = self.state.get_task(request_id, after_sequence=_after_sequence(query))
            if task is None:
                return 404, {"error": "Task progress not found."}
            return 200, task
        if path.startswith("/preview/"):
            request_id = unquote(path.removeprefix("/preview/")).strip()
            return self._preview_response(request_id)
        if path.startswith("/reports/"):
            return self._report_response(path, query)
        return 404, {"error": "Not found."}

    def _preview_response(self, request_id: str) -> tuple[int, object]:
        task = self.state.get_task(request_id)
        preview = task.get("preview") if task else None
        if not isinstance(preview, dict):
            return 404, {"error": "Preview not found."}
        run_id = preview.get("runId")
        path = preview.get("path")
        if not isinstance(run_id, str) or not isinstance(path, str):
            return 404, {"error": "Preview not found."}
        run_dir = Path(self.settings.output.runs_dir) / run_id
        preview_path = (run_dir / path).resolve()
        if not _is_relative_to(preview_path, run_dir) or not preview_path.is_file():
            return 404, {"error": "Preview not found."}
        return 200, {
            "requestId": request_id,
            "runId": run_id,
            "timestamp": preview.get("timestamp"),
            "token": preview.get("token"),
            "screenshot": base64.b64encode(preview_path.read_bytes()).decode("ascii"),
        }

    def handle_replay_video_file(self, path: str, range_header: str | None = None) -> tuple[int, bytes, str, dict[str, str]]:
        replay_id = unquote(path.removeprefix("/replay-video-file/")).strip()
        run_id = self.state.run_id_for_request(replay_id) or replay_id
        video_path = self._replay_video_path(run_id)
        if not video_path.exists():
            payload = {"available": False, "error": "Replay video not found.", "runId": run_id}
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            return 404, body, "application/json; charset=utf-8", {}
        total_size = video_path.stat().st_size
        byte_range = _parse_byte_range(range_header, total_size)
        if byte_range is None:
            body = video_path.read_bytes()
            return 200, body, "video/webm", {"Accept-Ranges": "bytes"}
        start, end = byte_range
        with video_path.open("rb") as handle:
            handle.seek(start)
            body = handle.read(end - start + 1)
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{total_size}",
        }
        return 206, body, "video/webm", headers

    def handle_post(self, path: str, body: dict[str, object]) -> tuple[int, object]:
        if path == "/runs/load":
            return self._load_run_response(body)
        if path == "/session":
            if self.settings.harness.platform != "android":
                return 409, self._android_unavailable(f"Android session selection is unavailable for the active {self.settings.harness.platform} platform.")
            device_id = body.get("deviceId")
            if not isinstance(device_id, str) or not device_id.strip():
                return 400, {"error": "deviceId is required."}
            try:
                return 200, {"session": self.state.create_session(device_id), "runtimeInfo": self._runtime_info()}
            except BusyError as exc:
                return 409, {"error": str(exc)}
        if path == "/session/auto":
            if self.settings.harness.platform != "android":
                return 409, self._android_unavailable(f"Android auto session selection is unavailable for the active {self.settings.harness.platform} platform.")
            try:
                session, info = resolve_auto_session(self.settings)
                if session is None:
                    status = 500 if info.get("reason") == "adb_error" else 409
                    return status, {"error": info.get("message") or "Unable to auto-create Android session.", **info}
                created = self.state.create_session(session.device_id or "")
                created["displayName"] = session.display_name
                created["metadata"] = session.metadata
                self.state.session.display_name = session.display_name
                self.state.session.metadata = session.metadata
                return 200, {"session": created, "runtimeInfo": self._runtime_info(), "autoCreate": info}
            except BusyError as exc:
                return 409, {"error": str(exc)}
        if path == "/execute":
            goal = body.get("goal")
            case_yaml_path = body.get("caseYamlPath")
            strict_case_yaml_path = body.get("strictCaseYamlPath")
            has_goal = isinstance(goal, str) and bool(goal.strip())
            has_case_yaml = isinstance(case_yaml_path, str) and bool(case_yaml_path.strip())
            has_strict_case_yaml = isinstance(strict_case_yaml_path, str) and bool(strict_case_yaml_path.strip())
            if sum([has_goal, has_case_yaml, has_strict_case_yaml]) != 1:
                return 400, {"error": "Exactly one of goal, caseYamlPath, or strictCaseYamlPath is required."}
            if self.settings.harness.platform == "android" and not self.state.session.connected:
                return 409, {"error": "No active Android session. Create a session before execution."}
            try:
                execution_settings = refresh_execution_settings(self.settings)
            except (ConfigurationError, OSError) as exc:
                return 400, {"error": str(exc)}
            if has_goal:
                task_label = goal.strip()
            elif has_case_yaml:
                task_label = f"Case YAML: {case_yaml_path.strip()}"
            else:
                task_label = f"Strict YAML: {strict_case_yaml_path.strip()}"
            try:
                request_id = self.state.start_task(task_label)
            except BusyError as exc:
                return 409, {"error": str(exc)}
            if has_strict_case_yaml:
                self._reset_replay_for_known_run(request_id, self._strict_case_run_id(strict_case_yaml_path.strip()))
            handle = start_dynamic_goal_execution(
                settings=execution_settings,
                state=self.state,
                request_id=request_id,
                goal=goal.strip() if has_goal else None,
                case_yaml_path=case_yaml_path.strip() if has_case_yaml else None,
                strict_case_yaml_path=strict_case_yaml_path.strip() if has_strict_case_yaml else None,
                device_id=self.state.session.device_id if execution_settings.harness.platform == "android" else None,
                record=self.options.record,
                record_on_failure=self.options.record_on_failure,
            )
            self._execution_handles[request_id] = handle
            return 202, {"requestId": request_id}
        if path.startswith("/replay-video/"):
            replay_id = unquote(path.removeprefix("/replay-video/")).strip()
            return self._store_replay_video(replay_id, body)
        if path.startswith("/cancel/"):
            request_id = unquote(path.removeprefix("/cancel/")).strip()
            cancelled = self.state.request_cancel(request_id)
            if cancelled is None:
                return 404, {"error": "Task progress not found."}
            handle = self._execution_handles.pop(request_id, None)
            if handle is not None:
                handle.cancel()
            return 200, cancelled
        return 404, {"error": "Not found."}

    def handle_put(self, path: str, body: dict[str, object]) -> tuple[int, object]:
        if path != "/yaml/input/lifecycle":
            return 404, {"error": "Not found."}
        if self.state.current_request_id is not None:
            return 409, {"available": False, "error": "Cannot save YAML while a task is running."}
        path_text = body.get("path")
        revision = body.get("revision")
        if not isinstance(path_text, str) or not path_text.strip():
            return 400, {"available": False, "error": "path is required."}
        if not isinstance(revision, str) or not revision:
            return 400, {"available": False, "error": "revision is required."}
        try:
            resolved_path = self._resolve_yaml_input_path(path_text.strip())
            save_lifecycle(
                resolved_path,
                expected_revision=revision,
                on_case_start=body.get("onCaseStart"),
                on_case_complete=body.get("onCaseComplete"),
                size_limit_bytes=YAML_DISPLAY_SIZE_LIMIT_BYTES,
            )
            return self._yaml_input_path_response(path_text.strip(), resolved_path)
        except YamlLifecycleConflictError as exc:
            return 409, {"available": False, "error": str(exc)}
        except YamlLifecycleValidationError as exc:
            status = 413 if "too large" in str(exc).lower() else 400
            return status, {"available": False, "error": str(exc)}
        except YamlLifecycleWriteError as exc:
            return 500, {"available": False, "error": str(exc)}
        except IsADirectoryError:
            return 400, {"available": False, "error": f"Case YAML path is a directory: {path_text}"}
        except FileNotFoundError:
            return 404, {"available": False, "error": f"Case YAML not found: {path_text}"}
        except OSError as exc:
            return 500, {"available": False, "error": str(exc) or exc.__class__.__name__}

    def _load_run_response(self, body: dict[str, object]) -> tuple[int, object]:
        path_value = body.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            return 400, {"available": False, "error": "Run directory path is required."}
        runs_root = Path(self.settings.output.runs_dir).resolve()
        requested = Path(path_value.strip())
        run_dir = requested.resolve() if requested.is_absolute() else (runs_root / requested).resolve()
        try:
            relative = run_dir.relative_to(runs_root)
        except ValueError:
            return 400, {"available": False, "error": "Run directory must be inside the configured runs directory."}
        if len(relative.parts) != 1:
            return 400, {"available": False, "error": "Run directory must be a direct child of the configured runs directory."}
        if not run_dir.exists():
            return 404, {"available": False, "error": f"Run directory not found: {path_value.strip()}"}
        if not run_dir.is_dir():
            return 400, {"available": False, "error": "Run path must identify a directory."}
        if not self._is_recognized_run_dir(run_dir):
            return 400, {"available": False, "error": "Directory does not contain a recognized run result."}
        return 200, {
            "available": True,
            "runId": relative.name,
            "availability": self._run_result_availability(run_dir),
        }

    def _loaded_run_progress_response(self, run_id: str) -> tuple[int, object]:
        if not run_id:
            return 400, {"available": False, "error": "Run id is required."}
        runs_root = Path(self.settings.output.runs_dir).resolve()
        run_dir = (runs_root / run_id).resolve()
        try:
            relative = run_dir.relative_to(runs_root)
        except ValueError:
            return 400, {"available": False, "error": "Run id resolves outside the configured runs directory."}
        if len(relative.parts) != 1:
            return 400, {"available": False, "error": "Run id must identify a direct child of the configured runs directory."}
        if not run_dir.exists() or not run_dir.is_dir():
            return 404, {"available": False, "error": f"Run directory not found: {run_id}"}
        events_path = run_dir / "events.jsonl"
        if not events_path.is_file():
            return 200, {"runId": relative.name, "events": []}
        try:
            lines = events_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            return 400, {"available": False, "error": str(exc) or "Unable to read run progress."}
        events: list[dict[str, object]] = []
        next_sequence = 0
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            sequence = event.get("sequence")
            if isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > 0:
                next_sequence = max(next_sequence, sequence)
            else:
                next_sequence += 1
                event["sequence"] = next_sequence
            events.append(event)
        return 200, {"runId": relative.name, "events": events}

    def _is_recognized_run_dir(self, run_dir: Path) -> bool:
        if any((run_dir / marker).is_file() for marker in _RUN_RESULT_MARKERS):
            return True
        replay_dir = run_dir / "playground-replay"
        return (replay_dir / "replay-manifest.json").is_file() or (replay_dir / "replay.webm").is_file()

    def _run_result_availability(self, run_dir: Path) -> dict[str, bool]:
        replay_dir = run_dir / "playground-replay"
        return {
            "report": any((run_dir / name).is_file() for name in ("report.md", "report.json", "core-report.md", "core-report.json")),
            "recordedYaml": (run_dir / "recording.json").is_file() or (run_dir / "recorded.codex.yaml").is_file(),
            "replay": (replay_dir / "replay-manifest.json").is_file() or (replay_dir / "replay.webm").is_file() or self._run_has_screenshot_replay_sources(run_dir),
            "stepArtifacts": (run_dir / "evidence-manifest.json").is_file() or (run_dir / "events.jsonl").is_file(),
        }

    def _run_has_screenshot_replay_sources(self, run_dir: Path) -> bool:
        manifest_path = run_dir / "evidence-manifest.json"
        if manifest_path.is_file():
            try:
                manifest = self._read_evidence_manifest(run_dir)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                manifest = None
            artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
            if isinstance(artifacts, list) and any(isinstance(ref, dict) and self._is_screenshot_artifact_ref(ref) for ref in artifacts):
                return True
        events_path = run_dir / "events.jsonl"
        if not events_path.is_file():
            return False
        try:
            lines = events_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return False
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            refs = payload.get("artifact_refs") if isinstance(payload.get("artifact_refs"), list) else []
            if any(isinstance(ref, dict) and self._is_screenshot_artifact_ref(ref) for ref in refs):
                return True
            artifact_path = payload.get("artifact_path")
            if isinstance(artifact_path, str) and self._is_screenshot_artifact_ref({"path": artifact_path}):
                return True
        return False

    def handle_delete(self, path: str) -> tuple[int, object]:
        if path == "/session":
            if self.settings.harness.platform != "android":
                return 409, self._android_unavailable(f"Android session selection is unavailable for the active {self.settings.harness.platform} platform.")
            try:
                return 200, {"session": self.state.destroy_session(), "runtimeInfo": self._runtime_info()}
            except BusyError as exc:
                return 409, {"error": str(exc)}
        return 404, {"error": "Not found."}

    def static_response(self, path: str) -> tuple[int, bytes, str]:
        entry = self._static_entry_path()
        relative = unquote(path.lstrip("/"))
        candidate = entry if path in {"/", "/index.html"} else (self._static_root / relative).resolve()
        if not candidate.is_file() or not _is_relative_to(candidate, self._static_root):
            candidate = entry
        if candidate is None or not candidate.is_file() or not _is_relative_to(candidate.resolve(), self._static_root):
            return 404, b"Not found", "text/plain; charset=utf-8"
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or candidate.suffix in {".js", ".css", ".html"}:
            content_type = f"{content_type}; charset=utf-8"
        return 200, candidate.read_bytes(), content_type

    def _static_entry_path(self) -> Path | None:
        for relative in (Path("playground/index.html"), Path("index.html")):
            candidate = (self._static_root / relative).resolve()
            if candidate.is_file() and _is_relative_to(candidate, self._static_root):
                return candidate
        return None

    def _runtime_info(self) -> dict[str, object]:
        if self.settings.harness.platform == "web":
            web = self.settings.harness.web
            return {
                "platformId": "web",
                "title": "FSQ-Agent Web Playground",
                "interface": {"type": "Web", "description": "FSQ-Agent Web harness"},
                "preview": {"kind": "screenshot", "screenshotPath": "/screenshot", "live": False},
                "session": self._android_unavailable("Android session selection is unavailable for the active Web platform."),
                "metadata": {
                    "backend": web.backend,
                    "channel": web.channel,
                    "browserExecutableConfigured": web.browser_executable_path is not None,
                    "headless": web.headless,
                    "baseUrlPresent": bool(web.base_url),
                    "viewportConfigured": web.viewport_width is not None and web.viewport_height is not None,
                    "busy": self.state.current_request_id is not None,
                    "lastRun": self.state.last_run,
                },
            }
        if self.settings.harness.platform == "windows":
            windows = self.settings.harness.windows
            return {
                "platformId": "windows",
                "title": "FSQ-Agent Windows Playground",
                "interface": {"type": "Windows", "description": "FSQ-Agent Windows harness"},
                "preview": {"kind": "screenshot", "screenshotPath": "/screenshot", "live": False},
                "session": self._android_unavailable("Android session selection is unavailable for the active Windows platform."),
                "metadata": {
                    "backend": windows.backend,
                    "backendKind": windows.backend_kind,
                    "appPathConfigured": windows.app_path is not None,
                    "windowTitleRePresent": bool(windows.window_title_re),
                    "launchArgsCount": len(windows.launch_args),
                    "busy": self.state.current_request_id is not None,
                    "lastRun": self.state.last_run,
                },
            }
        if self.settings.harness.platform == "macos":
            macos = self.settings.harness.macos
            return {
                "platformId": "macos",
                "title": "FSQ-Agent macOS Playground",
                "interface": {"type": "macOS", "description": "FSQ-Agent Appium Mac2 harness"},
                "preview": {"kind": "screenshot", "screenshotPath": "/screenshot", "live": False},
                "session": self._android_unavailable("Android session selection is unavailable for the active macOS platform."),
                "metadata": {
                    "backend": macos.backend,
                    "appiumServerConfigured": macos.appium_server_url is not None,
                    "bundleIdPresent": macos.bundle_id is not None,
                    "appPathConfigured": macos.app_path is not None,
                    "actionTimeoutSeconds": macos.action_timeout_seconds,
                    "newCommandTimeoutSeconds": macos.new_command_timeout_seconds,
                    "busy": self.state.current_request_id is not None,
                    "lastRun": self.state.last_run,
                },
            }
        return {
            "platformId": "android",
            "title": "FSQ-Agent Android Playground",
            "interface": {"type": "Android", "description": "FSQ-Agent Android harness"},
            "preview": {"kind": "screenshot", "screenshotPath": "/screenshot", "live": False},
            "session": self.state.session.to_json(),
            "metadata": {
                "appIdPresent": bool(self.settings.harness.android.app_id),
                "configuredSerial": self.settings.harness.android.serial,
                "selectedDeviceId": self.state.session.device_id,
                "busy": self.state.current_request_id is not None,
                "lastRun": self.state.last_run,
            },
        }

    def _android_unavailable(self, message: str) -> dict[str, object]:
        return {
            "available": False,
            "platform": self.settings.harness.platform,
            "connected": False,
            "message": message,
        }

    def _web_screenshot_response(self) -> tuple[int, object]:
        request_id = self.state.current_request_id
        if not request_id:
            return 200, {
                "available": False,
                "platform": self.settings.harness.platform,
                "error": f"No active {self.settings.harness.platform} harness execution.",
            }
        handle = self._execution_handles.get(request_id)
        harness = handle.current_harness() if handle is not None else None
        if harness is None:
            return 200, {
                "available": False,
                "platform": self.settings.harness.platform,
                "error": f"Live screenshot preview is not available before {self.settings.harness.platform} harness execution.",
            }
        try:
            context = harness.get_context()
            metadata = getattr(context, "metadata", {})
            if isinstance(metadata, dict) and metadata.get("browser_started") is False:
                return 200, {
                    "available": False,
                    "platform": self.settings.harness.platform,
                    "error": "Browser is not started. Call startBrowser before Web page actions.",
                }
            if self.settings.harness.platform == "macos" and getattr(context, "session_id", None) is None:
                return 200, {
                    "available": False,
                    "platform": self.settings.harness.platform,
                    "error": "Appium Mac2 session is not available. Call launchApp before macOS Appium actions.",
                }
            screenshot = harness.screenshot()
            payload = {
                "available": True,
                "platform": self.settings.harness.platform,
                "screenshot": base64.b64encode(screenshot).decode("ascii"),
                "timestamp": int(time.time() * 1000),
            }
            self._record_replay_frame(request_id, payload)
        except Exception as exc:  # noqa: BLE001 - API returns structured errors.
            return 500, {"available": False, "platform": self.settings.harness.platform, "error": str(exc) or exc.__class__.__name__}
        else:
            return 200, payload

    def _report_response(self, path: str, query: dict[str, list[str]]) -> tuple[int, object]:
        run_id = unquote(path.removeprefix("/reports/")).strip()
        report_format = (query.get("format") or ["markdown"])[0]
        if report_format not in {"markdown", "json"}:
            return 400, {"error": "format must be markdown or json."}
        try:
            report_path = resolve_report_path(self.settings.output.runs_dir, run_id, report_format)  # type: ignore[arg-type]
            return 200, {"runId": run_id, "format": report_format, "path": str(report_path), "content": report_path.read_text(encoding="utf-8")}
        except Exception as exc:  # noqa: BLE001 - API returns structured errors.
            return 404, {"error": str(exc) or exc.__class__.__name__}

    def _yaml_input_response(self, query: dict[str, list[str]]) -> tuple[int, object]:
        path_text = (query.get("path") or [""])[0].strip()
        if not path_text:
            return 400, {"available": False, "error": "path is required."}
        try:
            resolved_path = self._resolve_yaml_input_path(path_text)
            return self._yaml_input_path_response(path_text, resolved_path)
        except IsADirectoryError:
            return 400, {"available": False, "error": f"Case YAML path is a directory: {path_text}"}
        except FileNotFoundError:
            return 404, {"available": False, "error": f"Case YAML not found: {path_text}"}
        except UnicodeDecodeError:
            return 400, {"available": False, "error": f"Case YAML must be UTF-8 text: {path_text}"}
        except (TypeError, ValueError) as exc:
            return 400, {"available": False, "error": str(exc) or "Unable to parse YAML for display."}
        except OSError as exc:
            return 400, {"available": False, "error": str(exc) or exc.__class__.__name__}

    def _yaml_input_path_response(self, path_text: str, resolved_path: Path) -> tuple[int, object]:
        content_bytes = resolved_path.read_bytes()
        size_bytes = len(content_bytes)
        if size_bytes > YAML_DISPLAY_SIZE_LIMIT_BYTES:
            return 413, {
                "available": False,
                "error": f"YAML file is too large to display ({size_bytes} bytes).",
                "limitBytes": YAML_DISPLAY_SIZE_LIMIT_BYTES,
            }
        content = content_bytes.decode("utf-8")
        return 200, {
            "kind": "input",
            "path": path_text,
            "resolvedPath": str(resolved_path),
            "sizeBytes": size_bytes,
            "revision": yaml_revision(content_bytes),
            "editable": True,
            "display": self._yaml_display_model(content, source_path=path_text),
            "content": content,
        }

    def _resolve_yaml_input_path(self, path_text: str) -> Path:
        requested = Path(path_text.strip())
        candidates = [requested] if requested.is_absolute() else [self.settings.cases.dir / requested, Path.cwd() / requested]
        for candidate in candidates:
            if candidate.exists():
                if candidate.is_dir():
                    raise IsADirectoryError(str(candidate))
                if candidate.is_file():
                    return candidate.resolve()
        raise FileNotFoundError(path_text)

    def _yaml_recorded_response(self, yaml_id: str) -> tuple[int, object]:
        if not yaml_id:
            return 404, {"available": False, "error": "Recorded YAML not found."}
        run_id = self.state.run_id_for_request(yaml_id) or yaml_id
        runs_dir = Path(self.settings.output.runs_dir).resolve()
        run_dir = (runs_dir / run_id).resolve()
        if not _is_relative_to(run_dir, runs_dir) or not run_dir.is_dir():
            return 404, {"available": False, "error": "Recorded YAML not found.", "runId": run_id}
        recording_path = run_dir / "recording.json"
        if not recording_path.exists():
            return 404, {"available": False, "error": "Recording metadata not found.", "runId": run_id}
        try:
            recording = self._read_recording_json(recording_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return 400, {"available": False, "error": str(exc) or "Unable to read recording metadata.", "runId": run_id}
        if recording is None:
            return 400, {"available": False, "error": "Recording metadata must be a JSON object.", "runId": run_id}
        recorded_case_path = self._recorded_case_path(run_dir, recording)
        if recorded_case_path is None:
            return 400, {"available": False, "error": "Recorded case path is outside the run directory.", "runId": run_id}
        try:
            content = recorded_case_path.read_text(encoding="utf-8") if recorded_case_path.is_file() else None
        except UnicodeDecodeError:
            return 400, {"available": False, "error": "Recorded case must be UTF-8 text.", "runId": run_id}
        except OSError as exc:
            return 400, {"available": False, "error": str(exc) or exc.__class__.__name__, "runId": run_id}
        try:
            display = self._yaml_display_model(content, source_path=str(recorded_case_path), run_dir=run_dir) if content is not None else None
        except (TypeError, ValueError) as exc:
            return 400, {"available": False, "error": str(exc) or "Unable to parse recorded YAML for display.", "runId": run_id}
        return 200, {
            "kind": "recorded",
            "runId": run_id,
            "status": self._recording_value(recording, "status", "missing"),
            "validationStatus": self._recording_value(recording, "validation_status", "not_run"),
            "draft": bool(recording.get("draft")) if isinstance(recording, dict) else False,
            "commandCount": self._recording_int(recording, "command_count"),
            "recordingPath": str(recording_path) if recording_path.exists() else None,
            "recordedCasePath": str(recorded_case_path) if recorded_case_path.is_file() else None,
            "requiredRuntimeSecretNames": self._recording_list(recording, "required_runtime_secret_names"),
            "warnings": self._recording_list(recording, "warnings"),
            "skippedToolCalls": self._recording_list(recording, "skipped_tool_calls"),
            "errors": self._recording_list(recording, "errors"),
            "display": display,
            "content": content,
        }

    def _yaml_display_model(self, content: str, *, source_path: str | None = None, run_dir: Path | None = None) -> dict[str, object]:
        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError as exc:
            raise ValueError(str(exc) or "Unable to parse YAML for display.") from exc
        metadata_doc = docs[0] if docs and isinstance(docs[0], dict) else {}
        commands_doc = docs[1] if len(docs) > 1 else []
        if commands_doc is None:
            commands_doc = []
        if not isinstance(commands_doc, list):
            raise TypeError("FSQ command document must be a YAML list.")
        artifact_step_ids = self._recorded_artifact_step_ids(run_dir, commands_doc) if run_dir is not None else None
        return {
            "metadata": self._yaml_metadata_display(metadata_doc, source_path=source_path),
            "lifecycle": lifecycle_display(metadata_doc),
            "steps": [
                self._yaml_step_display(
                    command,
                    index,
                    artifact_step_id=artifact_step_ids[index - 1] if artifact_step_ids is not None else None,
                )
                for index, command in enumerate(commands_doc, start=1)
            ],
            "documentCount": len(docs),
        }

    def _recorded_artifact_step_ids(self, run_dir: Path, commands: list[object]) -> list[str | None] | None:
        events_path = run_dir / "events.jsonl"
        if not events_path.exists():
            return None
        try:
            lines = events_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return None
        replay_events: list[tuple[str, str | None]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or not self._event_is_recorded_replay_command(event):
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            alias = self._event_replay_policy(payload).get("alias")
            if isinstance(alias, str):
                replay_events.append((self._normalized_yaml_action(alias), self._event_step_id(event)))
        command_actions = [self._normalized_yaml_action(self._yaml_command_action(command)) for command in commands]
        return self._align_recorded_step_ids(command_actions, replay_events)

    def _align_recorded_step_ids(
        self,
        command_actions: list[str],
        replay_events: list[tuple[str, str | None]],
    ) -> list[str | None]:
        event_actions = [action for action, _step_id in replay_events]
        match_counts = [[0] * (len(event_actions) + 1) for _ in range(len(command_actions) + 1)]
        for command_index in range(len(command_actions) - 1, -1, -1):
            for event_index in range(len(event_actions) - 1, -1, -1):
                if command_actions[command_index] == event_actions[event_index]:
                    match_counts[command_index][event_index] = 1 + match_counts[command_index + 1][event_index + 1]
                else:
                    match_counts[command_index][event_index] = max(
                        match_counts[command_index + 1][event_index],
                        match_counts[command_index][event_index + 1],
                    )
        step_ids: list[str | None] = [None] * len(command_actions)
        command_index = 0
        event_index = 0
        while command_index < len(command_actions) and event_index < len(event_actions):
            if command_actions[command_index] == event_actions[event_index] and match_counts[command_index][event_index] == 1 + match_counts[command_index + 1][event_index + 1]:
                step_ids[command_index] = replay_events[event_index][1]
                command_index += 1
                event_index += 1
            elif match_counts[command_index + 1][event_index] > match_counts[command_index][event_index + 1]:
                command_index += 1
            else:
                event_index += 1
        return step_ids

    def _yaml_command_action(self, command: object) -> str:
        if isinstance(command, str):
            return command
        if isinstance(command, dict):
            for key in command:
                if str(key) not in _YAML_COMMAND_CONTROL_KEYS:
                    return str(key)
        return "command"

    def _normalized_yaml_action(self, action: str) -> str:
        return re.sub(r"[^a-z0-9]", "", action.lower())

    def _event_step_kind(self, event: dict[str, object]) -> str | None:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        value = payload.get("step_kind")
        if isinstance(value, str):
            return value
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        kind = metadata.get("step_kind")
        return kind if isinstance(kind, str) else None

    def _event_step_id(self, event: dict[str, object]) -> str | None:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        runner_result = payload.get("runner_result") if isinstance(payload.get("runner_result"), dict) else {}
        for candidate in (payload.get("runner_step_id"), payload.get("step_id"), runner_result.get("step_id")):
            if isinstance(candidate, str) and candidate:
                return candidate
        return None

    def _yaml_metadata_display(self, metadata: dict[object, object], *, source_path: str | None = None) -> dict[str, object]:
        fields = []
        for key in ("platform", "schemaVersion", "description"):
            value = metadata.get(key)
            if value is not None and value != "" and value != []:
                fields.append({"key": key, "label": self._yaml_label(key), "value": value})
        if source_path:
            fields.append({"key": "path", "label": "Path", "value": source_path})
        for key in ("appId", "url"):
            value = metadata.get(key)
            if value is not None and value != "" and value != []:
                fields.append({"key": key, "label": self._yaml_label(key), "value": value})
        tags = metadata.get("tags")
        return {
            "title": metadata.get("name") if isinstance(metadata.get("name"), str) else "Untitled case",
            "platform": metadata.get("platform") if isinstance(metadata.get("platform"), str) else "unknown",
            "schemaVersion": metadata.get("schemaVersion") if isinstance(metadata.get("schemaVersion"), str) else "unknown",
            "tags": tags if isinstance(tags, list) else [],
            "fields": fields,
        }

    def _yaml_step_display(self, command: object, index: int, *, artifact_step_id: str | None = None) -> dict[str, object]:
        badges: list[dict[str, object]] = []
        if isinstance(command, str):
            action = command
            payload = None
        elif isinstance(command, dict):
            action_items = [(key, value) for key, value in command.items() if str(key) not in _YAML_COMMAND_CONTROL_KEYS]
            if action_items:
                action, payload = action_items[0]
            else:
                action, payload = "command", command
            if command.get("optional") is True:
                badges.append({"label": "optional", "tone": "neutral"})
            timeout = command.get("timeout") or command.get("timeout_ms")
            if timeout is not None:
                badges.append({"label": f"timeout {timeout}", "tone": "neutral"})
        else:
            action = "command"
            payload = command
        action_text = str(action)
        return {
            "index": index,
            "displayIndex": index,
            "artifactStepId": artifact_step_id,
            "action": action_text,
            "kind": self._yaml_action_kind(action_text),
            "badges": badges,
            "params": self._yaml_param_entries(payload),
        }

    def _yaml_param_entries(self, payload: object) -> list[dict[str, object]]:
        if payload in (None, {}, []):
            return []
        if isinstance(payload, dict):
            return [{"key": str(key), **self._yaml_display_value(value)} for key, value in payload.items()]
        return [{"key": "value", **self._yaml_display_value(payload)}]

    def _yaml_display_value(self, value: object) -> dict[str, object]:
        if isinstance(value, dict):
            return {
                "value": "",
                "kind": "object",
                "fields": [{"key": str(key), **self._yaml_display_value(child_value)} for key, child_value in value.items()],
            }
        if isinstance(value, list):
            return {
                "value": "",
                "kind": "list",
                "fields": [{"key": str(index + 1), **self._yaml_display_value(child_value)} for index, child_value in enumerate(value)],
            }
        if isinstance(value, bool):
            return {"value": "true" if value else "false", "kind": "boolean"}
        if value is None:
            return {"value": "null", "kind": "null"}
        return {"value": str(value), "kind": "scalar"}

    def _yaml_action_kind(self, action: str) -> str:
        if action in _YAML_SETUP_ACTIONS:
            return "setup"
        if action in _YAML_TEARDOWN_ACTIONS:
            return "teardown"
        if action in _YAML_ASSERTION_ACTIONS:
            return "assertion"
        if action in _YAML_OBSERVATION_ACTIONS:
            return "observation"
        return "action"

    def _yaml_label(self, key: str) -> str:
        return {
            "schemaVersion": "Schema",
            "appId": "App ID",
        }.get(key, key[:1].upper() + key[1:])

    def _read_recording_json(self, recording_path: Path) -> dict[str, object] | None:
        if not recording_path.exists():
            return None
        payload = json.loads(recording_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def _recorded_case_path(self, run_dir: Path, recording: dict[str, object] | None) -> Path | None:
        raw_path = recording.get("recorded_case_path") if isinstance(recording, dict) else None
        if isinstance(raw_path, str) and raw_path.strip():
            candidate = Path(raw_path.strip())
            resolved = candidate.resolve() if candidate.is_absolute() else (run_dir / candidate).resolve()
        else:
            resolved = (run_dir / "recorded.codex.yaml").resolve()
        return resolved if _is_relative_to(resolved, run_dir) else None

    def _recording_value(self, recording: dict[str, object] | None, key: str, default: str) -> str:
        value = recording.get(key) if isinstance(recording, dict) else None
        return value if isinstance(value, str) and value else default

    def _recording_int(self, recording: dict[str, object] | None, key: str) -> int:
        value = recording.get(key) if isinstance(recording, dict) else None
        return int(value) if isinstance(value, int) else 0

    def _recording_list(self, recording: dict[str, object] | None, key: str) -> list[object]:
        value = recording.get(key) if isinstance(recording, dict) else None
        return value if isinstance(value, list) else []

    def _step_artifacts_response(self, artifact_id: str, step_id_or_index: str) -> tuple[int, object]:
        if not artifact_id or not step_id_or_index:
            return 400, {"available": False, "error": "Step artifact id and step id or index are required."}
        run_id = self.state.run_id_for_request(artifact_id) or artifact_id
        runs_root = Path(self.settings.output.runs_dir).resolve()
        run_dir = (runs_root / run_id).resolve()
        if not _is_relative_to(run_dir, runs_root):
            return 400, {"available": False, "error": "Run id resolves outside the runs directory."}
        if not run_dir.exists() or not run_dir.is_dir():
            return 404, {"available": False, "error": f"Run not found: {run_id}", "runId": run_id}
        selector = self._step_selector(step_id_or_index)
        if selector is None:
            return 400, {"available": False, "error": "Step id or 1-based step index is required.", "runId": run_id}
        try:
            refs = self._step_artifact_refs(run_dir, selector)
            artifacts = self._step_artifact_payloads(run_dir, refs)
        except UnicodeDecodeError:
            return 400, {"available": False, "error": "Step artifact text must be UTF-8.", "runId": run_id}
        except ValueError as exc:
            return 400, {"available": False, "error": str(exc), "runId": run_id}
        response = {
            "available": bool(artifacts),
            "runId": run_id,
            "stepId": selector.get("step_id"),
            "stepIndex": selector.get("step_index"),
            "artifacts": artifacts,
        }
        if not artifacts:
            response["message"] = "No artifacts for this step yet."
        return 200, response

    def _step_selector(self, step_id_or_index: str) -> dict[str, object] | None:
        value = step_id_or_index.strip()
        if not value:
            return None
        if value.isdecimal():
            step_index = int(value)
            return {"step_index": step_index} if step_index > 0 else None
        selector: dict[str, object] = {"step_id": value}
        parsed_index = _step_index_from_step_id(value)
        if parsed_index is not None:
            selector["step_index"] = parsed_index
        return selector

    def _step_artifact_refs(self, run_dir: Path, selector: dict[str, object]) -> list[dict[str, object]]:
        refs: list[dict[str, object]] = []
        manifest = self._read_evidence_manifest(run_dir)
        if manifest is not None:
            event_metadata = self._artifact_event_metadata(manifest)
            artifacts = manifest.get("artifacts")
            if isinstance(artifacts, list):
                for artifact in artifacts:
                    if not isinstance(artifact, dict) or not self._artifact_matches_step(artifact, selector):
                        continue
                    refs.append(self._artifact_with_event_metadata(artifact, event_metadata))
        refs.extend(self._step_artifact_refs_from_events(run_dir, selector))
        return self._dedupe_step_artifact_refs(refs)

    def _read_evidence_manifest(self, run_dir: Path) -> dict[str, object] | None:
        manifest_path = run_dir / "evidence-manifest.json"
        if not manifest_path.exists():
            return None
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            return None
        bundle = manifest.get("bundle")
        return bundle if isinstance(bundle, dict) else manifest

    def _artifact_event_metadata(self, manifest: dict[str, object]) -> dict[str, dict[str, object]]:
        metadata: dict[str, dict[str, object]] = {}
        events = manifest.get("events")
        if not isinstance(events, list):
            return metadata
        for event in events:
            if not isinstance(event, dict) or event.get("event_type") != "artifact_captured":
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            path = payload.get("path")
            if not isinstance(path, str) or not path:
                continue
            metadata[path] = {
                "timestamp": self._timestamp_ms(event.get("timestamp")),
                "reason": payload.get("reason"),
                "phase": payload.get("phase") or event.get("phase"),
            }
        return metadata

    def _artifact_with_event_metadata(self, artifact: dict[str, object], event_metadata: dict[str, dict[str, object]]) -> dict[str, object]:
        path = artifact.get("path")
        metadata = event_metadata.get(path, {}) if isinstance(path, str) else {}
        merged = dict(artifact)
        for key in ("timestamp", "reason", "phase"):
            current = merged.get(key)
            replacement = metadata.get(key)
            if (current is None or current == "") and replacement is not None and replacement != "":
                merged[key] = metadata[key]
        return merged

    def _step_artifact_refs_from_events(self, run_dir: Path, selector: dict[str, object]) -> list[dict[str, object]]:
        events_path = run_dir / "events.jsonl"
        if not events_path.exists():
            return []
        refs: list[dict[str, object]] = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("type") not in {"tool_call_completed", "tool_call_failed"}:
                continue
            if not self._event_matches_step(event, selector):
                continue
            timestamp = self._timestamp_ms(event.get("timestamp"))
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            artifact_refs = payload.get("artifact_refs")
            artifact_ref_paths: set[str] = set()
            if isinstance(artifact_refs, list):
                for ref in artifact_refs:
                    if isinstance(ref, dict):
                        refs.append({**ref, "timestamp": ref.get("timestamp") or timestamp})
                        ref_path = ref.get("path")
                        if isinstance(ref_path, str) and ref_path:
                            artifact_ref_paths.add(ref_path)
            artifact_path = payload.get("artifact_path")
            if isinstance(artifact_path, str) and artifact_path and artifact_path not in artifact_ref_paths:
                refs.append({"kind": "screenshot", "path": artifact_path, "timestamp": timestamp})
            inline_ref = self._event_inline_observation_ref(event, timestamp)
            if inline_ref is not None:
                refs.append(inline_ref)
        return refs

    def _event_is_recorded_replay_command(self, event: dict[str, object]) -> bool:
        if event.get("type") != "tool_call_completed":
            return False
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if payload.get("tool_origin") not in {"platform", "harness", "common"}:
            return False
        if payload.get("status") not in {"passed", "success", None}:
            return False
        replay = self._event_replay_policy(payload)
        return replay.get("kind") == "fsq_command" and isinstance(replay.get("alias"), str) and bool(replay.get("alias"))

    def _event_replay_policy(self, payload: dict[str, object]) -> dict[str, object]:
        replay = payload.get("replay")
        if isinstance(replay, dict):
            return replay
        replay_kind = payload.get("replay_kind")
        if isinstance(replay_kind, str) and replay_kind:
            return {"kind": "fsq_command", "alias": replay_kind}
        return {}

    def _event_inline_observation_ref(self, event: dict[str, object], timestamp: int | None) -> dict[str, object] | None:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        kind = self._event_observation_kind(event)
        if kind is None:
            return None
        content = self._event_harness_output_content(payload, kind)
        if content is None:
            return None
        mime_type = "application/xml" if kind == "ui_tree" and content.lstrip().startswith("<") else "application/json"
        return {
            "kind": kind,
            "content": content,
            "mime_type": mime_type,
            "reason": "output",
            "phase": "invoke",
            "timestamp": timestamp,
        }

    def _event_observation_kind(self, event: dict[str, object]) -> str | None:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        value = payload.get("fsq_action_name") or payload.get("tool_name") or event.get("tool_name")
        normalized = str(value or "").replace("_", "").lower()
        if normalized == "uitree":
            return "ui_tree"
        if normalized == "uisnapshot":
            return "ui_snapshot"
        return None

    def _event_harness_output_content(self, payload: dict[str, object], kind: str) -> str | None:
        runner_result = payload.get("runner_result") if isinstance(payload.get("runner_result"), dict) else {}
        phase_reports = runner_result.get("phase_reports") if isinstance(runner_result.get("phase_reports"), list) else []
        for phase_report in phase_reports:
            if not isinstance(phase_report, dict):
                continue
            metadata = phase_report.get("metadata") if isinstance(phase_report.get("metadata"), dict) else {}
            output = metadata.get("harness_output")
            if not isinstance(output, dict):
                continue
            if kind == "ui_tree" and isinstance(output.get("xml"), str):
                return output["xml"]
            if output:
                return json.dumps(output, indent=2, ensure_ascii=False)
        return None

    def _artifact_matches_step(self, artifact: dict[str, object], selector: dict[str, object]) -> bool:
        selector_step_id = selector.get("step_id")
        selector_step_index = selector.get("step_index")
        artifact_step_id = artifact.get("step_id") or artifact.get("stepId")
        if isinstance(selector_step_id, str) and artifact_step_id == selector_step_id:
            return True
        if isinstance(selector_step_index, int):
            if isinstance(artifact_step_id, str) and _step_index_from_step_id(artifact_step_id) == selector_step_index:
                return True
            path = artifact.get("path")
            if isinstance(path, str) and _step_index_from_step_id(path) == selector_step_index:
                return True
        return False

    def _event_matches_step(self, event: dict[str, object], selector: dict[str, object]) -> bool:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        runner_result = payload.get("runner_result") if isinstance(payload.get("runner_result"), dict) else {}
        source_ref = runner_result.get("source_ref") if isinstance(runner_result.get("source_ref"), dict) else {}
        selector_step_id = selector.get("step_id")
        selector_step_index = selector.get("step_index")
        step_ids = [
            payload.get("step_id"),
            payload.get("runner_step_id"),
            runner_result.get("step_id"),
        ]
        if isinstance(selector_step_id, str) and selector_step_id in step_ids:
            return True
        if isinstance(selector_step_index, int):
            for step_id in step_ids:
                if isinstance(step_id, str) and _step_index_from_step_id(step_id) == selector_step_index:
                    return True
            source_index = source_ref.get("step_index")
            if isinstance(source_index, int) and source_index + 1 == selector_step_index:
                return True
        return False

    def _dedupe_step_artifact_refs(self, refs: list[dict[str, object]]) -> list[dict[str, object]]:
        deduped: list[dict[str, object]] = []
        seen: set[tuple[str, str, str]] = set()
        for ref in refs:
            key = (str(ref.get("kind") or ""), str(ref.get("path") or ""), str(ref.get("phase") or ref.get("reason") or ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(ref)
        return sorted(deduped, key=self._step_artifact_sort_key)

    def _step_artifact_sort_key(self, ref: dict[str, object]) -> tuple[int, int, str]:
        phase_value = f"{ref.get('reason') or ''} {ref.get('phase') or ''}".lower()
        if "before" in phase_value or "prepare" in phase_value:
            phase_order = 0
        elif "after" in phase_value or "finalize" in phase_value:
            phase_order = 1
        elif "failure" in phase_value:
            phase_order = 2
        else:
            phase_order = 3
        kind_order = 0 if ref.get("kind") == "screenshot" else 1
        return (kind_order, phase_order, str(ref.get("path") or ""))

    def _step_artifact_payloads(self, run_dir: Path, refs: list[dict[str, object]]) -> list[dict[str, object]]:
        artifacts: list[dict[str, object]] = []
        for ref in refs:
            try:
                payload = self._step_artifact_payload(run_dir, ref)
            except _StepArtifactTextTooLargeError as exc:
                payload = {
                    "kind": str(ref.get("kind") or ""),
                    "path": str(ref.get("path") or ""),
                    "phase": ref.get("phase"),
                    "reason": ref.get("reason"),
                    "timestamp": ref.get("timestamp") or self._artifact_timestamp(ref),
                    "mimeType": ref.get("mime_type") or ref.get("mimeType"),
                    "error": str(exc),
                    "sizeBytes": exc.size_bytes,
                    "limitBytes": exc.limit_bytes,
                }
            if payload is not None:
                artifacts.append(payload)
        return artifacts

    def _step_artifact_payload(self, run_dir: Path, ref: dict[str, object]) -> dict[str, object] | None:
        kind = str(ref.get("kind") or "")
        if kind != "screenshot" and kind not in _STEP_TEXT_ARTIFACT_KINDS:
            return None
        inline_content = ref.get("content")
        if isinstance(inline_content, str):
            size_bytes = len(inline_content.encode("utf-8"))
            if size_bytes > STEP_ARTIFACT_TEXT_SIZE_LIMIT_BYTES:
                raise _StepArtifactTextTooLargeError(size_bytes=size_bytes, limit_bytes=STEP_ARTIFACT_TEXT_SIZE_LIMIT_BYTES)
            content, content_mime_type = self._normalize_step_text_artifact_content(inline_content)
            return {
                "kind": kind,
                "path": str(ref.get("path") or ""),
                "phase": ref.get("phase"),
                "reason": ref.get("reason"),
                "timestamp": ref.get("timestamp") or self._artifact_timestamp(ref),
                "mimeType": content_mime_type or ref.get("mime_type") or ref.get("mimeType"),
                "content": content,
            }
        artifact_path, relative_path = self._safe_run_artifact_path(run_dir, ref.get("path"))
        if not artifact_path.exists() or not artifact_path.is_file():
            return None
        payload: dict[str, object] = {
            "kind": kind,
            "path": relative_path,
            "phase": ref.get("phase"),
            "reason": ref.get("reason"),
            "timestamp": ref.get("timestamp") or self._artifact_timestamp(ref),
            "mimeType": ref.get("mime_type") or ref.get("mimeType") or mimetypes.guess_type(artifact_path.name)[0],
        }
        if kind == "screenshot":
            payload["contentBase64"] = base64.b64encode(artifact_path.read_bytes()).decode("ascii")
            return payload
        size_bytes = artifact_path.stat().st_size
        if size_bytes > STEP_ARTIFACT_TEXT_SIZE_LIMIT_BYTES:
            raise _StepArtifactTextTooLargeError(size_bytes=size_bytes, limit_bytes=STEP_ARTIFACT_TEXT_SIZE_LIMIT_BYTES)
        content, content_mime_type = self._step_text_artifact_content(artifact_path)
        payload["content"] = content
        if content_mime_type is not None:
            payload["mimeType"] = content_mime_type
        return payload

    def _step_text_artifact_content(self, artifact_path: Path) -> tuple[str, str | None]:
        content = artifact_path.read_text(encoding="utf-8")
        return self._normalize_step_text_artifact_content(content)

    def _normalize_step_text_artifact_content(self, content: str) -> tuple[str, str | None]:
        if content.lstrip().startswith("<"):
            return self._format_xml_for_display(content), "application/xml"
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return content, None
        if isinstance(payload, dict):
            xml = payload.get("xml")
            if isinstance(xml, str) and xml.strip():
                return self._format_xml_for_display(xml), "application/xml"
        return json.dumps(payload, indent=2, ensure_ascii=False), "application/json"

    def _format_xml_for_display(self, xml: str) -> str:
        try:
            root = _parse_xml_safely(xml)
        except ET.ParseError:
            return xml
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", short_empty_elements=True)

    def _safe_run_artifact_path(self, run_dir: Path, path_value: object) -> tuple[Path, str]:
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("Artifact path is required.")
        candidate = Path(path_value.strip())
        resolved = candidate.resolve() if candidate.is_absolute() else (run_dir / candidate).resolve()
        if not _is_relative_to(resolved, run_dir):
            raise ValueError("Artifact path resolves outside the run directory.")
        return resolved, resolved.relative_to(run_dir).as_posix()

    def _record_replay_frame(self, request_id: str, screenshot_payload: dict[str, object]) -> None:
        screenshot = screenshot_payload.get("screenshot")
        timestamp = screenshot_payload.get("timestamp")
        if not isinstance(screenshot, str) or not isinstance(timestamp, int):
            return
        run_id = self.state.run_id_for_request(request_id)
        if not run_id:
            return
        replay_dir = self._replay_dir(run_id)
        self._reset_replay_dir_once(request_id, replay_dir)
        replay_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = replay_dir / "replay-manifest.json"
        manifest = self._read_replay_manifest(manifest_path, request_id, run_id)
        frames = manifest["frames"]
        if frames and frames[-1].get("timestamp") == timestamp:
            return
        frame_index = len(frames) + 1
        frame_name = f"frame-{frame_index:04d}-{timestamp}.png"
        frame_path = replay_dir / frame_name
        frame_path.write_bytes(base64.b64decode(screenshot))
        frames.append({"timestamp": timestamp, "path": frame_name})
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        self.state.set_replay(
            request_id,
            {"requestId": request_id, "runId": run_id, "frameCount": len(frames)},
        )

    def _replay_response(self, replay_id: str) -> tuple[int, object]:
        run_id = self.state.run_id_for_request(replay_id) or replay_id
        manifest_path = self._replay_dir(run_id) / "replay-manifest.json"
        if not manifest_path.exists():
            return self._evidence_replay_response(replay_id, run_id)
        manifest = self._read_replay_manifest(manifest_path, replay_id, run_id)
        frames = []
        for index, frame in enumerate(manifest["frames"], start=1):
            frame_path = (manifest_path.parent / str(frame.get("path") or "")).resolve()
            if not _is_relative_to(frame_path, manifest_path.parent) or not frame_path.is_file():
                continue
            frames.append(
                {
                    "index": index,
                    "timestamp": frame.get("timestamp"),
                    "path": str(frame.get("path") or ""),
                    "screenshot": base64.b64encode(frame_path.read_bytes()).decode("ascii"),
                }
            )
        return 200, {"requestId": replay_id, "runId": run_id, "frames": frames}

    def _evidence_replay_response(self, replay_id: str, run_id: str) -> tuple[int, object]:
        run_dir = Path(self.settings.output.runs_dir) / run_id
        manifest_path = run_dir / "evidence-manifest.json"
        frames = []
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return 404, {"error": str(exc) or "Unable to read evidence manifest."}
            timestamps_by_path = self._screenshot_event_timestamps(manifest)
            frames.extend(self._frames_from_artifact_refs(run_dir, manifest.get("artifacts", []), timestamps_by_path))
        if not frames:
            frames.extend(self._event_replay_frames(run_dir))
        frames.sort(key=lambda frame: frame.get("timestamp") or 0)
        self._assign_frame_indexes(frames)
        if not frames:
            if run_dir.is_dir() or self.state.get_task(replay_id) is not None:
                return 200, {
                    "available": False,
                    "requestId": replay_id,
                    "runId": run_id,
                    "frames": [],
                    "message": "No replay frames were captured.",
                }
            return 404, {"error": "Replay frames not found."}
        return 200, {"requestId": replay_id, "runId": run_id, "frames": frames}

    def _assign_frame_indexes(self, frames: list[dict[str, object]]) -> None:
        for index, frame in enumerate(frames, start=1):
            frame["index"] = index

    def _frames_from_artifact_refs(
        self,
        run_dir: Path,
        artifact_refs: object,
        timestamps_by_path: dict[str, int] | None = None,
    ) -> list[dict[str, object]]:
        if not isinstance(artifact_refs, list):
            return []
        timestamps = timestamps_by_path or {}
        frames: list[dict[str, object]] = []
        seen_paths: set[str] = set()
        for artifact in artifact_refs:
            if not isinstance(artifact, dict) or not self._is_screenshot_artifact_ref(artifact):
                continue
            relative_path = str(artifact.get("path") or "")
            if not relative_path or relative_path in seen_paths:
                continue
            seen_paths.add(relative_path)
            frame_path = (run_dir / relative_path).resolve()
            if not _is_relative_to(frame_path, run_dir) or not frame_path.is_file():
                continue
            frames.append(
                {
                    "timestamp": timestamps.get(relative_path) or self._artifact_timestamp(artifact),
                    "path": relative_path,
                    "screenshot": base64.b64encode(frame_path.read_bytes()).decode("ascii"),
                }
            )
        return frames

    def _event_replay_frames(self, run_dir: Path) -> list[dict[str, object]]:
        events_path = run_dir / "events.jsonl"
        if not events_path.exists():
            return []
        refs: list[dict[str, object]] = []
        seen_paths: set[str] = set()
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("type") not in {"tool_call_completed", "tool_call_failed"}:
                continue
            timestamp = self._timestamp_ms(event.get("timestamp"))
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            artifact_refs = payload.get("artifact_refs")
            if isinstance(artifact_refs, list):
                for ref in artifact_refs:
                    self._append_event_artifact_ref(refs, seen_paths, ref, timestamp)
            artifact_path = payload.get("artifact_path")
            if isinstance(artifact_path, str) and artifact_path:
                self._append_event_artifact_ref(refs, seen_paths, {"kind": "screenshot", "path": artifact_path}, timestamp)
        return self._frames_from_artifact_refs(run_dir, refs)

    def _append_event_artifact_ref(
        self,
        refs: list[dict[str, object]],
        seen_paths: set[str],
        ref: object,
        timestamp: int | None,
    ) -> None:
        if not isinstance(ref, dict) or not self._is_screenshot_artifact_ref(ref):
            return
        path = ref.get("path")
        if not isinstance(path, str) or not path or path in seen_paths:
            return
        seen_paths.add(path)
        refs.append({**ref, "timestamp": ref.get("timestamp") or timestamp})

    def _artifact_timestamp(self, artifact: dict[str, object]) -> int | None:
        timestamp = artifact.get("timestamp")
        if isinstance(timestamp, int):
            return timestamp
        return self._timestamp_ms(artifact.get("created_at"))

    def _is_screenshot_artifact_ref(self, ref: dict[str, object]) -> bool:
        if ref.get("kind") == "screenshot":
            return True
        path = ref.get("path")
        if not isinstance(path, str):
            return False
        normalized = path.replace("\\", "/").lower()
        return "/screenshots/" in normalized and normalized.endswith((".png", ".jpg", ".jpeg", ".webp"))

    def _screenshot_event_timestamps(self, manifest: dict[str, object]) -> dict[str, int]:
        timestamps: dict[str, int] = {}
        events = manifest.get("events")
        if not isinstance(events, list):
            return timestamps
        for event in events:
            if not isinstance(event, dict) or event.get("event_type") != "artifact_captured":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict) or payload.get("kind") != "screenshot":
                continue
            path = payload.get("path")
            timestamp = self._timestamp_ms(event.get("timestamp"))
            if isinstance(path, str) and timestamp is not None:
                timestamps[path] = timestamp
        return timestamps

    def _timestamp_ms(self, value: object) -> int | None:
        if not isinstance(value, str):
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return int(time.mktime(time.strptime(normalized[:19], "%Y-%m-%dT%H:%M:%S")) * 1000)
        except ValueError:
            return None

    def _replay_video_response(self, replay_id: str) -> tuple[int, object]:
        run_id = self.state.run_id_for_request(replay_id) or replay_id
        video_path = self._replay_video_path(run_id)
        if not video_path.exists():
            return 200, {"available": False, "error": "Replay video not found.", "runId": run_id}
        return 200, {
            "available": True,
            "requestId": replay_id,
            "runId": run_id,
            "format": "webm",
            "videoUrl": f"/replay-video-file/{run_id}",
        }

    def _read_replay_manifest(self, manifest_path: Path, request_id: str, run_id: str) -> dict[str, object]:
        if manifest_path.exists():
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                frames = payload.get("frames") if isinstance(payload, dict) else None
                if isinstance(frames, list):
                    video = payload.get("video") if isinstance(payload.get("video"), dict) else None
                    return {"requestId": request_id, "runId": run_id, "frames": frames, "video": video}
            except (OSError, json.JSONDecodeError):
                pass
        return {"requestId": request_id, "runId": run_id, "frames": []}

    def _store_replay_video(self, replay_id: str, body: dict[str, object]) -> tuple[int, object]:
        run_id = self.state.run_id_for_request(replay_id) or replay_id
        video_base64 = body.get("videoBase64")
        mime_type = body.get("mimeType")
        if not isinstance(video_base64, str) or not video_base64.strip():
            return 400, {"error": "videoBase64 is required."}
        if not isinstance(mime_type, str) or not mime_type.lower().startswith("video/webm"):
            return 400, {"error": "Only video/webm replay uploads are supported."}
        replay_dir = self._replay_dir(run_id)
        self._reset_replay_dir_once(replay_id, replay_dir)
        replay_dir.mkdir(parents=True, exist_ok=True)
        video_path = replay_dir / "replay.webm"
        try:
            video_path.write_bytes(base64.b64decode(video_base64))
        except Exception as exc:  # noqa: BLE001 - API returns structured errors.
            return 400, {"error": str(exc) or "Invalid replay video."}
        manifest_path = replay_dir / "replay-manifest.json"
        manifest = self._read_replay_manifest(manifest_path, replay_id, run_id)
        manifest["video"] = {"path": "replay.webm", "mimeType": "video/webm"}
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return 200, {
            "available": True,
            "requestId": replay_id,
            "runId": run_id,
            "videoUrl": f"/replay-video-file/{run_id}",
            "mimeType": "video/webm",
        }

    def _replay_dir(self, run_id: str) -> Path:
        slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", run_id).strip("-") or "run"
        return Path(self.settings.output.runs_dir) / slug / "playground-replay"

    def _replay_video_path(self, run_id: str) -> Path:
        return self._replay_dir(run_id) / "replay.webm"

    def _reset_replay_dir_once(self, request_id: str, replay_dir: Path) -> None:
        if self.state.mark_replay_reset(request_id) and replay_dir.exists():
            shutil.rmtree(replay_dir)

    def _reset_replay_for_known_run(self, request_id: str, run_id: str | None) -> None:
        if not run_id:
            return
        self.state.bind_run_id(request_id, run_id)
        self._reset_replay_dir_once(request_id, self._replay_dir(run_id))

    def _strict_case_run_id(self, path_text: str) -> str | None:
        try:
            return FsqCaseLoader().load_case(self._resolve_case_yaml_path(path_text)).id
        except (ConfigurationError, OSError, UnicodeDecodeError):
            return None

    def _resolve_case_yaml_path(self, path_text: str) -> Path:
        requested = Path(path_text.strip())
        candidates = [requested] if requested.is_absolute() else [self.settings.cases.dir / requested, Path.cwd() / requested]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        raise FileNotFoundError(path_text)


class _PlaygroundHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], playground: PlaygroundServer) -> None:
        super().__init__(server_address, handler_class)
        self.playground = playground


class _RequestHandler(BaseHTTPRequestHandler):
    server: _PlaygroundHTTPServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/task-stream/"):
            request_id = unquote(parsed.path.removeprefix("/task-stream/")).strip()
            self._stream_task_progress(request_id, parse_qs(parsed.query))
            return
        if parsed.path.startswith("/replay-video-file/"):
            status, payload, content_type, extra_headers = self.server.playground.handle_replay_video_file(parsed.path, self.headers.get("Range"))
            self._send_bytes(status, payload, content_type, extra_headers)
            return
        if _is_api_path(parsed.path):
            status, payload = self.server.playground.handle_get(parsed.path, parse_qs(parsed.query))
            self._send_json(status, payload)
            return
        status, payload, content_type = self.server.playground.static_response(parsed.path)
        self._send_bytes(status, payload, content_type)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self._read_json_body()
        if isinstance(body, str):
            self._send_json(400, {"error": body})
            return
        status, payload = self.server.playground.handle_post(parsed.path, body)
        self._send_json(status, payload)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        body = self._read_json_body()
        if isinstance(body, str):
            self._send_json(400, {"error": body})
            return
        status, payload = self.server.playground.handle_put(parsed.path, body)
        self._send_json(status, payload)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        status, payload = self.server.playground.handle_delete(parsed.path)
        self._send_json(status, payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature.
        return None

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True

    def _stream_task_progress(self, request_id: str, query: dict[str, list[str]]) -> None:
        last_sequence = _after_sequence(query) or 0
        first = self.server.playground.handle_get(f"/task-progress/{request_id}", {"after_sequence": [str(last_sequence)]})
        if first[0] != 200 or not isinstance(first[1], dict):
            self._send_json(404, {"error": "Task progress not found."})
            return
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            last_sequence = self._write_sse_progress(first[1], last_sequence)
            status = str(first[1].get("status"))
            revision = 0
            while status == "running":
                payload, revision = self.server.playground.state.wait_for_update(request_id, last_sequence, revision, timeout=15.0)
                if not isinstance(payload, dict):
                    break
                last_sequence = self._write_sse_progress(payload, last_sequence)
                status = str(payload.get("status"))
        except (BrokenPipeError, ConnectionResetError):
            return

    def _write_sse_progress(self, payload: dict[str, object], last_sequence: int) -> int:
        events = payload.get("events")
        if isinstance(events, list):
            for event in events:
                if isinstance(event, dict) and isinstance(event.get("sequence"), int):
                    last_sequence = max(last_sequence, int(event["sequence"]))
        self.wfile.write(b"data: " + json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n\n")
        self.wfile.flush()
        return last_sequence

    def _read_json_body(self) -> dict[str, object] | str:
        content_length = int(self.headers.get("Content-Length") or "0")
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "Request body must be valid JSON."
        if not isinstance(body, dict):
            return "Request body must be a JSON object."
        return body

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(self, status: int, payload: bytes, content_type: str, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)


def run_playground(settings: Settings, options: PlaygroundServerOptions) -> None:
    server = PlaygroundServer(settings, options)
    server.start()
    try:
        print(f"Playground: {server.url}")
        if options.open_browser:
            webbrowser.open(server.url)
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return
    finally:
        server.stop()


def _is_api_path(path: str) -> bool:
    return path in {"/status", "/session", "/session/setup", "/session/auto", "/runtime-info", "/screenshot", "/yaml/input"} or path.startswith(
        ("/task-progress/", "/preview/", "/reports/", "/replay/", "/replay-video/", "/runs/", "/step-artifacts/", "/yaml/recorded/")
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    else:
        return True


def _step_index_from_step_id(value: str) -> int | None:
    match = re.search(r"(?:^|[-_/])step[-_](\d+)(?:\D|$)", value)
    if match is None:
        return None
    return int(match.group(1))


def _parse_byte_range(range_header: str | None, total_size: int) -> tuple[int, int] | None:
    if not range_header or total_size <= 0:
        return None
    raw = range_header.strip()
    if not raw.lower().startswith("bytes="):
        return None
    spec = raw[len("bytes=") :].split(",", 1)[0].strip()
    if not spec or "-" not in spec:
        return None
    start_text, end_text = spec.split("-", 1)
    start_text = start_text.strip()
    end_text = end_text.strip()
    last_index = total_size - 1
    try:
        if start_text == "":
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None
            start = max(0, total_size - suffix_length)
            end = last_index
        else:
            start = int(start_text)
            end = int(end_text) if end_text else last_index
    except ValueError:
        return None
    if start < 0 or start > last_index or end < start:
        return None
    return start, min(end, last_index)


def _after_sequence(query: dict[str, list[str]]) -> int | None:
    values = query.get("after_sequence") or query.get("afterSequence") or []
    if not values:
        return None
    try:
        return max(0, int(values[0]))
    except (TypeError, ValueError):
        return None
