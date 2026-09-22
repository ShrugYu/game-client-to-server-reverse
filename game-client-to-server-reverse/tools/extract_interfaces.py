#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_interfaces.py —— 通用「接口清单」提取器

用途：从客户端源码里把**所有服务端接口（opCode / 路由 / 消息名）**扒出来，
      生成可维护的清单，作为反推服务端的「待实现列表」。

支持模式（可叠加，自动识别）：
  1) 字符串 opCode：GetMessage("LOGIN_INFO") / opCode = "LOGIN_INFO"
  2) 数字 opCode  ：case 0x101: / MSG_ID = 1001 / const int LOGIN = 0x101
  3) HTTP 路由    ："/api/login" / $http.post('/login')
  4) protobuf 信封：protobuf.encode("GameMessage.Message", msg)
  5) 类/方法式    ：C2S_Login / SendLoginReq（按前缀聚类）

用法：
  python3 extract_interfaces.py <源码目录> [--out 报告.md] [--json out.json]
  python3 extract_interfaces.py ./lua_src --out interfaces.md

输出：按子系统前缀分组的清单 + 统计 + 未分类项。
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import sys

# ---- 提取模式（正则 -> 说明）----
PATTERNS = [
    # 1) 字符串 opCode
    ("opcode_str", re.compile(r'GetMessage\(\s*"([A-Za-z0-9_]+)"\s*\)')),
    ("opcode_str", re.compile(r'\bopCode\s*=\s*"([A-Za-z0-9_]+)"')),
    ("opcode_str", re.compile(r'\bopcode\s*=\s*"([A-Za-z0-9_]+)"')),
    ("opcode_str", re.compile(r'\bcmd\s*=\s*"([A-Za-z0-9_]+)"')),
    # 2) 数字 opCode / 常量
    ("opcode_num", re.compile(r'\bcase\s+(0x[0-9A-Fa-f]{2,6}|\d{3,6})\s*:')),
    ("opcode_num", re.compile(r'\b[A-Z][A-Z0-9_]*\s*=\s*(0x[0-9A-Fa-f]{3,6})\b')),
    # 3) HTTP 路由
    ("route", re.compile(r'["\'](/(?:api/)?[a-zA-Z][a-zA-Z0-9_/]{2,60})["\']')),
    # 4) protobuf 信封
    ("proto_msg", re.compile(r'protobuf\.encode\(\s*"([A-Za-z0-9_.]+)"')),
    # 5) 类/方法式（C++/C# 常见）
    ("method", re.compile(r'\b(?:void|virtual|public|private|protected)\s+\w*\s*'
                          r'(C2S_[A-Za-z0-9_]+|S2C_[A-Za-z0-9_]+)\s*\(')),
]

SKIP_DIRS = {".git", "node_modules", "venv", "__pycache__", ".idea", "dist", "build"}
TEXT_EXT = {".lua", ".cs", ".js", ".ts", ".java", ".cpp", ".h", ".hpp", ".py",
            ".go", ".as", ".json", ".txt", ".xml", ".yaml", ".yml"}

# 明显的噪音（路由/常量误报）
ROUTE_NOISE = re.compile(r'^/(?:[a-z]+/)*$|^/(?:index|favicon|static|assets|js|css|img)')


def walk(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                yield os.path.join(dirpath, fn)


def scan_file(path: str) -> dict:
    try:
        s = io.open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return {}
    found = collections.defaultdict(set)
    for kind, pat in PATTERNS:
        for m in pat.findall(s):
            v = m if isinstance(m, str) else m
            if not v:
                continue
            if kind == "route" and ROUTE_NOISE.match(v):
                continue
            if kind == "opcode_str" and len(v) < 3:
                continue
            found[kind].add(v)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="客户端源码目录")
    ap.add_argument("--out", default=None, help="输出 Markdown 报告路径")
    ap.add_argument("--json", default=None, help="输出 JSON 路径")
    ap.add_argument("--min-group", type=int, default=1)
    args = ap.parse_args()

    if not os.path.isdir(args.source):
        print(f"目录不存在: {args.source}", file=sys.stderr)
        sys.exit(1)

    all_found = collections.defaultdict(set)
    files = 0
    for fp in walk(args.source):
        files += 1
        for kind, vals in scan_file(fp).items():
            all_found[kind] |= vals

    lines = []
    lines.append("# 接口清单（自动提取）\n")
    lines.append(f"- 扫描目录：`{args.source}`")
    lines.append(f"- 扫描文件：{files}")
    lines.append("")

    summary = {}
    for kind in ("opcode_str", "opcode_num", "route", "proto_msg", "method"):
        vals = sorted(all_found.get(kind, set()))
        summary[kind] = vals
        if not vals:
            continue
        lines.append(f"## {kind}（{len(vals)}）\n")
        # 按前缀分组
        groups = collections.defaultdict(list)
        for v in vals:
            key = re.split(r"[_./]", v.lstrip("/"))[0].upper() if kind != "route" \
                else v.lstrip("/").split("/")[0].upper()
            groups[key].append(v)
        for g in sorted(groups, key=lambda k: -len(groups[k])):
            items = groups[g]
            if len(items) < args.min_group:
                continue
            lines.append(f"### {g} ({len(items)})")
            for it in items[:60]:
                lines.append(f"- `{it}`")
            if len(items) > 60:
                lines.append(f"- … 其余 {len(items) - 60} 项")
            lines.append("")

    report = "\n".join(lines)
    if args.out:
        io.open(args.out, "w", encoding="utf-8").write(report)
        print(f"[+] 报告 -> {args.out}")
    else:
        print(report[:4000])
    if args.json:
        io.open(args.json, "w", encoding="utf-8").write(
            json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"[+] JSON -> {args.json}")

    print(f"[*] 合计: " + ", ".join(f"{k}={len(v)}" for k, v in summary.items()))


if __name__ == "__main__":
    main()