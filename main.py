#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
integrated_pipeline.py
======================
一键完成：
  1. 解析 graph.json
  2. 生成 modules.json 并调用《批量添加模块.py》
  3. 捕获 “为新节点生成ID” → 解析 UUID
  4. 【新增】根据 graph.json 中的 data_type 生成修改指令
  5. 【新增】调用《modifier.py》修改节点数据类型
  6. 生成 output.json（连线指令）
  7. 自动调用《批量连线.py》把 output.json 写回存档

适配中文 Windows 终端（GBK），强制父/子进程均使用 UTF-8 编码，避免
Emoji / 中文输出触发 UnicodeEncodeError / DecodeError。
"""

# ---------------------------------------------------------------------
# 预处理：父进程 stdout/stderr 切换到 UTF-8（仅 Windows 需要）
import sys, os
if os.name == "nt":                                    # Windows 环境
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
# ---------------------------------------------------------------------

import json, re, subprocess, locale
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Tuple, Any

# =============================== 全局配置 ===============================
GRAPH_PATH        = Path("graph.json")         # 输入：思维导图
CHIP_DICT_PATH    = Path("chip_names.json")       # 输入：模块端口字典
MODULE_LIST_PATH  = Path("modules.json")       # 临时：批量添加输入
CONNECT_OUT_PATH  = Path("output.json")        # 输出：批量连线输入

# --- 新增：数据类型修改流程配置 ---
MODIFY_SCRIPT_PATH  = Path("modifier.py")            # 子进程：修改数据类型
MODIFY_INPUT_PATH   = Path("input.json")             # 输出：给 modifier.py 的指令文件
# 注意：你需要确保 modifier.py 脚本内部读取的文件名是 "input.json"。
# 如果不是，请修改这里的 MODIFY_INPUT_PATH 或修改 modifier.py 脚本。

ADD_SCRIPT_PATH   = Path("batch_add_modules.py")     # 子进程：批量添加
CONNECT_SCRIPT_PATH = Path("batch_connect.py")      # 子进程：批量连线

FUZZY_CUTOFF_NODE = 0.10                       # 节点 ↔ 芯片 模糊阈值
FUZZY_CUTOFF_PORT = 0.40                       # 端口名   模糊阈值
# ======================================================================


# --------------------------- 工具函数 (无变化) ---------------------------
def load_json(path: Path, desc: str) -> Any:
    if not path.exists():
        sys.exit(f"错误：未找到 {desc} 文件 “{path}”")
    try:
        return json.load(path.open("r", encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"错误：{desc} 文件解析失败：{e}")


def normalize(s: str) -> str:
    """统一为小写并去掉非字母数字字符，用于模糊匹配。"""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def fuzzy_match(name: str, candidates: List[str], cutoff: float) -> str | None:
    """返回最佳匹配，若分数低于 cutoff 则 None。"""
    return (get_close_matches(name, candidates, n=1, cutoff=cutoff) or [None])[0]
# ---------------------------------------------------------------------


# =========================== 主流程函数 (部分新增/修改) ===========================
def build_chip_index(chips: list) -> Dict[str, dict]:
    return {normalize(c["friendly_name"]): c for c in chips}


def parse_graph(graph: dict, chip_index: Dict[str, dict]
                ) -> Tuple[List[str], Dict[str, dict]]:
    modules: List[str] = []
    node_map: Dict[str, dict] = {}
    for node in graph["nodes"]:
        key = normalize(node["type"])
        best = fuzzy_match(key, list(chip_index.keys()), FUZZY_CUTOFF_NODE)
        if best is None:
            sys.exit(f"错误：无法识别模块类型 “{node['type']}”")
        chip = chip_index[best]
        order = len(modules)
        modules.append(chip["friendly_name"])
        node_map[node["id"]] = {
            "friendly_name": chip["friendly_name"],
            "game_name": chip["game_name"],
            "order_index": order,
            "new_full_id": None,   # 之后填充 “ClassName : UUID”
        }
    return modules, node_map


def run_subprocess(cmd: list[str]) -> str:
    """
    运行子进程：强制 UTF-8 模式 (-X utf8)，捕获 stdout，
    如出错则直接抛 RuntimeError。
    """
    script_path = Path(cmd[-1])
    # 确保脚本存在
    if not script_path.exists():
        sys.exit(f"错误：未找到脚本 {script_path}")
    
    # 动态确定执行命令
    if sys.executable:
        # 优先使用当前 Python 解释器
        base_cmd = [sys.executable]
        # Windows 默认编码非 UTF-8，故加 -X utf8
        if os.name == 'nt' and "-X" not in cmd:
            base_cmd.extend(["-X", "utf8"])
    else:
        # 如果 sys.executable 不可用，则回退到直接运行脚本
        base_cmd = []

    final_cmd = base_cmd + [str(script_path)]

    # 运行
    proc = subprocess.run(final_cmd, capture_output=True)
    if proc.returncode != 0:
        # 直接把子进程 stderr 打回终端（已是 UTF-8）
        sys.stderr.buffer.write(proc.stderr)
        raise RuntimeError(f"{script_path.name} 运行失败，返回码 {proc.returncode}")

    # 智能解码 stdout：优先 UTF-8，退而 GBK，再退 locale 默认
    for enc in ("utf-8", "gbk", locale.getpreferredencoding(False)):
        try:
            return proc.stdout.decode(enc)
        except UnicodeDecodeError:
            continue
    # 最后兜底：替换非法字符
    return proc.stdout.decode("utf-8", errors="replace")


def run_batch_add(modules: List[str], node_map: Dict[str, dict]) -> None:
    """
    批量调用《批量添加模块.py》，为每个节点写回 “ClassName : UUID”。
    """
    # ---------- 1. 先把待添加模块写入 modules.json ----------
    MODULE_LIST_PATH.write_text(
        json.dumps(modules, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"✅ 已生成模块添加列表 → {MODULE_LIST_PATH}")

    # ---------- 2. 调用子进程批量添加 ----------
    print("📦 正在执行批量添加模块脚本 …")
    stdout = run_subprocess([str(ADD_SCRIPT_PATH)])
    print(stdout)

    # ---------- 3. 正则解析 “为新节点生成ID: ClassName : uuid” ----------
    pattern = re.compile(
        r"为新节点生成ID:\s+([A-Za-z0-9_]+)\s*:\s*([0-9a-fA-F-]{36})"
    )
    extracted = pattern.findall(stdout)
    if not extracted:
        sys.exit("错误：从《批量添加模块.py》的输出中未能解析出任何新节点ID。请检查其输出格式。")
    if len(extracted) != len(modules):
        print(f"警告：批量添加生成的节点数量({len(extracted)})与请求数量({len(modules)})不一致。")


    # ---------- 4. 按 class_name 精确匹配 ----------
    unmatched: Dict[str, dict] = {nid: meta for nid, meta in node_map.items()}
    for class_name, uuid in extracted:
        found_match = False
        for nid, meta in list(unmatched.items()):
            if meta["game_name"] == class_name and meta["new_full_id"] is None:
                meta["new_full_id"] = f"{class_name} : {uuid}"
                del unmatched[nid]
                found_match = True
                break
        if not found_match:
             print(f"警告：解析到一个ID (Class: {class_name}, UUID: {uuid})，但在node_map中找不到未匹配的同类型节点。")

    if unmatched:
        missed = [f"{meta['friendly_name']} ({meta['game_name']})" for meta in unmatched.values()]
        sys.exit(f"错误：以下节点未匹配到新 ID：{', '.join(missed)}")

# --- 新增函数 ---
def generate_modify_instructions(graph: dict, node_map: Dict[str, dict]) -> List[dict]:
    """从 graph.json 中提取需要修改数据类型的节点信息。"""
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

# --- 新增函数 ---
def run_data_type_modifier() -> None:
    """调用《modifier.py》修改节点的数据类型。"""
    print("⚙️  正在执行数据类型修改脚本 …")
    stdout = run_subprocess([str(MODIFY_SCRIPT_PATH)])
    print(stdout)


def port_index(port_name: str, port_list: List[str]) -> int:
    # 修正：当只有一个端口时，直接返回索引0，避免模糊匹配问题
    if len(port_list) == 1:
        return 0
    
    normalized_ports = [normalize(p) for p in port_list]
    best = fuzzy_match(normalize(port_name), normalized_ports, FUZZY_CUTOFF_PORT)
    
    if best is None:
        sys.exit(f"错误：无法匹配端口 “{port_name}” ← 候选 {port_list}")
    return normalized_ports.index(best)


def build_connections(graph: dict, node_map: Dict[str, dict],
                      chip_index: Dict[str, dict]) -> List[dict]:
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


def run_batch_connect() -> None:
    """调用《批量连线.py》将 output.json 写入存档。"""
    print("🔗 正在执行批量连线脚本 …")
    stdout = run_subprocess([str(CONNECT_SCRIPT_PATH)])
    print(stdout)
# ======================================================================


def main() -> None:
    # ---------- 1. 读入并解析基础文件 ----------
    print("--- 步骤 1/5: 解析输入文件 ---")
    graph = load_json(GRAPH_PATH, "graph.json")
    chip_table = load_json(CHIP_DICT_PATH, "芯片名词.json")
    chip_index = build_chip_index(chip_table)
    modules, node_map = parse_graph(graph, chip_index)
    print("✅ 解析完成。")

    # ---------- 2. 批量添加模块 ----------
    print("\n--- 步骤 2/5: 批量添加模块 ---")
    run_batch_add(modules, node_map)
    print("✅ 模块添加完成，并已获取新节点ID。")

    # ---------- 3. 【新增】修改数据类型 ----------
    print("\n--- 步骤 3/5: 修改节点数据类型 ---")
    modify_instructions = generate_modify_instructions(graph, node_map)
    if modify_instructions:
        MODIFY_INPUT_PATH.write_text(
            json.dumps(modify_instructions, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"✅ 已生成类型修改指令 → {MODIFY_INPUT_PATH}")
        run_data_type_modifier()
        print("✅ 数据类型修改完成。")
    else:
        print("ℹ️ 无需修改数据类型，跳过此步骤。")


    # ---------- 4. 生成连线指令 ----------
    print("\n--- 步骤 4/5: 生成连线指令 ---")
    conns = build_connections(graph, node_map, chip_index)
    CONNECT_OUT_PATH.write_text(
        json.dumps(conns, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"✅ 已生成连线指令 → {CONNECT_OUT_PATH}")

    # ---------- 5. 自动调用批量连线 ----------
    print("\n--- 步骤 5/5: 执行批量连线 ---")
    run_batch_connect()

    print("\n🎉 全部流程完成！")


if __name__ == "__main__":
    main()