# --- START OF FILE batch_add_modules.py ---

#!/usr/bin/env python3
"""
批量添加/生成模块脚本 (batch_add_modules.py) - 已重构为可导入模块

核心函数 `add_modules` 被修改为：
- 接收已加载的 Python 对象 (字典, 列表)作为输入。
- 返回一个元组 `(updated_game_data, created_nodes_info)`，其中包含:
  1.  修改后的完整游戏存档数据。
  2.  一个包含新创建节点详细信息的列表，供调用方直接使用。
- 不再执行文件读写或打印关键信息到 stdout，实现了逻辑与 I/O 的分离。
"""
import argparse
from difflib import get_close_matches
import importlib
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
import copy

# ... (动态导入和复用工具部分保持不变) ...
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

# 变量模块：使用新的 VariableManager
try:
    from src.variable_manager import VariableManager
    # 兼容现有代码，仍使用 variable_mod.find_meta_data (它其实只是 chip_modifier.find_meta_data 的别名)
    variable_mod = importlib.import_module("variable")
    find_variable_meta_data = variable_mod.find_meta_data
except (ImportError, ModuleNotFoundError):
    # 尝试直接导入 variable.py 以兼容独立运行模式
    try:
        variable_mod = importlib.import_module("variable")
        find_variable_meta_data = variable_mod.find_meta_data
        print(" 提示: 使用旧版 variable.py 兼容模式 (未找到 src.variable_manager)")
    except ModuleNotFoundError:
        print(" 无法找到 variable.py，请确保它与本脚本位于同一目录。")
        sys.exit(1)

# 【修改】create_new_node 的调用方式将改变，但导入本身不变
create_new_node = add_module.create_new_node
find_meta_data = chip_modifier.find_meta_data
create_input_node = chip_modifier.create_input_node
create_output_node = chip_modifier.create_output_node
create_constant_node = chip_modifier.create_constant_node
add_node_to_graph = chip_modifier.add_node_to_graph
# ------------------------------------------------------------
# 辅助函数 (无变化)
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


# build_serialized_value_for_variable 已移除，改用 VariableManager 内部逻辑

# ------------------------------------------------------------
# 主处理逻辑 (核心重构)
# ------------------------------------------------------------

def add_modules(
    modules_wanted: List[Any],
    game_data: Dict[str, Any],
    module_definitions: Dict[str, Any], # 【修改】合并后的单一模块定义文件
    cutoff: float = 0.5,
) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """
    主流程：处理模块添加请求并返回修改后的数据和新节点信息。

    Args:
        modules_wanted: 待添加模块的指令列表。
        game_data: 已加载的游戏存档 (data.json 内容)。
        module_definitions: 已加载的模块定义 (moduledef.json 内容)。
        cutoff: 模糊匹配阈值。

    Returns:
        一个元组 (updated_game_data, created_nodes_info):
        - updated_game_data: 修改后的游戏存档字典。
        - created_nodes_info: 一个列表，每个元素是包含 'class_name' 和 'full_id' 的字典。
    """
    created_nodes_info: List[Dict[str, str]] = []
    
    # ---------- 1. 分类指令 (无变化) ----------
    internal_module_requests: List[str] = []
    special_node_defs: List[Dict[str, Any]] = []
    original_request_order = [] 

    for item in modules_wanted:
        if isinstance(item, dict):
            t = item.get("type")
            # input / output / constant：走原有专用分支
            if t in {"input", "output", "constant"}:
                node_def = {
                    "type": t.lower(),
                    "name": item.get("name", t.title()),
                    "dataType": item.get("dataType", 2),
                }
                if node_def["type"] == "constant":
                    node_def["value"] = 0
                special_node_defs.append(node_def)
                original_request_order.append(node_def)
            # 新增：variable 变量节点（由 DSL + converter_v2 提供完整信息）
            elif t == "variable":
                node_def = {
                    "type": "variable",
                    "key": item.get("key"),
                    "gateDataType": item.get("gateDataType", "Number"),
                    "value": item.get("value"),
                }
                special_node_defs.append(node_def)
                original_request_order.append(node_def)
            else:
                print(f" 警告: 跳过无法识别的 dict 指令: {item}")
        elif isinstance(item, str):
            special = parse_special_notation(item)
            if special:
                special_node_defs.append(special)
                original_request_order.append(special)
            else:
                internal_module_requests.append(item)
                original_request_order.append(item)
        else:
            print(f" 警告: 跳过无法识别的指令: {item}")

    # ---------- 2. 定位 chip_graph (无变化) ----------
    chip_graph_meta = None
    for container in game_data.get("saveObjectContainers", []):
        for meta in container.get("saveObjects", {}).get("saveMetaDatas", []):
            if meta.get("key") == "chip_graph":
                chip_graph_meta = meta
                break
        if chip_graph_meta:
            break
    
    if chip_graph_meta is None:
        raise ValueError("在 data.json 中找不到 'chip_graph'，请确认存档文件正确。")

    chip_graph_data = json.loads(chip_graph_meta["stringValue"])
    existing_nodes = chip_graph_data["Nodes"]

    # 新版存档：OperationType/GateDataType/DataType 可能为字符串
    # 注意：VariableNodeViewModel 往往天然是 OperationType="Variable"(str)，但这不代表全图需要切换到 string schema。
    # 这里复用 add_module._uses_string_schema 的判断逻辑，避免误判导致 int/str schema 混用而游戏加载失败。
    try:
        use_string_schema = bool(add_module._uses_string_schema(existing_nodes))
    except Exception:
        use_string_schema = False
        for n in existing_nodes or []:
            op = n.get("OperationType")
            if isinstance(op, str) and op.strip().lower() == "variable":
                continue
            if isinstance(op, str) or isinstance(n.get("GateDataType"), str):
                use_string_schema = True
                break
            for p in (n.get("Inputs") or []) + (n.get("Outputs") or []):
                if isinstance(p.get("DataType"), str):
                    use_string_schema = True
                    break
            if use_string_schema:
                break
    
    # ---------- 3. 【核心修改】从 moduledef.json 构建模块匹配映射 ----------
    candidate_map: Dict[str, str] = {}
    for internal_id, mod_info in module_definitions.items():
        source_info = mod_info.get("source_info", {})
        
        # 使用 allmod_viewmodel (游戏存档名) 作为匹配项
        view_model = source_info.get("allmod_viewmodel")
        if view_model and str(view_model).strip():
            candidate_map.setdefault(str(view_model).strip().lower(), internal_id)
            
        # 使用 chip_names_friendly_name (友好名称) 作为匹配项
        friendly_name = source_info.get("chip_names_friendly_name")
        if friendly_name and str(friendly_name).strip():
            candidate_map.setdefault(str(friendly_name).strip().lower(), internal_id)
            
    candidate_names = list(candidate_map.keys())

    # 创建处理队列，以保持原始顺序 (逻辑无大变化)
    processing_queue = []
    temp_requests = list(internal_module_requests)
    for req in original_request_order:
        if isinstance(req, str) and req in temp_requests:
            match_key_lower = fuzzy_best_match(req, candidate_names, cutoff)
            if match_key_lower:
                internal_id = candidate_map[match_key_lower]
                processing_queue.append({"type": "internal", "id": internal_id, "info": module_definitions[internal_id]})
                temp_requests.remove(req)
            else:
                print(f"️ 未找到与 '{req}' 相近的模块，跳过。")
        elif isinstance(req, dict):
            processing_queue.append(req)

    # 定位 I/O / 变量 元数据
    meta_datas = None
    chip_inputs_meta = None
    chip_outputs_meta = None
    chip_variables_meta = None

    if any(p.get("type") in ["input", "output", "variable"] for p in processing_queue):
        try:
            save_objects = game_data["saveObjectContainers"][0]["saveObjects"]
            meta_datas = save_objects["saveMetaDatas"]
        except (KeyError, IndexError):
            raise ValueError("存档文件结构异常，无法定位 meta 数据区。")

    chip_inputs_data: List[Dict[str, Any]] = []
    chip_outputs_data: List[Dict[str, Any]] = []
    chip_variables_data: List[Dict[str, Any]] = []

    if meta_datas is not None:
        if any(p.get("type") == "input" for p in processing_queue):
            chip_inputs_meta = find_meta_data(meta_datas, "chip_inputs")
            raw = chip_inputs_meta.get("stringValue") if chip_inputs_meta else None
            chip_inputs_data = json.loads(raw) if raw else []

        if any(p.get("type") == "output" for p in processing_queue):
            chip_outputs_meta = find_meta_data(meta_datas, "chip_outputs")
            raw = chip_outputs_meta.get("stringValue") if chip_outputs_meta else None
            chip_outputs_data = json.loads(raw) if raw else []

        if any(p.get("type") == "variable" for p in processing_queue):
            var_meta_list, var_index = find_variable_meta_data(game_data, "chip_variables")
            if var_meta_list is None or var_index is None:
                raise ValueError("在 data.json 中找不到 'chip_variables'，请确认存档文件正确。")
            chip_variables_meta = var_meta_list[var_index]
            raw = chip_variables_meta.get("stringValue")
            chip_variables_data = json.loads(raw) if raw else []
    
    max_y = max((n.get("VisualPosition", {}).get("y", 0) for n in existing_nodes), default=180.0)
    y_pos_counter = max_y + 200

    # ---------- 4. 【修改】按顺序统一处理所有节点创建 ----------
    for req_item in processing_queue:
        node_type = req_item.get("type")

        if node_type == "internal":
            module_info = req_item["info"]
            view_model_name = module_info.get("source_info", {}).get("allmod_viewmodel", f"Module_{req_item['id']}")

            # 调用更新后的 create_new_node，它不再需要 datatype_map
            new_node = create_new_node(view_model_name, module_info, existing_nodes)
            if new_node is None:
                continue

            existing_nodes.append(new_node)
            print(f" 已添加: {view_model_name}")
            created_nodes_info.append({"class_name": view_model_name, "full_id": new_node["Id"]})
        
        # 处理 input/output/constant 的逻辑不变
        elif node_type == "input":
            name = req_item.get("name", "Input")
            data_type = req_item.get("dataType", 2)
            input_entry, graph_node = create_input_node(name, data_type, use_string_schema=use_string_schema)
            chip_inputs_data.append(input_entry)
            node_id = graph_node["Id"]
            print(f"为新节点生成ID: RootNodeViewModel : {node_id.split(' : ')[-1]}")
            y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)
            print(f" 已添加: RootNodeViewModel")
            created_nodes_info.append({"class_name": "RootNodeViewModel", "full_id": node_id})
        
        elif node_type == "output":
            name = req_item.get("name", "Output")
            data_type = req_item.get("dataType", 2)
            output_entry, graph_node = create_output_node(name, data_type, use_string_schema=use_string_schema)
            chip_outputs_data.append(output_entry)
            node_id = graph_node["Id"]
            print(f"为新节点生成ID: ExitNodeViewModel : {node_id.split(' : ')[-1]}")
            y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)
            print(f" 已添加: ExitNodeViewModel")
            created_nodes_info.append({"class_name": "ExitNodeViewModel", "full_id": node_id})

        elif node_type == "constant":
            value = req_item.get("value", 0)
            data_type = req_item.get("dataType", 2)
            graph_node = create_constant_node(value, data_type, use_string_schema=use_string_schema)
            node_id = graph_node["Id"]
            class_name = node_id.split(" : ")[0]
            print(f"为新节点生成ID: {node_id}")
            y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)
            print(f" 已添加: {class_name}")
            created_nodes_info.append({"class_name": class_name, "full_id": node_id})

        elif node_type == "variable":
            var_key = req_item.get("key")
            gate_type = req_item.get("gateDataType", "Number")
            init_value = req_item.get("value")

            if not isinstance(var_key, str) or not var_key:
                print(" 警告: 跳过一个变量节点，因为缺少合法的 key。")
                continue

            # 使用 VariableManager (如果可用)
            if 'VariableManager' in globals():
                # 1) chip_variables 中追加 / 更新变量定义
                existing_def_idx = -1
                for i, vd in enumerate(chip_variables_data):
                    if vd.get("Key") == var_key:
                        existing_def_idx = i
                        break

                # 无论是否存在，都尝试生成一个新的定义（包含可能更新的 Value）
                # 注意：VariableManager.create_definition 会自动处理类型转换(str->int)
                # 注意：Variable 节点在很多存档里天然使用 string schema（OperationType="Variable"，且端口类型为字符串）。
                # 即使整体 chip_graph 仍是旧版 int schema，我们也应当让变量相关结构保持 string schema，避免游戏侧解析失败。
                var_string_schema = True
                new_var_def = VariableManager.create_definition(
                    var_key,
                    gate_type,
                    init_value,
                    use_string_schema=var_string_schema,
                )
                
                if existing_def_idx >= 0:
                    # 如果已存在，仅在需要时更新值？
                    # 原逻辑：同一个 Key 的第一个实例使用变量定义中的 Value 作为初始值，其余实例 value=None
                    # 这里 req_item["value"] 已经在 build_variable_module 中处理过（只有第一次有值）
                    if init_value is not None:
                        # 覆盖旧定义的 SerializedValue
                        chip_variables_data[existing_def_idx]["SerializedValue"] = new_var_def["SerializedValue"]
                        # 确保 GateDataType 也更新 (特别是修复 bug 时)
                        chip_variables_data[existing_def_idx]["GateDataType"] = new_var_def["GateDataType"]
                else:
                    chip_variables_data.append(new_var_def)

                # 2) chip_graph 中生成 Variable 节点
                # 需要 y_pos_counter
                graph_node = VariableManager.create_node(
                    var_key,
                    gate_type,
                    {"x": 0.0, "y": 0.0},  # 位置将在 add_node_to_graph 中被覆盖(y)
                    use_string_schema=var_string_schema,
                )
                node_id = graph_node["Id"]
                print(f"为新节点生成ID: {node_id}")
                y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)
                print(" 已添加: VariableNodeViewModel (via Manager)")
                created_nodes_info.append({"class_name": "VariableNodeViewModel", "full_id": node_id})
            else:
                # 严重错误：VariableManager 不可用
                print("错误：VariableManager 未加载，无法创建变量模块。")

    # ---------- 5. 写回修改 (无变化) ----------
    if chip_inputs_meta:
        chip_inputs_meta["stringValue"] = json.dumps(chip_inputs_data, separators=(',', ':'))
    if chip_outputs_meta:
        chip_outputs_meta["stringValue"] = json.dumps(chip_outputs_data, separators=(',', ':'))
    if chip_variables_meta:
        chip_variables_meta["stringValue"] = json.dumps(chip_variables_data, separators=(',', ':'))
    
    chip_graph_meta["stringValue"] = json.dumps(chip_graph_data, ensure_ascii=False, indent=2)

    return game_data, created_nodes_info


# ------------------------------------------------------------
# CLI 入口 (已修改)
# ------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量添加/生成模块到芯片图 (基于 add_module.py + chip_modifier.py)"
    )
    parser.add_argument("-m","--modules",type=Path,default=Path("modules.json"),help="包含待处理模块列表的 JSON 文件路径",)
    parser.add_argument("-d","--data",type=Path,default=Path("data.json"),help="芯片存档 data.json 路径",)
    # 【修改】更新参数以反映新的单一文件
    parser.add_argument("--moduledef",type=Path,default=Path("moduledef.json"),help="包含所有模块定义的 moduledef.json 路径",)
    parser.add_argument("-o","--output",type=Path,default=Path("data_modified_batch.json"),help="输出文件路径",)
    parser.add_argument("-c","--cutoff",type=float,default=0.4,help="模糊匹配阈值 0~1，越高越严格",)
    return parser.parse_args()


def main_cli() -> None:
    """独立的命令行执行逻辑"""
    args = parse_args()

    # 1. 【修改】载入所有文件
    try:
        with args.modules.open("r", encoding="utf-8") as f:
            modules_wanted = json.load(f)
        if not isinstance(modules_wanted, list):
            raise ValueError("modules.json 必须是数组！")
        
        with args.data.open("r", encoding="utf-8") as f:
            game_data = json.load(f)
        # 【修改】加载 moduledef.json
        with args.moduledef.open("r", encoding="utf-8") as f:
            module_definitions = json.load(f)

    except FileNotFoundError as exc:
        print(f" 加载文件失败: 找不到文件 {exc.filename}")
        sys.exit(1)
    except Exception as exc:
        print(f" 加载文件失败: {exc}")
        sys.exit(1)

    # 2. 【修改】调用核心处理函数
    updated_data, created_nodes = add_modules(
        modules_wanted, game_data, module_definitions, args.cutoff
    )

    # 3. 保存输出文件 (无变化)
    try:
        with args.output.open("w", encoding="utf-8") as f:
            json.dump(updated_data, f, ensure_ascii=False, indent=4)
        print("\n 全部处理完成!")
        print(f"   成功添加 {len(created_nodes)} 个模块 → {args.output}")
        if len(modules_wanted) > len(created_nodes):
             print(f"   ️ 有 {len(modules_wanted) - len(created_nodes)} 个模块未处理。")
    except Exception as exc:
        print(f" 保存输出文件失败: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main_cli()
# --- END OF FILE batch_add_modules.py ---
