# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import importlib
import sys

from fsq_agent.adapters.control_plane.playground import PlaygroundServer, PlaygroundServerOptions, run_playground

_PRIVATE_MODULES = ("_android", "_execution", "_recording", "_server", "_state", "_yaml_lifecycle")
for _module_name in _PRIVATE_MODULES:
    _module = importlib.import_module(f"fsq_agent.adapters.control_plane.playground.{_module_name}")
    sys.modules[f"{__name__}.{_module_name}"] = _module
    setattr(sys.modules[__name__], _module_name, _module)

__all__ = ["PlaygroundServer", "PlaygroundServerOptions", "run_playground"]
