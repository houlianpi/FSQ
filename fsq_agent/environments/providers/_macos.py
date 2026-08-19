# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent.environments.providers._runtime import RuntimeProvider

MACOS_RUNTIME_PROVIDER = RuntimeProvider(platform="macos", module="appium", extra="macos", required_host="Darwin")
