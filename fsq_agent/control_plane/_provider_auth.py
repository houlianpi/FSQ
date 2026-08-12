# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fsq_agent.models import ConfigurationError
from fsq_agent.providers import complete_github_copilot_device_flow, request_github_copilot_device_code

from ._config import ConfigAPIError

if TYPE_CHECKING:
    from pathlib import Path

    from fsq_agent.providers import GitHubDeviceCode

_MAX_RETAINED_RECORDS = 20


def _iso_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


@dataclass
class _AuthRecord:
    auth_request_id: str
    model: str
    verification_uri: str
    user_code: str
    expires_at: float
    poll_interval_seconds: int
    cancel_event: Event
    status: str = "waiting"
    message: str | None = None
    thread: Thread | None = None

    def presentation(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "authRequestId": self.auth_request_id,
            "verificationUri": self.verification_uri,
            "userCode": self.user_code,
            "expiresAt": _iso_timestamp(self.expires_at),
            "pollIntervalSeconds": self.poll_interval_seconds,
            "status": self.status,
        }
        if self.message:
            payload["message"] = self.message
        return payload


class ProviderAuthState:
    def __init__(self, user_config_root: Path | None) -> None:
        self._user_config_root = user_config_root
        self._lock = Lock()
        self._records: OrderedDict[str, _AuthRecord] = OrderedDict()
        self._starting = False
        self._closed = False

    def start(self, body: dict[str, Any]) -> dict[str, Any]:
        model = body.get("modelName")
        if set(body) != {"modelName"} or not isinstance(model, str) or not model.strip():
            raise ConfigAPIError(400, "invalid_request", "modelName must be one non-empty string.", "Enter a GitHub Copilot model name and retry.")
        with self._lock:
            if self._closed:
                raise ConfigAPIError(503, "device_flow_unavailable", "GitHub device flow is unavailable while Control Plane is stopping.", "Restart Control Plane and try again.")
            if self._starting or any(record.status == "waiting" for record in self._records.values()):
                raise ConfigAPIError(409, "device_flow_busy", "A GitHub device flow is already waiting.", "Complete or cancel the active device flow.")
            self._starting = True
        try:
            device_code = request_github_copilot_device_code()
        except Exception:
            with self._lock:
                self._starting = False
            raise
        record = _AuthRecord(
            auth_request_id=str(uuid4()),
            model=model.strip(),
            verification_uri=device_code.verification_uri,
            user_code=device_code.user_code,
            expires_at=device_code.expires_at,
            poll_interval_seconds=device_code.poll_interval_seconds,
            cancel_event=Event(),
        )
        thread = Thread(target=self._complete, args=(record, device_code), name=f"fsq-provider-auth-{record.auth_request_id}", daemon=True)
        record.thread = thread
        with self._lock:
            self._starting = False
            if self._closed:
                raise ConfigAPIError(503, "device_flow_unavailable", "GitHub device flow was cancelled while Control Plane stopped.", "Restart Control Plane and try again.")
            self._records[record.auth_request_id] = record
            self._trim_records()
        thread.start()
        return record.presentation()

    def get(self, auth_request_id: str) -> dict[str, Any]:
        with self._lock:
            return self._require(auth_request_id).presentation()

    def cancel(self, auth_request_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(auth_request_id)
            if record.status == "waiting":
                record.cancel_event.set()
                record.status = "cancelled"
                record.message = "GitHub device flow cancelled."
            return record.presentation()

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            records = list(self._records.values())
            for record in records:
                if record.status == "waiting":
                    record.cancel_event.set()
                    record.status = "cancelled"
                    record.message = "GitHub device flow cancelled during shutdown."
        for record in records:
            if record.thread is not None and record.thread.is_alive():
                record.thread.join(timeout=2)

    def _complete(self, record: _AuthRecord, device_code: GitHubDeviceCode) -> None:
        try:
            complete_github_copilot_device_flow(
                device_code,
                model=record.model,
                cancel_requested=record.cancel_event.is_set,
                user_config_root=self._user_config_root,
            )
        except ConfigurationError as exc:
            self._finish_error(record, exc)
        except Exception:  # noqa: BLE001 - background boundary retains only a safe terminal status.
            self._finish(record, "failed", "GitHub device flow failed unexpectedly.")
        else:
            self._finish(record, "success", "GitHub Copilot Provider saved.")

    def _finish_error(self, record: _AuthRecord, exc: ConfigurationError) -> None:
        message = str(exc).splitlines()[0]
        lowered = message.casefold()
        if record.cancel_event.is_set() or "cancel" in lowered:
            self._finish(record, "cancelled", "GitHub device flow cancelled.")
        elif "expired" in lowered:
            self._finish(record, "expired", "GitHub device code expired.")
        else:
            self._finish(record, "failed", message)

    def _finish(self, record: _AuthRecord, status: str, message: str) -> None:
        with self._lock:
            if record.status == "cancelled":
                return
            record.status = status
            record.message = message

    def _require(self, auth_request_id: str) -> _AuthRecord:
        record = self._records.get(auth_request_id)
        if record is None:
            raise ConfigAPIError(404, "auth_request_not_found", "GitHub device-flow request not found.", "Start a new GitHub device flow.")
        return record

    def _trim_records(self) -> None:
        while len(self._records) > _MAX_RETAINED_RECORDS:
            terminal_id = next((key for key, record in self._records.items() if record.status != "waiting"), None)
            if terminal_id is None:
                return
            self._records.pop(terminal_id)
