<div align="left">

# RecaptchaDomainReplicator
<a href="LICENSE"></a> <img src="https://github.com/DannyLuna17/BulletDroid2/raw/image-data/license-badge.svg" alt="License: MIT" height="22" /> <a href="https://pypi.org/project/recaptcha-domain-replicator/"><img src="https://img.shields.io/pypi/v/recaptcha-domain-replicator" alt="PyPI version" /></a> <img src="https://img.shields.io/pypi/pyversions/recaptcha-domain-replicator" alt="Python versions" /> <a href="https://github.com/DannyLuna17/recaptcha_domain_replicator/actions/workflows/ci.yml"><img src="https://github.com/DannyLuna17/recaptcha_domain_replicator/actions/workflows/ci.yml/badge.svg" alt="CI" /></a> <img src="https://upload.wikimedia.org/wikipedia/commons/2/21/Flag_of_Colombia.svg" alt="Colombia Flag" height="22" />

<p align="center">
  
</p>
<p align="center">
  
</p>

</div>

Serve a local replica of a reCAPTCHA widget and capture the token.

RecaptchaDomainReplicator generates a local HTML page that renders a reCAPTCHA widget, serves it via a local Flask server, opens it in Chromium, and monitors the DOM to capture the resulting token.

<p align="center">

https://github.com/user-attachments/assets/e267756c-30e0-452a-9b3e-7cd566bebeb1

</p>



---

## Features

• Generate local page for any sitekey and domain  
• Serve via local Flask server (in-memory by default, optional disk persistence)  
• Open in Chromium or reuse an existing browser/tab  
• Monitor page in separated thread and expose token via `TokenHandle`
• Proxy support (HTTP, HTTPS, SOCKS4, SOCKS5 with optional credentials)  
• Domain bypass modes (VPN-friendly browser rules & hosts file fallback)  
• HTTPS with temporary self-signed certificates  
• Support for invisible reCAPTCHA, enterprise, custom actions, and `data-s` values

---

## How It Works

<p align="center">
  <img src="assets/pipeline.svg" alt="Pipeline" width="700" />
</p>

The library follows a simple four-step pipeline:

• **Generate**: Build a single HTML page that renders reCAPTCHA for a given sitekey and domain (with optional params like `action`, `data-s`, enterprise).  
• **Serve**: Host it on a local Flask server (in-memory by default; can persist to disk).  
• **Open**: Launch (or reuse) a Chromium tab to load that page.  
• **Observe**: Poll the DOM to extract the token once it appears.

---

## Requirements

• **Python**: 3.9+  
• **Browser**: Chromium-based browser (Chrome, Chrome for Testing, Edge)  
• **For credential proxies**: Use [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/#stable) or Microsoft Edge  
• **Admin privileges** (optional): Required only for hosts file changes and port forwarding

---

## Installation

```bash
pip install recaptcha-domain-replicator
```

From source (with dev dependencies):

```bash
pip install -e ".[dev]"
```

---

## Usage

### Library Usage

```python
from recaptcha_domain_replicator import RecaptchaDomainReplicator

with RecaptchaDomainReplicator(
    download_dir="tmp",
    server_port=8080,
    proxy=None,  # "http://user:pass@host:port"
    browser_path=None,  # r"C:\path\to\chrome.exe"
) as replicator:
    browser, token_handle = replicator.replicate_captcha(
        website_key="YOUR_SITE_KEY",
        website_url="https://example.com/path",
        is_invisible=True,
        action="submit",
        data_s_value=None,
        api_domain="google.com",  # or "recaptcha.net"
        is_enterprise=False,
        bypass_domain_check=True,
        use_ssl=True,
        user_agent=None,
        cookies=None,
        browser=None, # already instanciated browser
        tab=None,
    )

    # replicate_captcha() returns immediately, wait with the async token monitor
    token = token_handle.wait(timeout=120) if token_handle else None # 0 to wait until token is received
    print("Token:", token)
```

### CLI Usage

After installation, a console script is available:

```bash
recaptcha-domain-replicator --help
```

Run the built-in demo:

```bash
recaptcha-domain-replicator demo
```

Replicate a captcha:

```bash
recaptcha-domain-replicator replicate \
  --website-key "YOUR_SITE_KEY" \
  --website-url "https://example.com/path" \
  --persist-html \
  --invisible \
  --action "submit" \
  --bypass-domain-check \
  --proxy "socks5://user:pass@host:port" \
  --browser-path "C:\path\to\chrome.exe" \
  --observation-time 0
```

**CLI behavior notes:**

• Prints the token (if obtained) as plain text  
• **logging**: Disabled by default, enable with `--log-level INFO` or `DEBUG`  
• **`--observation-time`**: Set to `0` to run until a token is captured or browser closes

---

## Domain Bypass Modes

When `bypass_domain_check=True` is enabled with a `website_url`, the tool makes the replica page appear to load from the original domain.

• **Preferred (VPN-friendly) mode**: Let the replicator create the browser
  - Uses Chromium `--host-resolver-rules` to map the target domain to `127.0.0.1` inside that browser only
  - Does **not** modify your system hosts file

• **Fallback mode**: You provide an existing browser/tab
  - The browser is already running, so host-resolver-rules can't be applied, it falls back to modifying the **Windows hosts file**
  - Requires an **elevated (Administrator) shell**

---

## HTTPS, Ports & System Changes

• **HTTPS by default**: `use_ssl=True` serves the replica over HTTPS using a temporary self-signed certificate. Use `--no-ssl` for plain HTTP.

• **Port forwarding (admin only)**: When elevated, the tool may create a Windows `netsh interface portproxy` rule to forward 80/443 -> the chosen high port. Port forwarding is removed during shutdown, firewall rules may remain.

---

## Limitations

Even if you successfully capture a token, it may not be accepted by server-side verification.

**Common rejection reasons:**
• **Action mismatch**: Backend expects a specific `action` value
• **Risk scoring**: reCAPTCHA considers IP reputation, browser state, and interaction signals
• **Session mismatch**: Server might expect the token from the same browser session 
• **IP mismatch**: Tokens might be evaluated relative to the client IP that solved the challenge
• **Token freshness**: Tokens are short-lived 
• **Enterprise vs non-enterprise**: Using the wrong API variant changes behavior
* **google.com vs recaptcha.net**: Using the wrong scripts domain

---

## Troubleshooting

• **reCAPTCHA iframe never loads / shows an error**
  - The sitekey may be domain-restricted. Try `--bypass-domain-check`
  - If relying on hosts-file bypass, run your terminal as **Administrator**
    
---

## Repository Layout

```text
recaptcha_domain_replicator/
├── recaptcha_domain_replicator/ # Package
│   ├── __init__.py
│   ├── __main__.py # CLI entry
│   ├── captcha_replicator.py # Replicator class
│   ├── html_builder.py # HTML generation
│   ├── server_manager.py # Flask server
│   ├── token_monitor.py # Token polling
│   ├── browser_config.py # Chromium options
│   ├── hosts_manager.py # Windows hosts file
│   ├── certificates.py # SSL certificate generation
│   ├── proxy_utils.py # Proxy parsing
│   ├── proxy_auth_extension.py # Chrome extension for proxy auth
│   └── logging_utils.py # Logging configuration
├── tests/ # Tests
├── assets/  # Images and diagrams
├── pyproject.toml # Project configuration
└── README.md
```

---

## Development

To run the tests just run:

```bash
pytest
```

---

## Should I star this repository?

You don't have to, but giving it a star would mean a lot. It helps more people discover the project. Your support helps grow an open and accessible community. Thank you!

---

## Contributing

We welcome issues, feature requests, and pull requests! Please read the [contribution guidelines](CONTRIBUTING.md) before you begin.

If you discovered a typo or small documentation bug, feel free to open a quick PR straight away. For anything larger, open an issue first.

---

## Code of Conduct

Be kind. We follow the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating in this project you agree to uphold those guidelines.

---

## Donate

If you find this project helpful, please consider supporting the developer with a donation. Thank you! :)

- BTC: `1EXLMgvU1pNaXNwuaRSMRQ69Vqp2UTjTSZ`
- ETH (ERC-20): `0xebb810aa4258d97f98157c32ac49b6be9dda4433`
- LTC: `LUqdVjS9cJFby5Mj5c7wkvyNM3zaJxzhTc`
- USDT (TRC-20): `TN5LEgpa1xu5EecC9LobzVN8KAgyi5kwgZ`
- BNB (BEP-20): `0xebb810aa4258d97f98157c32ac49b6be9dda4433`
- SOL: `GGWSzrdftR4aivxxWZCEqJspfcqtzmLso9AkVXBkDfEK`

---

## Acknowledgements

• [DrissionPage](https://github.com/g1879/DrissionPage) - Browser automation library  
• [Flask](https://flask.palletsprojects.com/) - Web framework for serving the replica  
• [pyOpenSSL](https://www.pyopenssl.org/) - SSL certificate generation

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Legal & Responsible Use

RecaptchaDomainReplicator is provided for educational and research purposes. Use responsibly and comply with all applicable laws and terms of service.
