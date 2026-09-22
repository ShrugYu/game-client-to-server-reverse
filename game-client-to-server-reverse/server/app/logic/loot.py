"""app.logic.loot —— 掉落 / 物资发放

职责：
  * 掉落表（DROP_TABLES）：按副本/场景 id 配置掉落
  * 服务端权威掷骰（roll_drops）
  * 入库（grant_items）：背包满 → 自动转邮件，避免物资丢失

掉落表结构：
  {table_id: {"name": str, "rolls": int,
              "entries": [{"item_id": int, "count": [min,max], "rate": 0~1}]}}
真机上把 DROP_TABLES 换成从客户端配置表反推出来的真实掉落表。
"""
from __future__ import annotations

import logging
import random

log = logging.getLogger("gsrv.loot")

BAG_LIMIT_DEFAULT = 50

# ---- 掉落表（示例，替换为真实配置）----
DROP_TABLES: dict[int, dict] = {
    1: {   # 新手森林
        "name": "新手森林",
        "rolls": 2,
        "entries": [
            {"item_id": 1001, "count": [1, 3], "rate": 0.80},   # 普通素材
            {"item_id": 1002, "count": [1, 1], "rate": 0.35},   # 稀有素材
            {"item_id": 2001, "count": [1, 1], "rate": 0.10},   # 装备
        ],
    },
    2: {   # 精英副本
        "name": "精英副本",
        "rolls": 3,
        "entries": [
            {"item_id": 1002, "count": [1, 2], "rate": 0.70},
            {"item_id": 2001, "count": [1, 1], "rate": 0.30},
            {"item_id": 3001, "count": [1, 1], "rate": 0.05},   # 稀有
        ],
    },
}


def roll_drops(table_id: int, rolls: int | None = None) -> list[tuple[int, int]]:
    """服务端掷骰；返回 [(item_id, count)]（同类合并）"""
    table = DROP_TABLES.get(table_id)
    if not table:
        return []
    n = rolls if rolls is not None else table.get("rolls", 1)
    bucket: dict[int, int] = {}
    for _ in range(n):
        for e in table.get("entries", []):
            if random.random() <= float(e.get("rate", 0)):
                lo, hi = e.get("count", [1, 1])
                cnt = random.randint(int(lo), int(hi))
                bucket[e["item_id"]] = bucket.get(e["item_id"], 0) + cnt
    out = sorted(bucket.items())
    log.info("drops rolled table=%s -> %s", table_id, out)
    return out


async def grant_items(db, server, cid: int, items: list[tuple[int, int]]):
    """按背包容量入库；装不下的转邮件。

    返回 (added, mailed)：added=[(item_id,count)] 已进背包；mailed=[(item_id,count)] 走邮件
    """
    if not items:
        return [], []
    limit = int(await db.get_config("max_bag_slots", str(BAG_LIMIT_DEFAULT)))
    rows = await db.list_items(cid)
    used_ids = {r["item_id"] for r in rows}
    slots = len(used_ids)

    added: list[tuple[int, int]] = []
    mailed: list[tuple[int, int]] = []
    for item_id, count in items:
        if item_id in used_ids:
            await db.add_item(cid, item_id, count)
            added.append((item_id, count))
        elif slots < limit:
            await db.add_item(cid, item_id, count)
            used_ids.add(item_id)
            slots += 1
            added.append((item_id, count))
        else:
            mailed.append((item_id, count))

    if mailed:
        from .handlers.mail import send_system_mail
        atts = [{"type": "item", "id": i, "count": c} for i, c in mailed]
        await send_system_mail(server, cid, "背包已满，物资已邮件补发",
                               "以下物资因背包已满，改由邮件发放，请及时领取。", atts)
        log.info("bag full -> %d kinds mailed cid=%d", len(mailed), cid)

    return added, mailed