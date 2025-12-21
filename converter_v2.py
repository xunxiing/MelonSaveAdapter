#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
converter_v2.py
==============

兼容入口：DSL(AST) -> graph.json。

历史上这里包含完整实现；现在实现已拆分到 `src/converter/` 下，
本文件仅保留对外 API 与命令行入口，避免其它模块改动。
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.converter.api import convert_dsl_to_graph


def _write_demo_dsl(path: Path) -> None:
    path.write_text(
        (
            "# demo_v2.py — AST converter DSL sample\n"
            "t = TIME()\n"
            "greet = Constant(attrs={\"value\": \"hello\"})\n"
            "player_pos = Constant(attrs={\"value\": {\"x\": 1, \"y\": 2, \"z\": 3}})\n"
            "xyz = Split(Vector=player_pos[\"OUT\"])\n"
            "out_dt = OUTPUT(INPUT=t[\"DELTA TIME\"], attrs={\"name\": \"#deltaTime\", \"data_type\": 2})\n"
            "out_g  = OUTPUT(INPUT=greet[\"OUT\"],    attrs={\"name\": \"#greeting\",  \"data_type\": 4})\n"
            "out_x  = OUTPUT(INPUT=xyz[\"X\"],        attrs={\"name\": \"#playerX\",   \"data_type\": 2})\n"
        ),
        encoding="utf-8",
    )


__all__ = ["convert_dsl_to_graph"]


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        DSL_PATH = Path(sys.argv[1])
        OUT_PATH = Path(sys.argv[2])
    else:
        DSL_PATH = Path("demo_v2.py")
        OUT_PATH = Path("graph.json")

    if not DSL_PATH.exists():
        if len(sys.argv) >= 3:
            sys.exit(f"输入文件 '{DSL_PATH}' 不存在")
        _write_demo_dsl(DSL_PATH)

    convert_dsl_to_graph(DSL_PATH, OUT_PATH)
    print(f"Graph saved -> {OUT_PATH}")

