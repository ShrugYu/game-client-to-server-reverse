#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GM 后台最小后端（Flask + SQLite）—— 含登录 / 角色权限 / 审计 / 安全加固。

两种登录（与游戏账号体系区分）：
  1) 操作员登录：`gm_operator` 表里的 **GM 操作员账号+密码**（PBKDF2 存储）→ 按角色拿权限；
  2) 玩家登录：用**游戏账号+密码**（与注册站同一套客户端哈希）→ 只有 `player` 的有限权限
     （生成自己的邀请码 / 看自己的记录）。

角色与权限（ROLE_PERMS）：
  player : invite.self, records.self
  viewer : player.query, records.view
  support: + reward.send, invite.manage
  admin  : + announce, cmd, online
  super  : *

安全要点：
  - 仅绑定 127.0.0.1；无默认口令（首个 super 由环境变量 GM_ROOT_USER/GM_ROOT_PASS 创建）。
  - 口令 PBKDF2-SHA256 加盐；常量时间比较；登录失败限流锁定。
  - 会话 token 存服务端（有过期），前端用 **X-GM-Token** 头携带 → 自带 CSRF 缓解。
  - 所有写操作写 `gm_audit`（含操作员、动作、目标、IP）。

运行：
  pip install flask
  GAME_DB=../server/data/game.db PWD_SALT=你的盐 GM_ROOT_USER=admin GM_ROOT_PASS=强口令 \
    GM_HOST=127.0.0.1 GM_PORT=9900 python3 server.py       # 监听 127.0.0.1:8090
"""
import os
import time
import hmac
import socket
import sqlite3
import secrets
import hashlib

from flask import Flask, jsonify, request, send_from_directory

GAME_DB = os.environ.get("GAME_DB", "../server/data/game.db")
PWD_SALT = os.environ.get("PWD_SALT", "")           # 与注册站/客户端一致
HASH_MODE = os.environ.get("HASH_MODE", "md5")
PREFIX = os.environ.get("ACCOUNT_PREFIX", "svr_")
GM_HOST = os.environ.get("GM_HOST", "127.0.0.1")
GM_PORT = int(os.environ.get("GM_PORT", "9900"))

ROOT_USER = os.environ.get("GM_ROOT_USER", "")
ROOT_PASS = os.environ.get("GM_ROOT_PASS", "")
SESSION_TTL = int(os.environ.get("GM_SESSION_TTL", "3600"))    # 会话有效期(秒)
MAX_FAIL = int(os.environ.get("GM_MAX_FAIL", "5"))             # 连续失败上限
LOCK_SEC = int(os.environ.get("GM_LOCK_SEC", "300"))           # 锁定时长(秒)

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

ROLE_PERMS = {
    "player":  {"invite.self", "records.self"},
    "viewer":  {"player.query", "records.view"},
    "support": {"player.query", "reward.send", "invite.manage", "records.view"},
    "admin":   {"player.query", "reward.send", "invite.manage", "records.view", "announce", "cmd", "online"},
    "super":   {"*"},
}


# ---------- 哈希 ----------
def game_hash(pwd: str) -> str:
    """玩家密码：与客户端/注册站同一套哈希。"""
    if HASH_MODE == "plain":
        return pwd
    raw = (pwd + PWD_SALT).encode("utf-8")
    return hashlib.md5(raw).hexdigest() if HASH_MODE == "md5" else hashlib.sha256(raw).hexdigest()


def op_hash(pwd: str, salt: str = None):
    """操作员密码：PBKDF2-SHA256 加盐。返回 (salt, hash)。"""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), bytes.fromhex(salt), 120_000)
    return salt, dk.hex()


# ---------- DB ----------
def db() -> sqlite3.Connection:
    c = sqlite3.connect(GAME_DB)
    c.executescript("""
      CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS invite_code(code TEXT PRIMARY KEY, created_by TEXT, quota INTEGER DEFAULT 1, used INTEGER DEFAULT 0, expire_at INTEGER DEFAULT 0, created_at INTEGER DEFAULT 0);
      CREATE TABLE IF NOT EXISTS gm_send_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, account TEXT, op TEXT, text TEXT);
      CREATE TABLE IF NOT EXISTS gm_operator(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, pwd_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'viewer', enabled INTEGER DEFAULT 1, created_at INTEGER DEFAULT 0);
      CREATE TABLE IF NOT EXISTS gm_session(token TEXT PRIMARY KEY, subject TEXT, role TEXT, expire INTEGER, created_at INTEGER, ip TEXT);
      CREATE TABLE IF NOT EXISTS gm_login_fail(username TEXT PRIMARY KEY, fails INTEGER DEFAULT 0, until INTEGER DEFAULT 0);
      CREATE TABLE IF NOT EXISTS gm_audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, operator TEXT, role TEXT, action TEXT, target TEXT, detail TEXT, ip TEXT);
    """)
    return c


def ensure_root():
    if not (ROOT_USER and ROOT_PASS):
        return
    c = db()
    if not c.execute("SELECT 1 FROM gm_operator WHERE username=?", (ROOT_USER,)).fetchone():
        salt, h = op_hash(ROOT_PASS)
        c.execute("INSERT INTO gm_operator(username,salt,pwd_hash,role,enabled,created_at) VALUES(?,?,?,?,1,?)",
                  (ROOT_USER, salt, h, "super", int(time.time())))
    c.commit(); c.close()


def audit(operator, role, action, target="", detail="", ip=""):
    try:
        c = db()
        c.execute("INSERT INTO gm_audit(ts,operator,role,action,target,detail,ip) VALUES(?,?,?,?,?,?,?)",
                  (int(time.time()), operator, role, action, target, detail, ip))
        c.commit(); c.close()
    except Exception:
        pass


def gen_code() -> str:
    return secrets.token_hex(4).upper()


def gm_cmd(line: str) -> str:
    try:
        with socket.create_connection((GM_HOST, GM_PORT), timeout=3) as s:
            s.sendall((line + "\n").encode())
            return s.recv(4096).decode(errors="replace").strip()
    except Exception as e:
        return "GM 通道不可用: %s" % e


# ---------- 会话 / 权限 ----------
def make_session(c, subject, role, ip):
    tok = secrets.token_urlsafe(32)
    now = int(time.time())
    c.execute("INSERT INTO gm_session(token,subject,role,expire,created_at,ip) VALUES(?,?,?,?,?,?)",
              (tok, subject, role, now + SESSION_TTL, now, ip))
    return tok


def current_session():
    tok = request.headers.get("X-GM-Token") or ""
    if not tok:
        return None
    c = db()
    row = c.execute("SELECT subject,role,expire FROM gm_session WHERE token=?", (tok,)).fetchone()
    if not row or row[2] < int(time.time()):
        if row:
            c.execute("DELETE FROM gm_session WHERE token=?", (tok,)); c.commit()
        c.close(); return None
    c.close()
    return {"subject": row[0], "role": row[1], "token": tok}


def has_perm(sess, perm):
    perms = ROLE_PERMS.get(sess["role"], set())
    return "*" in perms or perm in perms


def require(perm):
    """返回 (sess, err_response)。"""
    s = current_session()
    if not s:
        return None, (jsonify(ok=False, msg="未登录或会话已过期"), 401)
    if not has_perm(s, perm):
        return None, (jsonify(ok=False, msg="权限不足：" + perm), 403)
    return s, None


# ---------- 路由 ----------
@app.get("/")
def index():
    return send_from_directory(SITE_DIR, "index.html")


@app.get("/api/status")
def status():
    up = True
    try:
        with socket.create_connection((GM_HOST, GM_PORT), timeout=2):
            pass
    except Exception:
        up = False
    return jsonify(gm="up" if up else "down", db=os.path.exists(GAME_DB))


@app.post("/api/gm/login")
def login():
    d = request.get_json(silent=True) or {}
    typ = d.get("type") or "operator"
    u = (d.get("username") or "").strip()
    p = d.get("password") or ""
    ip = request.remote_addr or ""
    c = db()

    # 失败限流
    fr = c.execute("SELECT fails,until FROM gm_login_fail WHERE username=?", (u,)).fetchone()
    if fr and fr[1] and fr[1] > int(time.time()):
        c.close(); return jsonify(ok=False, msg="尝试过多，请稍后再试"), 429

    if typ == "operator":
        row = c.execute("SELECT salt,pwd_hash,role,enabled FROM gm_operator WHERE username=?", (u,)).fetchone()
        ok = False
        if row and row[3]:
            _, h = op_hash(p, row[0])
            ok = hmac.compare_digest(h, row[1])
        role = row[2] if (row and ok) else None
    else:  # 玩家：游戏账号 + 客户端哈希
        cands = [u] + ([PREFIX + u] if PREFIX and not u.startswith(PREFIX) else [])
        row = c.execute("SELECT username,password_hash FROM account WHERE username IN (%s)" % ",".join("?" * len(cands)), cands).fetchone()
        ok = bool(row) and hmac.compare_digest(game_hash(p), row[1])
        role = "player" if ok else None

    if not ok:
        fails = (fr[0] if fr else 0) + 1
        until = int(time.time()) + LOCK_SEC if fails >= MAX_FAIL else 0
        c.execute("INSERT INTO gm_login_fail(username,fails,until) VALUES(?,?,?) "
                  "ON CONFLICT(username) DO UPDATE SET fails=?,until=?", (u, fails, until, fails, until))
        c.commit(); c.close()
        audit(u, "-", "login_fail", ip=ip)
        return jsonify(ok=False, msg="账号或密码错误"), 401

    c.execute("DELETE FROM gm_login_fail WHERE username=?", (u,))
    subject = row[0] if typ == "player" else u
    tok = make_session(c, subject, role, ip)
    c.commit(); c.close()
    perms = list(ROLE_PERMS.get(role, set()))
    audit(subject, role, "login", ip=ip)
    return jsonify(ok=True, token=tok, subject=subject, role=role, perms=perms)


@app.post("/api/gm/logout")
def logout():
    s = current_session()
    if s:
        c = db(); c.execute("DELETE FROM gm_session WHERE token=?", (s["token"],)); c.commit(); c.close()
        audit(s["subject"], s["role"], "logout")
    return jsonify(ok=True)


@app.get("/api/gm/me")
def me():
    s = current_session()
    if not s:
        return jsonify(ok=False), 401
    return jsonify(ok=True, subject=s["subject"], role=s["role"], perms=list(ROLE_PERMS.get(s["role"], set())))


@app.post("/api/gm")
def gm():
    d = request.get_json(silent=True) or {}
    a = d.get("action")
    ip = request.remote_addr or ""
    pid = d.get("pid")

    # —— 只读 / 通用 ——
    if a == "servers":
        if not current_session():
            return jsonify(ok=False, msg="未登录"), 401
        return jsonify(servers=[{"id": "1", "name": "一区"}])

    if a == "query":
        s, err = require("player.query")
        if err: return err
        kw = (d.get("keyword") or "").strip()
        try:
            c = db()
            rows = c.execute("SELECT cid,name,level FROM character WHERE CAST(cid AS TEXT)=? OR name LIKE ? LIMIT 20",
                             (kw, "%" + kw + "%")).fetchall()
            c.close()
            return jsonify(roles=[{"pid": r[0], "name": r[1], "level": r[2], "account": kw} for r in rows])
        except Exception as e:
            return jsonify(roles=[], error=str(e))

    if a == "items":
        s, err = require("player.query")
        if err: return err
        return jsonify(items=[])

    # —— 发奖励（需 reward.send + 目标账号注册密码）——
    if a in ("send_money", "send_items", "send_mail"):
        s, err = require("reward.send")
        if err: return err
        account = (d.get("account") or "").strip()
        password = d.get("password") or ""
        c = db()
        cands = [account] + ([PREFIX + account] if PREFIX and not account.startswith(PREFIX) else [])
        row = c.execute("SELECT password_hash FROM account WHERE username IN (%s)" % ",".join("?" * len(cands)), cands).fetchone()
        if not row or not hmac.compare_digest(game_hash(password), row[0]):
            c.close(); audit(s["subject"], s["role"], a, account, "pwd_fail", ip)
            return jsonify(ok=False, msg="账号或密码错误（需该账号注册时的密码）"), 403
        c.close()

        if a == "send_money":
            res = gm_cmd("give %s %s %s" % (pid, d.get("currency"), int(d.get("amount") or 0)))
        elif a == "send_items":
            res = [gm_cmd("mail %s 系统发放 附件 %s %s" % (pid, it.get("id"), it.get("qty"))) for it in (d.get("items") or [])]
        else:
            res = gm_cmd("mail %s %s %s %s %s" % (pid, d.get("title") or "系统奖励", d.get("text") or "",
                                                  (d.get("item") or "").strip(), int(d.get("count") or 0)))
        # 玩家也可见自己相关的发放
        c = db(); c.execute("INSERT INTO gm_send_log(ts,account,op,text) VALUES(?,?,?,?)",
                            (int(time.time()), account, a, str(res)[:200])); c.commit(); c.close()
        audit(s["subject"], s["role"], a, account, str(res)[:200], ip)
        return jsonify(ok=True, result=res)

    # —— 全局操作 ——
    if a in ("announce", "cmd", "online"):
        perm = {"announce": "announce", "cmd": "cmd", "online": "online"}[a]
        s, err = require(perm)
        if err: return err
        if a == "announce":
            res = gm_cmd("broadcast %s" % (d.get("text") or ""))
        elif a == "cmd":
            res = gm_cmd((d.get("line") or "").strip())
        else:
            res = ""
        audit(s["subject"], s["role"], a, "", (d.get("text") or d.get("line") or "")[:150], ip)
        return jsonify(ok=True, result=res, players=[])

    # —— 记录（viewer 可看全部；player 只看自己）——
    if a == "logs":
        s = current_session()
        if not s: return jsonify(ok=False, msg="未登录"), 401
        kw = (d.get("keyword") or "").strip()
        c = db()
        if has_perm(s, "records.view"):
            rows = c.execute("SELECT ts,account,op,text FROM gm_send_log WHERE account LIKE ? OR text LIKE ? ORDER BY ts DESC LIMIT 200",
                             ("%" + kw + "%", "%" + kw + "%")).fetchall()
        elif has_perm(s, "records.self"):
            rows = c.execute("SELECT ts,account,op,text FROM gm_send_log WHERE account=? ORDER BY ts DESC LIMIT 100", (s["subject"],)).fetchall()
        else:
            c.close(); return jsonify(ok=False, msg="权限不足"), 403
        c.close()
        return jsonify(ok=True, logs=[{"time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r[0])),
                                      "account": r[1], "op": r[2], "text": r[3]} for r in rows])

    # —— 邀请码 ——
    if a == "invite_gen":
        s = current_session()
        if not s: return jsonify(ok=False, msg="未登录"), 401
        if has_perm(s, "invite.manage"):
            by = (d.get("by") or "").strip()
        elif has_perm(s, "invite.self"):
            by = s["subject"]                    # 玩家只能给自己生成
        else:
            return jsonify(ok=False, msg="权限不足：invite"), 403
        num = max(1, min(50, int(d.get("num") or 1)))
        quota = max(1, min(999, int(d.get("quota") or 1)))
        days = max(0, min(3650, int(d.get("days") or 7)))
        c = db()
        cands = [by] + ([PREFIX + by] if PREFIX and not by.startswith(PREFIX) else [])
        if not any(c.execute("SELECT 1 FROM account WHERE username=?", (u,)).fetchone() for u in cands):
            c.close(); return jsonify(ok=False, msg="生成者账号未注册：" + by), 403
        now = int(time.time()); expire = 0 if days <= 0 else now + days * 86400
        codes = []
        for _ in range(num):
            code = gen_code()
            c.execute("INSERT OR IGNORE INTO invite_code(code,created_by,quota,used,expire_at,created_at) VALUES(?,?,?,0,?,?)",
                      (code, by, quota, expire, now))
            codes.append(code)
        c.commit(); c.close()
        audit(s["subject"], s["role"], "invite_gen", by, str(codes)[:150], ip)
        return jsonify(ok=True, codes=codes)

    if a == "invite_list":
        s = current_session()
        if not s: return jsonify(ok=False, msg="未登录"), 401
        kw = (d.get("keyword") or "").strip()
        c = db()
        if has_perm(s, "invite.manage"):
            rows = c.execute("SELECT code,created_by,quota,used,expire_at FROM invite_code WHERE code LIKE ? OR created_by LIKE ? ORDER BY created_at DESC LIMIT 200",
                             ("%" + kw + "%", "%" + kw + "%")).fetchall()
        elif has_perm(s, "invite.self"):
            rows = c.execute("SELECT code,created_by,quota,used,expire_at FROM invite_code WHERE created_by IN (?,?) ORDER BY created_at DESC LIMIT 200",
                             (s["subject"], PREFIX + s["subject"])).fetchall()
        else:
            c.close(); return jsonify(ok=False, msg="权限不足"), 403
        c.close()
        keys = ["code", "created_by", "quota", "used", "expire_at"]
        return jsonify(ok=True, codes=[dict(zip(keys, r)) for r in rows])

    if a == "invite_revoke":
        s, err = require("invite.manage")
        if err: return err
        c = db(); c.execute("DELETE FROM invite_code WHERE code=?", ((d.get("code") or "").strip().upper(),)); c.commit(); c.close()
        audit(s["subject"], s["role"], "invite_revoke", d.get("code") or "", ip=ip)
        return jsonify(ok=True)

    # —— 操作员管理：仅 super（op.manage）——
    if a in ("op_list", "op_create", "op_update", "op_reset_pwd", "op_delete"):
        s, err = require("op.manage")
        if err: return err

        if a == "op_list":
            c = db()
            rows = c.execute("SELECT id,username,role,enabled,created_at FROM gm_operator ORDER BY id").fetchall()
            c.close()
            return jsonify(ok=True, operators=[{"id": r[0], "username": r[1], "role": r[2], "enabled": r[3], "created_at": r[4]} for r in rows])

        if a == "op_create":
            u = (d.get("username") or "").strip(); p = d.get("password") or ""; role = d.get("role") or "viewer"
            if not u or len(p) < 6: return jsonify(ok=False, msg="账号非空且密码≥6位"), 400
            if role not in ROLE_PERMS: return jsonify(ok=False, msg="角色不合法"), 400
            salt, h = op_hash(p)
            c = db()
            try:
                c.execute("INSERT INTO gm_operator(username,salt,pwd_hash,role,enabled,created_at) VALUES(?,?,?,?,1,?)",
                          (u, salt, h, role, int(time.time())))
                c.commit()
            except sqlite3.IntegrityError:
                c.close(); return jsonify(ok=False, msg="账号已存在"), 409
            c.close(); audit(s["subject"], s["role"], "op_create", u, role, ip)
            return jsonify(ok=True)

        if a == "op_update":
            uid = d.get("id"); role = d.get("role"); enabled = d.get("enabled")
            if role is not None and role not in ROLE_PERMS: return jsonify(ok=False, msg="角色不合法"), 400
            c = db()
            if role is not None: c.execute("UPDATE gm_operator SET role=? WHERE id=?", (role, uid))
            if enabled is not None: c.execute("UPDATE gm_operator SET enabled=? WHERE id=?", (1 if enabled else 0, uid))
            c.commit(); c.close()
            audit(s["subject"], s["role"], "op_update", str(uid), str(d)[:150], ip)
            return jsonify(ok=True)

        if a == "op_reset_pwd":
            p = d.get("password") or ""
            if len(p) < 6: return jsonify(ok=False, msg="密码≥6位"), 400
            salt, h = op_hash(p)
            c = db(); c.execute("UPDATE gm_operator SET salt=?,pwd_hash=? WHERE id=?", (salt, h, d.get("id"))); c.commit(); c.close()
            audit(s["subject"], s["role"], "op_reset_pwd", str(d.get("id")), ip=ip)
            return jsonify(ok=True)

        if a == "op_delete":
            uid = d.get("id")
            c = db()
            row = c.execute("SELECT username FROM gm_operator WHERE id=?", (uid,)).fetchone()
            if row and row[0] == s["subject"]:
                c.close(); return jsonify(ok=False, msg="不能删除自己"), 400
            c.execute("DELETE FROM gm_operator WHERE id=?", (uid,)); c.commit(); c.close()
            audit(s["subject"], s["role"], "op_delete", str(uid), ip=ip)
            return jsonify(ok=True)

    return jsonify(ok=False, msg="未知 action"), 400


ensure_root()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8090)