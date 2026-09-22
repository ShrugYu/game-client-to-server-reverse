"""app.logic.handlers.pay —— 充值 / 支付（自托管模式：点击购买直接成功）

设计要点：
  * 客户端连的是我们自己的服务端，真实的第三方支付 SDK 在本服务端里不存在。
    所以下单请求直接由本服务端判定"成功"，并发放货币/道具。
  * 幂等：order_no 唯一，重复回调只会发放一次（防重放）。
  * 两种发放方式（config: game.pay_grant_mode）：
      direct —— 直接把货币加到角色
      mail   —— 发到邮箱，玩家自行领取
  * 商品表在 store/models.py 的 PAY_PRODUCTS，用客户端真实 product_id 做键。

注意: 仅用于自建/离线/已授权服务器。不要用它去伪造真实支付渠道的凭证。
"""
from __future__ import annotations

import logging
import time
import uuid

from ...net.dispatcher import dispatch
from ...proto.opcodes import OP, ERR, ERR_TEXT
from ...proto.messages import (
    PayReq, PayRes, PayProductListRes, ErrorNtf, MailInfo,
)
from ...store.db import get_db
from ...store.models import PAY_PRODUCTS, CURRENCY_NAME

log = logging.getLogger("gsrv.pay")


def _cfg(path, default=None):
    from ...config import get_config
    return get_config().get(path, default)


async def _grant(db, session, currency: int, amount: int, product_id: str):
    """按配置发放；返回 (by_mail, new_balance, mail_mid)

    注意：邮件模式下**不在此处推送**，由调用方在回包之后推送，
    避免"推送早于请求回包"造成客户端消息错位。
    """
    mode = str(_cfg("game.pay_grant_mode", "direct")).lower()
    title = "充值到账"
    content = f"您购买的【{product_id}】已到账：{CURRENCY_NAME.get(currency, '?')} x{amount}"
    att = [{"type": CURRENCY_NAME.get(currency, "gold"), "id": 0, "count": amount}]

    if mode == "mail":
        from .mail import send_system_mail
        mid = await send_system_mail(session.server, session.char_id,
                                     title, content, att, push=False)
        return True, None, mid
    # direct
    gold, diamond = await db.grant_currency(session.char_id, currency, amount)
    return False, (gold if currency == 1 else diamond), None


@dispatch(OP.PAY_PRODUCT_LIST_REQ)
async def on_product_list(session, codec, body):
    products = []
    for pid, p in PAY_PRODUCTS.items():
        products.append((pid, p.get("name", pid), int(p.get("price", 0)),
                         int(p.get("currency", 1)), int(p.get("amount", 0))))
    await session.send_message(PayProductListRes(products))


@dispatch(OP.PAY_REQ)
async def on_pay(session, codec, body):
    if session.char_id is None:
        await session.send_message(ErrorNtf(ERR.NEED_LOGIN, ERR_TEXT[ERR.NEED_LOGIN]))
        return
    db = get_db()
    try:
        req = PayReq.decode(body, codec)
    except Exception:
        await session.send_message(ErrorNtf(ERR.BAD_PACKET, ERR_TEXT[ERR.BAD_PACKET]))
        return

    product = PAY_PRODUCTS.get(req.product_id)
    if product is None:
        log.warning("unknown product_id=%s", req.product_id)
        await session.send_message(PayRes(ERR.PAY_PRODUCT_NOT_FOUND, req.product_id,
                                          req.order_no))
        return

    # 生成 / 复用订单号
    order_no = req.order_no or f"{session.uid}-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    # 幂等：已处理过的订单直接返回成功（不重复发放）
    existing = await db.get_order(order_no)
    if existing:
        log.info("duplicate order %s -> return success (idempotent)", order_no)
        await session.send_message(PayRes(
            ERR.OK, req.product_id, order_no,
            int(existing["currency"]), int(existing["amount"]), False))
        return

    currency = int(product.get("currency", 1))
    amount = int(product.get("amount", 0))
    price = int(product.get("price", 0))

    # === 自托管支付判定：点击购买直接成功 ===
    auto = bool(_cfg("game.pay_auto_success", True))
    if not auto:
        # 若要接真实校验，在这里验证第三方回调凭证（本模板不带）
        await session.send_message(PayRes(ERR.PAY_FAILED, req.product_id, order_no))
        return

    # 记账 + 发放
    await db.create_order(session.uid, session.char_id, order_no,
                          req.product_id, price, currency, amount)
    by_mail, balance, mail_mid = await _grant(db, session, currency, amount,
                                              req.product_id)

    log.info("PAY OK uid=%d cid=%d product=%s order=%s +%s x%d by_mail=%s",
             session.uid, session.char_id, req.product_id, order_no,
             CURRENCY_NAME.get(currency), amount, by_mail)

    # 先回请求，再推邮件通知（保证客户端消息顺序正确）
    await session.send_message(PayRes(ERR.OK, req.product_id, order_no,
                                      currency, amount, by_mail))
    if by_mail and mail_mid is not None:
        from .mail import push_mail
        await push_mail(session, mail_mid)