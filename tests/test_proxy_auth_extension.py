import json
from pathlib import Path

from recaptcha_domain_replicator.proxy_auth_extension import create_proxy_auth_extension
from recaptcha_domain_replicator.proxy_utils import ProxyConfig


def test_create_proxy_auth_extension_writes_mv3_manifest_without_auth(tmp_path: Path):
    proxy = ProxyConfig(scheme="http", host="proxy.example", port=8080)
    ext_dir = Path(
        create_proxy_auth_extension(
            proxy=proxy, bypass_list=["localhost"], output_dir=tmp_path / "ext"
        )
    )

    manifest = json.loads((ext_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["background"]["service_worker"] == "background.js"
    assert manifest["host_permissions"] == ["<all_urls>"]
    assert "proxy" in manifest["permissions"]
    assert "webRequest" in manifest["permissions"]
    assert "webRequestAuthProvider" not in manifest["permissions"]

    background = (ext_dir / "background.js").read_text(encoding="utf-8")
    assert "chrome.proxy.settings.set" in background
    assert '"bypassList": ["localhost"]' in background
    assert "onAuthRequired" not in background


def test_create_proxy_auth_extension_writes_auth_listener_when_credentials_present(tmp_path: Path):
    proxy = ProxyConfig(
        scheme="http", host="proxy.example", port=8080, username="user", password="pass"
    )
    ext_dir = Path(
        create_proxy_auth_extension(
            proxy=proxy, bypass_list=["localhost", "example.com"], output_dir=tmp_path / "ext_auth"
        )
    )

    manifest = json.loads((ext_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "webRequestAuthProvider" in manifest["permissions"]

    background = (ext_dir / "background.js").read_text(encoding="utf-8")
    assert "chrome.webRequest.onAuthRequired.addListener" in background
    assert "details.isProxy" in background
    assert '"bypassList": ["localhost", "example.com"]' in background


def test_create_proxy_auth_extension_supports_socks5_scheme(tmp_path: Path):
    proxy = ProxyConfig(scheme="socks5", host="proxy.example", port=1080)
    ext_dir = Path(
        create_proxy_auth_extension(
            proxy=proxy, bypass_list=["localhost"], output_dir=tmp_path / "ext_socks5"
        )
    )

    background = (ext_dir / "background.js").read_text(encoding="utf-8")
    assert '"scheme": "socks5"' in background


def test_create_proxy_auth_extension_supports_socks4_scheme(tmp_path: Path):
    proxy = ProxyConfig(scheme="socks4", host="proxy.example", port=1080)
    ext_dir = Path(
        create_proxy_auth_extension(
            proxy=proxy, bypass_list=["localhost"], output_dir=tmp_path / "ext_socks4"
        )
    )

    background = (ext_dir / "background.js").read_text(encoding="utf-8")
    assert '"scheme": "socks4"' in background
