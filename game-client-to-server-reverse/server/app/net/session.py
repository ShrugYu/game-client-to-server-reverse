"""app.net.session —— 连接会话（状态 + 信封发送 + 心跳）"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from .codec import Codec

log = logging.getLogger("gsrv.session")


class Session:
    def __init__(self, reader, writer, codec: Codec, peer, server):
        self.id = uuid.uuid4().hex[:12]
        self.reader = reader
        self.writer = writer
        self.codec = codec
        self.peer = peer
        self.server = server
        self.alive = True
        self.last_active = time.time()
        self.closed = False

        # —— 业务状态（登录/选角后填充）——
        self.uid: int | None = None          # 账号 id
        self.username: str | None = None
        self.char_id: int | None = None      # 当前角色
        self.state = "CONNECTED"             # 状态机：CONNECTED→HANDSHAKED→LOGGED_IN→IN_GAME
        self.token: str | None = None
        self.attrs: dict = {}                # 临时属性袋

    async def send(self, opcode: int, payload: bytes = b""):
        if self.closed:
            return
        data = self.codec.encode(opcode, payload)
        try:
            self.writer.write(data)
            await self.writer.drain()
        except (ConnectionError, RuntimeError):
            await self.close("send_failed")

    async def send_json(self, opcode: int, obj: dict):
        await self.send(opcode, self.codec.serialize(obj))

    async def send_message(self, msg) -> None:
        """自动从消息对象取 opcode 与 payload"""
        opcode = getattr(msg, "OPCODE", 0)
        payload = msg.encode(self.codec)
        await self.send(opcode, payload)

    def touch(self):
        self.last_active = time.time()

    async def close(self, reason: str = ""):
        if self.closed:
            return
        self.closed = True
        self.alive = False
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
        if reason:
            log.info("session %s closed: %s", self.id, reason)
        await self.server.on_session_closed(self)

    def __repr__(self):
        return f"<Session {self.id} {self.peer} state={self.state} uid={self.uid}>"