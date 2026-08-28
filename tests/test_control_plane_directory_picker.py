# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import base64
import io
import subprocess
from pathlib import Path

import pytest

from fsq_agent.control_plane import _directory_picker as picker_module
from fsq_agent.control_plane._directory_picker import DirectoryPicker, DirectoryPickerAPIError


class _Process:
    def __init__(self, output: bytes = b"", return_code: int = 0) -> None:
        self.stdout = io.BytesIO(output)
        self.return_code = return_code
        self.terminated = False
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        return self.return_code

    def poll(self) -> int | None:
        return self.return_code if self.terminated else None

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


class _FailingOutput:
    def read(self, size: int = -1) -> bytes:
        raise OSError("picker output failed")


class _FailingWaitProcess(_Process):
    def wait(self, timeout: float | None = None) -> int:
        raise OSError("picker wait failed")


def test_picker_commands_are_fixed_for_windows_macos_and_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(picker_module.sys, "platform", "win32")
    monkeypatch.setattr(picker_module.shutil, "which", lambda name: "C:\\Windows\\powershell.exe" if name == "powershell.exe" else None)
    windows = picker_module._picker_command()
    assert windows.argv[:5] == ("C:\\Windows\\powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-Command")
    assert windows.base64_path is True

    monkeypatch.setattr(picker_module.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    macos = picker_module._picker_command()
    assert macos.argv[0:2] == ("/usr/bin/osascript", "-e")
    assert "choose folder" in macos.argv[2]

    monkeypatch.setattr(picker_module.sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(picker_module.shutil, "which", lambda name: "/usr/bin/zenity" if name == "zenity" else None)
    linux = picker_module._picker_command()
    assert linux.argv == ("/usr/bin/zenity", "--file-selection", "--directory", "--title=Choose workspace folder")
    assert linux.cancelled_return_codes == frozenset({1})

    monkeypatch.setattr(picker_module.shutil, "which", lambda name: "/usr/bin/kdialog" if name == "kdialog" else None)
    kdialog = picker_module._picker_command()
    assert kdialog.argv == ("/usr/bin/kdialog", "--getexistingdirectory", "--title", "Choose workspace folder")
    assert kdialog.cancelled_return_codes == frozenset({1})


def test_picker_decodes_selected_and_cancelled_results(tmp_path: Path) -> None:
    selected = picker_module._decode_result(picker_module._PickerCommand(("picker",)), 0, f"{tmp_path}\n".encode())
    encoded = base64.b64encode(str(tmp_path).encode()).decode()
    windows = picker_module._decode_result(
        picker_module._PickerCommand(("picker",), base64_path=True),
        0,
        f"{picker_module._SELECTED_PREFIX}{encoded}\r\n".encode(),
    )
    cancelled = picker_module._decode_result(picker_module._PickerCommand(("picker",), frozenset({1})), 1, b"")

    assert selected == windows == {"status": "selected", "selectedPath": str(tmp_path.resolve())}
    assert cancelled == {"status": "cancelled"}


@pytest.mark.parametrize(
    ("return_code", "output", "code"),
    [
        (2, b"", "directory_picker_failed"),
        (0, b"relative/path\n", "directory_picker_invalid_selection"),
        (0, b"missing-absolute-path\n", "directory_picker_invalid_selection"),
    ],
)
def test_picker_rejects_failed_or_invalid_results(return_code: int, output: bytes, code: str) -> None:
    with pytest.raises(DirectoryPickerAPIError) as error:
        picker_module._decode_result(picker_module._PickerCommand(("picker",)), return_code, output)

    assert error.value.code == code


def test_picker_launches_without_a_shell_and_bounds_output(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _Process(b"x" * (picker_module._MAX_OUTPUT_BYTES + 1))
    invocation: dict[str, object] = {}

    def popen(argv: tuple[str, ...], **kwargs: object) -> _Process:
        invocation.update({"argv": argv, **kwargs})
        return process

    monkeypatch.setattr(picker_module, "_picker_command", lambda: picker_module._PickerCommand(("fixed-picker", "--directory")))
    monkeypatch.setattr(picker_module.subprocess, "Popen", popen)

    with pytest.raises(DirectoryPickerAPIError) as error:
        DirectoryPicker().choose()

    assert error.value.code == "directory_picker_failed"
    assert invocation["argv"] == ("fixed-picker", "--directory")
    assert invocation["shell"] is False
    assert invocation["stderr"] == subprocess.DEVNULL
    assert process.terminated is True


def test_picker_rejects_concurrent_selection_and_terminates_on_shutdown() -> None:
    picker = DirectoryPicker()
    assert picker._selection_lock.acquire(blocking=False)
    try:
        with pytest.raises(DirectoryPickerAPIError) as error:
            picker.choose()
    finally:
        picker._selection_lock.release()
    assert error.value.status == 409
    assert error.value.code == "directory_picker_busy"

    process = _Process()
    picker._active_process = process
    picker.shutdown()
    assert process.terminated is True


@pytest.mark.parametrize("process", [_Process(), _FailingWaitProcess(b"selected")])
def test_picker_maps_process_io_failures_and_terminates(monkeypatch: pytest.MonkeyPatch, process: _Process) -> None:
    if type(process) is _Process:
        process.stdout = _FailingOutput()  # type: ignore[assignment]
    monkeypatch.setattr(picker_module, "_picker_command", lambda: picker_module._PickerCommand(("fixed-picker",)))
    monkeypatch.setattr(picker_module.subprocess, "Popen", lambda *args, **kwargs: process)

    with pytest.raises(DirectoryPickerAPIError) as error:
        DirectoryPicker().choose()

    assert error.value.code == "directory_picker_failed"
    assert process.terminated is True
    if isinstance(process, _FailingWaitProcess):
        assert process.killed is True


def test_picker_reports_missing_linux_desktop_and_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(picker_module.sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    with pytest.raises(DirectoryPickerAPIError) as error:
        picker_module._picker_command()

    assert error.value.status == 503
    assert error.value.code == "directory_picker_unavailable"
