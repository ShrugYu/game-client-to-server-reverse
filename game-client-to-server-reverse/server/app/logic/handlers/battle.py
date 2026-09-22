"""app.logic.handlers.battle —— 战斗（服务端权威）

流程：
  BATTLE_ACTION_REQ(act) → 结算伤害 → 广播 BATTLE_STATE_NTF
  全员行动完 → 回合结束（Boss 反击）→ 广播
  结束 → 掷掉落 → 发放（背包满转邮件）→ BATTLE_RESULT_NTF
"""
from __future__ import annotations

import logging
import struct

from ...net.dispatcher import dispatch
from ...proto.opcodes import OP, ERR
from ...proto.messages import ErrorNtf
from ..rooms import ROOMS, Room
from .. import loot

log = logging.getLogger("gsrv.battle")


def encode_state(room: Room) -> bytes:
    b = room.battle
    out = struct.pack("<IHiiB", room.id, b.turn, b.boss_hp, b.boss_max_hp,
                      len(b.players))
    for cid, hp in b.players.items():
        out += struct.pack("<Qi", cid, hp)
    return out


async def broadcast_state(server, room: Room):
    payload = encode_state(room)
    for uid in list(room.members.keys()):
        sess = server.by_uid.get(uid)
        if sess and sess.alive:
            await sess.send(OP.BATTLE_STATE_NTF, payload)


async def _broadcast_result(server, room: Room, win: bool, drops: list):
    out = struct.pack("<IBHB", room.id, 1 if win else 0,
                      room.battle.turn if room.battle else 0,
                      min(len(drops), 255))
    for item_id, count in drops[:255]:
        out += struct.pack("<II", int(item_id), int(count))
    for uid in list(room.members.keys()):
        sess = server.by_uid.get(uid)
        if sess and sess.alive:
            await sess.send(OP.BATTLE_RESULT_NTF, out)


@dispatch(OP.BATTLE_ACTION_REQ)
async def on_action(session, codec, body):
    room = ROOMS.room_of(session.uid)
    if room is None or room.battle is None or room.battle.finished:
        await session.send_message(ErrorNtf(ERR.BATTLE_NOT_ACTIVE,
                                            "battle not active"))
        return
    act = body[0] if body else 1
    dmg = room.battle.action(session.char_id, act)

    m = room.members.get(session.uid)
    if m:
        m.acted = True
    await session.send(OP.BATTLE_ACTION_RES, struct.pack("<BI", ERR.OK, dmg))

    if room.battle.all_acted():
        room.battle.end_turn()
        log.info("battle room=%d turn -> %d boss_hp=%d",
                 room.id, room.battle.turn, room.battle.boss_hp)

    await broadcast_state(session.server, room)

    if room.battle.finished:
        await _settle(session.server, room)


async def _settle(server, room: Room):
    win = room.battle.win
    drops: list = []
    if win:
        table_id = room.scene or 1
        drops = loot.roll_drops(table_id)          # 服务端权威掉落
        db = _db()
        for m in room.members.values():
            await loot.grant_items(db, server, m.cid, drops)   # 每人一份
        log.info("battle victory room=%d drops=%s", room.id, drops)
    else:
        log.info("battle defeat room=%d", room.id)

    await _broadcast_result(server, room, win, drops)

    # 战斗结束 → 房间回到等待态
    room.state = "WAITING"
    room.battle = None
    for m in room.members.values():
        m.ready = False
    from .room import broadcast_room
    await broadcast_room(server, room)


def _db():
    from ...store.db import get_db
    return get_db()