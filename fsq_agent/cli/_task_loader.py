# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

from fsq_agent.fsq import is_fsq_case_file
from fsq_agent.models import ConfigurationError


def _resolve_task_path(path: str | Path, cases_dir: Path | None = None) -> Path:
    task_path = Path(path).expanduser()
    if task_path.is_absolute():
        return task_path.resolve()
    if cases_dir is not None:
        candidate = (cases_dir / task_path).resolve()
        if candidate.exists():
            return candidate
    return task_path.resolve()


def resolve_case_yaml_path(path: str | Path, cases_dir: Path | None = None) -> Path:
    case_path = _resolve_task_path(path, cases_dir)
    if not case_path.exists() or not case_path.is_file():
        raise ConfigurationError("Case YAML file not found.", context={"path": str(case_path)})
    if not is_fsq_case_file(case_path):
        raise ConfigurationError("Strict FSQ case files must use the .codex.yaml suffix.", context={"path": str(case_path)})
    return case_path


def discover_case_yaml_paths(path: str | Path, cases_dir: Path | None = None) -> list[Path]:
    root = _resolve_task_path(path, cases_dir)
    if root.is_file():
        return [resolve_case_yaml_path(root, cases_dir)]
    if not root.exists() or not root.is_dir():
        raise ConfigurationError("Case directory not found.", context={"path": str(root)})
    candidates = sorted(candidate.resolve() for candidate in root.rglob("*.codex.yaml") if candidate.is_file())
    if not candidates:
        raise ConfigurationError("No .codex.yaml case files found.", context={"path": str(root)})
    return candidates


def read_raw_text_file(path: str | Path, cases_dir: Path | None = None) -> tuple[Path, str]:
    source_path = _resolve_task_path(path, cases_dir)
    if not source_path.exists() or not source_path.is_file():
        raise ConfigurationError("Input file not found.", context={"path": str(source_path)})
    try:
        return source_path, source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigurationError("Input file must be valid UTF-8 text.", context={"path": str(source_path)}) from exc
    except OSError as exc:
        raise ConfigurationError("Unable to read input file.", context={"path": str(source_path)}) from exc