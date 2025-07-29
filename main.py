# --- START OF FILE main.py ---

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
integrated_pipeline.py
======================
一键完成：
  1. 解析 graph.json
  2. 调用 batch_add_modules 函数，传入模块列表
  3. 从函数返回值中获取新节点ID和更新后的存档
  4. 根据 graph.json 中的 data_type 生成修改指令
  5. 【已修改】直接调用 modifier 函数修改节点数据类型
  6. 生成 output.json（连线指令）
  7. 直接调用函数执行批量连线
  8. 调用《layout_chip.py》的布局引擎，对最终存档进行自动排版
"""

import sys, os
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json, re, subprocess, locale
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Tuple, Any

# --- 修改后的导入 ---
from batch_add_modules import add_modules
from modifier import apply_data_type_modifications
from layout_chip import run_layout_engine, find_and_update_chip_graph
from batch_connect import apply_connections

# =============================== 全局配置 (简化和修改) ===============================
GRAPH_PATH        = Path("graph.json")
CHIP_DICT_PATH    = Path("chip_names.json") # 暂时保留，用于解析graph.json
MODULE_DEF_PATH   = Path("moduledef.json")   # 【新增】单一模块定义文件
DATA_PATH         = Path("data.json")
CONNECT_OUT_PATH  = Path("output.json")

# 中间文件和最终文件
MODIFIED_SAVE_PATH  = Path("data_after_modify.json")
FINAL_SAVE_PATH = Path("ungraph.json")

FUZZY_CUTOFF_NODE = 0.10
FUZZY_CUTOFF_PORT = 0.40
# ======================================================================

def load_json(path: Path, desc: str) -> Any:
    if not path.exists():
        sys.exit(f"错误：未找到 {desc} 文件 “{path}”")
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"错误：{desc} 文件 “{path}” 解析失败：{e}")

def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def fuzzy_match(name: str, candidates: List[str], cutoff: float) -> str | None:
    return (get_close_matches(name, candidates, n=1, cutoff=cutoff) or [None])[0]

# =========================== 主流程函数 (修改) ===========================
def build_chip_index(chips: list) -> Dict[str, dict]:
    return {normalize(c["friendly_name"]): c for c in chips}

def parse_graph(graph: dict, chip_index: Dict[str, dict]) -> Tuple[List[Any], Dict[str, dict]]:
    modules: List[Any] = []
    node_map: Dict[str, dict] = {}
    for node in graph["nodes"]:
        key = normalize(node["type"])
        node_type_lower = node["type"].lower()
        
        if node_type_lower in ('input', 'output', 'constant'):
            modules.append({
                "type": node_type_lower, 
                "name": node.get("name", node_type_lower.title())
            })
            chip_name = f"{node_type_lower.title()}NodeViewModel"
            friendly_name = node_type_lower.title()
        else:
            best = fuzzy_match(key, list(chip_index.keys()), FUZZY_CUTOFF_NODE)
            if best is None:
                sys.exit(f"错误：无法识别模块类型 “{node['type']}”")
            chip = chip_index[best]
            modules.append(chip["friendly_name"])
            chip_name = chip["game_name"]
            friendly_name = chip["friendly_name"]
            
        node_map[node["id"]] = {
            "friendly_name": friendly_name,
            "game_name": chip_name,
            "order_index": len(modules) - 1,
            "new_full_id": None,
        }
    return modules, node_map

# 【核心修改】此函数现在加载 moduledef.json 并调用更新后的 add_modules
def run_batch_add(modules_to_add: List[Any], node_map: Dict[str, dict]) -> Dict[str, Any]:
    print("📦 正在执行模块添加...")
    game_data = load_json(DATA_PATH, "原始游戏存档")
    # 【修改】加载新的单一模块定义文件
    module_defs = load_json(MODULE_DEF_PATH, "模块定义")
    
    try:
        # 【修改】调用更新后的 add_modules 函数
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
            original_id = next(k for k, v in node_map.items() if v['order_index'] == node_to_update['order_index'])
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
        if "data_type" in node.get("attrs", {}):
            original_id = node["id"]
            if original_id in node_map and node_map[original_id]["new_full_id"]:
                instruction = {
                    "node_id": node_map[original_id]["new_full_id"],
                    "new_data_type": node["attrs"]["data_type"]
                }
                instructions.append(instruction)
            else:
                 print(f"警告：节点 '{original_id}' 定义了 data_type 但未找到其生成的ID，将跳过。")
    return instructions

def port_index(port_name: str, port_list: List[str]) -> int:
    if len(port_list) == 1: return 0
    normalized_ports = [normalize(p) for p in port_list]
    best = fuzzy_match(normalize(port_name), normalized_ports, FUZZY_CUTOFF_PORT)
    if best is None:
        sys.exit(f"错误：无法匹配端口 “{port_name}” ← 候选 {port_list}")
    return normalized_ports.index(best)

def build_connections(graph: dict, node_map: Dict[str, dict], chip_index: Dict[str, dict]) -> List[dict]:
    conns: List[dict] = []
    for e in graph["edges"]:
        f_meta, t_meta = node_map[e["from_node"]], node_map[e["to_node"]]
        f_chip = chip_index[normalize(f_meta["friendly_name"])]
        t_chip = chip_index[normalize(t_meta["friendly_name"])]
        conns.append({
            "from_node_id": f_meta["new_full_id"],
            "from_port_index": port_index(e["from_port"], f_chip["outputs"]),
            "to_node_id": t_meta["new_full_id"],
            "to_port_index": port_index(e["to_port"], t_chip["inputs"]),
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
# ======================================================================

def main() -> None:
    # --- 步骤 1: 解析输入文件 ---
    print("--- 步骤 1: 解析输入文件 ---")
    graph = load_json(GRAPH_PATH, "graph.json")
    chip_table = load_json(CHIP_DICT_PATH, "芯片名词.json")
    chip_index = build_chip_index(chip_table)
    modules, node_map = parse_graph(graph, chip_index)
    print("✅ 解析完成。")

    # --- 步骤 2: 批量添加模块 ---
    print("\n--- 步骤 2: 批量添加模块 ---")
    current_save_data = run_batch_add(modules, node_map)
    print("✅ 模块添加完成，并已获取新节点ID。")

    # --- 步骤 3: 修改节点数据类型 ---
    print("\n--- 步骤 3: 修改节点数据类型 ---")
    modify_instructions = generate_modify_instructions(graph, node_map)
    
    if modify_instructions:
        print(f"ℹ️  需要进行 {len(modify_instructions)} 项数据类型修改。")
        current_save_data = apply_data_type_modifications(current_save_data, modify_instructions)
        print("✅ 数据类型修改完成。")
    else:
        print("ℹ️ 无需修改数据类型，跳过此步骤。")

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

    print("\n🎉 全部流程完成！")

if __name__ == "__main__":
    main()
# --- END OF FILE main.py ---