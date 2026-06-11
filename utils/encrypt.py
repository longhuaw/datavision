"""
Encryption utilities for password hashing, token generation, and sensitive data masking.

Uses passlib with bcrypt for password hashing.
"""

import secrets
from typing import Dict

from passlib.context import CryptContext

# ---------------------------------------------------------------------------
# bcrypt context – configured once and reused
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt and return the hash string."""
    if not password:
        raise ValueError("password must not be empty")
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Returns True when the password matches the hash, False otherwise.
    Handles malformed / empty hashes gracefully.
    """
    if not password or not hashed:
        return False
    try:
        valid, _ = _pwd_context.verify_and_update(password, hashed)
        return valid
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------
def generate_token(length: int = 32) -> str:
    """Generate a cryptographically-random URL-safe token string.

    Parameters
    ----------
    length : int
        Number of random *bytes* to generate.  The returned string will be ~4/3
        longer due to base64-url encoding (no padding).  Default is 32 bytes.
    """
    return secrets.token_urlsafe(length)


# ---------------------------------------------------------------------------
# Sensitive value masking
# ---------------------------------------------------------------------------
_DEFAULT_MASK_KEYS = {"password", "secret", "api_key"}


def mask_sensitive(
    config: Dict,
    keys: set | list | tuple | None = None,
) -> Dict:
    """Return a shallow copy of *config* with sensitive values replaced by
    ``"***"``.

    Keys are matched case-insensitively and the masking is performed on the
    **first two nesting levels** only (values that are dicts are searched
    recursively up to one additional level deep).

    Parameters
    ----------
    config : dict
        Configuration dictionary to mask.
    keys : set | list | tuple | None
        Key names whose values should be masked.  Defaults to
        ``{"password", "secret", "api_key"}`` when omitted or ``None``.

    Returns
    -------
    dict
        A new dict with sensitive values replaced.
    """
    if keys is None:
        keys = _DEFAULT_MASK_KEYS

    # Normalise keys to a set of lower-case strings for case-insensitive matching.
    targets = {k.lower() for k in keys}

    result = {}
    for k, v in config.items():
        if k.lower() in targets:
            result[k] = "***"
        elif isinstance(v, dict):
            result[k] = {
                k2: "***" if k2.lower() in targets else v2 for k2, v2 in v.items()
            }
        else:
            result[k] = v
    return result
