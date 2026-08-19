# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys

from fsq_agent.case_dsl import _loader as _canonical

sys.modules[__name__] = _canonical
