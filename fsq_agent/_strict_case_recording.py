# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Compatibility alias for the canonical execution recording module."""

import sys

from fsq_agent.execution import recording as _canonical

sys.modules[__name__] = _canonical
