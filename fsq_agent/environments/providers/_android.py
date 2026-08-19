# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent.environments.providers._runtime import RuntimeProvider

ANDROID_RUNTIME_PROVIDER = RuntimeProvider(platform="android", module="uiautomator2", extra="android")
