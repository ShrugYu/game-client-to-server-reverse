"""app.logic.handlers.mail —— 邮件系统

能力：
  - 邮箱列表 / 已读 / 删除
  - 附件领取（金币、钻石、道具）—— 服务端权威发放
  - 新邮件实时推送（MAIL_NEW_NTF）
  - 供其它模块调用：send_system_mail(session_server, cid, ...)
"""
from __future__ import annotations

import json
import logging

from ...net.dispatcher import dispatch
from ...proto.opcodes import OP, ERR, ERR_TEXT
from ...proto.messages import MailInfo, MailListRes, MailOpReq, MailOpRes, MailNewNtf, ErrorNtf
from ...store.db import get_db
from ...store.models import CURRENCY_NAME

log = logging.getLogger("gsrv.mail")


def _row_to_mailinfo(row) -> MailInfo:
    try:
        atts = json.loads(row["attachments"] or "[]")
    except Exception:
        atts = []
    return MailInfo(
        mid=row["id"],
        title=row["title"] or "",
        content=row["content"] or "",
        attachments=atts,
        claimed=bool(row["claimed"]),
        read=bool(row["is_read"]),
        ts=row["created_at"] or 0,
    )


async def push_new_mail(session, cid: int):
    """把某角色最新一封邮件推给在线会话（可选）"""
    db = get_db()
    rows = await db.list_mails(cid)
    if rows:
        await session.send_message(MailNewNtf(_row_to_mailinfo(rows[0])))


async def push_mail(session, mid: int):
    """按 mail id 推送一封邮件通知"""
    db = get_db()
    row = await db.get_mail(mid)
    if row:
        await session.send_message(MailNewNtf(_row_to_mailinfo(row)))


async def send_system_mail(server, cid: int, title: str, content: str,
                           attachments=None, push: bool = True):
    """给角色发一封系统邮件；若在线则实时推送。"""
    db = get_db()
    mid = await db.send_mail(cid, title, content, attachments or [])
    log.info("mail sent cid=%d mid=%d title=%s att=%s",
             cid, mid, title, attachments)
    if push:
        row = await db.get_mail(mid)
        # 找到该角色对应的在线会话
        for s in list(server.sessions.values()):
            if s.char_id == cid:
                await s.send_message(MailNewNtf(_row_to_mailinfo(row)))
                break
    return mid


@dispatch(OP.MAIL_LIST_REQ)
async def on_mail_list(session, codec, body):
    if session.char_id is None:
        await session.send_message(ErrorNtf(ERR.NEED_LOGIN, ERR_TEXT[ERR.NEED_LOGIN]))
        return
    db = get_db()
    rows = await db.list_mails(session.char_id)
    await session.send_message(MailListRes([_row_to_mailinfo(r) for r in rows]))


@dispatch(OP.MAIL_READ_REQ)
async def on_mail_read(session, codec, body):
    if session.char_id is None:
        return
    db = get_db()
    req = MailOpReq.decode(body, codec)
    row = await db.get_mail(req.mid)
    if row is None or row["cid"] != session.char_id:
        await session.send(OP.MAIL_READ_RES, MailOpRes(ERR.MAIL_NOT_FOUND, req.mid).encode(codec))
        return
    await db.mark_mail_read(req.mid)
    await session.send(OP.MAIL_READ_RES, MailOpRes(ERR.OK, req.mid).encode(codec))


@dispatch(OP.MAIL_CLAIM_REQ)
async def on_mail_claim(session, codec, body):
    """领取附件：服务端权威，逐个发放，标记已领，防重复。"""
    if session.char_id is None:
        return
    db = get_db()
    req = MailOpReq.decode(body, codec)
    row = await db.get_mail(req.mid)
    if row is None or row["cid"] != session.char_id:
        await session.send(OP.MAIL_CLAIM_RES, MailOpRes(ERR.MAIL_NOT_FOUND, req.mid).encode(codec))
        return
    if row["claimed"]:
        await session.send(OP.MAIL_CLAIM_RES, MailOpRes(ERR.MAIL_ALREADY_CLAIMED, req.mid).encode(codec))
        return

    try:
        atts = json.loads(row["attachments"] or "[]")
    except Exception:
        atts = []

    for a in atts:
        typ = a.get("type")
        count = int(a.get("count", 0))
        if typ in ("gold", "diamond"):
            cur = 1 if typ == "gold" else 2
            await db.grant_currency(session.char_id, cur, count)
        elif typ == "item":
            # 道具：入库到 item 表
            item_id = int(a.get("id", 0))
            await db.execute(
                "INSERT INTO item(cid, item_id, count) VALUES(?, ?, ?)",
                (session.char_id, item_id, count))
        log.info("mail claim cid=%d mid=%d +%s x%d",
                 session.char_id, req.mid, typ, count)

    await db.claim_mail(req.mid)
    gold, diamond = await db.get_currency(session.char_id)
    log.info("after claim cid=%d gold=%d diamond=%d",
             session.char_id, gold, diamond)
    await session.send(OP.MAIL_CLAIM_RES, MailOpRes(ERR.OK, req.mid).encode(codec))
    # 通知客户端刷新货币
    await push_new_mail(session, session.char_id)


@dispatch(OP.MAIL_DELETE_REQ)
async def on_mail_delete(session, codec, body):
    if session.char_id is None:
        return
    db = get_db()
    req = MailOpReq.decode(body, codec)
    row = await db.get_mail(req.mid)
    if row is None or row["cid"] != session.char_id:
        await session.send(OP.MAIL_CLAIM_RES, MailOpRes(ERR.MAIL_NOT_FOUND, req.mid).encode(codec))
        return
    await db.delete_mail(req.mid)
    await session.send(OP.MAIL_CLAIM_RES, MailOpRes(ERR.OK, req.mid).encode(codec))