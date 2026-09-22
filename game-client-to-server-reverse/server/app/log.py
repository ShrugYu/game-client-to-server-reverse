"""app.log —— 日志（控制台 + 轮转文件）"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(level="INFO", file=None, rotate_mb=32, keep_files=7):
    root = logging.getLogger()
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    if file:
        os.makedirs(os.path.dirname(os.path.abspath(file)), exist_ok=True)
        fh = RotatingFileHandler(
            file, maxBytes=rotate_mb * 1024 * 1024,
            backupCount=keep_files, encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    return root
