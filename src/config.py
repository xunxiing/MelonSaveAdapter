#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.config
==========

集中管理 DSL 流水线用到的路径与常量。
所有路径都基于项目根目录计算，并约定：
- Python 源码放在 `src/` 下面
- 运行过程中生成的中间结果和最终产物放在 `output/` 下面
"""

from pathlib import Path


# 项目根目录（即包含 main.py 的目录）
ROOT_DIR = Path(__file__).resolve().parent.parent

# 源码目录（目前仅用于引用，不强制使用）
SRC_DIR = ROOT_DIR / "src"

# 统一的输出目录
OUTPUT_DIR = ROOT_DIR / "output"


# ---------------------- DSL / JSON 文件路径 ----------------------

# DSL 输入脚本
DSL_INPUT_PATH = ROOT_DIR / "input.py"

# 由 converter_v2 生成的中间图结构
GRAPH_PATH = OUTPUT_DIR / "graph.json"

# 游戏原始配置 / 存档数据
MODULE_DEF_PATH = ROOT_DIR / "moduledef.json"
DATA_PATH = ROOT_DIR / "data.json"
RULES_PATH = ROOT_DIR / "data_type_rules.json"

# 由 DSL 图生成的连线指令
CONNECT_OUT_PATH = OUTPUT_DIR / "output.json"

# 连线前后用于批量操作的存档文件
MODIFIED_SAVE_PATH = OUTPUT_DIR / "data_after_modify.json"
FINAL_SAVE_PATH = OUTPUT_DIR / "ungraph.json"


# ---------------------- 其它常量配置 ----------------------

FUZZY_CUTOFF_NODE: float = 0.10
FUZZY_CUTOFF_PORT: float = 0.40


def ensure_output_dir() -> None:
    """
    确保输出目录存在。
    在流水线入口和任何可能单独运行的阶段前调用。
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


__all__ = [
    "ROOT_DIR",
    "SRC_DIR",
    "OUTPUT_DIR",
    "DSL_INPUT_PATH",
    "GRAPH_PATH",
    "MODULE_DEF_PATH",
    "DATA_PATH",
    "RULES_PATH",
    "CONNECT_OUT_PATH",
    "MODIFIED_SAVE_PATH",
    "FINAL_SAVE_PATH",
    "FUZZY_CUTOFF_NODE",
    "FUZZY_CUTOFF_PORT",
    "ensure_output_dir",
]

