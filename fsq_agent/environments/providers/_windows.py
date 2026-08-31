# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent.environments.providers._runtime import RuntimeProvider

WINDOWS_RUNTIME_PROVIDER = RuntimeProvider(platform="windows", module="pywinauto", required_host="Windows")
