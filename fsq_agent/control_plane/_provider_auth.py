# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event, Lock, Thread, Timer
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fsq_agent.models import ConfigurationError
from fsq_agent.providers import (
    GitHubCopilotAuthorization,
    GitHubCopilotModel,
    activate_github_copilot_authorization,
    complete_github_copilot_device_flow,
    list_github_copilot_models,
    request_github_copilot_device_code,
)

from ._config import ConfigAPIError

if TYPE_CHECKING:
    from pathlib import Path

    from fsq_agent.providers import GitHubDeviceCode

_MAX_RETAINED_RECORDS = 20
_PENDING_AUTHORIZATION_SECONDS = 10 * 60
_ACTIVE_STATUSES = {"waiting", "loading_models", "ready", "model_error"}


def _iso_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


@dataclass
class _AuthRecord:
    auth_request_id: str
    verification_uri: str
    user_code: str
    expires_at: float
    poll_interval_seconds: int
    cancel_event: Event
    status: str = "waiting"
    message: str | None = None
    thread: Thread | None = None
    expiry_timer: Timer | None = None
    authorization: GitHubCopilotAuthorization | None = None
    models: tuple[GitHubCopilotModel, ...] = ()
    offered_model_ids: frozenset[str] = frozenset()
    authorization_expires_at: float | None = None
    saving: bool = False

    def presentation(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "authRequestId": self.auth_request_id,
            "status": self.status,
        }
        if self.status == "waiting":
            payload.update(
                verificationUri=self.verification_uri,
                userCode=self.user_code,
                expiresAt=_iso_timestamp(self.expires_at),
                pollIntervalSeconds=self.poll_interval_seconds,
            )
        elif self.status in {"loading_models", "ready", "model_error"} and self.authorization_expires_at is not None:
            payload["expiresAt"] = _iso_timestamp(self.authorization_expires_at)
            if self.status == "loading_models":
                payload["pollIntervalSeconds"] = 1
            elif self.status == "ready":
                payload["models"] = [{"id": model.id, "name": model.name} for model in self.models]
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
        self._require_empty_body(body)
        with self._lock:
            if self._closed:
                raise ConfigAPIError(503, "device_flow_unavailable", "GitHub device flow is unavailable while Control Plane is stopping.", "Restart Control Plane and try again.")
            self._expire_due_records_locked()
            if self._starting or any(record.status in _ACTIVE_STATUSES or record.saving for record in self._records.values()):
                raise ConfigAPIError(409, "device_flow_busy", "A GitHub provider transaction is already active.", "Complete or cancel the active GitHub provider transaction.")
            self._starting = True
        try:
            device_code = request_github_copilot_device_code()
        except Exception:
            with self._lock:
                self._starting = False
            raise
        record = _AuthRecord(
            auth_request_id=str(uuid4()),
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
            record = self._require(auth_request_id)
            self._expire_record_if_due_locked(record)
            return record.presentation()

    def retry_models(self, auth_request_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._require_empty_body(body)
        with self._lock:
            record = self._require(auth_request_id)
            self._expire_record_if_due_locked(record)
            if record.status not in {"model_error", "ready"} or (record.status == "ready" and record.models):
                raise ConfigAPIError(409, "model_retry_unavailable", "Model discovery cannot be retried in the current state.", "Wait for authorization or start a new GitHub device flow.")
            if record.authorization is None:
                raise ConfigAPIError(409, "authorization_unavailable", "Pending GitHub authorization is unavailable.", "Start a new GitHub device flow.")
            record.status = "loading_models"
            record.message = None
            thread = Thread(target=self._discover, args=(record,), name=f"fsq-provider-models-{record.auth_request_id}", daemon=True)
            record.thread = thread
            presentation = record.presentation()
        thread.start()
        return presentation

    def save(self, auth_request_id: str, body: dict[str, Any]) -> None:
        model = body.get("modelName")
        if set(body) != {"modelName"} or not isinstance(model, str) or not model.strip():
            raise ConfigAPIError(400, "invalid_request", "modelName must be one non-empty string.", "Select an offered GitHub Copilot model and retry.")
        selected_model = model.strip()
        with self._lock:
            record = self._require(auth_request_id)
            self._expire_record_if_due_locked(record)
            if record.status != "ready" or record.authorization is None:
                raise ConfigAPIError(409, "provider_transaction_not_ready", "GitHub provider transaction is not ready to save.", "Wait for model discovery or start a new device flow.")
            if selected_model not in record.offered_model_ids:
                raise ConfigAPIError(400, "model_not_offered", "The selected model was not offered for this authorization.", "Select a model from the current list and retry.")
            if record.saving:
                raise ConfigAPIError(409, "provider_save_busy", "GitHub Provider save is already in progress.", "Wait for the current save to finish.")
            record.saving = True
            authorization = record.authorization
        try:
            activate_github_copilot_authorization(
                authorization,
                model=selected_model,
                user_config_root=self._user_config_root,
            )
        except Exception:
            with self._lock:
                record.saving = False
            raise
        with self._lock:
            record.saving = False
            record.status = "success"
            record.message = "GitHub Copilot Provider saved."
            self._scrub_locked(record)

    def cancel(self, auth_request_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(auth_request_id)
            self._expire_record_if_due_locked(record)
            if record.saving:
                raise ConfigAPIError(409, "provider_save_busy", "GitHub Provider save is already in progress.", "Wait for the current save to finish.")
            if record.status in _ACTIVE_STATUSES:
                record.cancel_event.set()
                record.status = "cancelled"
                record.message = "GitHub provider transaction cancelled."
                self._scrub_locked(record)
            return record.presentation()

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            records = list(self._records.values())
            for record in records:
                if record.status in _ACTIVE_STATUSES:
                    record.cancel_event.set()
                    record.status = "cancelled"
                    record.message = "GitHub provider transaction cancelled during shutdown."
                    self._scrub_locked(record)
        for record in records:
            if record.thread is not None and record.thread.is_alive():
                record.thread.join(timeout=2)

    def _complete(self, record: _AuthRecord, device_code: GitHubDeviceCode) -> None:
        try:
            authorization = complete_github_copilot_device_flow(
                device_code,
                cancel_requested=record.cancel_event.is_set,
            )
        except ConfigurationError as exc:
            self._finish_error(record, exc)
        except Exception:  # noqa: BLE001 - background boundary retains only a safe terminal status.
            self._finish(record, "failed", "GitHub device flow failed unexpectedly.")
        else:
            with self._lock:
                if record.status == "cancelled" or self._closed:
                    return
                record.authorization = authorization
                record.authorization_expires_at = time.time() + _PENDING_AUTHORIZATION_SECONDS
                record.status = "loading_models"
                timer = Timer(_PENDING_AUTHORIZATION_SECONDS, self._expire_authorization, args=(record.auth_request_id,))
                timer.daemon = True
                record.expiry_timer = timer
            timer.start()
            self._discover(record)

    def _discover(self, record: _AuthRecord) -> None:
        with self._lock:
            self._expire_record_if_due_locked(record)
            if record.status != "loading_models" or record.authorization is None:
                return
            authorization = record.authorization
        try:
            models = list_github_copilot_models(authorization)
        except ConfigurationError as exc:
            with self._lock:
                self._expire_record_if_due_locked(record)
                if record.status == "loading_models":
                    record.status = "model_error"
                    record.message = str(exc).splitlines()[0]
        except Exception:  # noqa: BLE001 - background boundary retains only a safe retry state.
            with self._lock:
                self._expire_record_if_due_locked(record)
                if record.status == "loading_models":
                    record.status = "model_error"
                    record.message = "GitHub Copilot model discovery failed unexpectedly."
        else:
            with self._lock:
                self._expire_record_if_due_locked(record)
                if record.status != "loading_models":
                    return
                record.models = models
                record.offered_model_ids = frozenset(model.id for model in models)
                record.status = "ready"
                record.message = None

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
            if status in {"failed", "expired", "cancelled", "success"}:
                self._scrub_locked(record)

    def _expire_authorization(self, auth_request_id: str) -> None:
        with self._lock:
            record = self._records.get(auth_request_id)
            if record is not None:
                self._expire_record_if_due_locked(record)

    def _expire_due_records_locked(self) -> None:
        for record in self._records.values():
            self._expire_record_if_due_locked(record)

    def _expire_record_if_due_locked(self, record: _AuthRecord) -> None:
        if (
            record.status in {"loading_models", "ready", "model_error"}
            and record.authorization_expires_at is not None
            and time.time() >= record.authorization_expires_at
        ):
            record.cancel_event.set()
            record.status = "expired"
            record.message = "Pending GitHub authorization expired."
            self._scrub_locked(record)

    @staticmethod
    def _scrub_locked(record: _AuthRecord) -> None:
        record.authorization = None
        record.models = ()
        record.offered_model_ids = frozenset()
        record.authorization_expires_at = None
        if record.expiry_timer is not None:
            record.expiry_timer.cancel()
            record.expiry_timer = None

    @staticmethod
    def _require_empty_body(body: dict[str, Any]) -> None:
        if body:
            raise ConfigAPIError(400, "invalid_request", "Request body must contain no fields.", "Remove request fields and retry.")

    def _require(self, auth_request_id: str) -> _AuthRecord:
        record = self._records.get(auth_request_id)
        if record is None:
            raise ConfigAPIError(404, "auth_request_not_found", "GitHub device-flow request not found.", "Start a new GitHub device flow.")
        return record

    def _trim_records(self) -> None:
        while len(self._records) > _MAX_RETAINED_RECORDS:
            terminal_id = next((key for key, record in self._records.items() if record.status not in _ACTIVE_STATUSES and not record.saving), None)
            if terminal_id is None:
                return
            self._records.pop(terminal_id)
