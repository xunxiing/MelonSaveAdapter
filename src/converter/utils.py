from __future__ import annotations

import ast
import re
from typing import Any, Dict, List


def _normalize_id_base(s: str) -> str:
    """把类型名归一化成节点 ID 前缀。"""
    s = re.sub(r"[^a-zA-Z0-9_]", "", s).lower()
    return s or "node"


def _auto_label(type_name: str, attrs: Dict[str, Any]) -> str:
    """为节点自动生成一个比较友好的 label。"""
    t = (type_name or "").upper()
    if t.startswith("CONSTANT"):
        v = (attrs or {}).get("value", "")
        try:
            import json as _json

            s = v if isinstance(v, str) else _json.dumps(v, ensure_ascii=False)
        except Exception:
            s = str(v)
        s = s.replace("\n", " ").strip()
        tail = "…" if len(s) > 18 else ""
        return f"Const {s[:18]}{tail}"
    if t in ("INPUT", "OUTPUT"):
        n = (attrs or {}).get("name")
        return n if isinstance(n, str) and n else type_name
    return type_name or "node"


def _ast_is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _func_name(fn: ast.AST) -> str:
    """把调用表达式里的函数对象转换成一个字符串名字。"""
    if isinstance(fn, ast.Name):
        return fn.id
    parts: List[str] = []
    cur: ast.AST = fn
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    try:
        return ast.unparse(fn)  # type: ignore[attr-defined]
    except Exception:
        return "<unknown>"


__all__ = ["_normalize_id_base", "_auto_label", "_ast_is_none", "_func_name"]

