# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import re
from typing import Any

from pydantic import ValidationError

from fsq_agent.models import AgentFinalOutput

JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def parse_structured_output(output: str) -> dict[str, Any] | None:
    candidate = output.strip()
    block_match = JSON_BLOCK_PATTERN.search(candidate)
    if block_match:
        candidate = block_match.group(1)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def coerce_agent_final_output(output: Any) -> AgentFinalOutput | None:
    if isinstance(output, AgentFinalOutput):
        return output
    if isinstance(output, dict):
        candidate = output
    elif isinstance(output, str):
        candidate = parse_structured_output(output)
        if candidate is None:
            return None
    else:
        model_dump = getattr(output, "model_dump", None)
        if callable(model_dump):
            candidate = model_dump(mode="json")
        else:
            return None
    try:
        return AgentFinalOutput.model_validate(candidate)
    except ValidationError:
        return None


def serialize_agent_final_output(output: AgentFinalOutput | str) -> str:
    if isinstance(output, AgentFinalOutput):
        return output.model_dump_json()
    return output


def coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]
