"""
Hosts file manager.

This module provides functions to add and remove entries to the Windows hosts file
to temporarily redirect domains to 127.0.0.1, to bypass domain restrictions
in reCAPTCHA challenges.

This is used only when the browser is already running and provided by the user,
because we can't set the --host-resolver-rules argument after the browser is running.
"""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .constants import (
    HOSTS_FILE_PATH,
    HOSTS_MARKER,
    HOSTS_MARKERS,
    RECAPTCHA_API_DOMAINS,
)

logger = logging.getLogger(__name__)


def _strip_port(host: str) -> str:
    return host.split(":", 1)[0]


def _base_domain(host: str) -> str:
    h = host.strip().lower()
    h = _strip_port(h)
    return h[4:] if h.startswith("www.") else h


def _domain_variants(domain: str) -> list[str]:
    """
    Return domain variants to add/remove from hosts.

    We add both www/non-www variants,
    except for known reCAPTCHA API domains
    to avoid breaking script loads.
    """
    d = _strip_port(domain.strip())
    if not d:
        return []

    base = _base_domain(d)
    variants: list[str] = [d]

    if base not in RECAPTCHA_API_DOMAINS:
        if d.lower().startswith("www."):
            variants.append(d[4:])
        else:
            variants.append(f"www.{d}")

    # De-duplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        key = v.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v.strip())
    return out


def _parse_hosts_entries(hosts_content: str) -> set[tuple[str, str]]:
    """
    Parse a hosts file into (ip, host) pairs.
    """
    entries: set[tuple[str, str]] = set()
    for line in hosts_content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        raw = stripped.split("#", 1)[0].strip()
        parts = raw.split()
        if len(parts) < 2:
            continue
        ip, host = parts[0], parts[1]
        entries.add((ip, host.lower()))
    return entries


def _backup_hosts_file(hosts_file: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = hosts_file.with_name(f"{hosts_file.name}.{timestamp}.bak")
    shutil.copy2(hosts_file, backup_path)
    return backup_path


def _atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    if content and not content.endswith("\n"):
        content += "\n"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(tmp_path, path)


def is_admin():
    """
    Check if the script is running with administrator privileges.

    Returns:
        bool: True if running as administrator, False otherwise
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def restart_with_admin():
    """
    Restart the current script with administrator privileges.
    """
    if not is_admin():
        params = subprocess.list2cmdline(sys.argv)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit(0)


def add_to_hosts(domain: str, ip_address: str = "127.0.0.1") -> bool:
    """
    Add a domain entry to the hosts file.

    Args:
        domain (str): The domain name to add
        ip_address (str, optional): The IP address to map the domain to. Defaults to "127.0.0.1".

    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrator privileges required to modify hosts file.")
        return False

    try:
        hosts_file = Path(HOSTS_FILE_PATH)
        hosts_content = hosts_file.read_text(encoding="utf-8", errors="ignore")

        domains_to_add = _domain_variants(domain)
        if not domains_to_add:
            logger.error("No valid domain provided.")
            return False

        existing = _parse_hosts_entries(hosts_content)

        new_content = hosts_content
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"

        added_any = False
        for d in domains_to_add:
            key = (ip_address, d.lower())
            if key in existing:
                logger.info("Hosts entry already exists: %s %s", ip_address, d)
                continue
            new_content += f"{ip_address} {d}{HOSTS_MARKER}\n"
            added_any = True

        if not added_any:
            return True

        backup_path = _backup_hosts_file(hosts_file)
        logger.info("Created hosts backup: %s", backup_path)

        _atomic_write_text(hosts_file, new_content)
        flush_dns_cache()
        return True

    except Exception as exc:
        logger.exception("Error adding entry to hosts file: %s", exc)
        return False


def remove_from_hosts(domain: str, ip_address: str = "127.0.0.1") -> bool:
    """
    Remove a domain entry from the hosts file.

    Args:
        domain (str): The domain name to remove
        ip_address (str, optional): The IP address mapped to the domain. Defaults to "127.0.0.1".

    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrator privileges required to modify hosts file.")
        return False

    try:
        hosts_file = Path(HOSTS_FILE_PATH)
        hosts_content = hosts_file.read_text(encoding="utf-8", errors="ignore")

        domains_to_remove = {d.lower() for d in _domain_variants(domain)}
        if not domains_to_remove:
            logger.error("No valid domain provided.")
            return False

        lines = hosts_content.splitlines()
        new_lines: list[str] = []
        removed_any = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                new_lines.append(line)
                continue

            # Only remove entries created by this tool.
            if not any(marker in line for marker in HOSTS_MARKERS):
                new_lines.append(line)
                continue

            raw = stripped.split("#", 1)[0].strip()
            parts = raw.split()
            if len(parts) >= 2 and parts[0] == ip_address and parts[1].lower() in domains_to_remove:
                removed_any = True
                continue

            new_lines.append(line)

        if not removed_any:
            return True

        new_content = "\n".join(new_lines)

        backup_path = _backup_hosts_file(hosts_file)
        logger.info("Created hosts backup: %s", backup_path)

        _atomic_write_text(hosts_file, new_content)
        flush_dns_cache()
        return True

    except Exception as exc:
        logger.exception("Error removing entry from hosts file: %s", exc)
        return False


def flush_dns_cache() -> None:
    """
    Flush the DNS cache to apply hosts file changes immediately.
    """
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() if getattr(exc, "stderr", None) else str(exc)
        logger.warning("Failed to flush DNS cache: %s", details)
    except Exception as exc:
        logger.exception("Error flushing DNS cache: %s", exc)


def check_domain_in_hosts(domain: str, ip_address: str = "127.0.0.1") -> bool:
    """
    Check if a domain entry exists in the hosts file.

    Args:
        domain (str): The domain name to check
        ip_address (str, optional): The IP address mapped to the domain. Defaults to "127.0.0.1".

    Returns:
        bool: True if entry exists, False otherwise
    """
    try:
        hosts_file = Path(HOSTS_FILE_PATH)
        hosts_content = hosts_file.read_text(encoding="utf-8", errors="ignore")
        entries = _parse_hosts_entries(hosts_content)
        return any((ip_address, d.lower()) in entries for d in _domain_variants(domain))

    except Exception as exc:
        logger.exception("Error checking hosts file: %s", exc)
        return False


def setup_port_forwarding(port: int, target_port: int = 80) -> bool:
    """
    Set up port forwarding from high port to port 80/443 using netsh interface portproxy.
    This allows a non-admin process to effectively use standard web ports via forwarding.

    Args:
        port (int): The high numbered port the app is actually running on
        target_port (int): The port to forward to (80 for HTTP, 443 for HTTPS)

    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrator privileges required to set up port forwarding")
        return False

    try:
        # Delete any existing port forwarding rules for target port
        delete_cmd = (
            "netsh interface portproxy delete v4tov4 "
            f"listenport={target_port} listenaddress=0.0.0.0"
        )
        subprocess.run(
            delete_cmd,
            shell=True,
            capture_output=True,
            text=True,
        )

        # Add new port forwarding rule that listens on all interfaces
        add_cmd = (
            "netsh interface portproxy add v4tov4 "
            f"listenport={target_port} listenaddress=0.0.0.0 "
            f"connectport={port} connectaddress=127.0.0.1"
        )
        subprocess.run(
            add_cmd,
            shell=True,
            capture_output=True,
            check=True,
            text=True,
        )

        # Add a firewall rule to allow incoming connections to the target port if it doesn't exist
        protocol = "HTTPS" if target_port == 443 else "HTTP"
        fw_name = f"DomainReplicator{protocol}Access"
        fw_cmd = (
            f'netsh advfirewall firewall show rule name="{fw_name}" >nul 2>&1 || '
            f'netsh advfirewall firewall add rule name="{fw_name}" '
            f"dir=in action=allow protocol=TCP localport={target_port}"
        )
        subprocess.run(
            fw_cmd,
            shell=True,
            capture_output=True,
            text=True,
        )

        return True
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() if getattr(exc, "stderr", None) else str(exc)
        logger.error("Error setting up port forwarding: %s", details)
        return False
    except Exception as exc:
        logger.exception("Unexpected error setting up port forwarding: %s", exc)
        return False


def remove_port_forwarding(target_port: int = 80) -> bool:
    """
    Remove port forwarding rules previously set up.

    Args:
        target_port (int): The listening port to remove forwarding for (usually 80)

    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrator privileges required to remove port forwarding")
        return False

    try:
        # Delete the port forwarding rule
        delete_cmd = (
            "netsh interface portproxy delete v4tov4 "
            f"listenport={target_port} listenaddress=0.0.0.0"
        )
        subprocess.run(
            delete_cmd,
            shell=True,
            capture_output=True,
            check=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() if getattr(exc, "stderr", None) else str(exc)
        logger.error("Error removing port forwarding: %s", details)
        return False
    except Exception as exc:
        logger.exception("Unexpected error removing port forwarding: %s", exc)
        return False


if __name__ == "__main__":
    # Test the hosts file manager
    import argparse

    parser = argparse.ArgumentParser(description="Manage Windows hosts file entries")
    parser.add_argument(
        "action", choices=["add", "remove", "check"], help="Action to perform on hosts file"
    )
    parser.add_argument("domain", help="Domain name to manipulate")
    parser.add_argument("--ip", default="127.0.0.1", help="IP address (default: 127.0.0.1)")

    # Check for admin rights first
    if len(sys.argv) > 1 and not is_admin() and sys.argv[1] in ["add", "remove"]:
        print("This operation requires administrator privileges.")
        restart_with_admin()

    args = parser.parse_args()

    if args.action == "add":
        add_to_hosts(args.domain, args.ip)
    elif args.action == "remove":
        remove_from_hosts(args.domain, args.ip)
    elif args.action == "check":
        exists = check_domain_in_hosts(args.domain, args.ip)
        status = "exists" if exists else "does not exist"
        print(f"Entry for '{args.domain}' {status} in hosts file.")
