import hmac
import hashlib


def make_signature(secret: str, *parts: str) -> str:
    message = ":".join(parts).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(secret: str, signature: str, *parts: str) -> bool:
    expected = make_signature(secret, *parts)
    return hmac.compare_digest(expected, signature)
