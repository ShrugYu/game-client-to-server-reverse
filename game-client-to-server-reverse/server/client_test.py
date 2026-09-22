#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试客户端 / 联调工具

用途：
  1. 验证服务端能跑通「握手 → 登录 → 建角 → 选角 → 进场景 → 移动」
  2. 作为"客户端协议行为的参照实现"，反向核对你的逆向结论
  3. 重放抓包数据（--replay）

用法:
  python client_test.py --host 127.0.0.1 --port 8888 --user test --pass 123456
"""
from __future__ import annotations

import argparse
import asyncio
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import Config                      # noqa: E402
from app.net.codec import Codec                    # noqa: E402
from app.proto.opcodes import OP                   # noqa: E402
from app.proto.messages import (                   # noqa: E402
    HandshakeReq, LoginReq, CharCreateReq, CharSelectReq,
)


async def recv_frame(reader, codec):
    ls = codec.len_size
    head = await reader.readexactly(ls)
    n, rest, need = codec.decode_head(head)
    inner = rest
    while need > 0:
        chunk = await reader.readexactly(need)
        inner += chunk
        need -= len(chunk)
    return codec.parse(inner)


async def send(reader, writer, codec, opcode, payload=b""):
    writer.write(codec.encode(opcode, payload))
    await writer.drain()


async def run(args):
    cfg = Config.load(args.config)
    codec = Codec(cfg.get("frame", {}), cfg.get("crypto", {}),
                  cfg.get("compress", {}), cfg.get("serialize", {}),
                  int(cfg.get("server.max_frame", 1 << 20)))

    reader, writer = await asyncio.open_connection(args.host, args.port)
    print(f"[+] connected {args.host}:{args.port}")

    # 1) 握手
    await send(reader, writer, codec, OP.HANDSHAKE_REQ,
               HandshakeReq(cfg.get("game.expected_version", "1.0.0"), 0x1234).encode(codec))
    op, body = await recv_frame(reader, codec)
    print(f"[<] handshake res: op=0x{op:04X} code={body[0] if body else '?'}")

    # 2) 登录
    await send(reader, writer, codec, OP.LOGIN_REQ,
               LoginReq(args.user, args.password).encode(codec))
    op, body = await recv_frame(reader, codec)
    print(f"[<] login res: op=0x{op:04X} code={body[0] if body else '?'}")

    # 登录后服务端会推送角色列表
    op, body = await recv_frame(reader, codec)
    print(f"[<] push: op=0x{op:04X} len={len(body)}")
    if op == OP.CHAR_LIST_RES:
        (cnt,) = struct.unpack_from("<H", body, 0)
        print(f"    char count = {cnt}")

    # 3) 创建角色
    cname = args.name
    await send(reader, writer, codec, OP.CHAR_CREATE_REQ,
               CharCreateReq(cname, 0).encode(codec))
    op, body = await recv_frame(reader, codec)
    print(f"[<] char create: op=0x{op:04X} code={body[0] if body else '?'}")
    cid = None
    if op == OP.CHAR_CREATE_RES and body[0] == 0:
        (cid,) = struct.unpack_from("<Q", body, 1)
        print(f"    created cid={cid}")

    # 可能又收到一次角色列表推送
    try:
        op, body = await asyncio.wait_for(recv_frame(reader, codec), timeout=1)
        print(f"[<] push: op=0x{op:04X} len={len(body)}")
        if op == OP.CHAR_LIST_RES:
            (cnt,) = struct.unpack_from("<H", body, 0)
            for i in range(cnt):
                off = 2 + i * 0  # 简单起见只读第一个
                break
    except asyncio.TimeoutError:
        pass

    if cid is None:
        print("[!] no char created; try different --name")
        writer.close()
        return

    # 4) 选角
    await send(reader, writer, codec, OP.CHAR_SELECT_REQ,
               CharSelectReq(cid).encode(codec))
    op, body = await recv_frame(reader, codec)
    print(f"[<] char select: op=0x{op:04X} code={body[0] if body else '?'}")

    # 5) 进场景
    await send(reader, writer, codec, OP.ENTER_SCENE_REQ, b"")
    op, body = await recv_frame(reader, codec)
    print(f"[<] enter scene: op=0x{op:04X} len={len(body)}")

    # 6) 移动
    await send(reader, writer, codec, OP.MOVE_REQ, struct.pack("<II", 110, 120))
    print("[+] move sent")
    await asyncio.sleep(0.3)

    # 7) 心跳
    await send(reader, writer, codec, OP.HEARTBEAT_REQ, b"ping")
    op, body = await recv_frame(reader, codec)
    print(f"[<] heartbeat echo: op=0x{op:04X} {body!r}")

    print("[+] full flow OK")
    writer.close()
    await writer.wait_closed()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--user", default="tester")
    ap.add_argument("--password", default="123456")
    ap.add_argument("--name", default="Hero01")
    ap.add_argument("--config", default="./config/config.yaml")
    args = ap.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()