"""app.config —— 配置加载（分层：默认值 → config.yaml → 环境变量 → 命令行）"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "server": {"host": "0.0.0.0", "port": 8888, "transport": "tcp",
               "backlog": 128, "max_connections": 5000,
               "idle_timeout": 30, "max_frame": 1 << 20},
    "frame": {"length_size": 4, "length_endian": "big",
              "length_includes_self": False, "opcode_size": 2,
              "opcode_endian": "little"},
    "crypto": {"enabled": False, "algorithm": "xor", "key": "",
               "per_connection": False},
    "compress": {"enabled": False, "algorithm": "zlib", "min_size": 256},
    "serialize": {"format": "binary", "fields": []},
    "database": {"url": "sqlite:///./data/game.db", "echo": False, "pool_size": 5},
    "cache": {"enabled": False, "url": "redis://127.0.0.1:6379/0"},
    "game": {"name": "MyGame", "version": "1.0.0", "require_version": True,
             "expected_version": "1.0.0", "server_authoritative": True,
             "auto_push_char_list": True},
    "log": {"level": "INFO", "file": "./logs/gsrv.log",
            "rotate_mb": 32, "keep_files": 7},
    "gm": {"enabled": True, "host": "127.0.0.1", "port": 9900},
    "bots": {"enabled": True, "tick_hz": 5, "auto_fill": 0,
             "default_scene": 1, "difficulty": "normal"},
    "security": {"token_secret": "change_me", "token_ttl": 86400,
                 "max_conn_per_ip": 32, "login_rate_limit": 10},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def get(self, path: str, default=None):
        cur: Any = self._data
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    @property
    def raw(self) -> dict:
        return self._data

    @classmethod
    def load(cls, path: str | None = None) -> "Config":
        data = dict(DEFAULTS)
        if path is None:
            path = os.environ.get("GSRV_CONFIG", "./config/config.yaml")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = _deep_merge(data, yaml.safe_load(f) or {})

        # 环境变量覆盖（GSRV_SERVER__PORT=9999 形式）
        for env_key, env_val in os.environ.items():
            if not env_key.startswith("GSRV_"):
                continue
            parts = env_key[5:].lower().split("__")
            if len(parts) < 2:
                continue
            cur = data
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            val = yaml.safe_load(env_val)
            cur[parts[-1]] = val

        return cls(data)


CFG: Config | None = None


def get_config() -> Config:
    global CFG
    if CFG is None:
        CFG = Config.load()
    return CFG