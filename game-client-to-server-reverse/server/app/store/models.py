"""app.store.models —— 表结构与默认游戏配置表

游戏配置表（config）就是客户端依赖的"数值表"的服务端镜像：
掉率、经验曲线、道具、技能等都可以放这里，由 GM 热改。
"""

SCHEMA = [
    # 账号
    """
    CREATE TABLE IF NOT EXISTS account (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at    INTEGER DEFAULT 0,
        last_login    INTEGER DEFAULT 0,
        banned        INTEGER DEFAULT 0
    )
    """,
    # 角色
    """
    CREATE TABLE IF NOT EXISTS character (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        uid        INTEGER NOT NULL,
        name       TEXT NOT NULL UNIQUE,
        level      INTEGER DEFAULT 1,
        exp        INTEGER DEFAULT 0,
        job        INTEGER DEFAULT 0,
        scene      INTEGER DEFAULT 1,
        x          INTEGER DEFAULT 100,
        y          INTEGER DEFAULT 100,
        hp         INTEGER DEFAULT 100,
        mp         INTEGER DEFAULT 50,
        gold       INTEGER DEFAULT 0,
        diamond    INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT 0,
        FOREIGN KEY(uid) REFERENCES account(id) ON DELETE CASCADE
    )
    """,
    # 背包
    """
    CREATE TABLE IF NOT EXISTS item (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        cid      INTEGER NOT NULL,
        item_id  INTEGER NOT NULL,
        count    INTEGER DEFAULT 1,
        FOREIGN KEY(cid) REFERENCES character(id) ON DELETE CASCADE
    )
    """,
    # 配置表（客户端数值镜像）
    """
    CREATE TABLE IF NOT EXISTS config (
        k TEXT PRIMARY KEY,
        v TEXT
    )
    """,
    # 操作日志（服务端权威校验/审计）
    """
    CREATE TABLE IF NOT EXISTS oplog (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        uid     INTEGER,
        cid     INTEGER,
        opcode  INTEGER,
        detail  TEXT,
        ts      INTEGER DEFAULT 0
    )
    """,
    # 邮件
    """
    CREATE TABLE IF NOT EXISTS mail (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        cid         INTEGER NOT NULL,
        title       TEXT DEFAULT '',
        content     TEXT DEFAULT '',
        attachments TEXT DEFAULT '[]',
        claimed     INTEGER DEFAULT 0,
        is_read     INTEGER DEFAULT 0,
        created_at  INTEGER DEFAULT 0,
        FOREIGN KEY(cid) REFERENCES character(id) ON DELETE CASCADE
    )
    """,
    # 充值订单（幂等：同一 order_no 只发一次）
    """
    CREATE TABLE IF NOT EXISTS recharge_order (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        uid        INTEGER NOT NULL,
        cid        INTEGER,
        order_no   TEXT NOT NULL UNIQUE,
        product_id TEXT NOT NULL,
        price      INTEGER DEFAULT 0,
        currency   INTEGER DEFAULT 0,
        amount     INTEGER DEFAULT 0,
        status     INTEGER DEFAULT 1,
        created_at INTEGER DEFAULT 0
    )
    """,
]

# 自动迁移：给老库补列（已存在则忽略错误）
MIGRATIONS = [
    "ALTER TABLE character ADD COLUMN diamond INTEGER DEFAULT 0",
]

# 默认游戏配置（按需扩展；这些值直接影响客户端表现）
DEFAULT_CONFIG = {
    "exp_curve_base": 100,        # 升级所需经验 = base * level^2
    "exp_curve_pow": 2,
    "max_char_per_account": 4,
    "initial_scene": 1,
    "start_gold": 0,
    "max_level": 100,
    "hp_per_level": 20,
    "mp_per_level": 10,
    "default_speed": 5,
    "drop_rate": 1.0,
    "max_bag_slots": 50,          # 背包格数上限（满则掉落转邮件）
    "room_max_size": 4,           # 房间默认人数上限
    "battle_max_turn": 20,        # 战斗回合上限（超时判负）
    # 充值发放方式：direct=直接加货币  mail=发邮件领取
    "pay_grant_mode": "direct",
    # 是否模拟支付成功（私服：跳过真实支付渠道，点击即成功）
    "pay_auto_success": True,
}

# ---- 充值商品表（独立于 DB 配置，改这里即可）----
# 键 = 客户端真实的 product_id；从客户端商品表/充值 SDK 反推后填这里
PAY_PRODUCTS: dict[str, dict] = {
    "com.demo.gold_60":    {"name": "60金",   "price": 600,  "currency": 1, "amount": 60},
    "com.demo.gold_300":   {"name": "300金",  "price": 3000, "currency": 1, "amount": 300},
    "com.demo.diamond_60": {"name": "60钻石", "price": 600,  "currency": 2, "amount": 60},
}

# 货币类型
CURRENCY_GOLD = 1
CURRENCY_DIAMOND = 2
CURRENCY_NAME = {CURRENCY_GOLD: "gold", CURRENCY_DIAMOND: "diamond"}