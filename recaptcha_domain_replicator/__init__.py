"""
ReCAPTCHA Domain Replicator.

This package spins up a local server hosting a replica page that renders a ReCAPTCHA widget,
then opens that replica in a Chromium instance so developers can solve
and retrieve the token.
"""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from .logging_utils import enable_console_logging as enable_console_logging

try:
    __version__ = version("recaptcha-domain-replicator")
except PackageNotFoundError:
    # Package is not installed, or running from source
    __version__ = "0.0.0.dev0"

logger = logging.getLogger(__name__)
# Add a null handler to prevent logging errors
logger.addHandler(logging.NullHandler())

if TYPE_CHECKING:
    from .captcha_replicator import RecaptchaDomainReplicator as RecaptchaDomainReplicator

__all__ = ["RecaptchaDomainReplicator", "enable_console_logging"]


def __getattr__(name: str):
    if name == "RecaptchaDomainReplicator":
        from .captcha_replicator import RecaptchaDomainReplicator

        return RecaptchaDomainReplicator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
