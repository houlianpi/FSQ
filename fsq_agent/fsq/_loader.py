# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from fsq_agent.models import ConfigurationError, FsqCase, FsqCaseConfig

FSQ_CASE_SUFFIX = ".fsq.yaml"


def is_fsq_case_file(path: str | Path) -> bool:
    return Path(path).name.endswith(FSQ_CASE_SUFFIX)


def _resolve_discovered_case_path(path: str | Path, discovery_root: Path) -> Path:
    root = discovery_root.expanduser().resolve()
    resolved = Path(path).expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ConfigurationError(
            "Discovered case path must stay within the case directory.",
            context={"path": str(path)},
        ) from exc
    return resolved


class FsqCaseLoader:
    def load_case(self, path: str | Path) -> FsqCase:
        case_path = Path(path)
        if not is_fsq_case_file(case_path):
            raise ConfigurationError(
                f"FSQ case files must use the {FSQ_CASE_SUFFIX} suffix.",
                context={"path": str(case_path)},
            )
        try:
            docs = list(yaml.safe_load_all(case_path.read_text(encoding="utf-8")))
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError("Unable to read FSQ case file.", context={"path": str(case_path)}) from exc
        return self._build_case(case_path, docs)

    def load_cases(self, path: str | Path) -> list[FsqCase]:
        root = Path(path).expanduser().resolve()
        if root.is_file():
            return [self.load_case(root)]
        candidates = sorted(_resolve_discovered_case_path(candidate, root) for candidate in root.rglob(f"*{FSQ_CASE_SUFFIX}") if candidate.is_file() and is_fsq_case_file(candidate))
        return [self.load_case(candidate) for candidate in candidates]

    def _build_case(self, path: Path, docs: list[Any]) -> FsqCase:
        if len(docs) not in {1, 2}:
            raise ConfigurationError("Invalid FSQ case file.", context={"path": str(path), "reason": "expected one or two YAML documents"})
        config_doc = docs[0]
        commands_doc = docs[1] if len(docs) == 2 else []
        if not isinstance(config_doc, dict):
            raise ConfigurationError("Invalid FSQ case config.", context={"path": str(path)})
        if commands_doc is None:
            commands_doc = []
        if not isinstance(commands_doc, list):
            raise ConfigurationError("Invalid FSQ case commands.", context={"path": str(path)})
        try:
            config = FsqCaseConfig.model_validate(config_doc)
        except ValidationError as exc:
            raise ConfigurationError("Invalid FSQ case config.", context={"path": str(path)}) from exc
        if config.schema_version != "fsq.ai-test/v1":
            raise ConfigurationError(
                "Unsupported FSQ case schema version.",
                context={"path": str(path), "schemaVersion": config.schema_version},
            )
        return FsqCase(path=path, config=config, commands=commands_doc)
