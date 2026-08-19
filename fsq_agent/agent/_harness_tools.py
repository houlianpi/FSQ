# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys

from fsq_agent.adapters.coding_agent import _harness_tools as _canonical

sys.modules[__name__] = _canonical
