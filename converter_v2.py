#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
converter_v2.py — 纯 AST 转换器，不执行、不找表、不拼写校验，只"看字面、抄格式"

特性：
1) 不再检查模块是否"注册/拼写正确"；LOOK_AT(...) 就是一个类型名 "LOOK_AT" 的节点
2) 不再执行 DSL；只读语法树。没有 NameRef、没有 LazyEnv
3) 不需要 module_defs；端口签名也不查
4) 只认 node['PORT'] 这种下标来连线；其它一律报错
5) 支持前向引用：遇到未定义变量时，先把边放进 unresolved，最后统一解析
6) attrs 若不是字面量 dict（能被 ast.literal_eval），就当成空；不跑表达式、不求值

使用：
convert_dsl_to_graph(dsl_script_path, output_path)
DSL 文件内直接写：
    t = TIME()
    greet = Constant(attrs={"value": "hi"})
    player_pos = Constant(attrs={"value": {"x": 1, "y": 2, "z": 3}})
    xyz = Split(Vector=player_pos["OUT"])     # 注意：必须写 Vector=
    out_dt = OUTPUT(INPUT=t["DELTA TIME"], attrs={"name":"#dt","data_type":2})
    out_g  = OUTPUT(INPUT=greet["OUT"],    attrs={"name":"#g","data_type":4})
    out_x  = OUTPUT(INPUT=xyz["X"],        attrs={"name":"#x","data_type":2})

注意：每个连接都必须 ["PORT"]；传字面量会报错，强制用 Constant。
支持前向调用示例：
    out_dt = OUTPUT(INPUT=t["DELTA TIME"], attrs={"name":"#dt","data_type":2})  # ← 先用
    t = TIME()                                                                  # ← 后定义
转换后会把 t["DELTA TIME"] -> OUTPUT.INPUT 的边在第二遍统一补上。
如果某个变量最终根本没定义，才会报错：引用了未定义变量 'xxx'（前向引用失败）。
"""

from __future__ import annotations
import ast, json, re, sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# ================== 工具与常量 ==================

def _normalize_id_base(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]", "", s).lower()
    return s or "node"

def _auto_label(type_name: str, attrs: Dict[str, Any]) -> str:
    t = (type_name or "").upper()
    if t.startswith("CONSTANT"):
        v = (attrs or {}).get("value", "")
        try:
            import json as _json
            s = v if isinstance(v, str) else _json.dumps(v, ensure_ascii=False)
        except Exception:
            s = str(v)
        s = s.replace("\n", " ").strip()
        return f"Const {s[:18]}{'…' if len(s) > 18 else ''}"
    if t in ("INPUT", "OUTPUT"):
        n = (attrs or {}).get("name")
        return n if isinstance(n, str) and n else type_name
    return type_name or "node"

def _ast_is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None

def _func_name(fn: ast.AST) -> str:
    # Name -> "ADD"; Attribute -> "pkg.mod.FUNC"（保留字面）
    if isinstance(fn, ast.Name):
        return fn.id
    parts = []
    cur = fn
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    # 其它非常规写法（比如调用表达式）直接转源码
    try:
        return ast.unparse(fn)
    except Exception:
        return "<unknown>"

# ================== 核心数据结构 ==================

class Graph:
    def __init__(self) -> None:
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, str]] = []
        self._used: Set[str] = set()
        self._ctr: Dict[str, int] = {}

    def next_id(self, type_name: str) -> str:
        base = _normalize_id_base(type_name)
        i = self._ctr.get(base, 0)
        while True:
            nid = f"{base}_{i}"
            i += 1
            if nid not in self._used:
                self._used.add(nid)
                self._ctr[base] = i
                return nid

    def add_node(self, node: Dict[str, Any]) -> None:
        self.nodes.append(node)

    def add_edge(self, from_node: str, from_port: str, to_node: str, to_port: str) -> None:
        self.edges.append({
            "from_node": from_node, "from_port": from_port,
            "to_node": to_node,     "to_port": to_port
        })

    def to_dict(self) -> Dict[str, Any]:
        return {"nodes": self.nodes, "edges": self.edges}

# ================== 解析器：只看语法，不执行 ==================

class Converter(ast.NodeVisitor):
    """
    只支持： 变量 = 函数调用( 端口名= 上游变量['PORT'] 或 None, ..., attrs= {...}, id=..., label=... )
    * 所有连线只从  node['PORT'] 这种下标里抽取
    * 不执行代码，不做模块注册/校验
    * 输出端口集合来自"别的地方对该节点做的下标访问"，未被引用的输出端口不记录
    """
    def __init__(self) -> None:
        self.g = Graph()
        self.var2node: Dict[str, str] = {}                 # 变量名 -> 节点ID（首次定义为准）
        self.inputs_seen: Dict[str, List[str]] = {}        # 节点ID -> 输入端口顺序
        self.outputs_seen: Dict[str, Set[str]] = {}        # 节点ID -> 被引用到的输出端口
        self.unresolved: List[Tuple[str, str, str, str]] = []  # (up_var, up_port, to_nid, to_port)

    # 仅处理最常见的顶层赋值： x = FUNC(...)
    def visit_Assign(self, node: ast.Assign):
        if isinstance(node.value, ast.Call) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var = node.targets[0].id
            nid = self._emit_call_as_node(node.value)
            # 采用"首次定义为准"，避免多次赋值造成前后引用歧义
            if var not in self.var2node:
                self.var2node[var] = nid
        # 继续遍历（以便处理嵌套结构里可能出现的 Call）
        self.generic_visit(node)

    # 也允许裸调用（不赋值）作为产生节点的副作用
    def visit_Expr(self, node: ast.Expr):
        if isinstance(node.value, ast.Call):
            self._emit_call_as_node(node.value)
        self.generic_visit(node)

    # —— 核心：把一次 Call 变成一个节点，并根据 kwargs 中的下标建立边 —— #
    def _emit_call_as_node(self, call: ast.Call) -> str:
        type_name = _func_name(call.func)

        # 解析 kwargs：attrs/id/label 是保留字；其它视为输入端口名
        attrs: Dict[str, Any] = {}
        fixed_id = None
        label = None
        conns: List[tuple[str, ast.AST]] = []  # (input_port, value_expr)

        for kw in call.keywords or []:
            if kw.arg is None:
                continue  # 跳过 **kwargs 这种
            key = kw.arg
            if key == "attrs":
                try:
                    attrs = ast.literal_eval(kw.value)  # 必须是常量 dict
                    if not isinstance(attrs, dict):
                        attrs = {}
                except Exception:
                    # 不执行表达式；强制静态。读不到就空。
                    attrs = {}
            elif key == "id":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    fixed_id = kw.value.value
            elif key == "label":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    label = kw.value.value
            else:
                conns.append((key, kw.value))

        # 分配 ID & 记录节点（inputs/outputs 先占位，稍后补齐）
        nid = fixed_id or self.g.next_id(type_name)
        if fixed_id and nid in self.g._used:
            # 不做严格冲突检查：若用户重复 id，就自动生成新 id（保持"少检查"原则）
            nid = self.g.next_id(type_name)

        self.inputs_seen.setdefault(nid, [])
        self.outputs_seen.setdefault(nid, set())

        node_rec = {
            "id": nid,
            "type": type_name,                          # 原样保留
            "label": _auto_label(type_name, attrs) if label is None else label,
            "attrs": attrs,
            "inputs": [],   # 稍后填：遍历 conns 的端口名
            "outputs": [],  # 稍后填：由别处引用该节点['PORT'] 时收集
        }
        self.g.add_node(node_rec)

        # 建立边：只接受 上游变量['PORT'] 或 None
        seen_inputs: List[str] = []
        for port_name, expr in conns:
            if _ast_is_none(expr):
                seen_inputs.append(port_name)
                continue
            # 期望形态： Name['PORT']
            if isinstance(expr, ast.Subscript) and isinstance(expr.value, ast.Name):
                up_var = expr.value.id
                # 切片必须是字符串常量
                sl = expr.slice
                if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    up_port = sl.value
                else:
                    try:
                        up_port = ast.literal_eval(sl)
                    except Exception:
                        raise TypeError(f"{type_name}.{port_name}: 端口下标必须是字符串字面量")
                # 已定义：立刻连
                if up_var in self.var2node:
                    up_nid = self.var2node[up_var]
                    self.g.add_edge(up_nid, up_port, nid, port_name)
                    self.outputs_seen.setdefault(up_nid, set()).add(up_port)
                else:
                    # 未定义：记录未决，稍后统一解析
                    self.unresolved.append((up_var, up_port, nid, port_name))
                seen_inputs.append(port_name)
            else:
                # 不做自动 Constant、不做句柄直传；你明确要求"必须通过下标"，这里就硬报错。
                raise TypeError(f"{type_name}.{port_name}: 只接受 node['PORT'] 或 None，禁止直接传变量/字面量/调用结果")

        # 补齐 node.inputs（按出现顺序）
        node_rec["inputs"] = [{"name": p, "type": ""} for p in seen_inputs]
        return nid

    def resolve_unresolved(self):
        for up_var, up_port, to_nid, to_port in self.unresolved:
            if up_var not in self.var2node:
                # 真未定义：这才报错（前向引用失败）
                raise NameError(f"{to_nid}.{to_port}: 引用了未定义变量 '{up_var}'（前向引用失败）")
            up_nid = self.var2node[up_var]
            self.g.add_edge(up_nid, up_port, to_nid, to_port)
            self.outputs_seen.setdefault(up_nid, set()).add(up_port)
        self.unresolved.clear()

    # 最后一次性把 outputs 列表填回去
    def finalize_outputs(self):
        nid2rec = {n["id"]: n for n in self.g.nodes}
        for nid, outs in self.outputs_seen.items():
            nid2rec[nid]["outputs"] = [{"name": p, "type": ""} for p in sorted(outs, key=str)]

# ================== 主流程 ==================

def convert_dsl_to_graph(dsl_script_path: Path, output_path: Path) -> None:
    """
    使用纯 AST 转换器将 DSL 转为 graph.json（不需要 module_defs）
    """
    try:
        code = Path(dsl_script_path).read_text(encoding="utf-8")
    except Exception as e:
        sys.exit(f"Failed to read DSL '{dsl_script_path}': {e}")

    try:
        tree = ast.parse(code, filename=str(dsl_script_path))
        cvt = Converter()
        cvt.visit(tree)
        # 先解析前向引用，再补 outputs
        cvt.resolve_unresolved()
        cvt.finalize_outputs()
    except Exception as e:
        sys.exit(f"Error executing DSL: {e}")

    try:
        out = {"nodes": cvt.g.nodes, "edges": cvt.g.edges}
        Path(output_path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        sys.exit(f"Failed to write graph JSON '{output_path}': {e}")

if __name__ == "__main__":
    # 示例：把 demo_v2.py 转为 graph.json
    DSL_PATH = Path("demo_v2.py")
    OUT_PATH = Path("graph.json")

    if not DSL_PATH.exists():
        # 写入一个可运行的示例 DSL
        DSL_PATH.write_text(
            """
# demo_v2.py — 纯 AST 转换器 DSL 样例
# 时间源
t = TIME()

# 常量（字符串、向量）
greet = Constant(attrs={"value": "多端口测试"})
player_pos = Constant(attrs={"value": {"x": 1, "y": 2, "z": 3}})

# 分解向量
xyz = Split(Vector=player_pos["OUT"])

# 输出：data_type 用数字
out_dt = OUTPUT(INPUT=t["DELTA TIME"], attrs={"name": "#deltaTime", "data_type": 2})
out_g  = OUTPUT(INPUT=greet["OUT"],    attrs={"name": "#greeting",  "data_type": 4})
out_x  = OUTPUT(INPUT=xyz["X"],        attrs={"name": "#playerX",   "data_type": 2})
        """.strip(),
            encoding="utf-8",
        )

    convert_dsl_to_graph(DSL_PATH, OUT_PATH)
    print(f"Graph saved -> {OUT_PATH}")
