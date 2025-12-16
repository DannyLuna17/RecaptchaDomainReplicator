"""Just constants."""

from __future__ import annotations

# Domains that should NOT be redirected because reCAPTCHA scripts are loaded from them.
RECAPTCHA_API_DOMAINS: frozenset[str] = frozenset({"google.com", "recaptcha.net"})

# Windows hosts file path
HOSTS_FILE_PATH: str = r"C:\Windows\System32\drivers\etc\hosts"

# Markers used to identify entries added in the hosts file
HOSTS_MARKER: str = " # Added by recaptcha-domain-replicator"
HOSTS_MARKERS: tuple[str, ...] = (
    "# Added by recaptcha-domain-replicator",
    "# Added by DomainReplicator",
)

# Default server configuration
DEFAULT_SERVER_PORT: int = 8080
DEFAULT_DOWNLOAD_DIR: str = "tmp"

# Browser arguments for Chromium
CHROMIUM_ARGUMENTS: tuple[str, ...] = (
    "--no-first-run",
    "--force-color-profile=srgb",
    "--metrics-recording-only",
    "--password-store=basic",
    "--use-mock-keychain",
    "--export-tagged-pdf",
    "--no-default-browser-check",
    "--enable-features=NetworkService",
    "--disable-features=FlashDeprecationWarning",
    "--deny-permission-prompts",
    "--disable-suggestions-ui",
    "--disable-popup-blocking",
    "--hide-crash-restore-bubble",
    "--disable-translate",
)

# Token placeholder values
TOKEN_PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {
        "[No token yet]",
        "[Token expired]",
    }
)

# Server startup configuration
SERVER_STARTUP_TIMEOUT: float = 5.0
SERVER_STARTUP_CHECK_INTERVAL: float = 0.05

# Port range validation
MIN_PORT: int = 1
MAX_PORT: int = 65535
