#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.utils
=========

通用工具函数：JSON 读写、字符串归一化与模糊匹配等。
"""

import json
import re
import sys
from pathlib import Path
from difflib import get_close_matches
from typing import Any, List


def load_json(path: Path, desc: str) -> Any:
    """
    读取 JSON 文件，出错时给出友好的中文提示并退出。
    """
    if not path.exists():
        sys.exit(f"错误：未找到 {desc} 文件 \"{path}\"")
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"错误：{desc} 文件 \"{path}\" 解析失败：{e}")


def normalize(s: str) -> str:
    """将字符串转为小写并移除非字母数字字符，用于构建模糊匹配 key。"""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def fuzzy_match(name: str, candidates: List[str], cutoff: float) -> str | None:
    """
    使用 difflib 做一次简单的“最接近匹配”，找不到时返回 None。
    """
    return (get_close_matches(name, candidates, n=1, cutoff=cutoff) or [None])[0]


__all__ = ["load_json", "normalize", "fuzzy_match"]

