"""app.logic.handlers.char —— 角色列表 / 创建 / 选择 / 删除"""
from __future__ import annotations

import logging

from ...net.dispatcher import dispatch
from ...proto.opcodes import OP, ERR, ERR_TEXT
from ...proto.messages import (
    CharInfo, CharListRes, CharCreateReq, CharCreateRes,
    CharSelectReq, CharSelectRes, ErrorNtf,
)
from ...store.db import get_db
from ..state import STATE

log = logging.getLogger("gsrv.char")


def _need_login(session) -> bool:
    return session.state not in ("LOGGED_IN", "IN_GAME")


async def _send_err(session, code):
    await session.send_message(ErrorNtf(code, ERR_TEXT.get(code, "error")))


async def push_char_list(session):
    db = get_db()
    rows = await db.list_chars(session.uid)
    chars = [CharInfo(r["id"], r["name"], r["level"], r["job"]) for r in rows]
    await session.send_message(CharListRes(chars))


@dispatch(OP.CHAR_LIST_REQ)
async def on_char_list(session, codec, body):
    if _need_login(session):
        await _send_err(session, ERR.NEED_LOGIN)
        return
    await push_char_list(session)


@dispatch(OP.CHAR_CREATE_REQ)
async def on_char_create(session, codec, body):
    if _need_login(session):
        await _send_err(session, ERR.NEED_LOGIN)
        return
    db = get_db()
    try:
        req = CharCreateReq.decode(body, codec)
    except Exception:
        await _send_err(session, ERR.BAD_PACKET)
        return
    if not req.name or len(req.name) > 16:
        await _send_err(session, ERR.BAD_PACKET)
        return
    limit = int(await db.get_config("max_char_per_account", "4"))
    rows = await db.list_chars(session.uid)
    if len(rows) >= limit:
        await _send_err(session, ERR.CHAR_LIMIT)
        return
    if await db.get_char_by_name(req.name):
        await _send_err(session, ERR.ACCOUNT_EXISTS)
        return
    cid = await db.create_char(session.uid, req.name, req.job)
    row = await db.get_char(cid)
    char = CharInfo(row["id"], row["name"], row["level"], row["job"])
    await session.send_message(CharCreateRes(ERR.OK, char))
    log.info("char created uid=%d cid=%d name=%s", session.uid, cid, req.name)
    await push_char_list(session)


@dispatch(OP.CHAR_SELECT_REQ)
async def on_char_select(session, codec, body):
    if _need_login(session):
        await _send_err(session, ERR.NEED_LOGIN)
        return
    db = get_db()
    try:
        req = CharSelectReq.decode(body, codec)
    except Exception:
        await _send_err(session, ERR.BAD_PACKET)
        return
    row = await db.get_char(req.cid)
    if row is None or row["uid"] != session.uid:
        await _send_err(session, ERR.NO_CHAR)
        return
    session.char_id = req.cid
    session.state = "IN_GAME"
    STATE.enter(req.cid, {
        "cid": req.cid, "uid": session.uid, "name": row["name"],
        "level": row["level"], "scene": row["scene"], "x": row["x"], "y": row["y"],
    })
    await session.send_message(CharSelectRes(ERR.OK, req.cid, row["scene"]))
    log.info("char selected uid=%d cid=%d scene=%d", session.uid, req.cid, row["scene"])


@dispatch(OP.CHAR_DELETE_REQ)
async def on_char_delete(session, codec, body):
    if _need_login(session):
        await _send_err(session, ERR.NEED_LOGIN)
        return
    db = get_db()
    try:
        req = CharSelectReq.decode(body, codec)  # 复用 cid 解包
    except Exception:
        await _send_err(session, ERR.BAD_PACKET)
        return
    row = await db.get_char(req.cid)
    if row is None or row["uid"] != session.uid:
        await _send_err(session, ERR.NO_CHAR)
        return
    await db.delete_char(req.cid)
    await push_char_list(session)