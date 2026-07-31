# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
from typing import Literal

from fsq_agent.models import ReportGenerationError


def resolve_report_path(
    runs_dir: Path,
    run_id: str,
    report_format: Literal["markdown", "json"] = "markdown",
) -> Path:
    suffix = "md" if report_format == "markdown" else "json"
    run_dir = Path(runs_dir) / run_id
    candidates = [run_dir / f"report.{suffix}", run_dir / f"core-report.{suffix}"]
    matches = [candidate for candidate in candidates if candidate.exists()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ReportGenerationError(
            "Report not found.",
            context={"run_id": run_id, "format": report_format, "runs_dir": str(runs_dir)},
        )
    raise ReportGenerationError(
        "Report lookup is ambiguous; both LLM and strict-core reports exist for this run id.",
        context={"run_id": run_id, "format": report_format, "matches": [str(path) for path in matches]},
    )
