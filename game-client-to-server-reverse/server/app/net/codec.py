"""app.net.codec —— 帧编解码（对应协议第 [2][4][5] 层）

链路（出站）: payload -> [压缩] -> [加密] -> [长度头 + opcode] -> bytes
链路（入站）: bytes -> 拆长度/opcode -> [解密] -> [解压] -> payload
"""
from __future__ import annotations

import struct
import zlib
import gzip
import json

from .crypto import CryptoBase, build_crypto


class CodecError(Exception):
    pass


class Codec:
    def __init__(self, frame_cfg: dict, crypto_cfg: dict, compress_cfg: dict,
                 serialize_cfg: dict, max_frame: int = 1 << 20):
        self.frame = frame_cfg
        self.compress_cfg = compress_cfg
        self.serialize_cfg = serialize_cfg
        self.max_frame = max_frame
        self.crypto: CryptoBase = build_crypto(crypto_cfg)

        self.len_size = int(frame_cfg.get("length_size", 4))
        self.len_endian = frame_cfg.get("length_endian", "big")
        self.len_fmt = (">" if self.len_endian == "big" else "<") + {1: "B", 2: "H", 4: "I"}[self.len_size]
        self.len_includes_self = bool(frame_cfg.get("length_includes_self", False))
        self.op_size = int(frame_cfg.get("opcode_size", 1))
        self.op_endian = frame_cfg.get("opcode_endian", "little")
        self.op_fmt = ("<" if self.op_endian == "little" else ">") + {1: "B", 2: "H", 4: "I"}[max(self.op_size, 1)]

    # ---------- 压缩 ----------
    def _compress(self, data: bytes) -> bytes:
        if not self.compress_cfg.get("enabled"):
            return data
        if len(data) < int(self.compress_cfg.get("min_size", 256)):
            return data
        algo = self.compress_cfg.get("algorithm", "zlib")
        if algo == "zlib":
            return zlib.compress(data)
        if algo == "gzip":
            return gzip.compress(data)
        try:
            import lz4.frame as lz4f
            return lz4f.compress(data)
        except ImportError:
            return zlib.compress(data)

    def _decompress(self, data: bytes) -> bytes:
        if not self.compress_cfg.get("enabled"):
            return data
        algo = self.compress_cfg.get("algorithm", "zlib")
        if algo == "gzip" or data[:2] == b"\x1f\x8b":
            return gzip.decompress(data)
        if algo == "lz4":
            try:
                import lz4.frame as lz4f
                return lz4f.decompress(data)
            except Exception:
                pass
        try:
            return zlib.decompress(data)
        except zlib.error:
            return data

    # ---------- 组帧 ----------
    def encode(self, opcode: int, payload: bytes) -> bytes:
        body = self._compress(payload)
        body = self.crypto.encrypt(body)

        inner = b""
        if self.op_size > 0:
            inner += struct.pack(self.op_fmt, opcode)
        inner += body

        n = len(inner)
        if self.len_includes_self:
            n += self.len_size
        header = struct.pack(self.len_fmt, n)
        return header + inner

    def decode_head(self, head: bytes):
        """返回 (frame_len, opcode, body_or_None)"""
        if len(head) < self.len_size:
            raise CodecError("head too short")
        (n,) = struct.unpack(self.len_fmt, head[:self.len_size])
        if self.len_includes_self:
            n -= self.len_size
        if n <= 0 or n > self.max_frame:
            raise CodecError(f"bad frame len {n}")
        rest = head[self.len_size:]
        need = n - len(rest)  # 还需读取的 body 字节
        return n, rest, need

    def parse(self, inner: bytes):
        """inner = opcode + encrypted(compressed(payload))"""
        if self.op_size > 0:
            op_len = 1 if self.op_size <= 1 else self.op_size
            opcode = struct.unpack(self.op_fmt, inner[:op_len])[0]
            body = inner[op_len:]
        else:
            opcode = 0
            body = inner
        body = self.crypto.decrypt(body)
        body = self._decompress(body)
        return opcode, body

    # ---------- 序列化 ----------
    def serialize(self, obj) -> bytes:
        fmt = self.serialize_cfg.get("format", "binary")
        if fmt == "json":
            return json.dumps(obj, ensure_ascii=False).encode("utf-8")
        if fmt == "protobuf":
            # 使用已编译的 pb 类：obj.SerializeToString()
            return obj.SerializeToString()
        # binary：按 fields 定义打包 dict
        fields = self.serialize_cfg.get("fields", [])
        if not fields:
            if isinstance(obj, (bytes, bytearray)):
                return bytes(obj)
            return b""
        parts = []
        for fdef in fields:
            name = fdef["name"]
            parts.append(_pack_field(fdef, obj.get(name)))
        return b"".join(parts)

    def deserialize(self, data: bytes) -> dict:
        fmt = self.serialize_cfg.get("format", "binary")
        if fmt == "json":
            return json.loads(data.decode("utf-8"))
        fields = self.serialize_cfg.get("fields", [])
        out = {}
        off = 0
        for fdef in fields:
            val, off = _unpack_field(fdef, data, off)
            out[fdef["name"]] = val
        return out


_TYPE_MAP = {
    "u8": ("B", 1), "i8": ("b", 1),
    "u16": ("H", 2), "i16": ("h", 2),
    "u32": ("I", 4), "i32": ("i", 4),
    "u64": ("Q", 8), "i64": ("q", 8),
    "f32": ("f", 4), "f64": ("d", 8),
}


def _pack_field(fdef: dict, val) -> bytes:
    t = fdef.get("type", "u8")
    if t in _TYPE_MAP:
        fmt, _ = _TYPE_MAP[t]
        return struct.pack("<" + fmt, val if val is not None else 0)
    if t == "bytes":
        n = int(fdef.get("size", 0))
        b = bytes(val or b"")
        return b[:n].ljust(n, b"\x00")
    if t == "str":
        n = int(fdef.get("size", 0))
        raw = str(val or "").encode("utf-8")
        if n:
            return raw[:n].ljust(n, b"\x00")
        return struct.pack("<I", len(raw)) + raw  # 长度前缀字符串
    raise ValueError(f"未知字段类型 {t}")


def _unpack_field(fdef: dict, data: bytes, off: int):
    t = fdef.get("type", "u8")
    if t in _TYPE_MAP:
        fmt, sz = _TYPE_MAP[t]
        val = struct.unpack_from("<" + fmt, data, off)[0]
        return val, off + sz
    if t == "bytes":
        n = int(fdef.get("size", 0))
        return data[off:off + n], off + n
    if t == "str":
        n = int(fdef.get("size", 0))
        if n:
            raw = data[off:off + n].split(b"\x00", 1)[0]
            return raw.decode("utf-8", "replace"), off + n
        (ln,) = struct.unpack_from("<I", data, off)
        off += 4
        raw = data[off:off + ln]
        return raw.decode("utf-8", "replace"), off + ln
    raise ValueError(f"未知字段类型 {t}")