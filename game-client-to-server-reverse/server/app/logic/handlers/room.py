"""app.logic.handlers.room —— 房间 / 匹配

生命周期：创建 → 加入/退出 → 准备 → 房主开始 → 进入战斗 → 结算后解散
每次变更都向房间内所有在线成员广播 ROOM_INFO_NTF。
"""
from __future__ import annotations

import logging
import struct

from ...net.dispatcher import dispatch
from ...proto.opcodes import OP, ERR, ERR_TEXT
from ...proto.messages import ErrorNtf
from ..rooms import ROOMS, Member, Room

log = logging.getLogger("gsrv.room")

_ERR_MAP = {
    "room_not_found": ERR.ROOM_NOT_FOUND,
    "room_full": ERR.ROOM_FULL,
    "room_not_owner": ERR.ROOM_NOT_OWNER,
    "room_not_ready": ERR.ROOM_NOT_READY,
    "already_in_room": ERR.ALREADY_IN_ROOM,
}


async def _send(session, session_server, uid, opcode, payload):
    sess = session_server.by_uid.get(uid)
    if sess and sess.alive:
        await sess.send(opcode, payload)


async def broadcast_room(server, room: Room):
    """向房间内所有在线成员推送房间信息"""
    payload = encode_room_info(room)
    for uid in list(room.members.keys()):
        await _send(None, server, uid, OP.ROOM_INFO_NTF, payload)
    log.debug("room %d broadcast members=%d", room.id, len(room.members))


def encode_room_info(room: Room) -> bytes:
    out = struct.pack("<IBIBB", room.id, 1 if room.state == "BATTLE" else 0,
                      room.owner_uid, room.max_size, len(room.members))
    for m in room.members.values():
        nm = m.name.encode("utf-8")
        out += (struct.pack("<Q", m.cid) + struct.pack("<I", m.uid)
                + struct.pack("<HB", m.level, 1 if m.ready else 0)
                + struct.pack("<H", len(nm)) + nm)
    return out


def _member_of(session) -> Member:
    return Member(session.uid, session.char_id or 0,
                  session.username or f"P{session.uid}", level=1)


@dispatch(OP.ROOM_CREATE_REQ)
async def on_create(session, codec, body):
    if session.char_id is None:
        await session.send_message(ErrorNtf(ERR.NEED_LOGIN, ERR_TEXT[ERR.NEED_LOGIN]))
        return
    max_size = body[0] if body else 4
    try:
        room = ROOMS.create(session.uid, session.char_id,
                            session.username or f"P{session.uid}", 1, max_size)
    except ValueError as e:
        code = _ERR_MAP.get(str(e), ERR.INTERNAL)
        await session.send(OP.ROOM_CREATE_RES, struct.pack("<BI", code, 0))
        return
    await session.send(OP.ROOM_CREATE_RES, struct.pack("<BI", ERR.OK, room.id))
    await broadcast_room(session.server, room)


@dispatch(OP.ROOM_JOIN_REQ)
async def on_join(session, codec, body):
    if session.char_id is None:
        await session.send_message(ErrorNtf(ERR.NEED_LOGIN, ERR_TEXT[ERR.NEED_LOGIN]))
        return
    (rid,) = struct.unpack_from("<I", body, 0) if len(body) >= 4 else (0,)
    try:
        room = ROOMS.join(rid, session.uid, session.char_id,
                          session.username or f"P{session.uid}", 1)
    except ValueError as e:
        code = _ERR_MAP.get(str(e), ERR.INTERNAL)
        await session.send(OP.ROOM_JOIN_RES, struct.pack("<BI", code, rid))
        return
    await session.send(OP.ROOM_JOIN_RES, struct.pack("<BI", ERR.OK, room.id))
    await broadcast_room(session.server, room)


@dispatch(OP.ROOM_LEAVE_REQ)
async def on_leave(session, codec, body):
    room = ROOMS.leave(session.uid)
    rid = room.id if room else 0
    await session.send(OP.ROOM_LEAVE_RES, struct.pack("<BI", ERR.OK, rid))
    if room:
        await broadcast_room(session.server, room)


@dispatch(OP.ROOM_READY_REQ)
async def on_ready(session, codec, body):
    ready = bool(body[0]) if body else True
    try:
        room = ROOMS.set_ready(session.uid, ready)
    except ValueError as e:
        await session.send(OP.ROOM_READY_RES,
                           struct.pack("<B", _ERR_MAP.get(str(e), ERR.INTERNAL)))
        return
    await session.send(OP.ROOM_READY_RES, struct.pack("<B", ERR.OK))
    await broadcast_room(session.server, room)


@dispatch(OP.ROOM_START_REQ)
async def on_start(session, codec, body):
    try:
        room = ROOMS.start(session.uid)
    except ValueError as e:
        code = _ERR_MAP.get(str(e), ERR.INTERNAL)
        await session.send(OP.ROOM_START_RES, struct.pack("<B", code))
        return
    await session.send(OP.ROOM_START_RES, struct.pack("<B", ERR.OK))
    await broadcast_room(session.server, room)
    # 开局即推送一次战斗状态
    from .battle import broadcast_state
    await broadcast_state(session.server, room)