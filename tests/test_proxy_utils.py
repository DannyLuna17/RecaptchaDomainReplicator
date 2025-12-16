import pytest

from recaptcha_domain_replicator.proxy_utils import (
    ProxyConfig,
    format_proxy_redacted,
    parse_proxy_url,
)


def test_parse_proxy_url_defaults_to_http_scheme():
    assert parse_proxy_url("example.com:8080") == ProxyConfig(
        scheme="http", host="example.com", port=8080
    )


def test_parse_proxy_url_supports_http_and_https():
    assert parse_proxy_url("http://example.com:8080") == ProxyConfig(
        scheme="http", host="example.com", port=8080
    )
    assert parse_proxy_url("https://example.com:443") == ProxyConfig(
        scheme="https", host="example.com", port=443
    )


def test_parse_proxy_url_supports_socks4():
    assert parse_proxy_url("socks4://example.com:1080") == ProxyConfig(
        scheme="socks4", host="example.com", port=1080
    )


def test_parse_proxy_url_supports_socks5():
    assert parse_proxy_url("socks5://example.com:1080") == ProxyConfig(
        scheme="socks5", host="example.com", port=1080
    )


def test_parse_proxy_url_supports_credentials():
    assert parse_proxy_url("http://user:pass@example.com:8080") == ProxyConfig(
        scheme="http",
        host="example.com",
        port=8080,
        username="user",
        password="pass",
    )
    assert parse_proxy_url("user:pass@example.com:8080") == ProxyConfig(
        scheme="http",
        host="example.com",
        port=8080,
        username="user",
        password="pass",
    )

    assert parse_proxy_url("socks4://user:pass@example.com:1080") == ProxyConfig(
        scheme="socks4",
        host="example.com",
        port=1080,
        username="user",
        password="pass",
    )

    assert parse_proxy_url("socks5://user:pass@example.com:1080") == ProxyConfig(
        scheme="socks5",
        host="example.com",
        port=1080,
        username="user",
        password="pass",
    )


@pytest.mark.parametrize(
    "proxy_url",
    [
        "socks4://example.com",  # missing port
        "socks5://example.com",  # missing port
        "http://example.com",  # missing port
        "http://user@example.com:8080",  # missing password
        "http://:pass@example.com:8080",  # missing username
        "http://example.com:8080/path",  # path not allowed
    ],
)
def test_parse_proxy_url_rejects_invalid_inputs(proxy_url: str):
    with pytest.raises(ValueError):
        parse_proxy_url(proxy_url)


def test_format_proxy_redacted_strips_credentials():
    cfg = parse_proxy_url("http://user:pass@example.com:8080")
    assert format_proxy_redacted(cfg) == "http://example.com:8080"
