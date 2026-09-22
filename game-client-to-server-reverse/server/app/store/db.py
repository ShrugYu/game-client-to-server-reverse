"""app.store.db —— 数据库抽象（默认 aiosqlite，生产可换 MySQL/PG）

表结构在 models.SCHEMA 里定义，启动时自动建表（幂等）。
"""
from __future__ import annotations

import logging
import os
import asyncio

log = logging.getLogger("gsrv.db")

try:
    import aiosqlite
    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False

from .models import SCHEMA, DEFAULT_CONFIG, MIGRATIONS


class Database:
    def __init__(self, cfg):
        self.cfg = cfg
        self.url = cfg.get("database.url", "sqlite:///./data/game.db")
        self._conn = None
        self._lock = asyncio.Lock()

    async def connect(self):
        if not HAS_SQLITE:
            raise RuntimeError("请安装 aiosqlite: pip install aiosqlite")
        path = self.url.replace("sqlite:///", "").replace("sqlite://", "")
        if not path.startswith(":memory:"):
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = await aiosqlite.connect(path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()
        log.info("database ready: %s", path)

    async def _init_schema(self):
        cur = await self._conn.cursor()
        for stmt in SCHEMA:
            await cur.execute(stmt)
        # 自动迁移（忽略"列已存在"错误）
        for stmt in MIGRATIONS:
            try:
                await cur.execute(stmt)
            except Exception:
                pass
        # 初始化配置表
        for k, v in DEFAULT_CONFIG.items():
            await cur.execute(
                "INSERT OR IGNORE INTO config(k, v) VALUES(?, ?)", (k, str(v))
            )
        await self._conn.commit()
        await cur.close()

    async def close(self):
        if self._conn:
            await self._conn.close()

    # ---------- 通用 ----------
    async def execute(self, sql, params=()):
        async with self._lock:
            cur = await self._conn.execute(sql, params)
            await self._conn.commit()
            rid = cur.lastrowid
            await cur.close()
            return rid

    async def fetchone(self, sql, params=()):
        cur = await self._conn.execute(sql, params)
        row = await cur.fetchone()
        await cur.close()
        return row

    async def fetchall(self, sql, params=()):
        cur = await self._conn.execute(sql, params)
        rows = await cur.fetchall()
        await cur.close()
        return rows

    # ---------- 账号 ----------
    async def get_account(self, username: str):
        return await self.fetchone(
            "SELECT * FROM account WHERE username=?", (username,)
        )

    async def create_account(self, username: str, password_hash: str):
        return await self.execute(
            "INSERT INTO account(username, password_hash, created_at) "
            "VALUES(?, ?, strftime('%s','now'))",
            (username, password_hash),
        )

    async def touch_login(self, uid: int):
        await self.execute(
            "UPDATE account SET last_login=strftime('%s','now') WHERE id=?", (uid,)
        )

    # ---------- 角色 ----------
    async def list_chars(self, uid: int):
        return await self.fetchall(
            "SELECT * FROM character WHERE uid=? ORDER BY id", (uid,)
        )

    async def get_char(self, cid: int):
        return await self.fetchone("SELECT * FROM character WHERE id=?", (cid,))

    async def get_char_by_name(self, name: str):
        return await self.fetchone("SELECT * FROM character WHERE name=?", (name,))

    async def create_char(self, uid: int, name: str, job: int = 0):
        return await self.execute(
            "INSERT INTO character(uid, name, level, job, scene, x, y, "
            "hp, mp, created_at) VALUES(?, ?, 1, ?, 1, 100, 100, 100, 50, "
            "strftime('%s','now'))",
            (uid, name, job),
        )

    async def delete_char(self, cid: int):
        await self.execute("DELETE FROM character WHERE id=?", (cid,))

    async def update_char_state(self, cid: int, scene=None, x=None, y=None,
                                hp=None, mp=None, level=None):
        sets, args = [], []
        for col, val in (("scene", scene), ("x", x), ("y", y),
                         ("hp", hp), ("mp", mp), ("level", level)):
            if val is not None:
                sets.append(f"{col}=?")
                args.append(val)
        if not sets:
            return
        args.append(cid)
        await self.execute(
            f"UPDATE character SET {', '.join(sets)} WHERE id=?", tuple(args)
        )

    # ---------- 配置表 ----------
    async def get_config(self, k: str, default=None):
        row = await self.fetchone("SELECT v FROM config WHERE k=?", (k,))
        return row["v"] if row else default

    # ---------- 货币 ----------
    async def get_currency(self, cid: int):
        row = await self.fetchone(
            "SELECT gold, diamond FROM character WHERE id=?", (cid,))
        return (row["gold"], row["diamond"]) if row else (0, 0)

    async def grant_currency(self, cid: int, currency: int, amount: int):
        """currency: 1=gold 2=diamond"""
        col = "gold" if currency == 1 else "diamond"
        await self.execute(
            f"UPDATE character SET {col}={col}+? WHERE id=?", (amount, cid))
        return await self.get_currency(cid)

    # ---------- 邮件 ----------
    async def send_mail(self, cid: int, title: str, content: str,
                        attachments=None):
        import json
        att = json.dumps(attachments or [], ensure_ascii=False)
        return await self.execute(
            "INSERT INTO mail(cid, title, content, attachments, created_at) "
            "VALUES(?, ?, ?, ?, strftime('%s','now'))",
            (cid, title, content, att))

    async def list_mails(self, cid: int):
        return await self.fetchall(
            "SELECT * FROM mail WHERE cid=? ORDER BY id DESC", (cid,))

    async def get_mail(self, mid: int):
        return await self.fetchone("SELECT * FROM mail WHERE id=?", (mid,))

    async def mark_mail_read(self, mid: int):
        await self.execute("UPDATE mail SET is_read=1 WHERE id=?", (mid,))

    async def claim_mail(self, mid: int):
        await self.execute("UPDATE mail SET claimed=1 WHERE id=?", (mid,))

    async def delete_mail(self, mid: int):
        await self.execute("DELETE FROM mail WHERE id=?", (mid,))

    # ---------- 充值订单 ----------
    async def create_order(self, uid, cid, order_no, product_id,
                           price, currency, amount):
        return await self.execute(
            "INSERT INTO recharge_order(uid, cid, order_no, product_id, price, "
            "currency, amount, status, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, 1, strftime('%s','now'))",
            (uid, cid, order_no, product_id, price, currency, amount))

    async def get_order(self, order_no: str):
        return await self.fetchone(
            "SELECT * FROM recharge_order WHERE order_no=?", (order_no,))

    # ---------- 背包 ----------
    async def list_items(self, cid: int):
        return await self.fetchall(
            "SELECT * FROM item WHERE cid=? ORDER BY item_id", (cid,))

    async def add_item(self, cid: int, item_id: int, count: int = 1):
        """存在则叠加，否则新增一格"""
        row = await self.fetchone(
            "SELECT id FROM item WHERE cid=? AND item_id=?", (cid, item_id))
        if row:
            await self.execute(
                "UPDATE item SET count=count+? WHERE id=?", (count, row["id"]))
            return row["id"]
        return await self.execute(
            "INSERT INTO item(cid, item_id, count) VALUES(?, ?, ?)",
            (cid, item_id, count))

    async def bag_slots(self, cid: int) -> int:
        row = await self.fetchone(
            "SELECT COUNT(DISTINCT item_id) AS n FROM item WHERE cid=?", (cid,))
        return int(row["n"]) if row else 0


DB: Database | None = None


async def init_db(cfg):
    global DB
    DB = Database(cfg)
    await DB.connect()
    return DB


def get_db() -> Database:
    assert DB is not None, "数据库未初始化"
    return DB