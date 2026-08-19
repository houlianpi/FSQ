# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import importlib
import sys

from fsq_agent.adapters.control_plane import ControlPlaneServer, ControlPlaneServerOptions, run_control_plane

_PRIVATE_MODULES = (
    "_cases", "_config", "_directory_picker", "_evidence", "_execution", "_provider_auth",
    "_readiness", "_replay", "_server", "_state", "_targets", "_workspace_files", "_workspaces",
)
for _module_name in _PRIVATE_MODULES:
    _module = importlib.import_module(f"fsq_agent.adapters.control_plane.{_module_name}")
    sys.modules[f"{__name__}.{_module_name}"] = _module
    setattr(sys.modules[__name__], _module_name, _module)

__all__ = ["ControlPlaneServer", "ControlPlaneServerOptions", "run_control_plane"]
