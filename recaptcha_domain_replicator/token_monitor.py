from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from .constants import TOKEN_PLACEHOLDER_VALUES

logger = logging.getLogger(__name__)

_TOKEN_DETECTION_JS = """
return (() => {
  const norm = (v) => (typeof v === 'string' ? v.trim() : '');

  const display = document.getElementById('g-recaptcha-response-display');
  if (display) {
    const t = norm(display.innerText || display.textContent);
    if (t && t !== '[No token yet]' && t !== '[Token expired]') return t;
  }

  const textarea = document.querySelector('textarea[name="g-recaptcha-response"]');
  if (textarea) {
    const t = norm(textarea.value);
    if (t) return t;
  }

  // Fallback: try grecaptcha.getResponse(widgetId) if available.
  try {
    const isEnt = !!(window.isEnterprise);
    const gc = isEnt && window.grecaptcha && window.grecaptcha.enterprise
      ? window.grecaptcha.enterprise
      : window.grecaptcha;
    if (gc && typeof gc.getResponse === 'function' && window.recaptchaWidgetId != null) {
      const t = norm(gc.getResponse(window.recaptchaWidgetId));
      if (t) return t;
    }
  } catch (e) {}

  return null;
})();
"""


def get_token_from_page(tab: Any) -> str | None:
    """Extract the current token from the page DOM."""
    try:
        token = tab.run_js(_TOKEN_DETECTION_JS)
    except Exception:
        return None

    if token is None:
        return None

    token_str = str(token).strip()
    if not token_str or token_str in TOKEN_PLACEHOLDER_VALUES:
        return None

    return token_str


class TokenHandle:
    """Thread-safe handle for the latest captured reCAPTCHA token."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._closed: bool = False
        self._lock = threading.Lock()
        self._event = threading.Event()

    def set(self, token: str | None) -> None:
        if token is None:
            return

        token_str = str(token).strip()
        if not token_str or token_str in TOKEN_PLACEHOLDER_VALUES:
            return

        with self._lock:
            self._token = token_str
            self._event.set()

    def close(self) -> None:
        """Mark the handle as closed and unblock any waiters."""
        with self._lock:
            self._closed = True
            self._event.set()

    def get(self) -> str | None:
        with self._lock:
            return self._token

    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    def wait(self, timeout: float | None = None) -> str | None:
        """
        Block until a token is set, the handle is closed, or timeout.

        Notes:
          - timeout=None and timeout=0 both wait forever
        """
        if timeout == 0:
            timeout = None

        # If already resolved, return immediately.
        with self._lock:
            tok = self._token
            closed = self._closed
        if tok is not None:
            return tok
        if closed:
            return None

        # We wait in short slices so KeyboardInterrupt can be processed
        # by the main thread.
        deadline = None if timeout is None else (time.monotonic() + max(0.0, float(timeout)))
        slice_seconds = 0.2

        while True:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if remaining is not None and remaining <= 0:
                return None

            wait_for = slice_seconds if remaining is None else min(slice_seconds, remaining)
            self._event.wait(wait_for)

            with self._lock:
                tok = self._token
                closed = self._closed
            if tok is not None:
                return tok
            if closed:
                return None


def start_token_monitor(
    tab: Any,
    on_token: Callable[[str], None],
    max_checks: int | None = 600,
    stop_event: threading.Event | None = None,
    on_stop: Callable[[], None] | None = None,
    poll_interval: float = 1.0,
) -> threading.Thread:
    """
    Monitor the reCAPTCHA page for token updates and invoke a callback when found.

    Args:
        tab: Chromium tab instance.
        on_token (Callable[[str], None]): Callback invoked with the token string.
        max_checks (int | None): Number of checks to perform before stopping.
            - None or <= 0: run indefinitely (until token found / stop_event set).
        stop_event (threading.Event, optional): When set, stops monitoring early.
        poll_interval (float): Seconds to sleep between checks.

    Returns:
        threading.Thread: The background thread started for monitoring.
    """

    def _tab_is_closed(t: Any) -> bool:
        if t is None:
            return True

        try:
            # Accessing .url is used in the project as "is the tab still alive?".
            _ = t.url
            return False
        except Exception:
            return True

    def monitor():
        try:
            consecutive_failures = 0
            checks_done = 0
            check_limit = None if max_checks is None or max_checks <= 0 else int(max_checks)
            while True:
                if check_limit is not None and checks_done >= check_limit:
                    break
                checks_done += 1
                if stop_event is not None and stop_event.is_set():
                    break
                if _tab_is_closed(tab):
                    break
                try:
                    token = get_token_from_page(tab)
                    consecutive_failures = 0

                    if token is None:
                        time.sleep(poll_interval)
                        continue

                    on_token(token)
                    break

                except Exception:
                    consecutive_failures += 1
                    if _tab_is_closed(tab):
                        break
                    if consecutive_failures >= 50:
                        break
                    time.sleep(poll_interval)
        except Exception as exc:
            logger.debug("Token monitor crashed: %s", exc, exc_info=True)
        finally:
            if on_stop is not None:
                try:
                    on_stop()
                except Exception:
                    logger.debug("Token monitor on_stop callback crashed", exc_info=True)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    return thread
