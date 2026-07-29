# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
from pathlib import Path

from fsq_agent.models import FsqAgentError, SkillBundle, SkillConfig


logger = logging.getLogger(__name__)


class SkillLoader:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, configs: list[SkillConfig]) -> list[SkillBundle]:
        bundles: list[SkillBundle] = []
        for config in configs:
            bundle = self._load_one(config)
            if bundle is not None:
                bundles.append(bundle)
        return bundles

    def _load_one(self, config: SkillConfig) -> SkillBundle | None:
        if config.kind == "markdown":
            return self._load_markdown(config)
        if not config.content:
            if config.required:
                raise FsqAgentError("Required inline skill content is missing.", context={"skill": config.name})
            return self._skip_optional(config, "Optional inline skill has no content.")
        return SkillBundle(name=config.name, description=config.description, kind=config.kind, instructions=config.content or "")

    def _load_markdown(self, config: SkillConfig) -> SkillBundle | None:
        if config.content:
            return SkillBundle(name=config.name, description=config.description, kind=config.kind, instructions=config.content)
        if config.path is None:
            if config.required:
                raise FsqAgentError("Required skill path is missing.", context={"skill": config.name})
            return self._skip_optional(config, "Optional skill has no path or inline content.")
        path = config.path if config.path.is_absolute() else self.root / config.path
        if not path.exists():
            if config.required:
                raise FsqAgentError("Required skill file does not exist.", context={"skill": config.name, "path": str(path)})
            return self._skip_optional(config, "Optional skill file does not exist.", path)
        if path.is_dir():
            files = sorted(path.glob("*.md"))
            if not files:
                if config.required:
                    raise FsqAgentError("Required skill directory contains no Markdown files.", context={"skill": config.name, "path": str(path)})
                return self._skip_optional(config, "Optional skill directory contains no Markdown files.", path)
            try:
                instructions = "\n\n".join(file.read_text(encoding="utf-8") for file in files)
            except OSError as exc:
                if config.required:
                    raise FsqAgentError("Unable to read required skill directory.", context={"skill": config.name, "path": str(path)}) from exc
                return self._skip_optional(config, "Unable to read optional skill directory.", path)
            return SkillBundle(name=config.name, description=config.description, kind=config.kind, instructions=instructions, files=files)
        try:
            instructions = path.read_text(encoding="utf-8")
        except OSError as exc:
            if config.required:
                raise FsqAgentError("Unable to read required skill file.", context={"skill": config.name, "path": str(path)}) from exc
            return self._skip_optional(config, "Unable to read optional skill file.", path)
        return SkillBundle(
            name=config.name,
            description=config.description,
            kind=config.kind,
            instructions=instructions,
            files=[path],
        )

    def _skip_optional(self, config: SkillConfig, reason: str, path: Path | None = None) -> None:
        context = f" path={path}" if path is not None else ""
        logger.warning("Skipping optional skill %s: %s%s", config.name, reason, context)
        return None