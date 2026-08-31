# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys

from fsq_agent.harnesses import _factory as _canonical

sys.modules[__name__] = _canonical
