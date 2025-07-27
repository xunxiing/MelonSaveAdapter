#!/usr/bin/env python3
"""
批量添加/生成模块脚本 (batch_add_modules.py)
=================================================
功能概览
^^^^^^^^
1. **批量添加现有计算模块**（内部存档名 / displayName 模糊匹配）。
2. **批量生成 Input / Output / Constant 三类节点**，直接写入 *chip_inputs / chip_outputs / chip_graph*。
   - 依赖 :file:`chip_modifier.py` 中的节点构造函数。
   - Constant 节点默认数值为 ``0``。
3. 参数全部有默认值，直接双击/运行脚本即可。

日志风格
--------
- 与 `add_module.create_new_node()` 保持一致：
  ``为新节点生成ID: SomeNodeViewModel : <GUID>``
  `` 已添加: SomeNodeViewModel``
- Input/Output/Constant 亦采用相同格式。

输入文件一览  ::

  modules.json   要添加的模块列表 (字符串或简易指令；见下)
  data.json      游戏存档 (含芯片)
  allmod.json    所有计算模块定义表
  datatype_map.json  节点类型映射表 (新增依赖)

modules.json 写法
-----------------
- **普通模块** : ``"AddNumbersNodeViewModel"``
- **Input  节点** : ``"input:Health"``  (默认 Number 类型)
- **Output 节点** : ``"output:Damage"`` (默认 Number 类型)
- **Constant 节点** : ``"constant:Speed"`` 或 ``"constant"``  (值固定 0)

也可使用字典形式提供更细参数 ::

  {"type": "input", "name": "Velocity", "dataType": 2}

更新记录
~~~~~~~~
- 2025‑07‑24：
  * **【修复】** 对接新版 `create_new_node`，加载并传入 `datatype_map` 参数。
- 2025‑07‑23：
  * 加入大小写无关匹配；支持 displayName / friendlyName 等字段。
  * 集成 *Input / Output / Constant* 生成逻辑，日志格式保持一致。
  * **修复** Constant 节点日志不一致 → 现在与普通节点完全统一。
"""

import argparse
import importlib
import json
import re
import sys
from difflib import get_close_matches
from pathlib import Path
from typing import List, Dict, Any

# ------------------------------------------------------------
# 动态导入外部模块
# ------------------------------------------------------------
try:
    add_module = importlib.import_module("add_module")
except ModuleNotFoundError:
    print(" 无法找到 add_module.py，请确保它与本脚本位于同一目录。")
    sys.exit(1)

try:
    chip_modifier = importlib.import_module("chip_modifier")
except ModuleNotFoundError:
    print(" 无法找到 chip_modifier.py，请确保它与本脚本位于同一目录。")
    sys.exit(1)

# 复用工具
create_new_node = add_module.create_new_node
DATA_TYPE_MAP = add_module.DATA_TYPE_MAP
OPERATION_TYPE_MAP = add_module.OPERATION_TYPE_MAP

find_meta_data = chip_modifier.find_meta_data
create_input_node = chip_modifier.create_input_node
create_output_node = chip_modifier.create_output_node
create_constant_node = chip_modifier.create_constant_node
add_node_to_graph = chip_modifier.add_node_to_graph

# ------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------

def parse_special_notation(item: str) -> Dict[str, Any] | None:
    """解析形如 "input:Health", "constant", "output:Damage" 的简易指令。"""
    m = re.match(r"^(input|output|constant)(?::(?P<name>.*))?$", item, re.I)
    if not m:
        return None

    node_type = m.group(1).lower()
    name = (m.group("name") or node_type.title()).strip()
    return {"type": node_type, "name": name, "dataType": 2}


def fuzzy_best_match(name: str, candidates: List[str], cutoff: float = 0.5) -> str | None:
    """返回与 ``name`` 最接近的候选者；若低于 ``cutoff`` 返回 ``None``。忽略大小写。"""
    name_lower = name.lower().strip()
    match = get_close_matches(name_lower, candidates, n=1, cutoff=cutoff)
    return match[0] if match else None

# ------------------------------------------------------------
# 主处理逻辑
# ------------------------------------------------------------

def add_modules(
    modules_wanted: List[Any],
    data_path: Path,
    allmod_path: Path,
    output_path: Path,
    cutoff: float = 0.5,
) -> None:
    """主流程：先处理普通模块，再批量生成 I/O/Constant 节点。"""

    # ---------- 1. 载入数据文件 ----------
    try:
        with data_path.open("r", encoding="utf-8") as f:
            game_data = json.load(f)
        with allmod_path.open("r", encoding="utf-8") as f:
            all_modules = json.load(f)
        # --- 【核心修改 ①】加载 datatype_map.json ---
        datatype_map_path = Path("datatype_map.json")
        with datatype_map_path.open("r", encoding="utf-8") as f:
            datatype_map = json.load(f)
    except FileNotFoundError as exc:
        print(f" 加载文件失败: 找不到文件 {exc.filename}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f" 加载文件失败: JSON 格式错误 - {exc}")
        sys.exit(1)


    # ---------- 2. 分类指令 ----------
    internal_module_requests: List[str] = []
    special_node_defs: List[Dict[str, Any]] = []

    for item in modules_wanted:
        # a) dict 形式
        if isinstance(item, dict) and item.get("type") in {"input", "output", "constant"}:
            node_def = {
                "type": item["type"].lower(),
                "name": item.get("name", item["type"].title()),
                "dataType": item.get("dataType", 2),
            }
            if node_def["type"] == "constant":
                node_def["value"] = 0
            special_node_defs.append(node_def)
            continue

        # b) 字符串形式
        if isinstance(item, str):
            special = parse_special_notation(item)
            if special:
                special_node_defs.append(special)
            else:
                internal_module_requests.append(item)
            continue

        # c) 其它格式
        print(f" 跳过无法识别的指令: {item}")

    # ---------- 3. 普通模块批量添加 ----------
    candidate_map: dict[str, str] = {}
    alt_keys = ("display_name", "friendlyName", "FriendlyName", "name", "Name")
    for internal_key, info in all_modules.items():
        candidate_map.setdefault(internal_key.lower(), internal_key)
        for k in alt_keys:
            if k in info and str(info[k]).strip():
                candidate_map.setdefault(str(info[k]).strip().lower(), internal_key)

    candidate_names = list(candidate_map.keys())

    chip_graph_meta = None
    for container in game_data.get("saveObjectContainers", []):
        for meta in container.get("saveObjects", {}).get("saveMetaDatas", []):
            if meta.get("key") == "chip_graph":
                chip_graph_meta = meta
                break
        if chip_graph_meta:
            break

    if chip_graph_meta is None:
        print(" 在 data.json 中找不到 'chip_graph'，请确认存档文件正确。")
        sys.exit(1)

    chip_graph_data = json.loads(chip_graph_meta["stringValue"])
    existing_nodes = chip_graph_data["Nodes"]

    success, fail = [], []

    for raw_name in internal_module_requests:
        match_key_lower = fuzzy_best_match(raw_name, candidate_names, cutoff)
        if match_key_lower is None:
            print(f"️ 未找到与 '{raw_name}' 相近的模块，跳过。")
            fail.append(raw_name)
            continue

        internal_key = candidate_map[match_key_lower]
        module_info = all_modules[internal_key]
        
        # --- 【核心修改 ②】调用 create_new_node 时传入 datatype_map ---
        new_node = create_new_node(internal_key, module_info, existing_nodes, datatype_map)
        
        if new_node is None:
            fail.append(raw_name)
            continue

        existing_nodes.append(new_node)
        success.append(internal_key)
        print(f" 已添加: {internal_key}")

    # ---------- 4. 生成 Input / Output / Constant ----------
    if special_node_defs:
        try:
            save_objects = game_data["saveObjectContainers"][0]["saveObjects"]
            meta_datas = save_objects["saveMetaDatas"]
        except (KeyError, IndexError):
            print(" 错误: 存档文件结构异常，无法定位 meta 数据区。")
            sys.exit(1)

        chip_inputs_meta = find_meta_data(meta_datas, "chip_inputs")
        chip_outputs_meta = find_meta_data(meta_datas, "chip_outputs")

        chip_inputs_data = json.loads(chip_inputs_meta["stringValue"])
        chip_outputs_data = json.loads(chip_outputs_meta["stringValue"])

        max_y = max((n.get("VisualPosition", {}).get("y", 0) for n in existing_nodes), default=180.0)
        y_pos_counter = max_y + 200

        for node_def in special_node_defs:
            ntype = node_def["type"]
            name = node_def.get("name", ntype.title())
            data_type = node_def.get("dataType", 2)

            if ntype == "input":
                input_entry, graph_node = create_input_node(name, data_type)
                chip_inputs_data.append(input_entry)
                node_id = graph_node["Id"]
                print(f"为新节点生成ID: {node_id}")
                y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)
                success.append("RootNodeViewModel")
                print(f" 已添加: RootNodeViewModel")

            elif ntype == "output":
                output_entry, graph_node = create_output_node(name, data_type)
                chip_outputs_data.append(output_entry)
                node_id = graph_node["Id"]
                print(f"为新节点生成ID: {node_id}")
                y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)
                success.append("ExitNodeViewModel")
                print(f" 已添加: ExitNodeViewModel")

            elif ntype == "constant":
                value = node_def.get("value", 0)
                graph_node = create_constant_node(value, data_type)
                node_id = graph_node["Id"]
                print(f"为新节点生成ID: {node_id}")
                y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)
                node_type = node_id.split(" : ")[0]
                success.append(node_type)
                print(f" 已添加: {node_type}")

        chip_inputs_meta["stringValue"] = json.dumps(chip_inputs_data, separators=(',', ':'))
        chip_outputs_meta["stringValue"] = json.dumps(chip_outputs_data, separators=(',', ':'))

    chip_graph_meta["stringValue"] = json.dumps(chip_graph_data, ensure_ascii=False, indent=2)

    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(game_data, f, ensure_ascii=False, indent=4)
        print("\n 全部处理完成!")
        print(f"   成功添加 {len(success)} 个模块 → {output_path}")
        if fail:
            print(f"   ️ 有 {len(fail)} 个模块未处理: {', '.join(fail)}")
    except Exception as exc:
        print(f" 保存输出文件失败: {exc}")
        sys.exit(1)

# ------------------------------------------------------------
# CLI 入口
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量添加/生成模块到芯片图 (基于 add_module.py + chip_modifier.py)"
    )
    parser.add_argument(
        "-m",
        "--modules",
        type=Path,
        default=Path("modules.json"),
        help="包含待处理模块列表的 JSON 文件路径",
    )
    parser.add_argument(
        "-d",
        "--data",
        type=Path,
        default=Path("data.json"),
        help="芯片存档 data.json 路径",
    )
    parser.add_argument(
        "-a",
        "--allmod",
        type=Path,
        default=Path("allmod.json"),
        help="所有计算模块定义 allmod.json 路径",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data_modified_batch.json"),
        help="输出文件路径",
    )
    parser.add_argument(
        "-c",
        "--cutoff",
        type=float,
        default=0.4,
        help="模糊匹配阈值 0~1，越高越严格",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        with args.modules.open("r", encoding="utf-8") as f:
            modules_wanted = json.load(f)
        if not isinstance(modules_wanted, list):
            raise ValueError("modules.json 必须是数组！")
    except FileNotFoundError:
        print(f" 加载 modules.json 失败: 找不到文件 {args.modules}")
        sys.exit(1)
    except Exception as exc:
        print(f" 加载 modules.json 失败: {exc}")
        sys.exit(1)

    add_modules(
        modules_wanted, args.data, args.allmod, args.output, args.cutoff
    )


if __name__ == "__main__":
    main()