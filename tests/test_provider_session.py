# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
from typing import Any

from fsq_agent.providers import ModelProviderSession
from fsq_agent.providers._azure_openai import ProviderClientConfig


class _LoopBoundResponses:
    def __init__(self, client: "_LoopBoundAsyncOpenAI") -> None:
        self.client = client

    async def create(self, **kwargs: Any) -> dict[str, Any]:
        self.client.create_loop = asyncio.get_running_loop()
        self.client.payloads.append(kwargs)
        return {"output_text": '{"passed": true}', "usage": {"input_tokens": 1}}


class _LoopBoundAsyncOpenAI:
    instances: list["_LoopBoundAsyncOpenAI"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.payloads: list[dict[str, Any]] = []
        self.create_loop: asyncio.AbstractEventLoop | None = None
        self.closed = False
        self.responses = _LoopBoundResponses(self)
        self.instances.append(self)

    async def close(self) -> None:
        if asyncio.get_running_loop() is not self.create_loop:
            raise RuntimeError("Event loop is closed")
        self.closed = True


def _client_config() -> ProviderClientConfig:
    return ProviderClientConfig(
        provider="test",
        model="test-model",
        api_key="test-key",
        base_url="https://example.test/openai/v1/",
    )


async def test_invoke_responses_sync_from_running_loop_does_not_reuse_closed_loop() -> None:
    _LoopBoundAsyncOpenAI.instances = []
    session = ModelProviderSession(_client_config())

    response = session.invoke_responses_sync(
        async_openai_type=_LoopBoundAsyncOpenAI,
        input=[{"role": "user", "content": "check"}],
    )
    session.close_sync()

    assert response["output_text"] == '{"passed": true}'
    assert len(_LoopBoundAsyncOpenAI.instances) == 1
    client = _LoopBoundAsyncOpenAI.instances[0]
    assert client.closed is True
    assert client.payloads == [
        {"model": "test-model", "input": [{"role": "user", "content": "check"}]}
    ]


async def test_invoke_responses_async_reuses_session_client_until_close() -> None:
    _LoopBoundAsyncOpenAI.instances = []
    session = ModelProviderSession(_client_config())

    response = await session.invoke_responses(
        async_openai_type=_LoopBoundAsyncOpenAI,
        input=[{"role": "user", "content": "check"}],
    )

    assert response["output_text"] == '{"passed": true}'
    assert len(_LoopBoundAsyncOpenAI.instances) == 1
    client = _LoopBoundAsyncOpenAI.instances[0]
    assert client.closed is False

    await session.close()

    assert client.closed is True