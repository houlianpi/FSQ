# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

import json

import pytest

from fsq_agent.models import (
    AgentToolCall,
    LocalToolOutputSettings,
    RunEvent,
    ToolExecutionError,
)
from fsq_agent.tools import AgentToolAdapter, AgentToolExecutor, AgentToolRegistry, DefaultAgentToolProvider, FileOps


class _FakeFunctionTool:
    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.description = kwargs["description"]
        self.params_json_schema = kwargs["params_json_schema"]
        self.strict_json_schema = kwargs.get("strict_json_schema", True)
        self.on_invoke_tool = kwargs["on_invoke_tool"]


def _provider(tmp_path: Path, **kwargs) -> DefaultAgentToolProvider:
    return DefaultAgentToolProvider(FileOps(tmp_path), **kwargs)


def _registry(provider: DefaultAgentToolProvider) -> AgentToolRegistry:
    return AgentToolRegistry.from_providers([provider])


@pytest.mark.asyncio
async def test_agent_tool_file_ops_are_scoped(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    executor = AgentToolExecutor(_registry(provider))

    result = await executor.execute(
        AgentToolCall(tool_name="write_file", arguments={"path": "nested/out.txt", "content": "hello"})
    )

    assert result.status == "success"
    assert (tmp_path / "nested" / "out.txt").read_text(encoding="utf-8") == "hello"


def test_agent_tool_registry_lists_only_dynamic_tools(tmp_path: Path) -> None:
    names = {definition.name for definition in _registry(_provider(tmp_path)).list_tools()}

    assert names == {
        "read_file",
        "write_file",
        "search_artifact",
        "read_artifact_slice",
    }
    assert "get_runtime_secret" not in names
    assert "wait_ms" not in names
    assert "run_cli_tool" not in names
    assert "submit_visual_assertion" not in names
    assert "publish_progress" not in names
    assert "shell" not in names


def test_agent_tool_adapter_passes_tool_strictness(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    adapter = AgentToolAdapter(_registry(provider))

    tools = adapter.build_tools(_FakeFunctionTool)

    assert {tool.name: tool.strict_json_schema for tool in tools} == {
        "read_file": True,
        "write_file": True,
        "search_artifact": True,
        "read_artifact_slice": True,
    }


@pytest.mark.asyncio
async def test_direct_harness_execution_is_not_common_tool_owned(tmp_path: Path) -> None:
    executor = AgentToolExecutor(_registry(_provider(tmp_path)))

    with pytest.raises(ToolExecutionError, match="Unknown AgentTool"):
        await executor.execute(AgentToolCall(tool_name="tap_on", arguments={}))


@pytest.mark.asyncio
async def test_agent_tool_adapter_emits_agent_tool_origin_without_replay(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    events: list[RunEvent] = []
    adapter = AgentToolAdapter(_registry(_provider(tmp_path)))
    read_tool = next(
        tool for tool in adapter.build_tools(_FakeFunctionTool, run_id="run-1", task_id="task-1", event_sink=events.append)
        if tool.name == "read_file"
    )

    output = await read_tool.on_invoke_tool(None, json.dumps({"path": "file.txt"}))

    payload = json.loads(output)
    assert payload["result"]["output"]["output"] == "hello"
    assert events[-1].payload["tool_origin"] == "agent_tool"
    assert events[-1].payload["executor_kind"] == "agent_tool"
    assert "replay" not in events[-1].payload


@pytest.mark.asyncio
async def test_agent_tool_writes_full_output_artifact_and_returns_inline(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    provider = _provider(
        tmp_path,
        local_tool_output_settings=LocalToolOutputSettings(full_output_max_chars=1000),
        runs_dir=runs_dir,
        run_id="run-1",
    )
    adapter = AgentToolAdapter(_registry(provider), local_tool_output_settings=LocalToolOutputSettings(full_output_max_chars=1000))
    read_target = tmp_path / "file.txt"
    read_target.write_text("hello", encoding="utf-8")
    read_tool = next(tool for tool in adapter.build_tools(_FakeFunctionTool, run_id="run-1", task_id="task-1") if tool.name == "read_file")

    output = await read_tool.on_invoke_tool(None, json.dumps({"path": "file.txt"}))

    payload = json.loads(output)
    artifact_path = Path(payload["artifact"]["path"])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["model_output"] == "full"
    assert payload["result"]["output"]["output"] == "hello"
    assert artifact["metadata"] == {"path": "file.txt"}
    assert '"output": "hello"' in artifact["content"]


@pytest.mark.asyncio
async def test_agent_tool_large_output_uses_artifact_search_and_slice(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    settings = LocalToolOutputSettings(
        full_output_max_chars=1000,
        historical_preview_chars=20,
        model_response_max_chars=500,
    )
    provider = _provider(tmp_path, local_tool_output_settings=settings, runs_dir=runs_dir, run_id="run-1")
    adapter = AgentToolAdapter(_registry(provider), local_tool_output_settings=settings)
    (tmp_path / "large.txt").write_text("alpha beta gamma " * 100, encoding="utf-8")
    tools = adapter.build_tools(_FakeFunctionTool, run_id="run-1", task_id="task-1")
    read_tool = next(tool for tool in tools if tool.name == "read_file")
    search_tool = next(tool for tool in tools if tool.name == "search_artifact")
    slice_tool = next(tool for tool in tools if tool.name == "read_artifact_slice")

    output = await read_tool.on_invoke_tool(None, json.dumps({"path": "large.txt"}))
    payload = json.loads(output)

    assert payload["model_output"] == "artifact_reference"
    assert "result" not in payload
    search_output = await search_tool.on_invoke_tool(
        None,
        json.dumps({"artifact_path": payload["artifact"]["path"], "query": "gamma", "max_matches": 1, "context_chars": 20}),
    )
    search_payload = json.loads(search_output)
    assert search_payload["result"]["output"]["matches"][0]["offset"] >= 0

    slice_output = await slice_tool.on_invoke_tool(
        None,
        json.dumps(
            {
                "artifact_path": payload["artifact"]["path"],
                "offset": search_payload["result"]["output"]["matches"][0]["offset"],
                "length": 30,
            }
        ),
    )
    assert "gamma" in json.loads(slice_output)["result"]["output"]["content"]
