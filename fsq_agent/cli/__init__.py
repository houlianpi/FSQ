# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import importlib
import sys

from fsq_agent.adapters.cli import main

_PRIVATE_MODULES = (
    "_android_devices", "_capability_bootstrap", "_case_lifecycle", "_core_execution", "_env_file",
    "_formatting", "_llm_setup", "_logging", "_main", "_strict_replay", "_task_loader",
)
for _module_name in _PRIVATE_MODULES:
    _module = importlib.import_module(f"fsq_agent.adapters.cli.{_module_name}")
    sys.modules[f"{__name__}.{_module_name}"] = _module
    setattr(sys.modules[__name__], _module_name, _module)

__all__ = ["main"]
