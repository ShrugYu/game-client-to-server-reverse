#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 充值直发 + 邮件系统（opcode 感知，容忍异步推送）。

流程：
  连接 → 握手 → 登录 → 建角/选角 → 拉商品 → 充值 → 邮件(可选) → 领取
"""
import argparse, asyncio, struct, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import Config
from app.net.codec import Codec
from app.proto.opcodes import OP
from app.proto.messages import (
    HandshakeReq, LoginReq, CharCreateReq, CharSelectReq, PayReq, MailOpReq,
)


async def recv(reader, codec):
    head = await reader.readexactly(codec.len_size)
    n, rest, need = codec.decode_head(head)
    inner = rest
    while need > 0:
        c = await reader.readexactly(need)
        inner += c
        need -= len(c)
    return codec.parse(inner)


async def recv_op(reader, codec, want, maxn=8):
    """读到指定 opcode，跳过其间的异步推送"""
    for _ in range(maxn):
        op, body = await asyncio.wait_for(recv(reader, codec), timeout=3)
        if op == want:
            return body
    raise RuntimeError(f"opcode 0x{want:04X} not received")


async def send(writer, codec, op, payload=b""):
    writer.write(codec.encode(op, payload))
    await writer.drain()


async def run(a):
    cfg = Config.load(a.config)
    codec = Codec(cfg.get("frame", {}), cfg.get("crypto", {}),
                  cfg.get("compress", {}), cfg.get("serialize", {}),
                  int(cfg.get("server.max_frame", 1 << 20)))
    r, w = await asyncio.open_connection(a.host, a.port)

    await send(w, codec, OP.HANDSHAKE_REQ,
               HandshakeReq(cfg.get("game.expected_version", "1.0.0"), 1).encode(codec))
    await recv(r, codec)

    await send(w, codec, OP.LOGIN_REQ, LoginReq(a.user, a.password).encode(codec))
    body = await recv_op(r, codec, OP.LOGIN_RES)
    print("login code =", body[0])

    body = await recv_op(r, codec, OP.CHAR_LIST_RES)
    cnt = struct.unpack_from("<H", body, 0)[0]
    cid = struct.unpack_from("<Q", body, 2)[0] if cnt > 0 else None
    if cid:
        print("existing cid =", cid)
    else:
        await send(w, codec, OP.CHAR_CREATE_REQ, CharCreateReq(a.name, 0).encode(codec))
        body = await recv_op(r, codec, OP.CHAR_CREATE_RES)
        cid = struct.unpack_from("<Q", body, 1)[0]
        print("created cid =", cid, "code =", body[0])
    print("cid =", cid)

    await send(w, codec, OP.CHAR_SELECT_REQ, CharSelectReq(cid).encode(codec))
    body = await recv_op(r, codec, OP.CHAR_SELECT_RES)
    print("select code =", body[0])

    # 商品列表
    await send(w, codec, OP.PAY_PRODUCT_LIST_REQ, b"")
    body = await recv_op(r, codec, OP.PAY_PRODUCT_LIST_RES)
    pcnt = struct.unpack_from("<H", body, 0)[0]
    print("products =", pcnt)

    # 充值
    await send(w, codec, OP.PAY_REQ, PayReq(a.product, "", 0).encode(codec))
    body = await recv_op(r, codec, OP.PAY_RES)
    code = body[0]
    cur = body[1]
    granted = struct.unpack_from("<I", body, 2)[0]
    by_mail = body[6]
    print(f"PAY res: code={code} currency={cur} granted={granted} by_mail={by_mail}")

    # 邮件列表
    await send(w, codec, OP.MAIL_LIST_REQ, b"")
    body = await recv_op(r, codec, OP.MAIL_LIST_RES)
    mcnt = struct.unpack_from("<H", body, 0)[0]
    print("mail count =", mcnt)

    if mcnt > 0:
        mid = struct.unpack_from("<Q", body, 2)[0]
        await send(w, codec, OP.MAIL_CLAIM_REQ, MailOpReq(mid).encode(codec))
        body = await recv_op(r, codec, OP.MAIL_CLAIM_RES)
        print("claim code =", body[0], "mid =", struct.unpack_from("<Q", body, 1)[0])

        # 再拉一次邮件，确认已标记领取
        await send(w, codec, OP.MAIL_LIST_REQ, b"")
        body = await recv_op(r, codec, OP.MAIL_LIST_RES)
        flags = body[10] if len(body) > 10 else 0
        print("after claim flags(bit0=claimed) =", flags)

    print("[+] pay & mail flow OK")
    w.close()
    await w.wait_closed()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--user", default="payer")
    ap.add_argument("--password", default="123456")
    ap.add_argument("--name", default="PayHero")
    ap.add_argument("--product", default="com.demo.diamond_60")
    ap.add_argument("--config", default="./config/config.yaml")
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()