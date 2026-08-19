# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import importlib


def test_cli_compatibility_paths_share_canonical_module_objects() -> None:
    legacy = importlib.import_module("fsq_agent.cli")
    canonical = importlib.import_module("fsq_agent.adapters.cli")
    assert legacy.main is canonical.main
    assert importlib.import_module("fsq_agent.cli._main") is importlib.import_module("fsq_agent.adapters.cli._main")


def test_control_plane_compatibility_paths_share_canonical_module_objects() -> None:
    legacy = importlib.import_module("fsq_agent.control_plane")
    canonical = importlib.import_module("fsq_agent.adapters.control_plane")
    assert legacy.ControlPlaneServer is canonical.ControlPlaneServer
    assert importlib.import_module("fsq_agent.control_plane._state") is importlib.import_module("fsq_agent.adapters.control_plane._state")


def test_playground_compatibility_paths_share_canonical_module_objects() -> None:
    legacy = importlib.import_module("fsq_agent.playground")
    canonical = importlib.import_module("fsq_agent.adapters.control_plane.playground")
    assert legacy.PlaygroundServer is canonical.PlaygroundServer
    assert importlib.import_module("fsq_agent.playground._state") is importlib.import_module("fsq_agent.adapters.control_plane.playground._state")
