#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
注册网站最小后端（Flask + SQLite）。

要点（否则"注册的账号登不上"）：
 1. 与游戏服**共用同一份数据库**（同 account 表）—— references/account.md §16.5；
 2. 与客户端**复用同一套密码哈希** —— references/account.md §16.2。

注册校验：三选一（环境变量 VERIFY_MODE）
  invite    邀请码：必须提交 invite，且命中 invite_code 表（未过期、未用尽），成功后 used+1；
  group     QQ群验证：必须提交 qq，且命中 group_members 表（可用文件导入）；
  whitelist 白名单：username 必须在 whitelist 表内；
  none      不校验。

表（都在同一 DB，GM 后台也会用）：
  account(id, username, password_hash)
  invite_code(code PK, created_by, quota, used, expire_at, created_at)
  group_members(qq PK, note)
  whitelist(username PK)

运行：
  pip install flask
  GAME_DB=../server/data/game.db PWD_SALT=你的盐 VERIFY_MODE=invite ACCOUNT_PREFIX=svr_ python3 server.py
接口：
  POST /api/register {username,password,confirm?,verify_mode?,invite?,qq?} -> {ok:true,username:"svr_xxx"}
  POST /api/login    {username,password}                                    -> {ok:true}
"""
import os
import time
import sqlite3
import hashlib

from flask import Flask, request, jsonify, send_from_directory

DB = os.environ.get("GAME_DB", "./data/game.db")
SALT = os.environ.get("PWD_SALT", "")
HASH_MODE = os.environ.get("HASH_MODE", "md5")          # md5 | sha256 | plain
PREFIX = os.environ.get("ACCOUNT_PREFIX", "svr_")        # 账号前缀；不需要设空串
VERIFY_MODE = os.environ.get("VERIFY_MODE", "invite")    # invite | group | whitelist | none
AUTO_GRANT_INVITE = os.environ.get("AUTO_GRANT_INVITE", "0") == "1"  # 新用户注册后自带一个邀请码
SITE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)


def client_side_hash(pwd: str) -> str:
    if HASH_MODE == "plain":
        return pwd
    raw = (pwd + SALT).encode("utf-8")
    return hashlib.md5(raw).hexdigest() if HASH_MODE == "md5" else hashlib.sha256(raw).hexdigest()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.executescript("""
      CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS invite_code(code TEXT PRIMARY KEY, created_by TEXT, quota INTEGER DEFAULT 1, used INTEGER DEFAULT 0, expire_at INTEGER DEFAULT 0, created_at INTEGER DEFAULT 0);
      CREATE TABLE IF NOT EXISTS group_members(qq TEXT PRIMARY KEY, note TEXT);
      CREATE TABLE IF NOT EXISTS whitelist(username TEXT PRIMARY KEY);
    """)
    return c


def gen_code() -> str:
    import secrets
    return secrets.token_hex(4).upper()   # 8位大写16进制，如 9F3A1C2E


def make_invite(c, created_by, quota=1, days=7):
    code = gen_code()
    now = int(time.time())
    c.execute("INSERT OR IGNORE INTO invite_code(code,created_by,quota,used,expire_at,created_at) VALUES(?,?,?,0,?,?)",
              (code, created_by, quota, 0 if days <= 0 else now + days * 86400, now))
    return code


@app.get("/")
def index():
    return send_from_directory(SITE_DIR, "index.html")


@app.post("/api/register")
def register():
    d = request.get_json(silent=True) or {}
    u = (d.get("username") or "").strip()
    p = d.get("password") or ""
    confirm = d.get("confirm")
    mode = (d.get("verify_mode") or VERIFY_MODE)

    if not (3 <= len(u) <= 16) or not all(ch.isalnum() or ch == "_" for ch in u):
        return jsonify(ok=False, msg="账号需为 3-16 位字母/数字/下划线"), 400
    if not (6 <= len(p) <= 64):
        return jsonify(ok=False, msg="密码需为 6-64 位"), 400
    if confirm is not None and confirm != p:
        return jsonify(ok=False, msg="两次输入的密码不一致"), 400

    c = db()
    try:
        # —— 校验（三选一）——
        if mode == "invite":
            code = (d.get("invite") or "").strip().upper()
            row = c.execute("SELECT quota,used,expire_at FROM invite_code WHERE code=?", (code,)).fetchone()
            if not row:
                return jsonify(ok=False, msg="邀请码无效"), 403
            quota, used, expire_at = row
            if expire_at and expire_at < int(time.time()):
                return jsonify(ok=False, msg="邀请码已过期"), 403
            if used >= quota:
                return jsonify(ok=False, msg="邀请码已被使用"), 403
            c.execute("UPDATE invite_code SET used=used+1 WHERE code=?", (code,))
        elif mode == "group":
            qq = (d.get("qq") or "").strip()
            if not c.execute("SELECT 1 FROM group_members WHERE qq=?", (qq,)).fetchone():
                return jsonify(ok=False, msg="该QQ号不在玩家群名单内"), 403
        elif mode == "whitelist":
            if not c.execute("SELECT 1 FROM whitelist WHERE username=?", (u,)).fetchone() \
               and not c.execute("SELECT 1 FROM whitelist WHERE username=?", (PREFIX + u,)).fetchone():
                return jsonify(ok=False, msg="该账号不在白名单内"), 403
        # none: 不校验

        # —— 建号 ——
        full = PREFIX + u
        c.execute("INSERT INTO account(username,password_hash) VALUES(?,?)", (full, client_side_hash(p)))
        # 可选：新用户自带一个邀请码（"已注册用户可生成"的最小实现）
        if AUTO_GRANT_INVITE:
            make_invite(c, full, quota=1, days=7)
        c.commit()
        return jsonify(ok=True, username=full)
    except sqlite3.IntegrityError:
        return jsonify(ok=False, msg="用户名已存在"), 409
    finally:
        c.close()


@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    u = (d.get("username") or "").strip()
    p = d.get("password") or ""
    full = u if u.startswith(PREFIX) else PREFIX + u
    try:
        c = db()
        row = c.execute("SELECT password_hash FROM account WHERE username=?", (full,)).fetchone()
        c.close()
        ok = bool(row) and row[0] == client_side_hash(p)
        return jsonify(ok=ok, msg="" if ok else "账号或密码错误"), (200 if ok else 401)
    except Exception as e:
        return jsonify(ok=False, msg=str(e)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)