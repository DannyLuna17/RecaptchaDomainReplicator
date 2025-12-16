from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from DrissionPage import ChromiumOptions

from .constants import CHROMIUM_ARGUMENTS, RECAPTCHA_API_DOMAINS


def mapped_hosts_for_domain(domain: str) -> list[str]:
    """
    Return hostnames that should be mapped to localhost for domain bypass.

    Notes:
        - Input must be just a hostname. If a port is present, it is stripped.
        - Adds both www/non-www variants, except for reCAPTCHA API domains.
    """
    host = domain.split(":", 1)[0].strip()
    if not host:
        return []

    domains_to_map: list[str] = [host]

    base_domain = host[4:] if host.lower().startswith("www.") else host
    if base_domain.lower() not in RECAPTCHA_API_DOMAINS:
        if host.lower().startswith("www."):
            domains_to_map.append(base_domain)
        else:
            domains_to_map.append(f"www.{host}")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for d in domains_to_map:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def build_host_resolver_rules(domain: str) -> str:
    """
    Build the value for Chromium's --host-resolver-rules argument to map a domain to localhost.

    Notes:
        - Adds both www/non-www variants, except for reCAPTCHA API domains.
    """
    domains_to_map = mapped_hosts_for_domain(domain)
    if not domains_to_map:
        return ""

    return ",".join([f"MAP {d} 127.0.0.1" for d in domains_to_map])


def create_browser_options(
    domain: str | None = None, use_ssl: bool = True, browser_path: str | None = None
) -> ChromiumOptions:
    """
    Build ChromiumOptions configured for optional domain bypass.

    Note:
        use_ssl=True means that the local replicator server may
        be started in HTTPS mode using a self-signed certificate,
        configured the browser to ignore certificate errors.

    Args:
        domain (str, optional): Domain to map to localhost via host-resolver-rules.
        use_ssl (bool): Whether the local replicator is expected to use HTTPS (SSL).
        When True, the browser is configured to ignore certificate errors so it can
        load pages served with a self-signed certificate.

    Returns:
        ChromiumOptions: Configured options instance.
    """
    from DrissionPage import ChromiumOptions

    options = ChromiumOptions()
    if browser_path:
        options.set_browser_path(browser_path)

    for argument in CHROMIUM_ARGUMENTS:
        options.set_argument(argument)

    if use_ssl:
        options.ignore_certificate_errors(True)

    if domain:
        rules = build_host_resolver_rules(domain)
        if rules:
            options.set_argument(f"--host-resolver-rules={rules}")

    return options
