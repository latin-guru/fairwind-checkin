"""Small double-submit CSRF guard: a random token in a cookie and in a hidden form field, signed with SECRET_KEY."""

import hashlib
import hmac
import secrets

COOKIE = "fw_csrf"


def new_token() -> str:
    return secrets.token_urlsafe(24)


def sign(token: str, secret: str) -> str:
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def valid(cookie_token: str | None, form_value: str | None, secret: str) -> bool:
    if not cookie_token or not form_value:
        return False
    return hmac.compare_digest(sign(cookie_token, secret), form_value)
