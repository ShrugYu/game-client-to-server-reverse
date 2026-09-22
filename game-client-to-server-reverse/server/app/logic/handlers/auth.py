"""app.logic.handlers.auth —— 握手 / 登录 / 注册 / 心跳"""
from __future__ import annotations

import logging

from ...net.dispatcher import dispatch
from ...proto.opcodes import OP, ERR, ERR_TEXT
from ...proto.messages import (
    HandshakeReq, HandshakeRes, LoginReq, LoginRes, ErrorNtf,
)
from ...store.db import get_db
from ..security import hash_password, verify_password, sign_token, RateLimiter

log = logging.getLogger("gsrv.auth")

_login_limiter = RateLimiter(limit=10, window=60.0)


@dispatch(OP.HANDSHAKE_REQ)
async def on_handshake(session, codec, body):
    try:
        req = HandshakeReq.decode(body, codec)
    except Exception:
        await session.send_message(ErrorNtf(ERR.BAD_PACKET, ERR_TEXT[ERR.BAD_PACKET]))
        return
    from ...config import get_config
    expect = get_config().get("game.expected_version", "")
    require = get_config().get("game.require_version", True)
    code = ERR.OK
    if require and expect and req.version != expect:
        code = ERR.BAD_VERSION
        log.warning("version mismatch: client=%s expect=%s", req.version, expect)
    session.state = "HANDSHAKED"
    session.attrs["nonce"] = req.nonce
    from ...config import get_config as gc
    await session.send_message(HandshakeRes(code, gc().get("game.version", "1.0.0")))
    log.info("handshake peer=%s version=%s nonce=%d -> code=%d",
             session.peer, req.version, req.nonce, code)


@dispatch(OP.HEARTBEAT_REQ)
async def on_heartbeat(session, codec, body):
    session.touch()
    await session.send(OP.HEARTBEAT_RES, body)  # 原样回显


@dispatch(OP.REGISTER_REQ)
async def on_register(session, codec, body):
    db = get_db()
    try:
        req = LoginReq.decode(body, codec)
    except Exception:
        await session.send_message(ErrorNtf(ERR.BAD_PACKET, ERR_TEXT[ERR.BAD_PACKET]))
        return
    if not req.username or not req.password:
        await session.send_message(ErrorNtf(ERR.AUTH_FAILED, ERR_TEXT[ERR.AUTH_FAILED]))
        return
    existing = await db.get_account(req.username)
    if existing:
        await session.send_message(ErrorNtf(ERR.ACCOUNT_EXISTS, ERR_TEXT[ERR.ACCOUNT_EXISTS]))
        return
    uid = await db.create_account(req.username, hash_password(req.password))
    token = sign_token(uid, _secret(), _ttl())
    await session.send(OP.REGISTER_RES, LoginRes(ERR.OK, token, uid).encode(codec))
    log.info("registered uid=%d username=%s", uid, req.username)


@dispatch(OP.LOGIN_REQ)
async def on_login(session, codec, body):
    if not _login_limiter.allow(str(session.peer)):
        await session.send_message(ErrorNtf(ERR.RATE_LIMITED, ERR_TEXT[ERR.RATE_LIMITED]))
        return
    db = get_db()
    try:
        req = LoginReq.decode(body, codec)
    except Exception:
        await session.send_message(ErrorNtf(ERR.BAD_PACKET, ERR_TEXT[ERR.BAD_PACKET]))
        return

    acc = await db.get_account(req.username)
    if acc is None:
        # 首次登录自动注册（私服常见便利行为；生产可关）
        uid = await db.create_account(req.username, hash_password(req.password))
        acc = await db.get_account(req.username)
    elif not verify_password(req.password, acc["password_hash"]):
        await session.send_message(ErrorNtf(ERR.AUTH_FAILED, ERR_TEXT[ERR.AUTH_FAILED]))
        log.warning("login failed username=%s", req.username)
        return
    if acc["banned"]:
        await session.send_message(ErrorNtf(ERR.AUTH_FAILED, "banned"))
        return

    uid = acc["id"]
    session.server.bind_uid(session, uid)
    session.username = req.username
    session.state = "LOGGED_IN"
    token = sign_token(uid, _secret(), _ttl())
    session.token = token
    await db.touch_login(uid)
    await session.send(OP.LOGIN_RES, LoginRes(ERR.OK, token, uid).encode(codec))
    log.info("login ok uid=%d username=%s", uid, req.username)

    from ...config import get_config
    if get_config().get("game.auto_push_char_list", True):
        from .char import push_char_list
        await push_char_list(session)


def _secret():
    from ...config import get_config
    return get_config().get("security.token_secret", "secret")


def _ttl():
    from ...config import get_config
    return int(get_config().get("security.token_ttl", 86400))