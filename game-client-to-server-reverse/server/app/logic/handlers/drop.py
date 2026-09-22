"""app.logic.handlers.drop —— 背包 / 掉落查询与测试

  BAG_LIST_REQ   → BAG_LIST_RES   列出背包
  DROP_TEST_REQ  → DROP_TEST_RES  按掉落表试掷并发放（调试用；真实项目可删）
"""
from __future__ import annotations

import logging
import struct

from ...net.dispatcher import dispatch
from ...proto.opcodes import OP, ERR, ERR_TEXT
from ...proto.messages import ErrorNtf
from ...store.db import get_db
from .. import loot

log = logging.getLogger("gsrv.drop")


@dispatch(OP.BAG_LIST_REQ)
async def on_bag_list(session, codec, body):
    if session.char_id is None:
        await session.send_message(ErrorNtf(ERR.NEED_LOGIN, ERR_TEXT[ERR.NEED_LOGIN]))
        return
    db = get_db()
    rows = await db.list_items(session.char_id)
    out = struct.pack("<H", len(rows))
    for r in rows:
        out += struct.pack("<II", r["item_id"], r["count"])
    await session.send(OP.BAG_LIST_RES, out)


@dispatch(OP.DROP_TEST_REQ)
async def on_drop_test(session, codec, body):
    """按 table_id 掷一次掉落并发放（联调 / 调试用）"""
    if session.char_id is None:
        await session.send_message(ErrorNtf(ERR.NEED_LOGIN, ERR_TEXT[ERR.NEED_LOGIN]))
        return
    table_id = struct.unpack_from("<I", body, 0)[0] if len(body) >= 4 else 1
    drops = loot.roll_drops(table_id)
    db = get_db()
    added, mailed = await loot.grant_items(db, session.server, session.char_id, drops)

    out = struct.pack("<HB", table_id, min(len(drops), 255))
    for item_id, count in drops[:255]:
        out += struct.pack("<II", item_id, count)
    await session.send(OP.DROP_TEST_RES, out)

    # 掉落通知（含走邮件的部分）
    ntf = struct.pack("<HBB", len(drops), len(added), len(mailed))
    for item_id, count in drops:
        ntf += struct.pack("<II", item_id, count)
    await session.send(OP.DROP_NTF, ntf)
    log.info("drop test cid=%d table=%d added=%s mailed=%s",
             session.char_id, table_id, added, mailed)