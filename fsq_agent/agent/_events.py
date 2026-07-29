# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import inspect

from fsq_agent.models import RunEvent, RunEventSink
from fsq_agent.observation import ExecutionLogger


class RunEventEmitter:
    def __init__(self, logger: ExecutionLogger | None = None, sink: RunEventSink | None = None) -> None:
        self.logger = logger
        self.sink = sink
        self.sequence = 0

    async def emit(self, event: RunEvent) -> None:
        self.sequence += 1
        sequenced = event.model_copy(update={"sequence": self.sequence})
        if self.logger:
            self.logger.write_run_event(sequenced)
        if self.sink:
            result = self.sink(sequenced)
            if inspect.isawaitable(result):
                await result
