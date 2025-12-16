from __future__ import annotations

import logging
import os
import socket
import threading
import time
from contextlib import suppress
from typing import TYPE_CHECKING

from flask import Flask, Response, request, send_from_directory
from werkzeug.serving import make_server

from . import hosts_manager
from .certificates import cleanup_cert_files, create_self_signed_cert
from .constants import SERVER_STARTUP_CHECK_INTERVAL, SERVER_STARTUP_TIMEOUT

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from werkzeug.serving import BaseWSGIServer


class CaptchaServer:
    """Local Flask server and SSL certificate setup."""

    def __init__(self, download_dir: str, server_port: int = 8080):
        self.download_dir = download_dir
        self.server_port = server_port
        self.flask_app: Flask | None = None
        self.server_thread: threading.Thread | None = None
        self._http_server: BaseWSGIServer | None = None
        self.port_forwarding_enabled: bool = False
        self.forward_target_port: int | None = None
        self.use_ssl: bool = False
        self.cert_file: str | None = None
        self.key_file: str | None = None

        # In-memory HTML (used when persistence is disabled).
        self._in_memory_html_filename: str | None = None
        self._in_memory_html_content: str | None = None

    def set_in_memory_html(self, filename: str, content: str) -> None:
        self._in_memory_html_filename = filename
        self._in_memory_html_content = content

    def clear_in_memory_html(self) -> None:
        self._in_memory_html_filename = None
        self._in_memory_html_content = None

    @property
    def port(self) -> int:
        return self.server_port

    def _get_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("", 0))
            return sock.getsockname()[1]

    def start(self, domain: str | None = None, use_ssl: bool = True) -> int:
        """Start the Flask server on a free port, optionally with SSL."""
        # Verify if the port is already in use
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("0.0.0.0", self.server_port))
        except OSError:
            logger.warning("Port %s is in use. Finding an available port...", self.server_port)
            self.server_port = self._get_free_port()

        ssl_context = None
        if use_ssl and not domain:
            logger.info("SSL requested but no domain was provided. Falling back to HTTP.")
            use_ssl = False

        if use_ssl and domain:
            self.cert_file, self.key_file = create_self_signed_cert(domain)
            if self.cert_file and self.key_file:
                ssl_context = (self.cert_file, self.key_file)
                target_port = 443
            else:
                logger.warning("Failed to create SSL certificate. Falling back to HTTP.")
                use_ssl = False
                target_port = 80
        else:
            target_port = 80

        self.use_ssl = bool(use_ssl and ssl_context)

        if hosts_manager.is_admin():
            self.port_forwarding_enabled = hosts_manager.setup_port_forwarding(
                self.server_port, target_port
            )
            self.forward_target_port = target_port if self.port_forwarding_enabled else None
        else:
            logger.info("No admin privileges. Port numbers will be visible in URLs.")
            self.port_forwarding_enabled = False
            self.forward_target_port = None

        abs_download_dir = os.path.abspath(self.download_dir)

        werkzeug_log = logging.getLogger("werkzeug")
        werkzeug_log.setLevel(logging.ERROR)
        if not any(isinstance(h, logging.NullHandler) for h in werkzeug_log.handlers):
            werkzeug_log.addHandler(logging.NullHandler())

        flask_app = Flask(__name__)
        self.flask_app = flask_app

        @flask_app.route("/", defaults={"path": ""})
        @flask_app.route("/<path:path>")
        def catch_all(path):
            # Serve in-memory HTML page when available.
            if self._in_memory_html_content is not None:
                requested = (path or "").lstrip("/")
                if requested in ("", self._in_memory_html_filename or ""):
                    return Response(self._in_memory_html_content, mimetype="text/html")

                file_path = os.path.join(abs_download_dir, requested)
                if not os.path.isfile(file_path):
                    return Response(self._in_memory_html_content, mimetype="text/html")

            file_path = os.path.join(abs_download_dir, path)
            if os.path.isfile(file_path):
                return send_from_directory(abs_download_dir, path)

            try:
                html_files = [f for f in os.listdir(abs_download_dir) if f.endswith(".html")]
            except FileNotFoundError:
                html_files = []
            if html_files:
                latest_html = sorted(
                    html_files,
                    key=lambda f: os.path.getctime(os.path.join(abs_download_dir, f)),
                    reverse=True,
                )[0]
                return send_from_directory(abs_download_dir, latest_html)

            return "No HTML files available"

        @flask_app.route("/shutdown")
        def shutdown():
            http_server = self._http_server
            if http_server is not None:
                # _http_server.shutdown() must not be called from the serving thread.
                # Because it will block the serving thread.
                threading.Thread(target=http_server.shutdown, daemon=True).start()
                return "Server shutting down..."

            # Fallback for when running under the Werkzeug dev server.
            func = request.environ.get("werkzeug.server.shutdown")
            if func is not None:
                func()

            # Don't raise if unavailable
            return "Server shutdown requested..."

        # Start a WSGI server.
        http_server = make_server("0.0.0.0", self.server_port, flask_app, ssl_context=ssl_context)
        self._http_server = http_server

        server_thread = threading.Thread(target=http_server.serve_forever)
        self.server_thread = server_thread
        server_thread.daemon = True
        server_thread.start()

        # Wait for server to be ready by checking if port is accepting connections
        self._wait_for_server_ready()

        return self.server_port

    def _wait_for_server_ready(self) -> None:
        """Poll until the server is accepting connections or timeout."""
        deadline = time.monotonic() + SERVER_STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(SERVER_STARTUP_CHECK_INTERVAL)
                    sock.connect(("127.0.0.1", self.server_port))
                    return  # Server is ready!
            except (ConnectionRefusedError, TimeoutError, OSError):
                time.sleep(SERVER_STARTUP_CHECK_INTERVAL)
        logger.warning("Server startup timeout - proceeding anyway")

    def stop(self) -> None:
        """Shutdown the server and clean up resources."""
        if self._http_server is not None:
            with suppress(Exception):
                self._http_server.shutdown()
            with suppress(Exception):
                self._http_server.server_close()

        if self.port_forwarding_enabled and hosts_manager.is_admin():
            if self.forward_target_port is not None:
                hosts_manager.remove_port_forwarding(self.forward_target_port)
            self.port_forwarding_enabled = False
            self.forward_target_port = None

        if self.server_thread is not None:
            with suppress(Exception):
                self.server_thread.join(timeout=2)

        cleanup_cert_files(self.cert_file, self.key_file)
        self.cert_file = None
        self.key_file = None

        self._http_server = None
        self.server_thread = None
        self.flask_app = None
        self.use_ssl = False
        self.clear_in_memory_html()
