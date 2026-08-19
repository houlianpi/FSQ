# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys

from fsq_agent.adapters.coding_agent import _openai_runtime as _canonical

sys.modules[__name__] = _canonical
