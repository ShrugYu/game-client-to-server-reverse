#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小可运行服务端骨架（Mock Server）
- 只实现：握手 + 长连接帧收发 + 可插拔 opcode 处理
- 用法: python3 mock_server.py --host 0.0.0.0 --port 8888

适配说明：
  * 把 FRAME_* / DECRYPT / ENCRYPT 换成从客户端逆向出的真实实现
  * 每个 opcode 在 HANDLERS 里注册
"""
import argparse, asyncio, struct, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("gsrv")

# ---------------- 协议层（占位，按逆向结果替换） ----------------
# 例：4 字节大端长度前缀 + 负载
LEN_FMT = ">I"
LEN_SIZE = 4
MAX_FRAME = 1 << 20


def decode_frame(buf: bytes) -> bytes:
    """剥离外层封装（去掉长度头/解压/解密后的业务体）"""
    return buf


def encode_frame(payload: bytes) -> bytes:
    """加外层封装"""
    return struct.pack(LEN_FMT, len(payload)) + payload


def decrypt(data: bytes) -> bytes:
    """占位：换成真实解密（RC4/XOR/AES...）"""
    return data


def encrypt(data: bytes) -> bytes:
    """占位：换成真实加密"""
    return data


# ---------------- opcode 处理器 ----------------
HANDLERS = {}


def handler(opcode: int):
    def deco(fn):
        HANDLERS[opcode] = fn
        return fn
    return deco


@handler(0x0001)
async def on_handshake(session, body: bytes) -> bytes:
    log.info("[0x0001] handshake body=%s", body.hex())
    # 真实实现：校验客户端版本/随机数，返回握手确认
    return b"\x01"


@handler(0x0002)
async def on_login(session, body: bytes) -> bytes:
    log.info("[0x0002] login body=%s", body.hex())
    # 真实实现：返回 token / 角色列表
    return b"\x02"


# ---------------- 连接处理 ----------------
class Session:
    def __init__(self, writer):
        self.writer = writer
        self.alive = True


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    log.info("client connected: %s", peer)
    session = Session(writer)
    try:
        while True:
            head = await reader.readexactly(LEN_SIZE)
            (n,) = struct.unpack(LEN_FMT, head)
            if n <= 0 or n > MAX_FRAME:
                log.warning("bad frame len=%s", n)
                break
            raw = await reader.readexactly(n)
            plain = decrypt(decode_frame(raw))
            if not plain:
                continue
            # 约定：首字节=opcode（按真实协议替换）
            opcode = plain[0]
            body = plain[1:]
            fn = HANDLERS.get(opcode)
            if fn is None:
                log.info("unhandled opcode=0x%04X body=%s", opcode, body.hex())
                continue
            resp = await fn(session, body)
            out = encode_frame(encrypt(bytes([opcode]) + resp))
            writer.write(out)
            await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    except Exception as e:  # noqa
        log.exception("session error: %s", e)
    finally:
        session.alive = False
        writer.close()
        log.info("client closed: %s", peer)


async def main(host, port):
    server = await asyncio.start_server(handle_client, host, port)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    log.info("listening on %s", addrs)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8888)
    args = ap.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass