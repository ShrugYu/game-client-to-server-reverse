"""app.logic.rooms —— 房间 / 匹配 / 战斗会话（服务端权威）

模型：
    RoomManager
      └ Room(id, scene, owner_uid, max_size, members, state, battle)
            └ Battle(turn, boss_hp, players{cid:hp}, log, finished, win)

战斗是"服务端权威"的简化回合制：每个回合所有成员各行动一次，
结算 Boss 伤害；Boss 反击；Boss 死 → 胜利 → 掉落；全员死/超时 → 失败。
真实游戏按自身协议替换 decide/resolve 即可。
"""
from __future__ import annotations

import logging
import random
import time

log = logging.getLogger("gsrv.rooms")

ROOM_MAX = 4
BATTLE_MAX_TURN = 20


class Member:
    __slots__ = ("uid", "cid", "name", "ready", "level", "acted")

    def __init__(self, uid: int, cid: int, name: str, level: int = 1):
        self.uid = uid
        self.cid = cid
        self.name = name
        self.level = level
        self.ready = False
        self.acted = False


class Battle:
    def __init__(self, room: "Room"):
        self.room = room
        self.room_id = room.id
        self.turn = 1
        self.boss_max_hp = 500 + 250 * len(room.members)
        self.boss_hp = self.boss_max_hp
        self.players = {m.cid: 100 + 20 * m.level for m in room.members.values()}
        self.levels = {m.cid: m.level for m in room.members.values()}
        self.finished = False
        self.win = False
        self.started_at = time.time()
        self.rng = random.Random()

    # ---- 玩家行动 ----
    def action(self, cid: int, act: int = 1) -> int:
        """返回本次造成的伤害"""
        if self.finished or cid not in self.players or self.players[cid] <= 0:
            return 0
        lv = self.levels.get(cid, 1)
        base = 20 + lv * 6
        dmg = base if act == 1 else base * 2          # act=2 视为技能
        dmg = int(dmg * self.rng.uniform(0.85, 1.15))  # 伤害浮动
        self.boss_hp = max(0, self.boss_hp - dmg)
        return dmg

    def all_acted(self) -> bool:
        return all(m.acted for m in self.room.members.values() if self.players.get(m.cid, 0) > 0)

    # ---- 回合结算 ----
    def end_turn(self) -> list[tuple[int, int]]:
        """Boss 反击；返回 [(cid, 受伤)]"""
        hits = []
        alive = [cid for cid, hp in self.players.items() if hp > 0]
        for cid in alive:
            dmg = self.rng.randint(5, 15)
            self.players[cid] = max(0, self.players[cid] - dmg)
            hits.append((cid, dmg))
        for m in self.room.members.values():
            m.acted = False
        self.turn += 1
        if self.boss_hp <= 0:
            self.finished, self.win = True, True
        elif not any(hp > 0 for hp in self.players.values()):
            self.finished, self.win = True, False
        elif self.turn > BATTLE_MAX_TURN:
            self.finished, self.win = True, False
        return hits


class Room:
    def __init__(self, rid: int, owner_uid: int, max_size: int = ROOM_MAX, scene: int = 1):
        self.id = rid
        self.owner_uid = owner_uid
        self.max_size = max(1, min(max_size, ROOM_MAX))
        self.scene = scene
        self.members: dict[int, Member] = {}
        self.state = "WAITING"          # WAITING | BATTLE | CLOSED
        self.battle: Battle | None = None
        self.created_at = time.time()

    # ---- 成员操作 ----
    def add(self, m: Member) -> bool:
        if len(self.members) >= self.max_size or self.state != "WAITING":
            return False
        self.members[m.uid] = m
        return True

    def remove(self, uid: int) -> bool:
        ok = self.members.pop(uid, None) is not None
        if self.owner_uid == uid and self.members:
            self.owner_uid = next(iter(self.members))     # 移交房主
        return ok

    def all_ready(self) -> bool:
        # 房主默认视为已准备
        return all(m.ready or m.uid == self.owner_uid for m in self.members.values())

    def snapshot(self) -> dict:
        return {
            "room_id": self.id, "state": self.state, "owner_uid": self.owner_uid,
            "scene": self.scene, "max_size": self.max_size,
            "members": [
                {"uid": m.uid, "cid": m.cid, "name": m.name,
                 "ready": m.ready, "level": m.level}
                for m in self.members.values()
            ],
        }


class RoomManager:
    def __init__(self):
        self.rooms: dict[int, Room] = {}
        self.uid_room: dict[int, int] = {}     # uid -> room_id
        self._seq = 0

    # ---------- 查询 ----------
    def get(self, rid: int) -> Room | None:
        return self.rooms.get(rid)

    def room_of(self, uid: int) -> Room | None:
        rid = self.uid_room.get(uid)
        return self.rooms.get(rid) if rid else None

    # ---------- 生命周期 ----------
    def create(self, uid: int, cid: int, name: str, level: int = 1,
               max_size: int = ROOM_MAX, scene: int = 1) -> Room:
        if self.room_of(uid):
            raise ValueError("already_in_room")
        self._seq += 1
        room = Room(self._seq, uid, max_size, scene)
        room.add(Member(uid, cid, name, level))
        self.rooms[room.id] = room
        self.uid_room[uid] = room.id
        log.info("room create id=%d owner=%d", room.id, uid)
        return room

    def join(self, rid: int, uid: int, cid: int, name: str, level: int = 1) -> Room:
        room = self.get(rid)
        if room is None:
            raise ValueError("room_not_found")
        if self.room_of(uid):
            raise ValueError("already_in_room")
        if not room.add(Member(uid, cid, name, level)):
            raise ValueError("room_full")
        self.uid_room[uid] = rid
        log.info("room join id=%d uid=%d (%d/%d)", rid, uid, len(room.members), room.max_size)
        return room

    def leave(self, uid: int) -> Room | None:
        room = self.room_of(uid)
        if room is None:
            return None
        room.remove(uid)
        self.uid_room.pop(uid, None)
        if not room.members:
            room.state = "CLOSED"
            self.rooms.pop(room.id, None)
            log.info("room closed id=%d (empty)", room.id)
        log.info("room leave id=%d uid=%d", room.id, uid)
        return room

    def set_ready(self, uid: int, ready: bool = True) -> Room:
        room = self.room_of(uid)
        if room is None:
            raise ValueError("room_not_found")
        if uid in room.members:
            room.members[uid].ready = ready
        return room

    def start(self, uid: int) -> Room:
        room = self.room_of(uid)
        if room is None:
            raise ValueError("room_not_found")
        if room.owner_uid != uid:
            raise ValueError("room_not_owner")
        if not room.all_ready():
            raise ValueError("room_not_ready")
        room.state = "BATTLE"
        room.battle = Battle(room)
        log.info("room start id=%d members=%d boss_hp=%d",
                 room.id, len(room.members), room.battle.boss_hp)
        return room

    def finish(self, rid: int):
        room = self.get(rid)
        if not room:
            return
        for uid in list(room.members.keys()):
            self.uid_room.pop(uid, None)
        room.state = "CLOSED"
        self.rooms.pop(rid, None)
        log.info("room finish/closed id=%d", rid)

    def stats(self) -> dict:
        return {
            "rooms": len(self.rooms),
            "in_battle": sum(1 for r in self.rooms.values() if r.state == "BATTLE"),
            "players": len(self.uid_room),
        }


ROOMS = RoomManager()