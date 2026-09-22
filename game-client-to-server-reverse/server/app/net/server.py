"""app.net.server —— asyncio TCP 服务器主循环

负责：接受连接 → 逐帧读取 → 解码 → 分发 → 广播 → 心跳清理 → 连接数限制
"""
from __future__ import annotations

import asyncio
import logging
import time

from .codec import Codec
from .dispatcher import DISPATCH, load_handlers
from .session import Session
from ..logic.bots import MANAGER as BOT_MANAGER

log = logging.getLogger("gsrv.server")


class GameServer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.sessions: dict[str, Session] = {}
        self.by_uid: dict[int, Session] = {}
        self._ip_count: dict[str, int] = {}
        self.server: asyncio.AbstractServer | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    # ---------- 生命周期 ----------
    def build_codec(self) -> Codec:
        return Codec(
            frame_cfg=self.cfg.get("frame", {}),
            crypto_cfg=self.cfg.get("crypto", {}),
            compress_cfg=self.cfg.get("compress", {}),
            serialize_cfg=self.cfg.get("serialize", {}),
            max_frame=int(self.cfg.get("server.max_frame", 1 << 20)),
        )

    async def start(self):
        load_handlers()
        host = self.cfg.get("server.host", "0.0.0.0")
        port = int(self.cfg.get("server.port", 8888))
        self.server = await asyncio.start_server(
            self._on_client, host, port, backlog=int(self.cfg.get("server.backlog", 128))
        )
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        # ---- 人机（假玩家 / Bot）----
        if self.cfg.get("bots.enabled", True):
            BOT_MANAGER.tick_hz = int(self.cfg.get("bots.tick_hz", 5))
            BOT_MANAGER.attach(self)
            await BOT_MANAGER.start()
            auto = int(self.cfg.get("bots.auto_fill", 0))
            if auto > 0:
                BOT_MANAGER.spawn(
                    scene=int(self.cfg.get("bots.default_scene", 1)),
                    count=auto,
                    difficulty=self.cfg.get("bots.difficulty", "normal"))
                log.info("auto-filled %d bots", auto)
        addrs = ", ".join(str(s.getsockname()) for s in self.server.sockets)
        log.info("[%s] listening on %s", self.cfg.get("game.name"), addrs)

    async def stop(self):
        self._running = False
        try:
            await BOT_MANAGER.stop()
        except Exception:
            pass
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        for s in list(self.sessions.values()):
            await s.close("server_stop")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        log.info("server stopped")

    # ---------- 连接处理 ----------
    async def _on_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername") or ("?", 0)
        ip = peer[0] if isinstance(peer, tuple) else str(peer)

        # 连接数限制
        max_conn = int(self.cfg.get("server.max_connections", 5000))
        if len(self.sessions) >= max_conn:
            log.warning("max connections reached, reject %s", ip)
            writer.close()
            return
        per_ip = int(self.cfg.get("security.max_conn_per_ip", 32))
        if self._ip_count.get(ip, 0) >= per_ip:
            log.warning("too many conn from %s", ip)
            writer.close()
            return

        codec = self.build_codec()
        sess = Session(reader, writer, codec, peer, self)
        self.sessions[sess.id] = sess
        self._ip_count[ip] = self._ip_count.get(ip, 0) + 1
        log.info("+ connect %s (total=%d)", ip, len(self.sessions))

        try:
            await self._read_loop(sess)
        except asyncio.IncompleteReadError:
            pass
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            log.exception("client loop error %s", peer)
        finally:
            await sess.close("eof")
            self._ip_count[ip] = max(0, self._ip_count.get(ip, 1) - 1)

    async def _read_loop(self, sess: Session):
        codec = sess.codec
        reader = sess.reader
        ls = codec.len_size
        while sess.alive and self._running:
            head = await reader.readexactly(ls)
            frame_len, rest, need = codec.decode_head(head)
            inner = rest
            while need > 0:
                chunk = await reader.readexactly(need)
                inner += chunk
                need -= len(chunk)
            sess.touch()
            opcode, body = codec.parse(inner)
            log.debug("< %s op=0x%04X len=%d", sess.id, opcode, len(body))
            await DISPATCH.dispatch(sess, codec, opcode, body)

    # ---------- 会话回收 ----------
    async def on_session_closed(self, sess: Session):
        self.sessions.pop(sess.id, None)
        if sess.uid is not None and self.by_uid.get(sess.uid) is sess:
            self.by_uid.pop(sess.uid, None)

    def bind_uid(self, sess: Session, uid: int):
        """登录成功后绑定 uid（顶号处理）"""
        old = self.by_uid.get(uid)
        if old and old is not sess:
            asyncio.create_task(old.close("kicked"))
        self.by_uid[uid] = sess
        sess.uid = uid

    # ---------- 广播 ----------
    async def broadcast(self, opcode: int, payload: bytes, predicate=None):
        for s in list(self.sessions.values()):
            if predicate is None or predicate(s):
                await s.send(opcode, payload)

    # ---------- 心跳清理 ----------
    async def _heartbeat_loop(self):
        idle = float(self.cfg.get("server.idle_timeout", 30))
        while self._running:
            await asyncio.sleep(max(idle / 2, 1))
            now = time.time()
            for s in list(self.sessions.values()):
                if now - s.last_active > idle * 4:
                    log.info("idle timeout %s", s.id)
                    await s.close("idle_timeout")