"""app.logic.security —— 密码哈希 / token 签发校验 / 频率限制"""
from __future__ import annotations

import hashlib
import hmac
import json
import base64
import time


def hash_password(password: str, salt: str = "gsrv") -> str:
    """生产请换 bcrypt/argon2；此处用 PBKDF2 保证开箱即用"""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex()


def verify_password(password: str, stored: str, salt: str = "gsrv") -> bool:
    return hmac.compare_digest(hash_password(password, salt), stored)


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def sign_token(uid: int, secret: str, ttl: int = 86400) -> str:
    payload = {"uid": uid, "exp": int(time.time()) + ttl, "iat": int(time.time())}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_token(token: str, secret: str) -> dict | None:
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None
    expect = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expect):
        return None
    try:
        payload = json.loads(_b64d(body))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


class RateLimiter:
    """简单滑动窗口限流（单进程内存版）"""

    def __init__(self, limit: int = 10, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        arr = [t for t in self._hits.get(key, []) if now - t < self.window]
        if len(arr) >= self.limit:
            self._hits[key] = arr
            return False
        arr.append(now)
        self._hits[key] = arr
        return True