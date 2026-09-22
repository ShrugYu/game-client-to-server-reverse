"""app.main —— 服务端入口

用法:
    python -m app.main                          # 默认 ./config/config.yaml
    python -m app.main -c /etc/gsrv/config.yaml
    GSRV_SERVER__PORT=9000 python -m app.main   # 环境变量覆盖
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from .config import get_config, Config
from .log import setup_logging
from .net.server import GameServer
from .store.db import init_db, get_db, Database

log = logging.getLogger("gsrv.main")


async def run(cfg):
    setup_logging(
        level=cfg.get("log.level", "INFO"),
        file=cfg.get("log.file"),
        rotate_mb=int(cfg.get("log.rotate_mb", 32)),
        keep_files=int(cfg.get("log.keep_files", 7)),
    )
    log.info("===== %s server starting =====", cfg.get("game.name"))
    await init_db(cfg)

    server = GameServer(cfg)
    await server.start()

    # GM 控制台（可选）
    gm_task = None
    if cfg.get("gm.enabled", False):
        from .gm.console import start_gm
        gm_task = asyncio.create_task(start_gm(cfg, server))

    stop_event = asyncio.Event()

    def _sig(*_):
        log.info("signal received, shutting down...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig)
        except NotImplementedError:
            pass  # Windows

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        if gm_task:
            gm_task.cancel()
        await server.stop()
        db = get_db()
        await db.close()
        log.info("===== server stopped =====")


def main():
    ap = argparse.ArgumentParser(description="Game Mock Server")
    ap.add_argument("-c", "--config", default=None, help="config.yaml 路径")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    from . import config as cfgmod
    cfgmod.CFG = cfg
    try:
        asyncio.run(run(cfg))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()