from __future__ import annotations

import logging
from typing import Protocol, TextIO, cast

DEFAULT_LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"


class _HasRdrConsoleHandler(Protocol):
    _rdr_console_handler: bool


def enable_console_logging(
    level: str = "INFO",
    *,
    stream: TextIO | None = None,
    log_format: str = DEFAULT_LOG_FORMAT,
) -> None:
    """Enable console logging."""

    numeric_level = getattr(logging, str(level).upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    pkg_logger = logging.getLogger("recaptcha_domain_replicator")
    pkg_logger.setLevel(numeric_level)

    # Avoid adding multiple console handlers if called repeatedly.
    for h in pkg_logger.handlers:
        if getattr(h, "_rdr_console_handler", False):
            h.setLevel(numeric_level)
            return

    handler = (
        logging.StreamHandler(stream=stream) if stream is not None else logging.StreamHandler()
    )
    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(log_format))
    cast(_HasRdrConsoleHandler, handler)._rdr_console_handler = True

    pkg_logger.addHandler(handler)

    # Prevent double-logging if the root logger is also configured.
    pkg_logger.propagate = False
