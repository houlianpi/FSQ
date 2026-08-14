# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import re
import secrets
from datetime import datetime


def new_run_id(stem: str) -> str:
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip("-._") or "run"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    return f"{safe_stem}-{timestamp}-{secrets.token_hex(4)}"
