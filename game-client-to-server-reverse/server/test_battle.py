#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 房间 + 战斗 + 掉落 全流程。

两个客户端：A 建房 → B 加入 → B 准备 → A 开始 → 双方连续攻击 → Boss 死 → 结算掉落
用法：python test_battle.py --host 127.0.0.1 --port 8888
"""
import argparse, asyncio, struct, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import Config
from app.net.codec import Codec
from app.proto.opcodes import OP
from app.proto.messages import (HandshakeReq, LoginReq, CharCreateReq, CharSelectReq)


class Cli:
    def __init__(self, name, cfg):
        self.name = name
        self.cfg = cfg
        self.codec = Codec(cfg.get("frame", {}), cfg.get("crypto", {}),
                           cfg.get("compress", {}), cfg.get("serialize", {}),
                           int(cfg.get("server.max_frame", 1 << 20)))
        self.r = None
        self.w = None
        self.cid = 0
        self.events = []

    async def recv(self):
        head = await self.r.readexactly(self.codec.len_size)
        n, rest, need = self.codec.decode_head(head)
        inner = rest
        while need > 0:
            c = await self.r.readexactly(need)
            inner += c
            need -= len(c)
        return self.codec.parse(inner)

    async def recv_op(self, want, maxn=12):
        for _ in range(maxn):
            op, body = await asyncio.wait_for(self.recv(), timeout=4)
            self.events.append(op)
            if op == want:
                return body
        raise RuntimeError(f"{self.name}: opcode 0x{want:04X} not received")

    async def send(self, op, payload=b""):
        self.w.write(self.codec.encode(op, payload))
        await self.w.drain()

    async def connect(self, host, port, user, charname):
        self.r, self.w = await asyncio.open_connection(host, port)
        await self.send(OP.HANDSHAKE_REQ, HandshakeReq("1.0.0", 1).encode(self.codec))
        await self.recv_op(OP.HANDSHAKE_RES)
        await self.send(OP.LOGIN_REQ, LoginReq(user, "123456").encode(self.codec))
        await self.recv_op(OP.LOGIN_RES)
        body = await self.recv_op(OP.CHAR_LIST_RES)
        cnt = struct.unpack_from("<H", body, 0)[0]
        if cnt:
            self.cid = struct.unpack_from("<Q", body, 2)[0]
        else:
            await self.send(OP.CHAR_CREATE_REQ, CharCreateReq(charname, 0).encode(self.codec))
            body = await self.recv_op(OP.CHAR_CREATE_RES)
            self.cid = struct.unpack_from("<Q", body, 1)[0]
        await self.send(OP.CHAR_SELECT_REQ, CharSelectReq(self.cid).encode(self.codec))
        await self.recv_op(OP.CHAR_SELECT_RES)
        print(f"[+] {self.name} cid={self.cid}")


async def wait_battle_end(c, timeout=15):
    """持续攻击直到战斗结束；返回 (win, drops)"""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await c.send(OP.BATTLE_ACTION_REQ, struct.pack("<B", 2))  # 技能
        try:
            while True:
                op, body = await asyncio.wait_for(c.recv(), timeout=0.6)
                c.events.append(op)
                if op == OP.BATTLE_RESULT_NTF:
                    rid, win, turn, n = struct.unpack_from("<IBHB", body, 0)
                    drops = []
                    off = 8
                    for _ in range(n):
                        item, cnt = struct.unpack_from("<II", body, off)
                        drops.append((item, cnt)); off += 8
                    return bool(win), turn, drops
        except asyncio.TimeoutError:
            pass
    raise RuntimeError("battle not finished in time")


async def run(a):
    cfg = Config.load(a.config)
    A = Cli("A", cfg); B = Cli("B", cfg)
    await A.connect(a.host, a.port, "battle_a", "FighterA")
    await B.connect(a.host, a.port, "battle_b", "FighterB")

    # 1) A 建房
    await A.send(OP.ROOM_CREATE_REQ, struct.pack("<B", 4))
    body = await A.recv_op(OP.ROOM_CREATE_RES)
    code, rid = struct.unpack_from("<BI", body, 0)
    print(f"[+] A create room: code={code} room_id={rid}")
    await A.recv_op(OP.ROOM_INFO_NTF)

    # 2) B 加入
    await B.send(OP.ROOM_JOIN_REQ, struct.pack("<I", rid))
    body = await B.recv_op(OP.ROOM_JOIN_RES)
    print(f"[+] B join: code={body[0]}")
    await A.recv_op(OP.ROOM_INFO_NTF); await B.recv_op(OP.ROOM_INFO_NTF)

    # 3) B 准备 → A 开始
    await B.send(OP.ROOM_READY_REQ, struct.pack("<B", 1))
    await B.recv_op(OP.ROOM_READY_RES)
    await A.send(OP.ROOM_START_REQ, b"")
    body = await A.recv_op(OP.ROOM_START_RES)
    print(f"[+] A start battle: code={body[0]}")

    # 4) 双方打到结束
    ta = asyncio.create_task(wait_battle_end(A))
    tb = asyncio.create_task(wait_battle_end(B))
    (win_a, turn_a, drops_a), (win_b, turn_b, drops_b) = await asyncio.gather(ta, tb)
    print(f"[+] battle end: win={win_a} turn={turn_a} drops={drops_a}")

    # 5) 查背包
    await A.send(OP.BAG_LIST_REQ, b"")
    body = await A.recv_op(OP.BAG_LIST_RES)
    n = struct.unpack_from("<H", body, 0)[0]
    items = []
    off = 2
    for _ in range(n):
        i, c = struct.unpack_from("<II", body, off); items.append((i, c)); off += 8
    print(f"[+] A bag: {items}")

    assert win_a and win_b, "[x] 战斗未胜利"
    assert items, "[x] 掉落未入背包"
    print("[+] room & battle & drop flow OK")
    A.w.close(); B.w.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--config", default="./config/config.yaml")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()