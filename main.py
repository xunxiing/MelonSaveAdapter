#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py / integrated_pipeline.py
================================
0. 【新增】将 input.py（DSL）转换为 graph.json（调用 converter_v2.convert_dsl_to_graph）
1. 解析 graph.json
2. 批量添加模块（函数化）
3. 节点修改（数据类型 & 常量值）（函数化）
4. 生成连线指令 output.json
5. 执行批量连线（函数化）
6. 自动布局（函数化）
7. 【新增】创建 .melsave 归档文件（将 ungraph.json 重命名为 data，与 MetaData、Icon 一起压缩）
"""

import sys, os
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from typing import Dict, List, Tuple, Any
import json, re, locale
from difflib import get_close_matches

# === 新增导入：直接函数式调用转换器（不启子进程） ===
from converter_v2 import convert_dsl_to_graph  # NEW: 阶段0所需

# === 原有函数式依赖 ===
from constantvalue import apply_constant_modifications
from batch_add_modules import add_modules
from modifier import apply_data_type_modifications
from layout_chip import run_layout_engine, find_and_update_chip_graph
from batch_connect import apply_connections
from archive_creator import run_archive_creation_stage

# =============================== 路径配置 ===============================
DSL_INPUT_PATH    = Path("input.py")        # NEW: DSL 输入
GRAPH_PATH        = Path("graph.json")      # 仍然按原流程读取此 JSON（由阶段0生成）
MODULE_DEF_PATH   = Path("moduledef.json")
DATA_PATH         = Path("data.json")
CONNECT_OUT_PATH  = Path("output.json")
RULES_PATH        = Path("data_type_rules.json")

MODIFIED_SAVE_PATH  = Path("data_after_modify.json")
FINAL_SAVE_PATH     = Path("ungraph.json")

FUZZY_CUTOFF_NODE = 0.10
FUZZY_CUTOFF_PORT = 0.40
# ======================================================================

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

# =========================== NEW 阶段 0：DSL -> graph.json ===========================
def run_stage0_convert_dsl_to_graph(dsl_path: Path, out_graph_path: Path) -> None:
    """
    使用 converter_v2.convert_dsl_to_graph 将 input.py 转为 graph.json（函数化执行）。
    """
    print("--- 阶段 0: 将 input.py 转换为 graph.json ---")
    convert_dsl_to_graph(dsl_script_path=dsl_path,
                         output_path=out_graph_path)
    print(f"✅ 已从 '{dsl_path}' 生成 '{out_graph_path}'")

# =========================== 其余函数（保持一致） ===========================
def build_chip_index_from_moduledef(module_defs: Dict[str, Any]) -> Dict[str, dict]:
    chip_index = {}
    for mod_id, mod_data in module_defs.items():
        source_info = mod_data.get("source_info", {})
        friendly_name = source_info.get("chip_names_friendly_name")
        game_name = source_info.get("allmod_viewmodel")
        if not friendly_name or not game_name:
            continue
        normalized_key = normalize(friendly_name)
        chip_index[normalized_key] = {
            "friendly_name": friendly_name,
            "game_name": game_name,
            "inputs": [p.get("name", "Input") for p in mod_data.get("inputs", [])],
            "outputs": [p.get("name", "Output") for p in mod_data.get("outputs", [])],
        }
    chip_index[normalize("Input")] = {"friendly_name": "Input", "game_name": "RootNodeViewModel", "inputs": [], "outputs": ["Number"]}
    chip_index[normalize("Output")] = {"friendly_name": "Output", "game_name": "ExitNodeViewModel", "inputs": ["Number"], "outputs": []}
    chip_index[normalize("Constant")] = {"friendly_name": "Constant", "game_name": "ConstantNodeViewModel", "inputs": [], "outputs": ["Output"]}
    return chip_index

def parse_graph(graph: dict, chip_index: Dict[str, dict]) -> Tuple[List[Any], Dict[str, dict]]:
    modules: List[Any] = []
    node_map: Dict[str, dict] = {}
    all_chip_keys = list(chip_index.keys())
    for node in graph["nodes"]:
        key = normalize(node["type"])
        best_match_key = fuzzy_match(key, all_chip_keys, FUZZY_CUTOFF_NODE)
        if best_match_key is None:
            sys.exit(f"错误：无法识别模块类型 \"{node['type']}\"")
        chip_info = chip_index[best_match_key]
        node_type_lower = chip_info["friendly_name"].lower()
        if node_type_lower in ('input', 'output', 'constant'):
            custom_name = node.get("attrs", {}).get("name", chip_info["friendly_name"])
            modules.append({"type": node_type_lower, "name": custom_name})
        else:
            modules.append(chip_info["friendly_name"])
        node_map[node["id"]] = {
            "friendly_name": chip_info["friendly_name"],
            "game_name": chip_info["game_name"],
            "order_index": len(modules) - 1,
            "new_full_id": None
        }
    return modules, node_map

def run_batch_add(modules_to_add: List[Any], node_map: Dict[str, dict]) -> Dict[str, Any]:
    print("📦 正在执行模块添加...")
    game_data = load_json(DATA_PATH, "原始游戏存档")
    module_defs = load_json(MODULE_DEF_PATH, "模块定义")
    try:
        updated_game_data, created_nodes_info = add_modules(
            modules_wanted=modules_to_add,
            game_data=game_data,
            module_definitions=module_defs,
            cutoff=FUZZY_CUTOFF_NODE
        )
    except ValueError as e:
        sys.exit(f"错误: 模块添加失败 - {e}")
    print(f"✅ 模块添加逻辑执行完毕，获得 {len(created_nodes_info)} 个新节点信息。")
    if len(created_nodes_info) != len(modules_to_add):
        print(f"警告：请求添加 {len(modules_to_add)} 个模块，实际成功创建 {len(created_nodes_info)} 个。")

    nodes_in_map = sorted(node_map.values(), key=lambda x: x['order_index'])
    for i, created_node in enumerate(created_nodes_info):
        if i < len(nodes_in_map):
            node_to_update = nodes_in_map[i]
            original_id = next(k for k, v in node_map.items()
                               if v['order_index'] == node_to_update['order_index'])
            node_map[original_id]["new_full_id"] = created_node["full_id"]
        else:
            print(f"警告: 创建了一个多余的节点 {created_node['full_id']}，无法在 node_map 中找到对应项。")
    unmatched = [meta['friendly_name'] for meta in node_map.values() if meta['new_full_id'] is None]
    if unmatched:
        sys.exit(f"错误：以下节点未匹配到新 ID：{', '.join(unmatched)}")
    return updated_game_data

def generate_modify_instructions(graph: dict, node_map: Dict[str, dict]) -> List[dict]:
    instructions = []
    for node in graph["nodes"]:
        attrs = node.get("attrs", {}) or {}
        # 兼容两种写法
        dt = attrs.get("data_type", attrs.get("datatype"))
        if dt is None:
            continue
        original_id = node["id"]
        if original_id in node_map and node_map[original_id]["new_full_id"]:
            instructions.append({
                "node_id": node_map[original_id]["new_full_id"],
                "new_data_type": dt
            })
        else:
            print(f"警告：节点 '{original_id}' 定义了 data_type/datatype 但未找到其生成的ID，将跳过。")
    return instructions

def port_index(port_name: str, port_list: List[str]) -> int:
    if len(port_list) == 1:
        return 0
    normalized_ports = [normalize(p) for p in port_list]
    best = fuzzy_match(normalize(port_name), normalized_ports, FUZZY_CUTOFF_PORT)
    if best is None:
        sys.exit(f"错误：无法匹配端口 \"{port_name}\" ← 候选 {port_list}")
    return normalized_ports.index(best)

def build_connections(graph: dict, node_map: Dict[str, dict], chip_index: Dict[str, dict]) -> List[dict]:
    conns: List[dict] = []
    for e in graph["edges"]:
        f_meta, t_meta = node_map[e["from_node"]], node_map[e["to_node"]]
        f_chip_key = normalize(f_meta["friendly_name"])
        t_chip_key = normalize(t_meta["friendly_name"])
        if f_chip_key not in chip_index or t_chip_key not in chip_index:
            sys.exit(f"内部错误: 无法在 chip_index 中找到 \"{f_meta['friendly_name']}\" 或 \"{t_meta['friendly_name']}\"")
        f_chip, t_chip = chip_index[f_chip_key], chip_index[t_chip_key]
        conns.append({
            "from_node_id": f_meta["new_full_id"],
            "from_port_index": port_index(e["from_port"], f_chip["outputs"]),
            "to_node_id": t_meta["new_full_id"],
            "to_port_index": port_index(e["to_port"], t_chip["inputs"])
        })
    return conns

def run_batch_connect(input_path: Path) -> None:
    print("🔗 正在执行批量连线 …")
    if not input_path.exists():
        sys.exit(f"错误：在执行连线前，未找到输入存档文件 '{input_path}'。")
    success = apply_connections(
        input_graph_path=str(input_path),
        connections_path=str(CONNECT_OUT_PATH),
        output_graph_path=str(FINAL_SAVE_PATH)
    )
    if not success:
        sys.exit("错误：批量连线过程中发生错误，流程终止。")

def run_auto_layout() -> None:
    print("🎨 正在对最终存档文件进行自动布局...")
    if not FINAL_SAVE_PATH.exists():
        print(f"⚠️ 警告：找不到最终存档文件 '{FINAL_SAVE_PATH}'，跳过自动布局步骤。")
        return
    full_save_data = load_json(FINAL_SAVE_PATH, "最终游戏存档")
    try:
        save_obj = full_save_data['saveObjectContainers'][0]['saveObjects']
        chip_graph_str = next(md['stringValue'] for md in save_obj['saveMetaDatas'] if md.get('key') == 'chip_graph')
        chip_nodes = json.loads(chip_graph_str).get('Nodes', [])
    except (KeyError, IndexError, StopIteration, json.JSONDecodeError) as e:
        print(f"⚠️ 警告：在存档文件 '{FINAL_SAVE_PATH}' 中无法找到或解析'chip_graph'，跳过布局。错误: {e}")
        return
    if not chip_nodes:
        print("ℹ️ 'chip_graph'中没有节点，无需布局。")
        return
    print(f"   从存档中找到 {len(chip_nodes)} 个节点进行布局。")
    final_positions = run_layout_engine(chip_nodes)
    print("   使用新坐标更新存档数据...")
    updated = find_and_update_chip_graph(full_save_data, final_positions)
    if updated:
        with FINAL_SAVE_PATH.open("w", encoding="utf-8") as f:
            json.dump(full_save_data, f, separators=(',', ':'))
        print(f"✅ 自动布局完成，已更新存档文件: '{FINAL_SAVE_PATH}'")
    else:
        print("❌ 错误：布局计算完成，但在存档中更新坐标失败。文件未被修改。")

def generate_constant_instructions(graph: dict, node_map: Dict[str, dict]) -> List[dict]:
    instructions = []
    for node in graph["nodes"]:
        node_type_clean = node.get("type", "").strip().lower()
        if node_type_clean == "constant" and "value" in node.get("attrs", {}):
            original_id = node["id"]
            node_attrs = node["attrs"]
            if original_id not in node_map or not node_map[original_id]["new_full_id"]:
                print(f"警告：常量节点 '{original_id}' 定义了 value 但未找到其生成的ID，将跳过。")
                continue
            value = node_attrs["value"]
            new_full_id = node_map[original_id]["new_full_id"]

            value_type = None
            new_value = None
            if isinstance(value, (int, float)):
                value_type = 'decimal'
                new_value = value
            elif isinstance(value, str):
                value_type = 'string'
                new_value = value
            elif isinstance(value, dict) and all(k in value for k in ['x', 'y', 'z']):
                value_type = 'vector'
                new_value = [value.get('x', 0.0), value.get('y', 0.0), value.get('z', 0.0)]
            else:
                print(f"警告：跳过常量 '{original_id}'，因为其 'value' 格式无法识别: {value}")
                continue

            instructions.append({
                "node_id": new_full_id,
                "new_value": new_value,
                "value_type": value_type
            })
    return instructions

def main() -> None:
    # --- 阶段 0: DSL -> graph.json（函数式） ---
    run_stage0_convert_dsl_to_graph(DSL_INPUT_PATH, GRAPH_PATH)

    # --- 步骤 1: 解析输入文件 ---
    print("--- 步骤 1: 解析输入文件 ---")
    graph = load_json(GRAPH_PATH, "graph.json")
    module_definitions = load_json(MODULE_DEF_PATH, "模块定义文件")
    rules = load_json(RULES_PATH, "数据类型规则文件")

    chip_index = build_chip_index_from_moduledef(module_definitions)
    modules, node_map = parse_graph(graph, chip_index)
    print("✅ 解析完成。")

    # --- 步骤 2: 批量添加模块 ---
    print("\n--- 步骤 2: 批量添加模块 ---")
    current_save_data = run_batch_add(modules, node_map)
    print("✅ 模块添加完成，并已获取新节点ID。")

    # --- 步骤 3: 节点修改阶段 ---
    print("\n--- 步骤 3: 节点修改阶段 ---")

    # 子步骤 3.1: 修改节点数据类型
    print("\n--- 步骤 3.1: 修改节点数据类型 ---")
    modify_instructions = generate_modify_instructions(graph, node_map)
    if modify_instructions:
        print(f"ℹ️  需要进行 {len(modify_instructions)} 项数据类型修改。")
        current_save_data = apply_data_type_modifications(
            game_data=current_save_data,
            mod_instructions=modify_instructions,
            rules=rules,
            module_defs=module_definitions
        )
        print("✅ 数据类型修改完成。")
    else:
        print("ℹ️ 无需修改数据类型，跳过此步骤。")

    # 子步骤 3.2: 修改常量节点值
    print("\n--- 步骤 3.2: 修改常量节点值 ---")
    constant_instructions = generate_constant_instructions(graph, node_map)
    if constant_instructions:
        print(f"ℹ️  需要进行 {len(constant_instructions)} 项常量值修改。")
        current_save_data = apply_constant_modifications(
            game_data=current_save_data,
            instructions=constant_instructions
        )
        print("✅ 常量值修改完成。")
    else:
        print("ℹ️ 无需修改常量值，跳过此步骤。")

    # --- 步骤 4: 生成连线指令 ---
    print("\n--- 步骤 4: 生成连线指令 ---")
    conns = build_connections(graph, node_map, chip_index)
    CONNECT_OUT_PATH.write_text(
        json.dumps(conns, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"✅ 已生成连线指令 → {CONNECT_OUT_PATH}")

    # --- 步骤 5: 执行批量连线 ---
    print("\n--- 步骤 5: 执行批量连线 ---")
    print(f"ℹ️ 将当前存档状态写入到 '{MODIFIED_SAVE_PATH}' 以进行连线。")
    with MODIFIED_SAVE_PATH.open("w", encoding="utf-8") as f:
        json.dump(current_save_data, f, indent=4)

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
