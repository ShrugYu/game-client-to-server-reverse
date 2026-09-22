"""app.proto.messages —— 消息结构

两种用法：
  1) binary：用 codec 的 fields 配置自动打包（简单场景）
  2) 结构化：每个消息实现 encode(codec)/decode(body, codec)（复杂场景，推荐）
"""
from __future__ import annotations

import struct


class Message:
    OPCODE = 0

    def encode(self, codec) -> bytes:
        return b""

    @classmethod
    def decode(cls, body: bytes, codec):
        return cls()


# ---------- 握手 ----------
class HandshakeReq(Message):
    OPCODE = 0x0001

    def __init__(self, version: str = "", nonce: int = 0):
        self.version = version
        self.nonce = nonce

    def encode(self, codec):
        v = self.version.encode("utf-8")
        return struct.pack("<H", len(v)) + v + struct.pack("<I", self.nonce)

    @classmethod
    def decode(cls, body, codec):
        (n,) = struct.unpack_from("<H", body, 0)
        ver = body[2:2 + n].decode("utf-8", "replace")
        (nonce,) = struct.unpack_from("<I", body, 2 + n)
        return cls(ver, nonce)


class HandshakeRes(Message):
    OPCODE = 0x0002

    def __init__(self, code: int = 0, server_ver: str = "1.0.0", session_key: bytes = b""):
        self.code = code
        self.server_ver = server_ver
        self.session_key = session_key

    def encode(self, codec):
        v = self.server_ver.encode("utf-8")
        return (struct.pack("<B", self.code) + struct.pack("<H", len(v)) + v
                + struct.pack("<H", len(self.session_key)) + self.session_key)


# ---------- 登录 ----------
class LoginReq(Message):
    OPCODE = 0x0101

    def __init__(self, username: str = "", password: str = ""):
        self.username = username
        self.password = password

    def encode(self, codec):
        u = self.username.encode("utf-8")
        p = self.password.encode("utf-8")
        return struct.pack("<H", len(u)) + u + struct.pack("<H", len(p)) + p

    @classmethod
    def decode(cls, body, codec):
        (n,) = struct.unpack_from("<H", body, 0)
        u = body[2:2 + n].decode("utf-8", "replace")
        (m,) = struct.unpack_from("<H", body, 2 + n)
        p = body[4 + n:4 + n + m].decode("utf-8", "replace")
        return cls(u, p)


class LoginRes(Message):
    OPCODE = 0x0102

    def __init__(self, code: int = 0, token: str = "", uid: int = 0):
        self.code = code
        self.token = token
        self.uid = uid

    def encode(self, codec):
        t = self.token.encode("utf-8")
        return (struct.pack("<B", self.code) + struct.pack("<Q", self.uid)
                + struct.pack("<H", len(t)) + t)


# ---------- 角色列表 ----------
class CharInfo:
    def __init__(self, cid: int, name: str, level: int = 1, job: int = 0):
        self.cid = cid
        self.name = name
        self.level = level
        self.job = job

    def encode(self) -> bytes:
        n = self.name.encode("utf-8")
        return (struct.pack("<Q", self.cid) + struct.pack("<H", len(n)) + n
                + struct.pack("<HB", self.level, self.job))


class CharListRes(Message):
    OPCODE = 0x0202

    def __init__(self, chars: list[CharInfo] | None = None):
        self.chars = chars or []

    def encode(self, codec):
        out = struct.pack("<H", len(self.chars))
        for c in self.chars:
            out += c.encode()
        return out


class CharCreateReq(Message):
    OPCODE = 0x0203

    def __init__(self, name: str = "", job: int = 0):
        self.name = name
        self.job = job

    def encode(self, codec):
        n = self.name.encode("utf-8")
        return struct.pack("<H", len(n)) + n + struct.pack("<B", self.job)

    @classmethod
    def decode(cls, body, codec):
        (n,) = struct.unpack_from("<H", body, 0)
        name = body[2:2 + n].decode("utf-8", "replace")
        (job,) = struct.unpack_from("<B", body, 2 + n)
        return cls(name, job)


class CharCreateRes(Message):
    OPCODE = 0x0204

    def __init__(self, code: int = 0, char: CharInfo | None = None):
        self.code = code
        self.char = char

    def encode(self, codec):
        out = struct.pack("<B", self.code)
        if self.char:
            out += self.char.encode()
        return out


class CharSelectReq(Message):
    OPCODE = 0x0205

    def __init__(self, cid: int = 0):
        self.cid = cid

    def encode(self, codec):
        return struct.pack("<Q", self.cid)

    @classmethod
    def decode(cls, body, codec):
        (cid,) = struct.unpack_from("<Q", body, 0)
        return cls(cid)


class CharSelectRes(Message):
    OPCODE = 0x0206

    def __init__(self, code: int = 0, cid: int = 0, scene: int = 1):
        self.code = code
        self.cid = cid
        self.scene = scene

    def encode(self, codec):
        return struct.pack("<BQH", self.code, self.cid, self.scene)


# ---------- 错误 ----------
class ErrorNtf(Message):
    OPCODE = 0x7F01

    def __init__(self, code: int = 99, text: str = ""):
        self.code = code
        self.text = text

    def encode(self, codec):
        t = self.text.encode("utf-8")
        return struct.pack("<BH", self.code, len(t)) + t


# ---------- 邮件 ----------
class MailInfo:
    """邮件条目。attachments 形如 [{"type":"gold","id":0,"count":1000}]"""
    def __init__(self, mid: int, title: str, content: str, attachments=None,
                 claimed: bool = False, read: bool = False, ts: int = 0):
        self.mid = mid
        self.title = title
        self.content = content
        self.attachments = attachments or []
        self.claimed = claimed
        self.read = read
        self.ts = ts

    def _att_blob(self) -> bytes:
        # type(1B) id(4B) count(4B) 逐条
        out = struct.pack("<H", len(self.attachments))
        for a in self.attachments:
            t = {"gold": 1, "diamond": 2, "item": 3}.get(a.get("type"), 0)
            out += struct.pack("<BI I", t & 0xFF, int(a.get("id", 0)),
                               int(a.get("count", 0)))
        return out

    def encode(self) -> bytes:
        t = self.title.encode("utf-8")
        c = self.content.encode("utf-8")
        return (struct.pack("<Q", self.mid)
                + struct.pack("<B", (1 if self.claimed else 0) | (2 if self.read else 0))
                + struct.pack("<I", self.ts)
                + struct.pack("<H", len(t)) + t
                + struct.pack("<H", len(c)) + c
                + self._att_blob())


class MailListRes(Message):
    OPCODE = 0x0402

    def __init__(self, mails: list[MailInfo] | None = None):
        self.mails = mails or []

    def encode(self, codec):
        out = struct.pack("<H", len(self.mails))
        for m in self.mails:
            out += m.encode()
        return out


class MailOpReq(Message):
    """通用邮件操作请求：mid(u64)"""
    def __init__(self, mid: int = 0):
        self.mid = mid

    def encode(self, codec):
        return struct.pack("<Q", self.mid)

    @classmethod
    def decode(cls, body, codec):
        (mid,) = struct.unpack_from("<Q", body, 0)
        return cls(mid)


class MailOpRes(Message):
    def __init__(self, code: int = 0, mid: int = 0):
        self.code = code
        self.mid = mid

    def encode(self, codec):
        return struct.pack("<BQ", self.code, self.mid)


class MailNewNtf(Message):
    OPCODE = 0x0407

    def __init__(self, mail: MailInfo | None = None):
        self.mail = mail

    def encode(self, codec):
        return self.mail.encode() if self.mail else b""


# ---------- 充值 / 支付 ----------
class PayReq(Message):
    """客户端发起购买。product_id 来自客户端商品表。"""
    OPCODE = 0x0503

    def __init__(self, product_id: str = "", order_no: str = "", pay_type: int = 0):
        self.product_id = product_id
        self.order_no = order_no
        self.pay_type = pay_type

    def encode(self, codec):
        p = self.product_id.encode("utf-8")
        o = self.order_no.encode("utf-8")
        return (struct.pack("<H", len(p)) + p
                + struct.pack("<H", len(o)) + o
                + struct.pack("<B", self.pay_type))

    @classmethod
    def decode(cls, body, codec):
        (n,) = struct.unpack_from("<H", body, 0)
        pid = body[2:2 + n].decode("utf-8", "replace")
        (m,) = struct.unpack_from("<H", body, 2 + n)
        order = body[4 + n:4 + n + m].decode("utf-8", "replace")
        (pt,) = struct.unpack_from("<B", body, 4 + n + m)
        return cls(pid, order, pt)


class PayRes(Message):
    OPCODE = 0x0504

    def __init__(self, code: int = 0, product_id: str = "", order_no: str = "",
                 currency: int = 0, granted: int = 0, by_mail: bool = False):
        self.code = code
        self.product_id = product_id
        self.order_no = order_no
        self.currency = currency       # 1=gold 2=diamond
        self.granted = granted         # 实际发放数量
        self.by_mail = by_mail         # 走邮件发放

    def encode(self, codec):
        p = self.product_id.encode("utf-8")
        o = self.order_no.encode("utf-8")
        return (struct.pack("<B", self.code)
                + struct.pack("<B", self.currency)
                + struct.pack("<I", self.granted)
                + struct.pack("<B", 1 if self.by_mail else 0)
                + struct.pack("<H", len(p)) + p
                + struct.pack("<H", len(o)) + o)


class PayProductListRes(Message):
    OPCODE = 0x0502

    def __init__(self, products: list[tuple] | None = None):
        # (product_id, name, price_cents, currency, amount)
        self.products = products or []

    def encode(self, codec):
        out = struct.pack("<H", len(self.products))
        for pid, name, price, cur, amt in self.products:
            p = pid.encode("utf-8")
            n = name.encode("utf-8")
            out += (struct.pack("<H", len(p)) + p
                    + struct.pack("<H", len(n)) + n
                    + struct.pack("<I", price)
                    + struct.pack("<BI", cur, amt))
        return out