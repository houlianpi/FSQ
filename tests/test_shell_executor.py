# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent import tools


def test_tools_package_does_not_export_shell_executor() -> None:
    assert "ShellCommandExecutor" not in tools.__all__
    assert not hasattr(tools, "ShellCommandExecutor")


def test_tools_package_does_not_export_removed_tool_owners() -> None:
    removed_exports = {
        "AgentsToolFactory",
        "CapabilityRegistry",
        "CLIRunner",
        "ShellCommandExecutor",
        "ToolExecutor",
    }

    assert removed_exports.isdisjoint(tools.__all__)
