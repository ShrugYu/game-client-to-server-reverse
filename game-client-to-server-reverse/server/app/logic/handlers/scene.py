"""app.logic.handlers.scene —— 进入场景 / 移动 / 玩家信息推送"""
from __future__ import annotations

import logging
import struct

from ...net.dispatcher import dispatch
from ...proto.opcodes import OP, ERR, ERR_TEXT
from ...proto.messages import ErrorNtf
from ...store.db import get_db
from ..state import STATE

log = logging.getLogger("gsrv.scene")


@dispatch(OP.ENTER_SCENE_REQ)
async def on_enter_scene(session, codec, body):
    if session.char_id is None:
        await session.send_message(ErrorNtf(ERR.NEED_LOGIN, ERR_TEXT[ERR.NEED_LOGIN]))
        return
    db = get_db()
    row = await db.get_char(session.char_id)
    if row is None:
        await session.send_message(ErrorNtf(ERR.NO_CHAR, ERR_TEXT[ERR.NO_CHAR]))
        return
    scene = row["scene"]
    # 返回场景快照：scene + x + y + 同场景玩家数（占位协议）
    payload = struct.pack("<HIIH", scene, row["x"], row["y"],
                          len(STATE.scenes.get(scene, set())))
    await session.send(OP.ENTER_SCENE_RES, payload)
    log.info("enter scene uid=%d cid=%d scene=%d", session.uid, session.char_id, scene)


@dispatch(OP.MOVE_REQ)
async def on_move(session, codec, body):
    if session.char_id is None:
        return
    # 客户端上报：x(u32) y(u32) —— 服务端权威校验
    try:
        x, y = struct.unpack_from("<II", body, 0)
    except struct.error:
        return

    from ...config import get_config
    snap = STATE.players.get(session.char_id)
    if snap and get_config().get("game.server_authoritative", True):
        # 速度校验：单帧位移不能超过 speed * 容差
        speed = 5
        max_step = speed * 4
        dx = abs(int(x) - int(snap.get("x", x)))
        dy = abs(int(y) - int(snap.get("y", y)))
        if dx > max_step or dy > max_step:
            log.warning("speedhack? cid=%d dx=%d dy=%d", session.char_id, dx, dy)
            await session.send(OP.MOVE_NTF, struct.pack("<QII", session.char_id,
                                                        snap["x"], snap["y"]))
            return  # 拒绝非法位移，回推旧位置

    STATE.move(session.char_id, x=x, y=y)
    db = get_db()
    await db.update_char_state(session.char_id, x=x, y=y)

    # 广播给同场景其他玩家
    snap = STATE.players.get(session.char_id, {})
    scene = snap.get("scene", 1)
    pkt = struct.pack("<QII", session.char_id, x, y)
    cids = STATE.scenes.get(scene, set())
    for cid in list(cids):
        other = STATE.players.get(cid)
        if not other:
            continue
        s = session.server.by_uid.get(other.get("uid"))
        if s and s is not session:
            await s.send(OP.MOVE_NTF, pkt)


@dispatch(OP.PLAYER_INFO_NTF)
async def on_player_info(session, codec, body):
    # 客户端主动请求自身信息（占位）
    if session.char_id is None:
        return
    snap = STATE.players.get(session.char_id, {})
    name = (snap.get("name") or "").encode("utf-8")
    payload = struct.pack("<QH", session.char_id, len(name)) + name
    await session.send(OP.PLAYER_INFO_NTF, payload)