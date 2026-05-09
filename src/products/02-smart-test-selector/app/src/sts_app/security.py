"""HMAC signature verification for incoming GitHub webhooks.

GitHub signs every webhook delivery with HMAC-SHA256 using the secret
configured in the webhook settings. The signature arrives in the
`X-Hub-Signature-256` header in the form `sha256=<hex>`.

This module is deliberately minimal - we use `hmac.compare_digest` for
constant-time comparison and accept ONLY the `sha256=` prefix.

If the configured secret is None (dev mode), `verify` returns True
unconditionally and logs a warning at the call site.
"""

from __future__ import annotations

import hashlib
import hmac

# Header name GitHub uses for the SHA-256 signature
SIGNATURE_HEADER = "X-Hub-Signature-256"
SIGNATURE_PREFIX = "sha256="


def compute_signature(secret: str, payload: bytes) -> str:
    """Return the expected `sha256=<hex>` value for the given payload."""
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return SIGNATURE_PREFIX + mac.hexdigest()


def verify(secret: str | None, payload: bytes, signature_header: str | None) -> bool:
    """Constant-time-compare the signature header against the expected value.

    Args:
        secret: The webhook secret. If None, verification is skipped.
        payload: Raw request body bytes (do NOT use parsed JSON - the
                 byte order matters for HMAC).
        signature_header: The value of `X-Hub-Signature-256` from the request.

    Returns:
        True if the signature matches OR if secret is None (dev mode).
        False if the signature is missing, malformed, or doesn't match.
    """
    if secret is None:
        # Dev mode - caller should log a warning.
        return True
    if not signature_header or not signature_header.startswith(SIGNATURE_PREFIX):
        return False
    expected = compute_signature(secret, payload)
    return hmac.compare_digest(expected, signature_header)
