# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys

from fsq_agent.environments import _service as _canonical

sys.modules[__name__] = _canonical
