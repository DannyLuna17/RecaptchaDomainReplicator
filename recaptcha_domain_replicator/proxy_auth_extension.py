from __future__ import annotations

import json
from pathlib import Path

from .proxy_utils import ProxyConfig


def create_proxy_auth_extension(
    *,
    proxy: ProxyConfig,
    bypass_list: list[str] | None = None,
    output_dir: str | Path,
) -> str:
    """
    Create an unpacked Manifest V3 Chrome extension that:
      - sets a fixed proxy (chrome.proxy)
      - optionally provides proxy credentials (webRequest.onAuthRequired)

    Returns:
        str: The extension directory path.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bypass_list = bypass_list or []
    cleaned_bypass: list[str] = []
    seen: set[str] = set()
    for entry in bypass_list:
        item = str(entry or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned_bypass.append(item)

    permissions: list[str] = ["proxy", "webRequest"]
    if proxy.username is not None and proxy.password is not None:
        permissions.append("webRequestAuthProvider")

    manifest = {
        "name": "Proxy Auth",
        "version": "1.0.0",
        "manifest_version": 3,
        "permissions": permissions,
        "host_permissions": ["<all_urls>"],
        "background": {"service_worker": "background.js"},
    }

    config = {
        "mode": "fixed_servers",
        "rules": {
            "singleProxy": {"scheme": proxy.scheme, "host": proxy.host, "port": int(proxy.port)},
            "bypassList": cleaned_bypass,
        },
    }

    config_json = json.dumps(config, ensure_ascii=False)
    credentials_json = (
        json.dumps({"username": proxy.username, "password": proxy.password}, ensure_ascii=False)
        if proxy.username is not None and proxy.password is not None
        else None
    )

    background_lines: list[str] = [
        f"const config = {config_json};",
        "",
        "function applyProxyConfig() {",
        "  chrome.proxy.settings.set({ value: config, scope: 'regular' }, () => {});",
        "}",
        "",
        "applyProxyConfig();",
        "chrome.runtime.onInstalled.addListener(applyProxyConfig);",
        "chrome.runtime.onStartup.addListener(applyProxyConfig);",
    ]

    if credentials_json is not None:
        background_lines += [
            "",
            f"const credentials = {credentials_json};",
            "",
            "chrome.webRequest.onAuthRequired.addListener(",
            "  (details, callback) => {",
            "    if (!details || !details.isProxy) {",
            "      callback({});",
            "      return;",
            "    }",
            "    callback({ authCredentials: credentials });",
            "  },",
            "  { urls: ['<all_urls>'] },",
            "  ['asyncBlocking']",
            ");",
        ]

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "background.js").write_text("\n".join(background_lines) + "\n", encoding="utf-8")

    return str(out_dir)
