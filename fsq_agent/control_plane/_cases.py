# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fsq_agent._capability_bootstrap import build_capability_registry, provider_required_capability_names, steps_require_provider
from fsq_agent._strict_lifecycle import collect_strict_lifecycle_cases
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter

from ._evidence import safe_exception_message

if TYPE_CHECKING:
    from fsq_agent.config import Settings

CASE_LIMIT = 500


def build_strict_registry_context(platform: str) -> tuple[Any, Any, frozenset[str]]:
    registry = build_capability_registry(platform=platform, include_ai_assertion=True)
    snapshot = registry.snapshot()
    return registry, snapshot, provider_required_capability_names(platform)


def discover_cases(settings: Settings, *, limit: int = CASE_LIMIT) -> dict[str, Any]:
    root = settings.cases.dir.resolve()
    if not root.is_dir():
        return {"platform": settings.harness.platform, "cases": [], "truncated": False}
    candidates = sorted((path for path in root.rglob("*.yaml") if path.is_file()), key=lambda path: path.relative_to(root).as_posix().casefold())
    truncated = len(candidates) > limit
    _, registry_snapshot, provider_required = build_strict_registry_context(settings.harness.platform)
    entries = [_case_summary(path, root, settings, registry_snapshot, provider_required) for path in candidates[:limit]]
    return {"platform": settings.harness.platform, "cases": entries, "truncated": truncated}


def resolve_case(settings: Settings, path_text: str) -> Path:
    if not isinstance(path_text, str) or not path_text.strip():
        raise ValueError("casePath is required.")
    requested = Path(path_text.strip())
    if requested.is_absolute():
        raise ValueError("casePath must be relative to the configured cases directory.")
    root = settings.cases.dir.resolve()
    resolved = (root / requested).resolve()
    if not _is_relative_to(resolved, root) or resolved.suffix != ".yaml":
        raise ValueError("casePath must identify a contained .yaml case.")
    if not resolved.is_file():
        raise ValueError("The selected strict case no longer exists.")
    return resolved


def _case_summary(path: Path, root: Path, settings: Settings, registry_snapshot: Any, provider_required: frozenset[str]) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    try:
        case = FsqCaseLoader().load_case(path)
        lifecycle_cases = collect_strict_lifecycle_cases(case_path=path, case=case, settings=settings)
        _require_lifecycle_containment(lifecycle_cases, root)
        steps_by_case = [FsqExecutableStepAdapter(registry_snapshot=registry_snapshot).to_executable_steps(lifecycle_case) for _, lifecycle_case in lifecycle_cases]
        steps = steps_by_case[0]
        diagnostics: list[str] = []
        mismatched_platforms = sorted({lifecycle_case.config.platform for _, lifecycle_case in lifecycle_cases if lifecycle_case.config.platform != settings.harness.platform})
        selectable = not mismatched_platforms
        if not selectable:
            diagnostics.append(f"Case lifecycle platform does not match {settings.harness.platform}: {', '.join(mismatched_platforms)}.")
        status = "validated" if selectable else "invalid"
        return {
            "path": relative,
            "id": case.id,
            "name": case.config.name,
            "platform": case.config.platform,
            "commandCount": len(steps),
            "requiresAiAssertion": any(steps_require_provider(case_steps, registry_snapshot, provider_required) for case_steps in steps_by_case),
            "validationStatus": status,
            "selectable": selectable,
            "diagnostics": diagnostics,
        }
    except Exception as exc:  # noqa: BLE001 - one malformed case must not hide other cases.
        return {
            "path": relative,
            "id": path.name.removesuffix(".yaml"),
            "name": path.name,
            "platform": None,
            "commandCount": 0,
            "requiresAiAssertion": False,
            "validationStatus": "invalid",
            "selectable": False,
            "diagnostics": [safe_exception_message(exc, settings=settings)],
        }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _require_lifecycle_containment(lifecycle_cases: list[tuple[Path, Any]], root: Path) -> None:
    if any(not _is_relative_to(lifecycle_path.resolve(), root) for lifecycle_path, _ in lifecycle_cases):
        raise ValueError("Case lifecycle dependency escapes the configured cases directory.")


__all__ = ["CASE_LIMIT", "discover_cases", "resolve_case"]
