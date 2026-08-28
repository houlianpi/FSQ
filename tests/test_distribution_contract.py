# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_default_distribution_contract() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    dependencies = project["project"]["dependencies"]
    for name in ("uiautomator2", "playwright", "pywinauto", "pillow", "Appium-Python-Client"):
        assert any(dependency.startswith(f"{name}==") for dependency in dependencies)
    assert set(project["project"]["optional-dependencies"]) == {"dev"}
    assert project["project"]["scripts"] == {
        "fsq": "fsq_agent.adapters.cli:main",
        "fsq-agent": "fsq_agent.adapters.cli:main",
    }


def test_distribution_includes_both_frontend_asset_trees() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected = {
        "fsq_agent/adapters/control_plane/static",
        "fsq_agent/adapters/control_plane/playground/static",
    }

    for target in ("wheel", "sdist"):
        force_include = project["tool"]["hatch"]["build"]["targets"][target]["force-include"]
        assert expected <= set(force_include)
        assert all(force_include[path] == path for path in expected)


def test_readme_uses_current_installation_and_cli_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "pip install fsq-agent" in readme
    for command in ("fsq init", "fsq doctor", "fsq providers", "fsq case create", "fsq case test", "fsq runs", "fsq ui"):
        assert command in readme
    for obsolete in (
        "fsq-agent run",
        "run --strict",
        "fsq-agent control-plane",
        "fsq-agent report",
        "fsq-agent playground",
        "init --name",
        "fsq-agent[web]",
        "fsq-agent[android]",
        "fsq-agent[windows]",
        "fsq-agent[macos]",
    ):
        assert obsolete not in readme
