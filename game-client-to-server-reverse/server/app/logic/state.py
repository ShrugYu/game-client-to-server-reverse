"""app.logic.state —— 全局游戏状态（在线玩家、场景）"""


class GameState:
    def __init__(self):
        # cid -> 玩家快照
        self.players: dict[int, dict] = {}
        # scene -> set(cid)
        self.scenes: dict[int, set] = {}

    def enter(self, cid: int, snapshot: dict):
        self.players[cid] = snapshot
        scene = snapshot.get("scene", 1)
        self.scenes.setdefault(scene, set()).add(cid)

    def leave(self, cid: int):
        snap = self.players.pop(cid, None)
        if snap:
            self.scenes.get(snap.get("scene", 1), set()).discard(cid)

    def move(self, cid: int, scene: int | None = None, x=None, y=None):
        snap = self.players.get(cid)
        if not snap:
            return
        if scene is not None and scene != snap.get("scene"):
            self.scenes.get(snap["scene"], set()).discard(cid)
            snap["scene"] = scene
            self.scenes.setdefault(scene, set()).add(cid)
        if x is not None:
            snap["x"] = x
        if y is not None:
            snap["y"] = y


STATE = GameState()