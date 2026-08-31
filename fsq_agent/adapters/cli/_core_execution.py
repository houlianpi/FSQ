# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Compatibility alias for deterministic execution services."""

import sys

from fsq_agent.execution import deterministic as _canonical

sys.modules[__name__] = _canonical
