#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.type_inference
==================

基于 DSL 生成的 graph.json（nodes/edges）做“自动 GateDataType 推断”。

目标：
- AI 忘记写 attrs.data_type 时，仍然能根据连线与常量/变量定义推导出合理类型；
- 类型系统保持简单：1/2/4/8（Signal/Decimal/String/Vector）。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.utils import fuzzy_match, normalize
from src.config import FUZZY_CUTOFF_PORT


# 旧版（以及部分推断逻辑）常用 1/2/4/8；
# 新版数组模块会引入 ArrayXxx（在本项目里用 128/256/512/1024 表示）。
TYPE_DOMAIN = {1, 2, 4, 8, 128, 256, 512, 1024}


def _type_from_port_type_str(s: str | None) -> int | None:
    if not isinstance(s, str):
        return None
    t = s.strip()
    if not t:
        return None
    key = t.lower()
    if key in ("decimal", "number"):
        return 2
    if key in ("string",):
        return 4
    if key in ("vector",):
        return 8
    if key in ("entity", "signal"):
        return 1
    if key in ("integernumber", "integer"):
        # 旧类型系统没有单独的 IntegerNumber，这里按 Number 处理（用于推断 GateDataType）
        return 2
    if key in ("arraynumber",):
        return 128
    if key in ("arraystring",):
        return 256
    if key in ("arrayvector",):
        return 512
    if key in ("arrayentity",):
        return 1024
    if key in ("any",):
        return None
    return None


def _parse_explicit_data_type(attrs: Dict[str, Any]) -> int | None:
    dt = attrs.get("data_type", attrs.get("datatype"))
    if isinstance(dt, bool):
        return None
    if isinstance(dt, int) and dt in TYPE_DOMAIN:
        return dt
    if isinstance(dt, str) and dt.strip().isdigit():
        v = int(dt.strip())
        return v if v in TYPE_DOMAIN else None
    if isinstance(dt, str):
        t = _type_from_port_type_str(dt)
        return t if t in TYPE_DOMAIN else None
    return None


def _infer_constant_type(attrs: Dict[str, Any]) -> int | None:
    if "value" not in attrs:
        return None
    v = attrs.get("value")
    if isinstance(v, (int, float)):
        return 2
    if isinstance(v, str):
        return 4
    if isinstance(v, dict) and all(k in v for k in ("x", "y", "z")):
        return 8
    if isinstance(v, (list, tuple)):
        if not v:
            return None
        # ArrayNumber / ArrayString / ArrayVector
        if all(isinstance(x, (int, float)) for x in v):
            return 128
        if all(isinstance(x, str) for x in v):
            return 256
        # ArrayVector: 支持字典格式 {"x": ..., "y": ..., "z": ...} 和列表格式 [x, y, z, ...]
        if all(isinstance(x, dict) and all(k in x for k in ("x", "y", "z")) for x in v):
            return 512
        # 检查是否为向量列表（每个元素是包含至少3个数字的列表）
        if all(isinstance(x, (list, tuple)) and len(x) >= 3 and all(isinstance(i, (int, float)) for i in x[:3]) for x in v):
            return 512
    return None


def _port_index(port_name: str, port_list: List[str]) -> int | None:
    if not port_list:
        return None
    if len(port_list) == 1:
        return 0
    if isinstance(port_name, str) and port_name.isdigit():
        idx = int(port_name)
        return idx if 0 <= idx < len(port_list) else None
    normalized_ports = [normalize(p) for p in port_list]
    best = fuzzy_match(normalize(str(port_name)), normalized_ports, FUZZY_CUTOFF_PORT)
    return normalized_ports.index(best) if best is not None else None


@dataclass(frozen=True)
class _PortTypeExpr:
    kind: str  # "fixed" | "var"
    value: int | str


class _UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}
        self.fixed: Dict[str, int] = {}
        self.conflicts: List[Tuple[str, int, int]] = []
        for it in items:
            self.parent[it] = it
            self.rank[it] = 0

    def find(self, x: str) -> str:
        p = self.parent.get(x, x)
        if p != x:
            self.parent[x] = self.find(p)
        return self.parent.get(x, x)

    def set_fixed(self, x: str, t: int) -> None:
        if t not in TYPE_DOMAIN:
            return
        r = self.find(x)
        cur = self.fixed.get(r)
        if cur is None:
            self.fixed[r] = t
        elif cur != t:
            self.conflicts.append((r, cur, t))

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

        ta = self.fixed.get(ra)
        tb = self.fixed.get(rb)
        if ta is None and tb is not None:
            self.fixed[ra] = tb
        elif ta is not None and tb is not None and ta != tb:
            self.conflicts.append((ra, ta, tb))


def infer_gate_data_types(
    graph: Dict[str, Any],
    *,
    node_map: Dict[str, Dict[str, Any]],
    chip_index: Dict[str, Dict[str, Any]],
    rules: Dict[str, Any],
    module_defs: Dict[str, Any],
) -> Dict[str, int]:
    """
    返回：original_node_id -> GateDataType(int, in {1,2,4,8})
    """
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    nodes_by_id: Dict[str, Dict[str, Any]] = {
        n.get("id"): n for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), str)
    }

    node_ids = [n.get("id") for n in nodes if isinstance(n.get("id"), str)]
    uf = _UnionFind(node_ids)

    node_default: Dict[str, int | None] = {}
    vector_hints: Dict[str, int] = {}

    # 1) 给每个节点一个“默认类型”与“已知类型”（显式/常量/变量）
    for n in nodes:
        nid = n.get("id")
        if not isinstance(nid, str):
            continue
        attrs = n.get("attrs") or {}
        if not isinstance(attrs, dict):
            attrs = {}

        explicit = _parse_explicit_data_type(attrs)
        if explicit is not None:
            uf.set_fixed(nid, explicit)
            node_default[nid] = explicit
            continue

        meta = node_map.get(nid) or {}
        friendly = str(meta.get("friendly_name", "")).lower()

        if friendly == "constant":
            t = _infer_constant_type(attrs)
            if t is not None:
                uf.set_fixed(nid, t)
            node_default[nid] = t
            continue

        if friendly == "variable":
            var_gate = meta.get("var_gate_type")
            t = _type_from_port_type_str(var_gate) if isinstance(var_gate, str) else None
            if t is not None:
                uf.set_fixed(nid, t)
            node_default[nid] = t
            continue

        op_type = meta.get("op_type")
        mod_def = module_defs.get(str(op_type)) if op_type is not None else None
        gate_default = None
        if isinstance(mod_def, dict):
            gd = mod_def.get("gate_data_type")
            if isinstance(gd, int) and gd in TYPE_DOMAIN:
                gate_default = gd
        node_default[nid] = gate_default

    def port_expr(nid: str, *, direction: str, port_name: str) -> _PortTypeExpr | None:
        meta = node_map.get(nid) or {}
        friendly = str(meta.get("friendly_name", "")).lower()

        chip_key = normalize(str(meta.get("friendly_name", "")))
        info = chip_index.get(chip_key) or {}
        port_list = info.get(direction) or []
        if not isinstance(port_list, list):
            port_list = []

        inst_ports = None
        if not port_list:
            inst = nodes_by_id.get(nid) or {}
            inst_ports = inst.get(direction) or []
            if not isinstance(inst_ports, list):
                inst_ports = []
            port_list = [p.get("name", "") if isinstance(p, dict) else str(p) for p in inst_ports]

        idx = _port_index(port_name, [str(p) for p in port_list])
        if idx is None:
            return None

        # 特殊节点：I/O / Variable / Constant 的端口类型规则在此内置
        if friendly == "output":
            return _PortTypeExpr("var", nid)
        if friendly == "input":
            return _PortTypeExpr("var", nid)
        if friendly == "variable":
            var_gate = meta.get("var_gate_type")
            t = _type_from_port_type_str(var_gate) if isinstance(var_gate, str) else None
            if direction == "inputs":
                # inputs: ["Value", "Set"]
                if idx == 1:
                    return _PortTypeExpr("fixed", 1)
                return _PortTypeExpr("fixed", t) if t is not None else None
            # outputs: ["Value"]
            return _PortTypeExpr("fixed", t) if t is not None else None
        if friendly == "constant":
            t = node_default.get(nid)
            return _PortTypeExpr("fixed", t) if isinstance(t, int) else None

        op_type = meta.get("op_type")
        op_key = str(op_type) if op_type is not None else None
        rule = rules.get(op_key) if op_key is not None else None
        if isinstance(rule, dict):
            rule_list = rule.get("inputs" if direction == "inputs" else "outputs") or []
            if isinstance(rule_list, list) and idx < len(rule_list):
                r = rule_list[idx]
                if r is None or r == "any":
                    return None
                if r == "same":
                    return _PortTypeExpr("var", nid)
                if isinstance(r, int) and r in TYPE_DOMAIN:
                    return _PortTypeExpr("fixed", r)

        # fallback: graph.json 节点实例端口 type（若提供）
        if isinstance(inst_ports, list) and idx < len(inst_ports):
            p = inst_ports[idx]
            if isinstance(p, dict):
                t = _type_from_port_type_str(p.get("type"))
                if t is not None:
                    return _PortTypeExpr("fixed", t)

        # fallback：无规则的模块，把 moduledef 里的端口 type 当做固定类型
        mod_def = module_defs.get(op_key) if op_key is not None else None
        if isinstance(mod_def, dict):
            ports = mod_def.get(direction) or []
            if isinstance(ports, list) and idx < len(ports):
                p = ports[idx]
                if isinstance(p, dict):
                    t = _type_from_port_type_str(p.get("type"))
                    if t is not None:
                        return _PortTypeExpr("fixed", t)

        return None

    # 2) 根据每条边做类型约束（端口类型相等）
    for e in edges:
        if not isinstance(e, dict):
            continue
        f_nid = e.get("from_node")
        t_nid = e.get("to_node")
        f_port = e.get("from_port")
        t_port = e.get("to_port")
        if not all(isinstance(x, str) for x in (f_nid, t_nid, f_port, t_port)):
            continue

        left = port_expr(f_nid, direction="outputs", port_name=f_port)
        right = port_expr(t_nid, direction="inputs", port_name=t_port)
        if left is None or right is None:
            continue

        if left.kind == "fixed" and right.kind == "fixed":
            if left.value != right.value:
                # 冲突：先记录；最后仍按“显式/默认”兜底
                pass
            continue
        if left.kind == "var" and right.kind == "fixed":
            # 兼容规则：Number(Decimal) 可以直接连 Vector。
            # 这里把 Vector 视为“软约束”：不强制回推到上游节点类型，只做一个偏好提示。
            if int(right.value) == 8:
                vector_hints[str(left.value)] = vector_hints.get(str(left.value), 0) + 1
                continue
            uf.set_fixed(str(left.value), int(right.value))
            continue
        if left.kind == "fixed" and right.kind == "var":
            if int(left.value) == 8:
                vector_hints[str(right.value)] = vector_hints.get(str(right.value), 0) + 1
                continue
            uf.set_fixed(str(right.value), int(left.value))
            continue
        if left.kind == "var" and right.kind == "var":
            uf.union(str(left.value), str(right.value))
            continue

    # 2.5) ArraysGet 多态：若已能确定其 ArrayXxx 类型，则把 Output[0] 的元素类型回灌给下游节点
    for e in edges:
        if not isinstance(e, dict):
            continue
        f_nid = e.get("from_node")
        t_nid = e.get("to_node")
        f_port = e.get("from_port")
        t_port = e.get("to_port")
        if not all(isinstance(x, str) for x in (f_nid, t_nid, f_port, t_port)):
            continue

        f_meta = node_map.get(f_nid) or {}
        if str(f_meta.get("friendly_name", "")).lower() != "arraysget":
            continue

        chip_key = normalize(str(f_meta.get("friendly_name", "")))
        info = chip_index.get(chip_key) or {}
        outs = info.get("outputs") or []
        if not isinstance(outs, list):
            continue
        out_idx = _port_index(f_port, [str(p) for p in outs])
        if out_idx != 0:
            continue

        arr_t = uf.fixed.get(uf.find(f_nid))
        if arr_t is None:
            arr_t = node_default.get(f_nid)
        if not isinstance(arr_t, int):
            continue
        if arr_t == 128:
            elem_t = 2
        elif arr_t == 256:
            elem_t = 4
        elif arr_t == 512:
            elem_t = 8
        elif arr_t == 1024:
            elem_t = 1
        else:
            continue

        right = port_expr(t_nid, direction="inputs", port_name=t_port)
        if right is None:
            continue
        if right.kind == "var":
            uf.set_fixed(str(right.value), int(elem_t))

    # 3) 给每个集合选择最终类型：fixed 优先，否则用集合内默认值投票
    groups: Dict[str, List[str]] = {}
    for nid in node_ids:
        groups.setdefault(uf.find(nid), []).append(nid)

    group_type: Dict[str, int] = {}
    for root, members in groups.items():
        fixed = uf.fixed.get(uf.find(root))
        if fixed is not None:
            group_type[root] = fixed
            continue
        defaults = [node_default.get(m) for m in members if node_default.get(m) in TYPE_DOMAIN]
        c = Counter([d for d in defaults if isinstance(d, int)])

        # 把“vector 软约束”作为额外投票，避免 Vector 端口把整条链强制改成 Vector，
        # 但在缺乏更强信息时仍能倾向于 Vector。
        hint_sum = sum(vector_hints.get(m, 0) for m in members)
        if hint_sum:
            c[8] += hint_sum

        if not c:
            continue

        best_count = max(c.values())
        best_types = [t for t, cnt in c.items() if cnt == best_count and t in TYPE_DOMAIN]
        if 8 in best_types:
            group_type[root] = 8
        else:
            group_type[root] = int(best_types[0])

    out: Dict[str, int] = {}
    for nid in node_ids:
        root = uf.find(nid)
        t = group_type.get(root)
        if isinstance(t, int) and t in TYPE_DOMAIN:
            out[nid] = t
    return out


__all__ = ["infer_gate_data_types"]
