# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging


class CLILogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if getattr(record, "fsq_raw_message", False):
            return record.getMessage()
        return super().format(record)


def configure_cli_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger("fsq_agent")
    logger.setLevel(level)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(CLILogFormatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    logger.propagate = False