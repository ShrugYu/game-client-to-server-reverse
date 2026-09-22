"""app.logic.bots —— 服务端人机（假玩家 / Bot）——  后续拓展（可选骨架）

注意: 本模块属「后续拓展」：**不做也不影响核心运行**。
   默认 auto_fill=0，不会生成任何假玩家。需要用配置手动生成。

注意:注意: 这只是**通用骨架**，不是任何具体游戏的答案。 注意:注意:

复刻真实人机必须：
  1. 先读 extensions/bot-reverse.md，从用户的客户端**反推**人机机制
     （找 IsAI/robot 字段、判归属模型、还原身份/标记/动作/流程消息）
  2. 把结论写进 protocol.spec.yaml 的 bots 段
  3. 再用本骨架去**实现那个游戏的**人机

本文件提供的是可复用的结构（tick / 拟人化 / 广播），
不代表目标游戏的人机逻辑。

设计要点（详见 extensions/bots.md）：
  * 逻辑 Bot：在服务端内部实例化，**复用同一套状态与广播**，不走网络编解码
  * 独立 tick：固定频率驱动，不挂在网络事件里
  * 拟人化：反应延迟 + 坐标抖动 + 失误率
  * 可通过配置增减、切换难度
  * Bot 的移动通过**与真人相同的 MOVE_NTF** 下发给客户端，所以客户端能"看到"它们

用法：
    from app.logic.bots import MANAGER
    MANAGER.attach(server)
    MANAGER.spawn(scene=1, count=3, difficulty="normal")
"""
from __future__ import annotations

import asyncio
import logging
import random
import time

log = logging.getLogger("gsrv.bots")

# 难度档位：反应延迟区间(秒)、失误率、漫游步长
DIFFICULTY = {
    "easy":   {"reaction": (0.9, 1.8), "mistake": 0.30, "step": (1, 3)},
    "normal": {"reaction": (0.5, 1.1), "mistake": 0.12, "step": (2, 5)},
    "hard":   {"reaction": (0.25, 0.6), "mistake": 0.05, "step": (3, 7)},
}

# 随机名字词库（拟人化：有身份感）
NAME_POOL = [
    "夜风", "青柠", "阿凯", "小满", "白露", "星屑", "迟夏", "雾都",
    "银烛", "南栀", "无铭", "北岛", "拾光", "浅川", "暮色", "橙子",
    "流浪猫", "半糖", "不眠", "远山", "折枝", "月见", "青鸟", "琥珀",
]

# 地图边界（demo 用；真实项目按场景配置）
MAP_W, MAP_H = 1000, 1000


class Bot:
    def __init__(self, bot_id: int, scene: int, difficulty: str = "normal"):
        cfg = DIFFICULTY.get(difficulty, DIFFICULTY["normal"])
        self.bot_id = 0x40000000 + bot_id      # 用高位段与真人 cid 区分
        self.name = random.choice(NAME_POOL) + str(random.randint(10, 99))
        self.scene = scene
        self.difficulty = difficulty
        self.cfg = cfg
        self.x = random.randint(0, MAP_W)
        self.y = random.randint(0, MAP_H)
        self.tx, self.ty = self.x, self.y          # 目标点
        self.next_act = time.time() + random.uniform(*cfg["reaction"])
        self.job = random.randint(0, 3)
        self.level = random.randint(1, 30)

    def humanize(self):
        """拟人化：下一次行动的间隔，带随机抖动"""
        lo, hi = self.cfg["reaction"]
        return random.uniform(lo, hi)

    def pick_target(self):
        """选一个新目标点（漫游）"""
        self.tx = max(0, min(MAP_W, self.x + random.randint(-120, 120)))
        self.ty = max(0, min(MAP_H, self.y + random.randint(-120, 120)))

    def step_towards(self):
        """向目标点走一步，带坐标抖动"""
        lo, hi = self.cfg["step"]
        step = random.randint(lo, hi)
        dx, dy = self.tx - self.x, self.ty - self.y
        dist = max(1, int((dx * dx + dy * dy) ** 0.5))
        # 失误：有一定概率走反/走偏
        if random.random() < self.cfg["mistake"]:
            nx = self.x + random.randint(-step, step)
            ny = self.y + random.randint(-step, step)
        else:
            nx = self.x + int(dx / dist * step)
            ny = self.y + int(dy / dist * step)
        self.x = max(0, min(MAP_W, nx))
        self.y = max(0, min(MAP_H, ny))
        if abs(self.x - self.tx) < 8 and abs(self.y - self.ty) < 8:
            self.pick_target()

    def __repr__(self):
        return f"<Bot {self.bot_id} {self.name} scene={self.scene} @({self.x},{self.y})>"


class BotManager:
    def __init__(self):
        self.bots: dict[int, Bot] = {}
        self.server = None
        self._seq = 0
        self._task: asyncio.Task | None = None
        self._running = False
        self.tick_hz = 5          # tick 频率（每秒几次）
        self.enabled = True

    # ---------- 生命周期 ----------
    def attach(self, server):
        self.server = server

    async def start(self):
        if self._running or self.server is None:
            return
        self._running = True
        self._task = asyncio.create_task(self._tick_loop())
        log.info("bot manager started (tick=%dHz)", self.tick_hz)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        self.bots.clear()

    # ---------- 增删 ----------
    def spawn(self, scene: int = 1, count: int = 3, difficulty: str = "normal",
              stagger: bool = True) -> list[Bot]:
        """生成 Bot。stagger=True 时模拟"陆续加入"，不瞬间满员。"""
        created = []
        for _ in range(count):
            self._seq += 1
            b = Bot(self._seq, scene, difficulty)
            self.bots[b.bot_id] = b
            created.append(b)
            log.info("bot spawn %s", b)
        return created

    def despawn(self, bot_id: int) -> bool:
        b = self.bots.pop(bot_id, None)
        if b:
            log.info("bot despawn %s", b)
            return True
        return False

    def clear(self, scene: int | None = None) -> int:
        if scene is None:
            n = len(self.bots)
            self.bots.clear()
            return n
        ids = [b.bot_id for b in self.bots.values() if b.scene == scene]
        for i in ids:
            self.bots.pop(i, None)
        return len(ids)

    def set_difficulty(self, difficulty: str) -> int:
        cfg = DIFFICULTY.get(difficulty)
        if not cfg:
            return 0
        for b in self.bots.values():
            b.difficulty = difficulty
            b.cfg = cfg
        return len(self.bots)

    def stats(self) -> dict:
        per_scene: dict[int, int] = {}
        for b in self.bots.values():
            per_scene[b.scene] = per_scene.get(b.scene, 0) + 1
        return {"total": len(self.bots), "per_scene": per_scene,
                "running": self._running}

    # ---------- tick ----------
    async def _tick_loop(self):
        interval = 1.0 / max(1, self.tick_hz)
        while self._running:
            try:
                await self._tick()
            except Exception:
                log.exception("bot tick error")
            await asyncio.sleep(interval)

    async def _tick(self):
        if not self.enabled or not self.bots:
            return
        now = time.time()
        import struct
        from ..proto.opcodes import OP
        for b in list(self.bots.values()):
            if now < b.next_act:
                continue
            b.step_towards()
            b.next_act = now + b.humanize()
            # 与真人相同的下行消息：MOVE_NTF(cid, x, y)
            pkt = struct.pack("<QII", b.bot_id, b.x, b.y)
            await self._broadcast_to_scene(b.scene, OP.MOVE_NTF, pkt)

    async def _broadcast_to_scene(self, scene: int, opcode: int, payload: bytes):
        """只发给该场景内的真人在线会话"""
        server = self.server
        if server is None:
            return
        from .state import STATE
        cids = STATE.scenes.get(scene, set())
        for cid in list(cids):
            snap = STATE.players.get(cid)
            if not snap:
                continue
            sess = server.by_uid.get(snap.get("uid"))
            if sess and sess.alive:
                await sess.send(opcode, payload)


MANAGER = BotManager()