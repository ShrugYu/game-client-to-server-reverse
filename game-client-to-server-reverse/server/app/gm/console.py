"""app.gm.console —— GM 运维控制台（TCP，默认只监听 127.0.0.1）

命令：
    help                     帮助
    stats                    在线人数/场景
    online                   在线玩家列表
    kick <uid>               踢下线
    ban <username>           封号
    unban <username>         解封
    setlevel <cid> <level>   设置等级
    givegold <cid> <n>       给金币
    cfg <key>                查配置
    setcfg <key> <value>     改配置
    reload                   重载配置
    broadcast <opcode-hex> <hex>  广播原始包
    bots                      人机状态
    bots spawn <scene> <n> [easy|normal|hard]   生成人机
    bots clear [scene]        清空人机
    bots difficulty <level>   切换人机难度
    give <cid> <gold|diamond> <n> 直接发货币
    mail <cid> <title> <text> <type> <count>  发邮件带附件
    pay <cid> <product_id>   模拟一次充值发放
    stop                     关服
"""
from __future__ import annotations

import asyncio
import logging

from ..store.db import get_db
from ..config import get_config

log = logging.getLogger("gsrv.gm")

HELP = __doc__


async def start_gm(cfg, server):
    host = cfg.get("gm.host", "127.0.0.1")
    port = int(cfg.get("gm.port", 9900))

    async def handle(reader, writer):
        writer.write(b"GSRV GM console\n> ")
        await writer.drain()
        while True:
            line = await reader.readline()
            if not line:
                break
            cmd = line.decode("utf-8", "replace").strip()
            try:
                out = await execute(cmd, server)
            except Exception as e:  # noqa
                out = f"error: {e}"
            writer.write((str(out) + "\n> ").encode())
            await writer.drain()
        writer.close()

    srv = await asyncio.start_server(handle, host, port)
    log.info("GM console on %s:%d", host, port)
    async with srv:
        await srv.serve_forever()


async def execute(cmd: str, server) -> str:
    db = get_db()
    parts = cmd.split()
    if not parts:
        return ""
    op = parts[0].lower()

    if op in ("help", "?"):
        return HELP
    if op == "stats":
        return (f"online_sessions={len(server.sessions)} "
                f"uid_bound={len(server.by_uid)}")
    if op == "online":
        from ..logic.state import STATE
        lines = [f"{cid}: {snap}" for cid, snap in STATE.players.items()]
        return "\n".join(lines) or "(none)"
    if op == "kick" and len(parts) == 2:
        uid = int(parts[1])
        s = server.by_uid.get(uid)
        if not s:
            return "not online"
        await s.close("gm_kick")
        return f"kicked {uid}"
    if op in ("ban", "unban") and len(parts) == 2:
        await db.execute("UPDATE account SET banned=? WHERE username=?",
                         (1 if op == "ban" else 0, parts[1]))
        return f"{op} {parts[1]} ok"
    if op == "setlevel" and len(parts) == 3:
        await db.update_char_state(int(parts[1]), level=int(parts[2]))
        return "ok"
    if op == "givegold" and len(parts) == 3:
        await db.execute("UPDATE character SET gold=gold+? WHERE id=?",
                         (int(parts[2]), int(parts[1])))
        return "ok"
    if op == "cfg" and len(parts) == 2:
        return str(await db.get_config(parts[1]))
    if op == "setcfg" and len(parts) == 3:
        await db.execute("INSERT OR REPLACE INTO config(k, v) VALUES(?, ?)",
                         (parts[1], parts[2]))
        return "ok"
    if op == "reload":
        get_config().__init__(get_config().raw)  # noop 占位，可扩展热重载
        return "reloaded"
    if op == "broadcast" and len(parts) == 3:
        opcode = int(parts[1], 16)
        payload = bytes.fromhex(parts[2])
        await server.broadcast(opcode, payload)
        return "broadcasted"
    if op == "give" and len(parts) == 4:
        cid = int(parts[1])
        typ = parts[2].lower()
        n = int(parts[3])
        cur = 1 if typ == "gold" else 2
        gold, diamond = await db.grant_currency(cid, cur, n)
        return f"cid={cid} gold={gold} diamond={diamond}"
    if op == "mail" and len(parts) >= 6:
        cid = int(parts[1])
        title = parts[2]
        text = parts[3]
        typ = parts[4].lower()
        count = int(parts[5])
        from ..logic.handlers.mail import send_system_mail
        att = [{"type": typ, "id": 0, "count": count}]
        mid = await send_system_mail(server, cid, title, text, att)
        return f"mail sent mid={mid}"
    if op == "pay" and len(parts) == 3:
        cid = int(parts[1])
        pid = parts[2]
        from ..store.models import PAY_PRODUCTS
        p = PAY_PRODUCTS.get(pid)
        if not p:
            return "unknown product"
        cur = int(p["currency"])
        amt = int(p["amount"])
        mode = str(get_config().get("game.pay_grant_mode", "direct")).lower()
        if mode == "mail":
            from ..logic.handlers.mail import send_system_mail
            att = [{"type": "gold" if cur == 1 else "diamond", "id": 0, "count": amt}]
            await send_system_mail(server, cid, "GM充值", f"product={pid}", att)
            return f"granted via mail x{amt}"
        gold, diamond = await db.grant_currency(cid, cur, amt)
        return f"granted cid={cid} gold={gold} diamond={diamond}"
    if op == "bots":
        from ..logic.bots import MANAGER as BM
        if len(parts) == 1:
            return str(BM.stats())
        sub = parts[1].lower()
        if sub == "spawn":
            scene = int(parts[2]) if len(parts) > 2 else 1
            n = int(parts[3]) if len(parts) > 3 else 3
            diff = parts[4] if len(parts) > 4 else "normal"
            created = BM.spawn(scene=scene, count=n, difficulty=diff)
            return f"spawned {len(created)} bots in scene {scene} (difficulty={diff})"
        if sub == "clear":
            scene = int(parts[2]) if len(parts) > 2 else None
            return f"cleared {BM.clear(scene)} bots"
        if sub == "difficulty" and len(parts) > 2:
            return f"set difficulty={parts[2]} on {BM.set_difficulty(parts[2])} bots"
        return "usage: bots [spawn <scene> <n> [diff] | clear [scene] | difficulty <level>]"
    if op == "stop":
        await server.stop()
        return "server stopping"
    return "unknown command; type help"