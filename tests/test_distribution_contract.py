# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import yaml

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
    assert project["project"]["license"] == "MIT"
    assert project["project"]["authors"] == [{"name": "Microsoft Corporation"}]
    assert project["project"]["urls"] == {
        "Documentation": "https://github.com/microsoft/FSQ#readme",
        "Issues": "https://github.com/microsoft/FSQ/issues",
        "Repository": "https://github.com/microsoft/FSQ",
    }
    classifiers = set(project["project"]["classifiers"])
    assert "Operating System :: OS Independent" in classifiers
    assert "Intended Audience :: Developers" in classifiers
    for version in ("3.11", "3.12", "3.13"):
        assert f"Programming Language :: Python :: {version}" in classifiers


def test_release_workflow_is_manual_safe_and_uses_oidc_trusted_publishing() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "release.yml"
    raw = workflow_path.read_text(encoding="utf-8")
    workflow: dict[str, Any] = yaml.safe_load(raw)
    trigger = workflow[True]  # PyYAML 1.1 parses the unquoted GitHub Actions `on` key as true.
    dispatch = trigger["workflow_dispatch"]
    assert set(trigger) == {"workflow_dispatch"}
    assert dispatch["inputs"]["publish"] == {
        "description": "Publish the verified distributions to PyPI",
        "required": True,
        "type": "boolean",
        "default": False,
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"verify", "publish"}
    publish = workflow["jobs"]["publish"]
    assert publish["if"] == "${{ inputs.publish }}"
    assert publish["needs"] == "verify"
    assert publish["environment"] == "pypi"
    assert publish["permissions"] == {"contents": "read", "id-token": "write"}
    assert any(step.get("uses", "").startswith("actions/download-artifact@") for step in publish["steps"])
    assert publish["steps"][-1]["run"] == "uv publish --trusted-publishing always dist/*"
    verify = workflow["jobs"]["verify"]
    assert any(step.get("uses", "").startswith("actions/upload-artifact@") for step in verify["steps"])
    commands = "\n".join(str(step.get("run", "")) for step in verify["steps"])
    for command in (
        "ruff check .",
        "ruff format --check .",
        "python -m pytest",
        "npm run typecheck",
        "npm test",
        "npm run build",
        "uv build",
        "twine check dist/*",
        "tests/test_distribution_contract.py",
        '"$RUNNER_TEMP/fsq-release-smoke/bin/fsq" --help',
        '"$RUNNER_TEMP/fsq-release-smoke/bin/fsq-agent" --help',
    ):
        assert command in commands
    assert "PYPI_API_TOKEN" not in raw
    assert "password:" not in raw


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


def test_ci_verifies_all_runtime_package_resources() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    for resource in (
        "fsq_agent/resources/config.android.yaml",
        "fsq_agent/resources/config.web.yaml",
        "fsq_agent/resources/config.windows.yaml",
        "fsq_agent/resources/config.macos.yaml",
        "fsq_agent/resources/knowledge/skills/android-harness.md",
        "fsq_agent/resources/knowledge/skills/web-harness.md",
        "fsq_agent/resources/knowledge/skills/windows-harness.md",
        "fsq_agent/resources/knowledge/skills/macos-harness.md",
        "fsq_agent/agent/templates/agent_instructions.j2",
        "fsq_agent/agent/templates/task_input.j2",
    ):
        assert resource in workflow


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


def test_release_acceptance_checklist_uses_current_public_commands() -> None:
    checklist = (ROOT / "docs" / "release-acceptance-checklist.md").read_text(encoding="utf-8")

    for command in (
        "pip install fsq-agent",
        "fsq init",
        "fsq doctor",
        "fsq providers configure",
        "fsq providers status",
        "fsq case create",
        "fsq case test",
        "fsq runs list",
        "fsq runs show",
        "fsq runs logs",
        "fsq ui",
    ):
        assert command in checklist
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
        assert obsolete not in checklist
