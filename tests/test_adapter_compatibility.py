# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import importlib
from importlib.util import find_spec


def test_cli_compatibility_paths_share_canonical_module_objects() -> None:
    legacy = importlib.import_module("fsq_agent.cli")
    canonical = importlib.import_module("fsq_agent.adapters.cli")
    assert legacy.main is canonical.main


def test_control_plane_compatibility_paths_share_canonical_module_objects() -> None:
    legacy = importlib.import_module("fsq_agent.control_plane")
    canonical = importlib.import_module("fsq_agent.adapters.control_plane")
    assert legacy.ControlPlaneServer is canonical.ControlPlaneServer


def test_legacy_playground_packages_are_absent() -> None:
    assert find_spec("fsq_agent.playground") is None
    assert find_spec("fsq_agent.adapters.control_plane.playground") is None
