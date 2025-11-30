#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py / integrated_pipeline.py
================================
整体流程：
0. 使用 converter_v2 将 DSL (`input.py`) 转成 `graph.json`
1. 解析 `graph.json`，按模块定义 (`moduledef.json`) 构建要添加的模块列表
2. 批量添加模块到存档 (`data.json`)
3. 根据 DSL 中的 `data_type` / 常量 value 生成修改指令并应用
4. 根据 DSL 连接关系生成连线指令 `output.json`
5. 调用 `batch_connect.apply_connections` 批量连线，生成 `ungraph.json`
6. 使用 `layout_chip` 对最终图做自动布局
7. 使用 `archive_creator` 生成 `.melsave` 归档

本文件同时新增 DSL 特性支持：
- 节点变量可以直接作为参数（“裸节点变量”），等价于该节点的唯一输出端口；
  若该模块有多个输出端口则会报错提示用户显式指定端口。
- 支持使用数字序号访问端口：  node[0]，与旧版 node["输出端口名"] 共存。
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from difflib import get_close_matches

from converter_v2 import convert_dsl_to_graph
from constantvalue import apply_constant_modifications
from batch_add_modules import add_modules
from modifier import apply_data_type_modifications
from layout_chip import run_layout_engine, find_and_update_chip_graph
from batch_connect import apply_connections
from archive_creator import run_archive_creation_stage


# Windows 下确保控制台能正常打印 UTF-8
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# =============================== 路径配置 ===============================

DSL_INPUT_PATH = Path("input.py")       # DSL 输入
GRAPH_PATH = Path("graph.json")         # AST 转换后的中间图
MODULE_DEF_PATH = Path("moduledef.json")
DATA_PATH = Path("data.json")
CONNECT_OUT_PATH = Path("output.json")
RULES_PATH = Path("data_type_rules.json")

MODIFIED_SAVE_PATH = Path("data_after_modify.json")
FINAL_SAVE_PATH = Path("ungraph.json")

FUZZY_CUTOFF_NODE = 0.10
FUZZY_CUTOFF_PORT = 0.40


# =============================== 工具函数 ===============================

def load_json(path: Path, desc: str) -> Any:
    if not path.exists():
        sys.exit(f"错误：未找到 {desc} 文件 \"{path}\"")
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"错误：{desc} 文件 \"{path}\" 解析失败：{e}")


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def fuzzy_match(name: str, candidates: List[str], cutoff: float) -> str | None:
    return (get_close_matches(name, candidates, n=1, cutoff=cutoff) or [None])[0]


# =========================== 阶段 0：DSL -> graph.json ===========================

def run_stage0_convert_dsl_to_graph(dsl_path: Path, out_graph_path: Path) -> None:
    """
    使用 converter_v2.convert_dsl_to_graph 将 DSL 脚本转为 graph.json。
    """
    print("--- 阶段 0: 将 input.py 转换为 graph.json ---")
    convert_dsl_to_graph(dsl_script_path=dsl_path, output_path=out_graph_path)
    print(f"✔ 已从 '{dsl_path}' 生成 '{out_graph_path}'")


# =========================== graph.json 解析相关 ===========================

def build_chip_index_from_moduledef(module_defs: Dict[str, Any]) -> Dict[str, dict]:
    """
    从 moduledef.json 构建一个索引：
        归一化友好名 -> {friendly_name, game_name, inputs, outputs}
    """
    chip_index: Dict[str, dict] = {}
    for _mod_id, mod_data in module_defs.items():
        source_info = mod_data.get("source_info", {})
        friendly_name = source_info.get("chip_names_friendly_name")
        game_name = source_info.get("allmod_viewmodel")
        if not friendly_name or not game_name:
            continue
        key = normalize(friendly_name)
        chip_index[key] = {
            "friendly_name": friendly_name,
            "game_name": game_name,
            "inputs": [p.get("name", "Input") for p in mod_data.get("inputs", [])],
            "outputs": [p.get("name", "Output") for p in mod_data.get("outputs", [])],
        }

    # 补充内置节点（输入 / 输出 / 常量）
    chip_index[normalize("Input")] = {
        "friendly_name": "Input",
        "game_name": "RootNodeViewModel",
        "inputs": [],
        "outputs": ["Number"],
    }
    chip_index[normalize("Output")] = {
        "friendly_name": "Output",
        "game_name": "ExitNodeViewModel",
        "inputs": ["Number"],
        "outputs": [],
    }
    chip_index[normalize("Constant")] = {
        "friendly_name": "Constant",
        "game_name": "ConstantNodeViewModel",
        "inputs": [],
        "outputs": ["Output"],
    }
    # 变量节点：不在 moduledef.json 中，手动补充
    # Inputs:  Value, Set
    # Outputs: Value（唯一输出端口，方便裸节点变量自动端口）
    chip_index[normalize("Variable")] = {
        "friendly_name": "Variable",
        "game_name": "VariableNodeViewModel",
        "inputs": ["Value", "Set"],
        "outputs": ["Value"],
    }
    return chip_index


def parse_graph(graph: dict, chip_index: Dict[str, dict]) -> Tuple[List[Any], Dict[str, dict]]:
    """
    根据 graph.json 里的节点类型，结合 moduledef 构建：
      - modules: 传给 add_modules 的“希望添加的模块列表”
      - node_map: DSL 节点 id -> {friendly_name, game_name, order_index, new_full_id}
    """
    modules: List[Any] = []
    node_map: Dict[str, dict] = {}
    all_chip_keys = list(chip_index.keys())

    # 从 graph.json 中取出可选的变量定义列表（由 converter_v2 收集）
    # 每项形如 {"Key": "...", "GateDataType": "...", "Value": ...}
    variable_defs: List[dict] = graph.get("variables") or []
    variable_iter = iter(variable_defs)

    for node in graph["nodes"]:
        key = normalize(node["type"])
        best_match_key = fuzzy_match(key, all_chip_keys, FUZZY_CUTOFF_NODE)
        if best_match_key is None:
            sys.exit(f"错误：无法识别模块类型 \"{node['type']}\"")

        chip_info = chip_index[best_match_key]
        node_type_lower = chip_info["friendly_name"].lower()

        # INPUT / OUTPUT / CONSTANT 用 dict 形式，方便 add_modules 走专用分支
        if node_type_lower in ("input", "output", "constant"):
            custom_name = node.get("attrs", {}).get("name", chip_info["friendly_name"])
            modules.append({"type": node_type_lower, "name": custom_name})
        # VARIABLE 变量节点：从 graph["variables"] 顺序取出对应的定义
        elif node_type_lower == "variable":
            try:
                var_def = next(variable_iter)
            except StopIteration:
                sys.exit(
                    "错误：DSL 中存在 VARIABLE 节点，但未找到足够的变量定义 "
                    '(形如 {"Key": "...", "GateDataType": "...", "Value": ...})'
                )
            modules.append(
                {
                    "type": "variable",
                    "key": var_def.get("Key"),
                    "gateDataType": var_def.get("GateDataType"),
                    "value": var_def.get("Value"),
                }
            )
        else:
            modules.append(chip_info["friendly_name"])

        node_map[node["id"]] = {
            "friendly_name": chip_info["friendly_name"],
            "game_name": chip_info["game_name"],
            "order_index": len(modules) - 1,
            "new_full_id": None,
        }

    # 若存在变量定义但 DSL 中没有显式的 VARIABLE 节点，
    # 为每个剩余的变量定义追加一个“孤立的”变量模块，
    # 这样步骤 2 仍会帮我们写入 chip_variables 并生成 Variable 节点。
    for var_def in variable_iter:
        modules.append(
            {
                "type": "variable",
                "key": var_def.get("Key"),
                "gateDataType": var_def.get("GateDataType"),
                "value": var_def.get("Value"),
            }
        )

    return modules, node_map


def parse_graph_v2(graph: dict, chip_index: Dict[str, dict]) -> Tuple[List[Any], Dict[str, dict]]:
    """
    新版 graph 解析：
    - 支持同一个变量 Key 对应多个 VARIABLE 节点
    - 通过连线自动推断 VARIABLE 节点应该使用哪个变量定义
    """
    modules: List[Any] = []
    node_map: Dict[str, dict] = {}
    all_chip_keys = list(chip_index.keys())

    # 从 graph.json 中取出可选的变量定义列表（由 converter_v2 收集）
    variable_defs: List[dict] = graph.get("variables") or []
    # 按 Key 建立索引，保持插入顺序
    var_defs_by_key: Dict[str, dict] = {}
    for vd in variable_defs:
        k = vd.get("Key")
        if isinstance(k, str):
            var_defs_by_key[k] = vd
    var_keys_set = set(var_defs_by_key.keys())

    # ---------- 为 VARIABLE 节点预先推断变量 Key ----------
    nodes_by_id: Dict[str, dict] = {n["id"]: n for n in graph.get("nodes", [])}
    edges = graph.get("edges") or []
    edges_by_to: Dict[str, List[dict]] = {}
    for e in edges:
        to_node = e.get("to_node")
        if isinstance(to_node, str):
            edges_by_to.setdefault(to_node, []).append(e)

    # 第一步：从 Value 端口上游的 Constant 节点里拿字符串，匹配 variables[*]["Key"]
    var_key_for_node: Dict[str, str] = {}
    for node in graph.get("nodes", []):
        if str(node.get("type", "")).lower() != "variable":
            continue
        nid = node["id"]
        incoming = edges_by_to.get(nid, []) or []
        for e in incoming:
            if e.get("to_port") != "Value":
                continue
            up = nodes_by_id.get(e.get("from_node"))
            if not up or str(up.get("type", "")).lower() != "constant":
                continue
            v = (up.get("attrs") or {}).get("value")
            if isinstance(v, str) and v in var_keys_set:
                var_key_for_node[nid] = v
                break

    # 第二步：若 Value 来自其他 VARIABLE 节点，则继承其 key（支持多次“转手”）
    changed = True
    while changed:
        changed = False
        for node in graph.get("nodes", []):
            if str(node.get("type", "")).lower() != "variable":
                continue
            nid = node["id"]
            if nid in var_key_for_node:
                continue
            incoming = edges_by_to.get(nid, []) or []
            for e in incoming:
                if e.get("to_port") != "Value":
                    continue
                up = nodes_by_id.get(e.get("from_node"))
                if not up or str(up.get("type", "")).lower() != "variable":
                    continue
                up_id = up["id"]
                if up_id in var_key_for_node:
                    var_key_for_node[nid] = var_key_for_node[up_id]
                    changed = True
                    break

    # 记录每个变量 Key 已经创建了多少个 VARIABLE 节点（首个用于设初值，其余只生成节点）
    var_instance_count: Dict[str, int] = {}
    used_var_keys: set[str] = set()

    for node in graph["nodes"]:
        key = normalize(node["type"])
        best_match_key = fuzzy_match(key, all_chip_keys, FUZZY_CUTOFF_NODE)
        if best_match_key is None:
            sys.exit(f"错误：无法识别模块类型 \"{node['type']}\"")

        chip_info = chip_index[best_match_key]
        node_type_lower = chip_info["friendly_name"].lower()

        # INPUT / OUTPUT / CONSTANT 用 dict 形式，方便 add_modules 走专用分支
        if node_type_lower in ("input", "output", "constant"):
            custom_name = node.get("attrs", {}).get("name", chip_info["friendly_name"])
            modules.append({"type": node_type_lower, "name": custom_name})
        # VARIABLE 变量节点：根据图中的连接关系推断使用哪个变量 Key
        elif node_type_lower == "variable":
            nid = node["id"]
            var_key = var_key_for_node.get(nid)
            var_def = None

            if var_key is not None:
                var_def = var_defs_by_key.get(var_key)

            # 若无法从连线中推断，则退回到“按顺序取尚未使用的定义”
            if var_def is None:
                fallback_key = None
                for k in var_defs_by_key.keys():
                    if k not in used_var_keys:
                        fallback_key = k
                        break
                if fallback_key is None:
                    sys.exit(
                        "错误：DSL 中存在 VARIABLE 节点，但未找到足够、且可匹配的变量定义 "
                        '(形如 {"Key": "...", "GateDataType": "...", "Value": ...})'
                    )
                var_key = fallback_key
                var_def = var_defs_by_key[var_key]

            used_var_keys.add(var_key)

            # 同一变量可以对应多个 VARIABLE 节点：
            #   - 第 1 个实例：使用变量定义中的 Value 作为初始值
            #   - 之后的实例：不再改动变量定义（value=None，避免覆盖）
            count = var_instance_count.get(var_key, 0)
            if count == 0:
                init_value = var_def.get("Value")
            else:
                init_value = None
            var_instance_count[var_key] = count + 1

            modules.append(
                {
                    "type": "variable",
                    "key": var_key,
                    "gateDataType": var_def.get("GateDataType"),
                    "value": init_value,
                }
            )
        else:
            modules.append(chip_info["friendly_name"])

        node_map[node["id"]] = {
            "friendly_name": chip_info["friendly_name"],
            "game_name": chip_info["game_name"],
            "order_index": len(modules) - 1,
            "new_full_id": None,
        }

    # 若存在变量定义但 DSL 中没有显式的 VARIABLE 节点：
    # 为每个“完全未被使用”的变量定义追加一个“孤立的”变量模块，
    # 这样步骤 2 仍会帮我们写入 chip_variables 并生成一个 Variable 节点。
    for k, var_def in var_defs_by_key.items():
        if k in used_var_keys:
            continue
        modules.append(
            {
                "type": "variable",
                "key": var_def.get("Key"),
                "gateDataType": var_def.get("GateDataType"),
                "value": var_def.get("Value"),
            }
        )

    return modules, node_map


def run_batch_add(modules_to_add: List[Any], node_map: Dict[str, dict]) -> Dict[str, Any]:
    """
    调用 batch_add_modules.add_modules，将 DSL 中的节点实际添加到存档 data.json 里。
    同时回填 node_map[*]["new_full_id"]。
    """
    print("📦 正在执行模块添加...")
    game_data = load_json(DATA_PATH, "原始游戏存档")
    module_defs = load_json(MODULE_DEF_PATH, "模块定义")

    try:
        updated_game_data, created_nodes_info = add_modules(
            modules_wanted=modules_to_add,
            game_data=game_data,
            module_definitions=module_defs,
            cutoff=FUZZY_CUTOFF_NODE,
        )
    except ValueError as e:
        sys.exit(f"错误: 模块添加失败 - {e}")

    print(f"✔ 模块添加逻辑执行完毕，获得 {len(created_nodes_info)} 个新节点信息")
    if len(created_nodes_info) != len(modules_to_add):
        print(f"⚠️ 警告：请求添加 {len(modules_to_add)} 个模块，实际成功创建 {len(created_nodes_info)} 个")

    # 按顺序回填 new_full_id
    nodes_in_map = sorted(node_map.values(), key=lambda x: x["order_index"])
    for i, created_node in enumerate(created_nodes_info):
        if i < len(nodes_in_map):
            node_to_update = nodes_in_map[i]
            original_id = next(
                k for k, v in node_map.items() if v["order_index"] == node_to_update["order_index"]
            )
            node_map[original_id]["new_full_id"] = created_node["full_id"]
        else:
            print(f"⚠️ 警告: 创建了一个多余的节点 {created_node['full_id']}，无法在 node_map 中找到对应项")

    unmatched = [meta["friendly_name"] for meta in node_map.values() if meta["new_full_id"] is None]
    if unmatched:
        sys.exit(f"错误：以下节点未匹配到新 ID：{', '.join(unmatched)}")
    return updated_game_data


def generate_modify_instructions(graph: dict, node_map: Dict[str, dict]) -> List[dict]:
    """
    从 graph.json 中读取每个节点 attrs.data_type / attrs.datatype，生成数据类型修改指令。
    """
    instructions: List[dict] = []
    for node in graph["nodes"]:
        attrs = node.get("attrs", {}) or {}
        # 兼容两种写法
        dt = attrs.get("data_type", attrs.get("datatype"))
        if dt is None:
            continue
        original_id = node["id"]
        if original_id in node_map and node_map[original_id]["new_full_id"]:
            instructions.append(
                {
                    "node_id": node_map[original_id]["new_full_id"],
                    "new_data_type": dt,
                }
            )
        else:
            print(
                f"⚠️ 警告：节点 '{original_id}' 定义了 data_type/datatype 但未找到其生成的 ID，将跳过"
            )
    return instructions


# =========================== 端口索引解析 ===========================

def port_index(port_name: str, port_list: List[str]) -> int:
    """
    将 DSL 里的“端口标识”转换为模块定义里的端口下标。

    支持三种写法：
    1) 旧版：端口名字符串，例如 "OUTPUT"、"A*B"
    2) 新增：数字序号字符串，例如 "0"、"1"（直接视为端口下标）
    3) 新增：特殊标记 "__auto__" —— 表示“唯一输出端口”（裸节点变量）
    """
    # 特例：自动端口（裸节点变量）——必须只有一个端口
    if port_name == "__auto__":
        if not port_list:
            sys.exit("错误：尝试从没有输出端口的节点上获取自动端口")
        if len(port_list) != 1:
            sys.exit(
                f"错误：节点有多个输出端口 {port_list}，无法推断唯一输出，请在 DSL 中显式写端口名或数字序号"
            )
        return 0

    # 特例：只有一个端口时，任何写法都视为下标 0（保持旧行为）
    if len(port_list) == 1:
        return 0

    # 新增：纯数字 -> 直接按下标使用
    if isinstance(port_name, str) and port_name.isdigit():
        idx = int(port_name)
        if 0 <= idx < len(port_list):
            return idx
        sys.exit(
            f"错误：端口序号 {idx} 超出范围，可用序号为 0..{len(port_list) - 1}，端口列表: {port_list}"
        )

    # 旧版：按端口“名字”做模糊匹配
    normalized_ports = [normalize(p) for p in port_list]
    best = fuzzy_match(normalize(str(port_name)), normalized_ports, FUZZY_CUTOFF_PORT)
    if best is None:
        sys.exit(f"错误：无法匹配端口 \"{port_name}\" 候选 {port_list}")
    return normalized_ports.index(best)


def build_connections(graph: dict, node_map: Dict[str, dict], chip_index: Dict[str, dict]) -> List[dict]:
    """
    将 AST 转换出的 edge 列表转换为批量连线脚本所需的连接指令：
        {
          "from_node_id": "...",
          "from_port_index": 0,
          "to_node_id": "...",
          "to_port_index": 1
        }
    """
    conns: List[dict] = []
    for e in graph["edges"]:
        f_meta = node_map[e["from_node"]]
        t_meta = node_map[e["to_node"]]

        f_chip_key = normalize(f_meta["friendly_name"])
        t_chip_key = normalize(t_meta["friendly_name"])
        if f_chip_key not in chip_index or t_chip_key not in chip_index:
            sys.exit(
                f"内部错误: 无法在 chip_index 中找到 \"{f_meta['friendly_name']}\" 或 "
                f"\"{t_meta['friendly_name']}\""
            )

        f_chip = chip_index[f_chip_key]
        t_chip = chip_index[t_chip_key]

        conns.append(
            {
                "from_node_id": f_meta["new_full_id"],
                "from_port_index": port_index(e["from_port"], f_chip["outputs"]),
                "to_node_id": t_meta["new_full_id"],
                "to_port_index": port_index(e["to_port"], t_chip["inputs"]),
            }
        )
    return conns


# =========================== 批量连线 & 自动布局 ===========================

def run_batch_connect(input_path: Path) -> None:
    print("🔗 正在执行批量连线 ...")
    if not input_path.exists():
        sys.exit(f"错误：在执行连线前，未找到输入存档文件 '{input_path}'")

    success = apply_connections(
        input_graph_path=str(input_path),
        connections_path=str(CONNECT_OUT_PATH),
        output_graph_path=str(FINAL_SAVE_PATH),
    )
    if not success:
        sys.exit("错误：批量连线过程中发生错误，流程终止")


def run_auto_layout() -> None:
    print("🎨 正在对最终存档文件进行自动布局...")
    if not FINAL_SAVE_PATH.exists():
        print(f"⚠️ 警告：找不到最终存档文件 '{FINAL_SAVE_PATH}'，跳过自动布局步骤")
        return

    full_save_data = load_json(FINAL_SAVE_PATH, "最终游戏存档")
    try:
        save_obj = full_save_data["saveObjectContainers"][0]["saveObjects"]
        chip_graph_str = next(
            md["stringValue"] for md in save_obj["saveMetaDatas"] if md.get("key") == "chip_graph"
        )
        chip_nodes = json.loads(chip_graph_str).get("Nodes", [])
    except (KeyError, IndexError, StopIteration, json.JSONDecodeError) as e:
        print(
            f"⚠️ 警告：在存档文件 '{FINAL_SAVE_PATH}' 中无法找到或解析 'chip_graph'，跳过布局。错误: {e}"
        )
        return

    if not chip_nodes:
        print("ℹ️ 'chip_graph' 中没有节点，无需布局")
        return

    print(f"   从存档中找到 {len(chip_nodes)} 个节点进行布局")
    final_positions = run_layout_engine(chip_nodes)
    print("   使用新坐标更新存档数据...")
    updated = find_and_update_chip_graph(full_save_data, final_positions)
    if updated:
        with FINAL_SAVE_PATH.open("w", encoding="utf-8") as f:
            json.dump(full_save_data, f, separators=(",", ":"))
        print(f"✔ 自动布局完成，已更新存档文件: '{FINAL_SAVE_PATH}'")
    else:
        print("⚠️ 错误：布局计算完成，但在存档中更新坐标失败。文件未被修改")


# =========================== 常量修改指令生成 ===========================

def generate_constant_instructions(graph: dict, node_map: Dict[str, dict]) -> List[dict]:
    """
    扫描 graph.json 中的 Constant 节点，读取 attrs.value，生成常量修改指令。
    支持标量 / 向量 / 向量数组等多种格式。
    """
    instructions: List[dict] = []
    for node in graph["nodes"]:
        node_type_clean = node.get("type", "").strip().lower()
        if node_type_clean != "constant" or "value" not in node.get("attrs", {}):
            continue

        original_id = node["id"]
        node_attrs = node["attrs"]
        if original_id not in node_map or not node_map[original_id]["new_full_id"]:
            print(
                f"⚠️ 警告：常量节点 '{original_id}' 定义了 value 但未找到其生成的 ID，将跳过"
            )
            continue

        value = node_attrs["value"]
        new_full_id = node_map[original_id]["new_full_id"]

        value_type: str | None = None
        new_value: Any | None = None

        # 标量：数字
        if isinstance(value, (int, float)):
            value_type = "decimal"
            new_value = value

        # 标量：字符串
        elif isinstance(value, str):
            value_type = "string"
            new_value = value

        # 向量：{x,y,z}
        elif isinstance(value, dict) and all(k in value for k in ["x", "y", "z"]):
            value_type = "vector"
            new_value = [
                value.get("x", 0.0),
                value.get("y", 0.0),
                value.get("z", 0.0),
            ]

        # 数组支持
        elif isinstance(value, list):
            # 全是数字 -> ArrayNumber
            if all(isinstance(v, (int, float)) for v in value):
                value_type = "array_number"
                new_value = [float(v) for v in value]

            # 全是字符串 -> ArrayString
            elif all(isinstance(v, str) for v in value):
                value_type = "array_string"
                new_value = value

            # 全是向量 {x,y,z} 或 [x,y,z] / [x,y,z,w] -> ArrayVector
            elif all(
                (isinstance(v, dict) and all(k in v for k in ["x", "y", "z"]))
                or (isinstance(v, (list, tuple)) and len(v) in (3, 4))
                for v in value
            ):
                value_type = "array_vector"
                norm_vecs: List[list[float]] = []
                for v in value:
                    if isinstance(v, dict):
                        x = float(v.get("x", 0.0))
                        y = float(v.get("y", 0.0))
                        z = float(v.get("z", 0.0))
                        w = float(v.get("w", 0.0)) if "w" in v else 0.0
                        if w != 0.0 or "w" in v:
                            norm_vecs.append([x, y, z, w])
                        else:
                            norm_vecs.append([x, y, z])
                    else:
                        # 列表 / 元组，支持 3 维或 4 维
                        if len(v) == 4:
                            norm_vecs.append(
                                [float(v[0]), float(v[1]), float(v[2]), float(v[3])]
                            )
                        else:
                            norm_vecs.append(
                                [float(v[0]), float(v[1]), float(v[2])]
                            )
                new_value = norm_vecs
            else:
                print(
                    f"⚠️ 警告：跳过常量 '{original_id}'，因为其列表元素类型混合或不支持: {value}"
                )
                continue
        else:
            print(
                f"⚠️ 警告：跳过常量 '{original_id}'，因为其 value 格式无法识别: {value}"
            )
            continue

        instructions.append(
            {
                "node_id": new_full_id,
                "new_value": new_value,
                "value_type": value_type,
            }
        )

    return instructions


# =========================== 主流程 ===========================

def main() -> None:
    # --- 阶段 0: DSL -> graph.json ---
    run_stage0_convert_dsl_to_graph(DSL_INPUT_PATH, GRAPH_PATH)

    # --- 步骤 1: 解析输入文件 ---
    print("\n--- 步骤 1: 解析输入文件 ---")
    graph = load_json(GRAPH_PATH, "graph.json")
    module_definitions = load_json(MODULE_DEF_PATH, "模块定义文件")
    rules = load_json(RULES_PATH, "数据类型规则文件")

    chip_index = build_chip_index_from_moduledef(module_definitions)
    modules, node_map = parse_graph_v2(graph, chip_index)
    print("✔ graph.json 解析完成")

    # --- 步骤 2: 批量添加模块 ---
    print("\n--- 步骤 2: 批量添加模块 ---")
    current_save_data = run_batch_add(modules, node_map)
    print("✔ 模块添加完成，并已获取新节点 ID")

    # --- 步骤 3: 节点修改阶段 ---
    print("\n--- 步骤 3: 节点修改阶段 ---")

    # 子步骤 3.1: 修改节点数据类型
    print("\n--- 步骤 3.1: 修改节点数据类型 ---")
    modify_instructions = generate_modify_instructions(graph, node_map)
    if modify_instructions:
        print(f"ℹ️  需要进行 {len(modify_instructions)} 项数据类型修改")
        current_save_data = apply_data_type_modifications(
            game_data=current_save_data,
            mod_instructions=modify_instructions,
            rules=rules,
            module_defs=module_definitions,
        )
        print("✔ 数据类型修改完成")
    else:
        print("ℹ️ 无需修改数据类型，跳过此步骤")

    # 子步骤 3.2: 修改常量节点
    print("\n--- 步骤 3.2: 修改常量节点 ---")
    constant_instructions = generate_constant_instructions(graph, node_map)
    if constant_instructions:
        print(f"ℹ️  需要进行 {len(constant_instructions)} 项常量值修改")
        current_save_data = apply_constant_modifications(
            game_data=current_save_data,
            instructions=constant_instructions,
        )
        print("✔ 常量值修改完成")
    else:
        print("ℹ️ 无需修改常量值，跳过此步骤")

    # --- 步骤 4: 生成连线指令 ---
    print("\n--- 步骤 4: 生成连线指令 ---")
    conns = build_connections(graph, node_map, chip_index)
    CONNECT_OUT_PATH.write_text(
        json.dumps(conns, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✔ 已生成连线指令到 {CONNECT_OUT_PATH}")

    # --- 步骤 5: 执行批量连线 ---
    print("\n--- 步骤 5: 执行批量连线 ---")
    print(f"ℹ️ 将当前存档状态写入到 '{MODIFIED_SAVE_PATH}' 以进行连线")
    with MODIFIED_SAVE_PATH.open("w", encoding="utf-8") as f:
        json.dump(current_save_data, f, ensure_ascii=False, indent=4)

    run_batch_connect(MODIFIED_SAVE_PATH)

    # --- 步骤 6: 执行自动布局 ---
    print("\n--- 步骤 6: 执行自动布局 ---")
    run_auto_layout()

    if MODIFIED_SAVE_PATH.exists():
        MODIFIED_SAVE_PATH.unlink()

    # --- 阶段 7: 创建 .melsave 归档文件 ---
    print("\n--- 阶段 7: 创建 .melsave 归档文件 ---")
    run_archive_creation_stage()

    print("\n🎉 全部流程完成！")


if __name__ == "__main__":
    main()
