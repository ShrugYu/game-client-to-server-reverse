#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证服务端人机（假玩家 / Bot）。

流程：
  登录 → 建角/选角（进入场景）→ 通过 GM 生成人机
  → 监听下行包，统计 Bot 的 MOVE_NTF → 断言能看到假玩家

用法：
  python test_bots.py --host 127.0.0.1 --port 8888 --gm-port 9900
"""
import argparse, asyncio, socket, struct, sys, os, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import Config
from app.net.codec import Codec
from app.proto.opcodes import OP
from app.proto.messages import HandshakeReq, LoginReq, CharCreateReq, CharSelectReq

BOT_ID_MIN = 0x40000000          # 与 bots.py 中的约定一致


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
    for _ in range(maxn):
        op, body = await asyncio.wait_for(recv(reader, codec), timeout=3)
        if op == want:
            return body
    raise RuntimeError(f"opcode 0x{want:04X} not received")


async def send(writer, codec, op, payload=b""):
    writer.write(codec.encode(op, payload))
    await writer.drain()


async def gm(port, cmd, timeout=3):
    """向 GM 控制台发一条命令"""
    r, w = await asyncio.open_connection("127.0.0.1", port)
    await asyncio.sleep(0.2)
    await r.read(4096)                      # 欢迎语
    w.write((cmd + "\n").encode())
    await w.drain()
    data = await asyncio.wait_for(r.read(4096), timeout=timeout)
    w.close()
    return data.decode("utf-8", "replace").strip()


async def run(a):
    cfg = Config.load(a.config)
    codec = Codec(cfg.get("frame", {}), cfg.get("crypto", {}),
                  cfg.get("compress", {}), cfg.get("serialize", {}),
                  int(cfg.get("server.max_frame", 1 << 20)))
    r, w = await asyncio.open_connection(a.host, a.port)

    # 1) 握手 / 登录
    await send(w, codec, OP.HANDSHAKE_REQ,
               HandshakeReq(cfg.get("game.expected_version", "1.0.0"), 1).encode(codec))
    await recv_op(r, codec, OP.HANDSHAKE_RES)
    await send(w, codec, OP.LOGIN_REQ, LoginReq(a.user, a.password).encode(codec))
    await recv_op(r, codec, OP.LOGIN_RES)

    # 2) 建角 / 选角
    body = await recv_op(r, codec, OP.CHAR_LIST_RES)
    cnt = struct.unpack_from("<H", body, 0)[0]
    cid = struct.unpack_from("<Q", body, 2)[0] if cnt > 0 else None
    if cid is None:
        await send(w, codec, OP.CHAR_CREATE_REQ, CharCreateReq(a.name, 0).encode(codec))
        body = await recv_op(r, codec, OP.CHAR_CREATE_RES)
        cid = struct.unpack_from("<Q", body, 1)[0]
    print(f"[+] cid = {cid}")

    await send(w, codec, OP.CHAR_SELECT_REQ, CharSelectReq(cid).encode(codec))
    await recv_op(r, codec, OP.CHAR_SELECT_RES)
    print("[+] entered scene (IN_GAME)")
    print(f"[+] scene = {struct.unpack_from('<H', (await _enter_scene(w, r, codec)), 0)[0]}")

    # 3) GM 生成人机
    print("[*] GM:", await gm(a.gm_port, f"bots spawn {a.scene} {a.count} {a.difficulty}"))
    print("[*] GM:", await gm(a.gm_port, "bots"))

    # 4) 监听下行，统计 Bot 的 MOVE_NTF
    seen = {}
    deadline = time.time() + a.listen
    while time.time() < deadline:
        try:
            op, body = await asyncio.wait_for(recv(r, codec), timeout=1)
        except asyncio.TimeoutError:
            continue
        if op == OP.MOVE_NTF and len(body) >= 16:
            bid, x, y = struct.unpack_from("<QII", body, 0)
            if bid >= BOT_ID_MIN:
                seen.setdefault(bid, []).append((x, y))

    print(f"[+] 收到 {len(seen)} 个不同的 Bot 实体：")
    for bid, pos in list(seen.items())[:8]:
        print(f"    bot 0x{bid:08X}: {len(pos)} 次移动, 最新 ({pos[-1][0]},{pos[-1][1]})")

    assert seen, "[x] 没有收到任何 Bot 的 MOVE_NTF —— 人机未生效"

    # 5) 清理
    print("[*] GM:", await gm(a.gm_port, "bots clear"))
    print("[+] bots flow OK")
    w.close()
    await w.wait_closed()


async def _enter_scene(w, r, codec):
    await send(w, codec, OP.ENTER_SCENE_REQ, b"")
    return await recv_op(r, codec, OP.ENTER_SCENE_RES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--gm-port", type=int, default=9900)
    ap.add_argument("--user", default="botfan")
    ap.add_argument("--password", default="123456")
    ap.add_argument("--name", default="BotWatcher")
    ap.add_argument("--scene", type=int, default=1)
    ap.add_argument("--count", type=int, default=4)
    ap.add_argument("--difficulty", default="normal")
    ap.add_argument("--listen", type=float, default=3.0)
    ap.add_argument("--config", default="./config/config.yaml")
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()