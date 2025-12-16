from __future__ import annotations

import logging
import os
import tempfile
import time

from OpenSSL import crypto

logger = logging.getLogger(__name__)


def create_self_signed_cert(domain: str) -> tuple[str | None, str | None]:
    """
    Create a self-signed SSL certificate for the given domain.

    Args:
        domain (str): Domain to include in the certificate.

    Returns:
        tuple: (cert_path, key_path) or (None, None) on failure.
    """
    try:
        # Create a key pair and generate a 2048-bit RSA key for the certificate
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 2048)

        # Create a self-signed certificate, set the subject
        cert = crypto.X509()
        cert.get_subject().C = "US"
        cert.get_subject().ST = "State"
        cert.get_subject().L = "City"
        cert.get_subject().O = "Organization"
        cert.get_subject().OU = "Organizational Unit"
        cert.get_subject().CN = domain

        # Add SubjectAltName for the domain and its www version
        san = crypto.X509Extension(
            b"subjectAltName",
            False,
            f"DNS:{domain}, DNS:www.{domain}".encode(),
        )
        cert.add_extensions([san])

        cert.set_serial_number(int(time.time() * 1000))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.sign(key, "sha256")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".crt") as cert_file:
            cert_file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
            cert_path = cert_file.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as key_file:
            key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
            key_path = key_file.name

        return cert_path, key_path
    except Exception as exc:
        logger.exception("Error creating self-signed certificate for %s: %s", domain, exc)
        return None, None


def cleanup_cert_files(cert_file: str | None, key_file: str | None) -> None:
    """Remove temporary certificate files if they exist."""
    for path in (cert_file, key_file):
        try:
            if path and os.path.exists(path):
                os.unlink(path)
        except Exception as exc:
            logger.warning("Error cleaning up certificate file '%s': %s", path, exc)
