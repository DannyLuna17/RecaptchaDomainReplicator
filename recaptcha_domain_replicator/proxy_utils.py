from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True)
class ProxyConfig:
    scheme: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None


def parse_proxy_url(proxy_url: str) -> ProxyConfig:
    """
    Parse and validate a proxy URL.

    Supported forms:
        - http://host:port
        - https://host:port
        - socks4://host:port
        - socks5://host:port
        - http://user:pass@host:port
        - https://user:pass@host:port
        - socks4://user:pass@host:port
        - socks5://user:pass@host:port
        - host:port (assumes http)
        - user:pass@host:port (assumes http)

    Notes:
        - Username/password are optional.
    """
    raw = (proxy_url or "").strip()
    if not raw:
        raise ValueError("proxy must be a non-empty string")

    candidate = raw if "://" in raw else f"http://{raw}"
    split = urlsplit(candidate)

    scheme = (split.scheme or "").lower().strip()
    if scheme not in {"http", "https", "socks4", "socks5"}:
        raise ValueError("proxy scheme must be http, https, socks4, or socks5")

    if split.path not in ("", "/") or split.query or split.fragment:
        raise ValueError("proxy URL must not contain a path, query, or fragment")

    host = (split.hostname or "").strip()
    port = split.port
    if not host or port is None:
        raise ValueError("proxy must include host and port")

    username = unquote(split.username) if split.username is not None else None
    password = unquote(split.password) if split.password is not None else None

    if username is not None:
        username = username.strip()
        if not username:
            username = None
    if password is not None:
        password = password.strip()
        if not password:
            password = None

    if (username is None) != (password is None):
        raise ValueError("proxy credentials must include both username and password")

    return ProxyConfig(
        scheme=scheme, host=host, port=int(port), username=username, password=password
    )


def format_proxy_redacted(proxy: ProxyConfig) -> str:
    """Return a proxy string without credentials."""
    return f"{proxy.scheme}://{proxy.host}:{proxy.port}"
