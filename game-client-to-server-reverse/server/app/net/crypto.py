"""app.net.crypto —— 可插拔加解密层（对应协议第 [3] 层）

从客户端逆向出的算法在这里 1:1 复现。
支持：xor（单字节/多字节循环）、rc4、aes(cbc/ecb)。
密钥来源：config.crypto.key 或握手协商（per_connection）。
"""
from __future__ import annotations

import struct


def _key_bytes(key) -> bytes:
    if isinstance(key, bytes):
        return key
    if isinstance(key, str):
        s = key.strip()
        if s.startswith("0x") or s.startswith("0X"):
            return bytes.fromhex(s[2:])
        # 尝试纯 hex
        try:
            return bytes.fromhex(s)
        except ValueError:
            return s.encode("utf-8")
    return bytes(key)


class CryptoBase:
    def encrypt(self, data: bytes) -> bytes:
        return data

    def decrypt(self, data: bytes) -> bytes:
        return data


class XorCrypto(CryptoBase):
    """循环 XOR —— 游戏里最常见的轻量混淆"""

    def __init__(self, key):
        self.key = _key_bytes(key) or b"\x00"

    def _x(self, data: bytes) -> bytes:
        k = self.key
        n = len(k)
        return bytes(b ^ k[i % n] for i, b in enumerate(data))

    def encrypt(self, data: bytes) -> bytes:
        return self._x(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._x(data)


class Rc4Crypto(CryptoBase):
    def __init__(self, key):
        self.key = _key_bytes(key) or b"\x00"

    def _ksa(self):
        key = self.key
        S = list(range(256))
        j = 0
        for i in range(256):
            j = (j + S[i] + key[i % len(key)]) & 0xFF
            S[i], S[j] = S[j], S[i]
        return S

    def _crypt(self, data: bytes) -> bytes:
        S = self._ksa()
        i = j = 0
        out = bytearray()
        for b in data:
            i = (i + 1) & 0xFF
            j = (j + S[i]) & 0xFF
            S[i], S[j] = S[j], S[i]
            out.append(b ^ S[(S[i] + S[j]) & 0xFF])
        return bytes(out)

    def encrypt(self, data: bytes) -> bytes:
        return self._crypt(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._crypt(data)


class AesCrypto(CryptoBase):
    """AES-CBC/ECB（需要 cryptography 包）"""

    def __init__(self, key, iv=b"\x00" * 16, mode="cbc"):
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        except ImportError as e:  # noqa
            raise RuntimeError("AES 需要安装 cryptography: pip install cryptography") from e
        self._key = _key_bytes(key)
        self._iv = iv if isinstance(iv, bytes) else _key_bytes(iv)
        self._mode = mode
        if mode == "cbc":
            self._cipher = Cipher(algorithms.AES(self._key), modes.CBC(self._iv))
        else:
            self._cipher = Cipher(algorithms.AES(self._key), modes.ECB())

    def encrypt(self, data: bytes) -> bytes:
        from cryptography.hazmat.primitives.padding import PKCS7
        pad = PKCS7(128).padder()
        data = pad.update(data) + pad.finalize()
        enc = self._cipher.encryptor()
        return enc.update(data) + enc.finalize()

    def decrypt(self, data: bytes) -> bytes:
        from cryptography.hazmat.primitives.padding import PKCS7
        dec = self._cipher.decryptor()
        out = dec.update(data) + dec.finalize()
        unpad = PKCS7(128).unpadder()
        return unpad.update(out) + unpad.finalize()


def build_crypto(cfg: dict, key_override=None) -> CryptoBase:
    """根据配置构建加解密器；key_override 用于 per_connection 协商"""
    if not cfg.get("enabled"):
        return CryptoBase()
    algo = str(cfg.get("algorithm", "xor")).lower()
    key = key_override if key_override is not None else cfg.get("key", "")
    if algo == "xor":
        return XorCrypto(key)
    if algo == "rc4":
        return Rc4Crypto(key)
    if algo == "aes":
        return AesCrypto(key)
    raise ValueError(f"未知加密算法: {algo}")