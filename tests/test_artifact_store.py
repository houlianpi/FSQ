# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path

from fsq_agent.core import ArtifactStore


def test_artifact_store_writes_json_artifact_with_relative_ref(tmp_path: Path) -> None:
    store = ArtifactStore(run_dir=tmp_path)

    ref = store.write_json(
        kind="ui_tree",
        step_id="step-1",
        phase="finalize",
        name="UI Tree",
        payload={"nodes": [{"text": "Login"}]},
    )

    expected_path = tmp_path / "artifacts" / "ui-trees" / "step-1-finalize-ui-tree.json"
    assert expected_path.exists()
    assert json.loads(expected_path.read_text(encoding="utf-8")) == {"nodes": [{"text": "Login"}]}
    assert ref.artifact_id == "step-1-finalize-ui-tree"
    assert ref.kind == "ui_tree"
    assert ref.path == Path("artifacts/ui-trees/step-1-finalize-ui-tree.json")
    assert ref.mime_type == "application/json"
    assert ref.step_id == "step-1"
    assert ref.phase == "finalize"


def test_artifact_store_writes_text_log_artifact(tmp_path: Path) -> None:
    store = ArtifactStore(run_dir=tmp_path)

    ref = store.write_text(
        kind="log",
        step_id="step-1",
        phase="invoke",
        name="Driver Log",
        text="tap started\ntap finished\n",
    )

    expected_path = tmp_path / "artifacts" / "logs" / "step-1-invoke-driver-log.txt"
    assert expected_path.read_text(encoding="utf-8") == "tap started\ntap finished\n"
    assert ref.artifact_id == "step-1-invoke-driver-log"
    assert ref.kind == "log"
    assert ref.path == Path("artifacts/logs/step-1-invoke-driver-log.txt")
    assert ref.mime_type == "text/plain"


def test_artifact_store_writes_screenshot_bytes_artifact(tmp_path: Path) -> None:
    store = ArtifactStore(run_dir=tmp_path)

    ref = store.write_bytes(
        kind="screenshot",
        step_id="step-1",
        phase="finalize",
        name="Screen",
        data=b"fake-png",
    )

    expected_path = tmp_path / "artifacts" / "screenshots" / "step-1-finalize-screen.png"
    assert expected_path.read_bytes() == b"fake-png"
    assert ref.artifact_id == "step-1-finalize-screen"
    assert ref.kind == "screenshot"
    assert ref.path == Path("artifacts/screenshots/step-1-finalize-screen.png")
    assert ref.mime_type == "image/png"
