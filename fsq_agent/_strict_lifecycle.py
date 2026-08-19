# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Compatibility alias for the canonical execution lifecycle module."""

import sys

from fsq_agent.execution import lifecycle as _canonical

sys.modules[__name__] = _canonical
