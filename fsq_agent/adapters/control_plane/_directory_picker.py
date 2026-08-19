# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Final

_MAX_OUTPUT_BYTES: Final = 64 * 1024
_SELECTED_PREFIX: Final = "__FSQ_SELECTED__:"
_CANCELLED: Final = "__FSQ_CANCELLED__"


class DirectoryPickerAPIError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, action: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.action = action


@dataclass(frozen=True)
class _PickerCommand:
    argv: tuple[str, ...]
    cancelled_return_codes: frozenset[int] = frozenset()
    base64_path: bool = False


class DirectoryPicker:
    def __init__(self) -> None:
        self._selection_lock = Lock()
        self._state_lock = Lock()
        self._active_process: subprocess.Popen[bytes] | None = None
        self._closed = False

    def choose(self) -> dict[str, str]:
        if not self._selection_lock.acquire(blocking=False):
            raise DirectoryPickerAPIError(
                409,
                "directory_picker_busy",
                "Another folder selection is already open.",
                "Complete or cancel the open folder selection and retry.",
            )
        process: subprocess.Popen[bytes] | None = None
        completed = False
        try:
            with self._state_lock:
                if self._closed:
                    raise _unavailable("Folder selection is unavailable because Control Plane is stopping.")
            command = _picker_command()
            try:
                process = subprocess.Popen(  # noqa: S603 - fixed host adapter arguments, never user supplied.
                    command.argv,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    shell=False,
                )
            except OSError as exc:
                raise _unavailable("The system folder chooser could not be started.") from exc
            with self._state_lock:
                if self._closed:
                    _terminate(process)
                    raise _unavailable("Folder selection is unavailable because Control Plane is stopping.")
                self._active_process = process
            if process.stdout is None:
                raise _failed()
            output = process.stdout.read(_MAX_OUTPUT_BYTES + 1)
            if len(output) > _MAX_OUTPUT_BYTES:
                _terminate(process)
                raise _invalid_result()
            return_code = process.wait()
            completed = True
            with self._state_lock:
                if self._closed:
                    raise _unavailable("Folder selection is unavailable because Control Plane is stopping.")
            return _decode_result(command, return_code, output)
        except DirectoryPickerAPIError:
            raise
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise _failed() from exc
        finally:
            if process is not None and not completed:
                _terminate(process)
            with self._state_lock:
                if self._active_process is process:
                    self._active_process = None
            self._selection_lock.release()

    def shutdown(self) -> None:
        with self._state_lock:
            self._closed = True
            process = self._active_process
        if process is not None:
            _terminate(process)


def _picker_command() -> _PickerCommand:
    if sys.platform == "win32":
        executable = shutil.which("powershell.exe") or shutil.which("powershell")
        if executable is None:
            raise _unavailable("Windows folder selection requires the system PowerShell executable.")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$dialog.Description = 'Choose workspace parent folder';"
            "$dialog.ShowNewFolderButton = $false;"
            "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {"
            "$bytes = [System.Text.Encoding]::UTF8.GetBytes($dialog.SelectedPath);"
            f"Write-Output ('{_SELECTED_PREFIX}' + [Convert]::ToBase64String($bytes))"
            f"}} else {{ Write-Output '{_CANCELLED}' }}"
        )
        return _PickerCommand(
            (executable, "-NoProfile", "-NonInteractive", "-STA", "-Command", script),
            base64_path=True,
        )
    if sys.platform == "darwin":
        executable = "/usr/bin/osascript"
        if not Path(executable).is_file():
            raise _unavailable("The macOS folder chooser is unavailable.")
        script = (
            'try\nset selectedFolder to choose folder with prompt "Choose workspace parent folder"\n'
            f'return "{_SELECTED_PREFIX}" & POSIX path of selectedFolder\n'
            f'on error number -128\nreturn "{_CANCELLED}"\nend try'
        )
        return _PickerCommand((executable, "-e", script))
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise _unavailable("Folder selection requires a graphical desktop session.")
    if executable := shutil.which("zenity"):
        return _PickerCommand(
            (executable, "--file-selection", "--directory", "--title=Choose workspace parent folder"),
            frozenset({1}),
        )
    if executable := shutil.which("kdialog"):
        return _PickerCommand(
            (executable, "--getexistingdirectory", "--title", "Choose workspace parent folder"),
            frozenset({1}),
        )
    raise _unavailable("Folder selection requires zenity or kdialog on Linux.")


def _decode_result(command: _PickerCommand, return_code: int, output: bytes) -> dict[str, str]:
    if return_code in command.cancelled_return_codes:
        return {"status": "cancelled"}
    if return_code != 0:
        raise _failed()
    try:
        text = os.fsdecode(output).rstrip("\r\n")
    except UnicodeError as exc:
        raise _failed() from exc
    if text == _CANCELLED:
        return {"status": "cancelled"}
    if text.startswith(_SELECTED_PREFIX):
        text = text.removeprefix(_SELECTED_PREFIX)
        if command.base64_path:
            try:
                text = base64.b64decode(text, validate=True).decode("utf-8")
            except (UnicodeError, ValueError) as exc:
                raise _failed() from exc
    if not text or "\x00" in text:
        raise _failed()
    selected = Path(text)
    if not selected.is_absolute():
        raise _invalid_selection()
    try:
        resolved = selected.resolve(strict=True)
    except OSError as exc:
        raise _invalid_selection() from exc
    if not resolved.is_dir():
        raise _invalid_selection()
    return {"status": "selected", "parentPath": str(resolved)}


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
            process.wait(timeout=2)
        except OSError:
            return
        except subprocess.TimeoutExpired:
            return


def _unavailable(message: str) -> DirectoryPickerAPIError:
    return DirectoryPickerAPIError(
        503,
        "directory_picker_unavailable",
        message,
        "Restore the desktop folder chooser and retry.",
    )


def _failed() -> DirectoryPickerAPIError:
    return DirectoryPickerAPIError(
        503,
        "directory_picker_failed",
        "The system folder chooser failed.",
        "Close other folder dialogs and retry.",
    )


def _invalid_result() -> DirectoryPickerAPIError:
    return DirectoryPickerAPIError(
        503,
        "directory_picker_failed",
        "The system folder chooser returned an invalid result.",
        "Close other folder dialogs and retry.",
    )


def _invalid_selection() -> DirectoryPickerAPIError:
    return DirectoryPickerAPIError(
        409,
        "directory_picker_invalid_selection",
        "The selected folder is no longer available.",
        "Choose an existing folder and retry.",
    )
