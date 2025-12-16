"""
reCAPTCHA domain replicator.

This module provides a class for creating and displaying a replicated reCAPTCHA challenge
locally, served via a local Flask server and opened in a Chromium.
"""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import signal
import tempfile
import threading
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, urlunparse

# Get Chromium type from DrissionPage for type checking
if TYPE_CHECKING:
    from DrissionPage import Chromium

from . import hosts_manager
from .browser_config import create_browser_options, mapped_hosts_for_domain
from .constants import MAX_PORT, MIN_PORT, TOKEN_PLACEHOLDER_VALUES
from .html_builder import CaptchaHtml
from .html_builder import create_captcha_html as build_captcha_html
from .proxy_auth_extension import create_proxy_auth_extension
from .proxy_utils import ProxyConfig, format_proxy_redacted, parse_proxy_url
from .server_manager import CaptchaServer
from .token_monitor import TokenHandle, start_token_monitor

logger = logging.getLogger(__name__)

# Track all replicator instances so we can clean them on Ctrl+C
_ACTIVE_REPLICATORS: set[RecaptchaDomainReplicator] = set()
_SHUTDOWN_HANDLER_LOCK = threading.Lock()
_SHUTDOWN_HANDLERS_INSTALLED = False
_SIGINT_CLEANUP_IN_PROGRESS = False


def _cleanup_all_replicators(reason: str | None = None) -> None:
    reps = list(_ACTIVE_REPLICATORS)
    if not reps:
        return

    for rep in reps:
        try:
            rep.close()
        except Exception:
            with suppress(Exception):
                logger.debug(
                    "Error while cleaning up replicator (%s)",
                    reason or "shutdown",
                    exc_info=True,
                )


def _sigint_handler(signum, frame) -> None:
    """
    Ctrl+C handler. We do cleanup and then terminate the process.
    """
    global _SIGINT_CLEANUP_IN_PROGRESS

    if _SIGINT_CLEANUP_IN_PROGRESS:
        os._exit(130)

    _SIGINT_CLEANUP_IN_PROGRESS = True
    try:
        _cleanup_all_replicators(reason="SIGINT")
    finally:
        raise SystemExit(130)


def _install_shutdown_handlers() -> None:
    """
    Install atexit + SIGINT cleanup handlers once per process.
    """
    global _SHUTDOWN_HANDLERS_INSTALLED

    with _SHUTDOWN_HANDLER_LOCK:
        if _SHUTDOWN_HANDLERS_INSTALLED:
            return

        _SHUTDOWN_HANDLERS_INSTALLED = True

        with suppress(Exception):
            atexit.register(_cleanup_all_replicators, reason="atexit")

        # Only the main thread should can set signal handlers.
        if threading.current_thread() is not threading.main_thread():
            return

        try:
            signal.signal(signal.SIGINT, _sigint_handler)
        except Exception:
            with suppress(Exception):
                logger.debug("Could not install SIGINT handler", exc_info=True)


def _register_replicator(rep: RecaptchaDomainReplicator) -> None:
    _ACTIVE_REPLICATORS.add(rep)
    _install_shutdown_handlers()


def _unregister_replicator(rep: RecaptchaDomainReplicator) -> None:
    _ACTIVE_REPLICATORS.discard(rep)


class RecaptchaDomainReplicator:
    """
    Create and display a replicated reCAPTCHA challenge locally.

    The replicated captcha is served from a local Flask server and opened in a Chromium
    instance. Optionally, the original website domain can be
    spoofed (via hosts file or browser host-resolver-rules) to bypass domain restrictions.
    """

    def __init__(
        self,
        download_dir: str = "tmp",
        server_port: int = 8080,
        persist_html: bool = False,
        proxy: str | None = None,
        browser_path: str | None = None,
    ):
        # Validate server_port
        if not isinstance(server_port, int) or not (MIN_PORT <= server_port <= MAX_PORT):
            raise ValueError(f"server_port must be an integer between {MIN_PORT} and {MAX_PORT}")

        self.download_dir = download_dir
        self.server_port = server_port
        self.persist_html = bool(persist_html)

        self.server = CaptchaServer(download_dir=self.download_dir, server_port=self.server_port)

        self._proxy: ProxyConfig | None = parse_proxy_url(proxy) if proxy is not None else None
        self._proxy_extension_dir: str | None = None
        self._browser_path = browser_path

        self.browser: Any = None
        self.tab: Any = None
        self._owns_browser: bool = False
        self.last_token: str | None = None
        self.last_html_path: str | None = None
        self.last_html_filename: str | None = None
        self.last_html_content: str | None = None
        self.token_handle: TokenHandle | None = None
        self.token_monitor_thread: threading.Thread | None = None
        self._token_monitor_stop_event: threading.Event | None = None

        # When we fall back to hosts-file bypass (external browser/tab), keep track so the
        # caller can clean it up later via stop_http_server().
        self._hosts_bypass_domain: str | None = None
        self._hosts_bypass_active: bool = False

        if self.persist_html:
            os.makedirs(self.download_dir, exist_ok=True)

        # Ensure this instance is cleaned up when exiting.
        _register_replicator(self)

    def _cleanup_proxy_extension(self) -> None:
        if not self._proxy_extension_dir:
            return
        try:
            shutil.rmtree(self._proxy_extension_dir, ignore_errors=True)
        finally:
            self._proxy_extension_dir = None

    @staticmethod
    def _prune_missing_chromium_extensions(co: Any) -> None:
        """
        This helper removes *missing* extension paths while leaving existing ones intact.
        """
        try:
            existing = list(getattr(co, "extensions", []) or [])
        except Exception:
            return

        if not existing:
            return

        keep: list[str] = []
        missing: list[str] = []

        # De-duplicate while preserving order.
        seen: set[str] = set()
        for ext in existing:
            ext_str = str(ext or "").strip()
            if not ext_str or ext_str in seen:
                continue
            seen.add(ext_str)
            if Path(ext_str).exists():
                keep.append(ext_str)
            else:
                missing.append(ext_str)

        if not missing:
            return

        try:
            if hasattr(co, "remove_extensions"):
                co.remove_extensions()
                for ext_str in keep:
                    co.add_extension(ext_str)
            else:
                co.extensions = keep
        except Exception:
            logger.exception("Failed to prune missing extension path(s) from DrissionPage options")
            return

        logger.warning(
            "Removed %d missing extension path(s) from DrissionPage options: %s",
            len(missing),
            ", ".join(missing),
        )

    def _build_proxy_bypass_list(
        self, *, original_domain: str | None = None, bypass_domain_check: bool = False
    ) -> list[str]:
        bypass_list: list[str] = ["localhost", "127.0.0.1", "<local>"]

        if bypass_domain_check and original_domain:
            bypass_list.extend(mapped_hosts_for_domain(original_domain))

        # De-duplicate while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for host in bypass_list:
            if host not in seen:
                seen.add(host)
                unique.append(host)
        return unique

    # Runs when the class (replicator) is instantiated on a With statement
    def __enter__(self) -> RecaptchaDomainReplicator:
        return self

    # Runs when leaving a With statement, by error or normal exit
    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _normalize_google_demo_url(website_url: str) -> str:
        """
        Normalize Google's demo URL to avoid mapping www.google.com to localhost.
        We rewrite www.google.com to google.com
        """
        if not website_url:
            return website_url

        try:
            parsed = urlparse(website_url)
        except Exception:
            return website_url

        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").rstrip("/")

        if host == "www.google.com" and path == "/recaptcha/api2/demo":
            normalized = urlunparse(
                parsed._replace(netloc="google.com", path="/recaptcha/api2/demo")
            )
            if normalized != website_url:
                msg = (
                    f"website_url '{website_url}' was normalized to '{normalized}' "
                    "to avoid redirecting www.google.com to localhost "
                    "(which breaks loading reCAPTCHA scripts)."
                )
                logger.warning("%s", msg)
            return normalized

        return website_url

    def create_captcha_html(
        self,
        website_key: str,
        website_url: str,
        is_invisible: bool = False,
        data_s_value: str | None = None,
        api_domain: str = "google.com",
        is_enterprise: bool = False,
        action: str | None = None,
    ) -> CaptchaHtml:
        return build_captcha_html(
            download_dir=self.download_dir,
            website_key=website_key,
            website_url=website_url,
            is_invisible=is_invisible,
            data_s_value=data_s_value,
            api_domain=api_domain,
            is_enterprise=is_enterprise,
            action=action,
            persist_html=self.persist_html,
        )

    def start_http_server(self, domain: str | None = None, use_ssl: bool = True) -> int:
        port = self.server.start(domain=domain, use_ssl=use_ssl)
        self.server_port = self.server.port
        return port

    def stop_http_server(self) -> None:
        self.server.stop()

        # Clean up hosts-file bypass if it was used
        if self._hosts_bypass_active and self._hosts_bypass_domain:
            try:
                logger.info("Removing domain '%s' from hosts file...", self._hosts_bypass_domain)
                hosts_manager.remove_from_hosts(self._hosts_bypass_domain)
            except Exception:
                logger.exception("Failed to remove '%s' from hosts file", self._hosts_bypass_domain)
            self._hosts_bypass_active = False
            self._hosts_bypass_domain = None

    def replicate_captcha(
        self,
        website_key: str,
        website_url: str,
        browser: Any = None,
        tab: Any = None,
        is_invisible: bool = False,
        data_s_value: str | None = None,
        is_enterprise: bool = False,
        api_domain: str = "google.com",
        user_agent: str | None = None,
        cookies: dict[str, Any] | None = None,
        observation_time: int = 0,
        bypass_domain_check: bool = False,
        use_ssl: bool = True,
        action: str | None = None,
    ) -> tuple[Chromium | None, TokenHandle | None]:
        """
        Create and display a replicated reCAPTCHA challenge.

        Returns:
            tuple: (browser, token_handle)

        Notes:
            - This method returns immediately after opening the replicated captcha page.
            - The token will be updated asynchronously and is accessible via:
                - token_handle.get() / token_handle.wait(...)
                - replicator.get_last_token()
        """

        # Validate required inputs
        if not website_key or not isinstance(website_key, str):
            raise ValueError("website_key must be a non-empty string")
        website_key = website_key.strip()
        if not website_key:
            raise ValueError("website_key must be a non-empty string")

        if not website_url or not isinstance(website_url, str):
            raise ValueError("website_url must be a non-empty string")
        website_url = website_url.strip()
        if not website_url:
            raise ValueError("website_url must be a non-empty string")
        if not website_url.startswith(("http://", "https://")):
            raise ValueError("website_url must start with http:// or https://")

        domain_added = False
        website_url = self._normalize_google_demo_url(website_url)
        parsed_url = urlparse(website_url) if website_url else None
        original_domain = parsed_url.hostname if parsed_url else None

        try:
            self.last_token = None
            self.last_html_path = None
            self.last_html_filename = None
            self.last_html_content = None
            self.stop_token_monitor()
            self.token_handle = TokenHandle()
            self._token_monitor_stop_event = threading.Event()

            # If bypass is enabled and an external browser/tab is provided, fall back to hosts file.
            if bypass_domain_check and original_domain and (browser is not None or tab is not None):
                logger.info(
                    "External browser provided. Attempting hosts file bypass for '%s'...",
                    original_domain,
                )
                logger.info(
                    "Note: For VPN compatibility, let the replicator create its own "
                    "browser instance."
                )

                if hosts_manager.is_admin():
                    domain_added = hosts_manager.add_to_hosts(original_domain)
                    if domain_added:
                        logger.info(
                            "Domain '%s' added to hosts file successfully.", original_domain
                        )
                        self._hosts_bypass_domain = original_domain
                        self._hosts_bypass_active = True
                    else:
                        logger.warning("Failed to add domain '%s' to hosts file.", original_domain)
                else:
                    logger.warning("No admin privileges - hosts file bypass skipped.")
                    logger.info(
                        "For VPN compatible bypass, don't pass a browser and let the replicator "
                        "create one."
                    )

            html_page = self.create_captcha_html(
                website_key=website_key,
                website_url=website_url,
                is_invisible=is_invisible,
                data_s_value=data_s_value,
                api_domain=api_domain,
                is_enterprise=is_enterprise,
                action=action,
            )
            self.last_html_path = html_page.path
            self.last_html_filename = html_page.filename
            self.last_html_content = html_page.content
            self.server.set_in_memory_html(html_page.filename, html_page.content)

            server_port = self.start_http_server(domain=original_domain, use_ssl=use_ssl)
            if not server_port:
                logger.error("Failed to start HTTP server")
                return None, None

            file_basename = html_page.filename

            use_domain_bypass = bool(bypass_domain_check and original_domain)
            protocol = "https" if self.server.use_ssl else "http"

            if use_domain_bypass:
                original_path = parsed_url.path if parsed_url else ""
                original_query = parsed_url.query if parsed_url else ""
                original_fragment = parsed_url.fragment if parsed_url else ""

                if self.server.port_forwarding_enabled:
                    local_file_url = f"{protocol}://{original_domain}{original_path}"
                else:
                    local_file_url = (
                        f"{protocol}://{original_domain}:{self.server_port}{original_path}"
                    )

                if original_query:
                    local_file_url += f"?{original_query}"
                if original_fragment:
                    local_file_url += f"#{original_fragment}"

                logger.info("Using spoofed domain URL: %s", local_file_url)
            else:
                local_file_url = f"{protocol}://localhost:{self.server_port}/{file_basename}"
                logger.info("Using localhost URL: %s", local_file_url)

            self._get_or_create_browser(
                browser=browser,
                tab=tab,
                bypass_domain_check=bypass_domain_check,
                original_domain=original_domain,
                use_ssl=self.server.use_ssl,
            )

            # Navigate to the replica page.
            self._handle_captcha_interaction(
                tab=self.tab,
                local_file_url=local_file_url,
                user_agent=user_agent,
                cookies=cookies,
                # observation_time=observation_time,
            )

            # Start token monitoring, asynchronously, and return browser immediately
            token_handle_ref = self.token_handle

            def _on_token(tok):
                self._set_token(tok)
                if token_handle_ref is not None:
                    token_handle_ref.set(tok)

            def _on_monitor_stop() -> None:
                if token_handle_ref is not None:
                    token_handle_ref.close()

            # observation_time == 0 means run until solved/closed, so monitor indefinitely.
            poll_interval = 1.0
            try:
                obs_seconds = float(observation_time)
            except Exception:
                obs_seconds = 0.0
            max_checks = 0 if obs_seconds <= 0 else int(obs_seconds / poll_interval) + 1

            self.token_monitor_thread = start_token_monitor(
                self.tab,
                on_token=_on_token,
                max_checks=max_checks,
                stop_event=self._token_monitor_stop_event,
                on_stop=_on_monitor_stop,
                poll_interval=poll_interval,
            )

            browser_to_return = self.browser if self.browser is not None else browser
            if browser_to_return is None and self.tab is not None:
                browser_to_return = getattr(self.tab, "browser", None) or getattr(
                    self.tab, "_browser", None
                )

            return browser_to_return, self.token_handle

        except Exception as exc:
            logger.exception("Error in replicate_captcha: %s", exc)
            self.stop_http_server()
            if domain_added and original_domain:
                with suppress(Exception):
                    hosts_manager.remove_from_hosts(original_domain)
            return None, None

    def _get_or_create_browser(
        self,
        browser: Any = None,
        tab: Any = None,
        bypass_domain_check: bool = False,
        original_domain: str | None = None,
        use_ssl: bool = True,
    ) -> None:
        if tab is not None:
            if self._proxy is not None:
                logger.warning(
                    "Proxy was requested but an existing tab was provided; "
                    "proxy can only be applied when launching a new browser. "
                    "Continuing without proxy."
                )
            if self._browser_path:
                logger.warning(
                    "browser_path was provided but an existing tab was provided; "
                    "browser_path can only be applied when launching a new browser. "
                    "Continuing with existing tab."
                )
            self.tab = tab
            self.browser = None
            self._owns_browser = False
            self._ignore_cert_errors_if_needed(use_ssl=use_ssl)
            return

        if browser is not None:
            if self._proxy is not None:
                logger.warning(
                    "Proxy was requested but an existing browser was provided; "
                    "proxy can only be applied when launching a new browser. "
                    "Continuing without proxy."
                )
            if self._browser_path:
                logger.warning(
                    "browser_path was provided but an existing browser was provided; "
                    "browser_path can only be applied when launching a new browser. "
                    "Continuing with existing browser."
                )
            self.browser = browser
            self.tab = browser.latest_tab
            self._owns_browser = False
            self._ignore_cert_errors_if_needed(use_ssl=use_ssl)
            return

        from DrissionPage import Chromium, ChromiumOptions

        logger.info("Creating new Chromium browser instance...")
        self._owns_browser = True
        if bypass_domain_check and original_domain:
            co = create_browser_options(
                domain=original_domain, use_ssl=use_ssl, browser_path=self._browser_path
            )
            co = co.new_env()
            self._prune_missing_chromium_extensions(co)
            if self._proxy is None:
                co.set_argument("--no-proxy-server")
            else:
                bypass_list = self._build_proxy_bypass_list(
                    original_domain=original_domain, bypass_domain_check=bypass_domain_check
                )
                self._cleanup_proxy_extension()
                ext_dir = tempfile.mkdtemp(prefix="rdr_proxy_auth_ext_")
                self._proxy_extension_dir = create_proxy_auth_extension(
                    proxy=self._proxy, bypass_list=bypass_list, output_dir=ext_dir
                )
                co.add_extension(self._proxy_extension_dir)
            self.browser = Chromium(addr_or_opts=co)
            logger.info("Browser created with domain bypass for: %s", original_domain)
        else:
            if use_ssl or self._proxy is not None or self._browser_path:
                co = ChromiumOptions()
                co = co.new_env()
                self._prune_missing_chromium_extensions(co)
                if self._browser_path:
                    co.set_browser_path(self._browser_path)
                if use_ssl:
                    co.ignore_certificate_errors(True)
                if self._proxy is not None:
                    bypass_list = self._build_proxy_bypass_list(
                        original_domain=original_domain, bypass_domain_check=bypass_domain_check
                    )
                    self._cleanup_proxy_extension()
                    ext_dir = tempfile.mkdtemp(prefix="rdr_proxy_auth_ext_")
                    self._proxy_extension_dir = create_proxy_auth_extension(
                        proxy=self._proxy, bypass_list=bypass_list, output_dir=ext_dir
                    )
                    co.add_extension(self._proxy_extension_dir)
                else:
                    co.set_argument("--no-proxy-server")
                self.browser = Chromium(addr_or_opts=co)
            else:
                co = ChromiumOptions()
                co = co.new_env()
                self._prune_missing_chromium_extensions(co)
                co.set_argument("--no-proxy-server")
                self.browser = Chromium(addr_or_opts=co)

        if self._proxy is not None:
            logger.info("Browser configured with proxy: %s", format_proxy_redacted(self._proxy))

        self.tab = self.browser.latest_tab

    def _ignore_cert_errors_if_needed(self, use_ssl: bool = True) -> None:
        if not use_ssl or not self.tab:
            return
        try:
            self.tab.run_cdp("Security.setIgnoreCertificateErrors", ignore=True)
        except Exception as exc:
            logger.warning("Could not set ignore certificate errors: %s", exc)

    def _handle_captcha_interaction(
        self,
        tab: Any,
        local_file_url: str,
        user_agent: str | None = None,
        cookies: dict[str, Any] | None = None,
        # observation_time: int = 5,
    ) -> bool:
        try:
            if user_agent:
                try:
                    tab.set.user_agent(ua=user_agent)
                except Exception as exc:
                    logger.warning("Could not set user agent: %s", exc)

            tab.get(local_file_url)

            if cookies:
                try:
                    tab.set.cookies(cookies)
                except Exception as exc:
                    logger.warning("Could not set cookies: %s", exc)

            try:
                has_iframe = bool(
                    tab.run_js("return !!document.querySelector('iframe[src*=\"recaptcha\"]');")
                )
                if has_iframe:
                    logger.info("reCAPTCHA iframe detected")
                else:
                    err = tab.run_js(
                        "return (document.getElementById('error-message')?.innerText || '').trim();"
                    )
                    if err:
                        logger.error("reCAPTCHA error: %s", err)
                        logger.info(
                            "This may be due to domain restrictions on the reCAPTCHA site key."
                        )
            except Exception:
                pass

            return True
        except Exception as exc:
            logger.exception("Error in _handle_captcha_interaction: %s", exc)
            return False

    def _set_token(self, token: str | None) -> None:
        if token is None:
            return

        token_str = str(token).strip()
        if not token_str or token_str in TOKEN_PLACEHOLDER_VALUES:
            return

        if self.last_token == token_str:
            return

        self.last_token = token_str

    def get_last_token(self) -> str | None:
        return self.last_token

    def close_browser(self) -> None:
        self.stop_token_monitor()
        if self.browser is not None and self._owns_browser:
            with suppress(Exception):
                self.browser.quit()
        self.browser = None
        self.tab = None
        self._owns_browser = False
        self._cleanup_proxy_extension()

    def stop_token_monitor(self) -> None:
        if self._token_monitor_stop_event is not None:
            with suppress(Exception):
                self._token_monitor_stop_event.set()

        if self.token_monitor_thread is not None:
            with suppress(Exception):
                self.token_monitor_thread.join(timeout=2)

        if self.token_handle is not None:
            with suppress(Exception):
                self.token_handle.close()

        self.token_monitor_thread = None
        self._token_monitor_stop_event = None

    def close(self) -> None:
        """Stop monitor, close browser, stop server."""
        try:
            self.close_browser()
        finally:
            try:
                self.stop_http_server()
            finally:
                _unregister_replicator(self)
