"""app.net.dispatcher —— opcode 路由

用法：
    @dispatch(OP.LOGIN_REQ)
    async def on_login(session, codec, body): ...
"""
from __future__ import annotations

import logging
import inspect
from typing import Awaitable, Callable

log = logging.getLogger("gsrv.dispatch")

Handler = Callable[..., Awaitable[None]]


class Dispatcher:
    def __init__(self):
        self._handlers: dict[int, Handler] = {}

    def register(self, opcode: int, fn: Handler):
        self._handlers[opcode] = fn

    def get(self, opcode: int):
        return self._handlers.get(opcode)

    async def dispatch(self, session, codec, opcode: int, body: bytes):
        fn = self._handlers.get(opcode)
        if fn is None:
            log.warning("no handler for opcode=0x%04X len=%d", opcode, len(body))
            await session.send(opcode, b"")  # 回空包，避免客户端卡住
            return
        try:
            res = fn(session, codec, body)
            if inspect.isawaitable(res):
                await res
        except Exception:
            log.exception("handler error opcode=0x%04X", opcode)
            await session.close("handler_error")


DISPATCH = Dispatcher()


def dispatch(opcode: int):
    """装饰器注册"""
    def deco(fn: Handler):
        DISPATCH.register(opcode, fn)
        return fn
    return deco


def load_handlers():
    """导入 handlers 包，触发装饰器注册"""
    from ..logic import handlers  # noqa: F401
    log.info("handlers loaded: %d opcodes", len(DISPATCH._handlers))