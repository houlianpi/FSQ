# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fsq_agent.providers._azure_openai import ProviderClientConfig


class ModelProviderSession:
    def __init__(self, client_config: ProviderClientConfig) -> None:
        self.client_config = client_config
        self.provider = client_config.provider
        self.model = client_config.model
        self.metadata = dict(client_config.metadata)
        self._client: Any | None = None

    def create_agents_provider(self, *, openai_provider_type: Any, async_openai_type: Any) -> Any:
        client = self._ensure_client(async_openai_type)
        return openai_provider_type(openai_client=client, use_responses=True)

    async def invoke_responses(self, *, async_openai_type: Any | None = None, **kwargs: Any) -> Any:
        client = self._ensure_client(async_openai_type)
        payload = {"model": self.model, **kwargs}
        return await client.responses.create(**payload)

    def invoke_responses_sync(self, *, async_openai_type: Any | None = None, **kwargs: Any) -> Any:
        return _run_async_sync(self._invoke_responses_once(async_openai_type=async_openai_type, **kwargs))

    async def close(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        close = getattr(client, "close", None)
        if close is None:
            return
        result = close()
        if asyncio.iscoroutine(result):
            await result

    def close_sync(self) -> None:
        _run_async_sync(self.close())

    def _ensure_client(self, async_openai_type: Any | None) -> Any:
        if self._client is not None:
            return self._client
        self._client = self._new_client(async_openai_type)
        return self._client

    async def _invoke_responses_once(self, *, async_openai_type: Any | None = None, **kwargs: Any) -> Any:
        client = self._new_client(async_openai_type)
        payload = {"model": self.model, **kwargs}
        try:
            return await client.responses.create(**payload)
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result

    def _new_client(self, async_openai_type: Any | None) -> Any:
        if async_openai_type is None:
            from openai import AsyncOpenAI

            async_openai_type = AsyncOpenAI
        return async_openai_type(
            api_key=self.client_config.api_key,
            base_url=self.client_config.base_url,
            default_headers=self.client_config.default_headers or None,
        )


def _run_async_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()
