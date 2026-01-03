# --- START OF FILE add_module.py ---

import json
import uuid
import sys

# --- 配置 ---

# 【修改】模块类型名 -> 游戏内部数据类型代码的映射
# 根据你的 moduledef.json 示例，将 "Number" 更新为 "DECIMAL"
# 其他类型如果在新 json 中有不同名称，也需要在此更新
# 保持键为大写，作为标准格式
DATA_TYPE_MAP_INT = {
    "ENTITY": 1,
    "DECIMAL": 2, # "Number" 在新json中似乎被称为 "DECIMAL"
    "STRING": 4,
    "VECTOR": 8,
     "NUMBER": 2, # 保持大写以匹配 "Vector"
}

# 新节点在编辑器中的垂直间距
Y_SPACING = 200
DEFAULT_X_POS = -120.0

# 新版游戏数据中，GateDataType/DataType/OperationType 可能使用字符串。
# 这里提供一个双向的归一化，用于兼容旧 (int) / 新 (str) 两种格式。
TYPE_INT_TO_STR = {
    1: "Entity",
    2: "Number",
    4: "String",
    8: "Vector",
    128: "ArrayNumber",
    256: "ArrayString",
    512: "ArrayVector",
    1024: "ArrayEntity",
}
TYPE_STR_TO_INT = {v: k for k, v in TYPE_INT_TO_STR.items()}
TYPE_STR_ALIASES = {
    "decimal": "Number",
    "number": "Number",
    "string": "String",
    "vector": "Vector",
    "entity": "Entity",
    "signal": "Entity",
    "integernumber": "IntegerNumber",
    "arraynumber": "ArrayNumber",
    "arraystring": "ArrayString",
    "arrayvector": "ArrayVector",
    "arrayentity": "ArrayEntity",
    "any": "Any",
}


def _uses_string_schema(existing_nodes: list) -> bool:
    for n in existing_nodes or []:
        if isinstance(n.get("OperationType"), str):
            return True
        if isinstance(n.get("GateDataType"), str):
            return True
        for p in (n.get("Inputs") or []) + (n.get("Outputs") or []):
            if isinstance(p.get("DataType"), str):
                return True
    return False


def _canonical_type_str(t: object) -> str | None:
    if t is None or isinstance(t, bool):
        return None
    if isinstance(t, int):
        return TYPE_INT_TO_STR.get(t)
    if isinstance(t, str):
        s = t.strip()
        if not s:
            return None
        if s.isdigit():
            return TYPE_INT_TO_STR.get(int(s))
        key = s.replace("_", "").replace(" ", "").lower()
        return TYPE_STR_ALIASES.get(key, s)
    return None


def _coerce_type_value(t: object, *, use_string_types: bool) -> object:
    canon = _canonical_type_str(t)
    if canon is None:
        return t
    if use_string_types:
        return canon
    if canon == "IntegerNumber":
        return 2
    return TYPE_STR_TO_INT.get(canon, 0)

# --- 核心功能 ---

def create_new_node(module_name, module_info, existing_nodes):
    """
    【函数已修改】
    根据从 moduledef.json 读取的模块信息，创建一个新的、带有唯一ID的节点字典。
    不再需要 datatype_map 参数，因为所有信息都在 module_info 中。
    
    Args:
        module_name (str): 模块的ViewModel名称, e.g., "ConstantNodeViewModel".
        module_info (dict): 从 moduledef.json 中获取的该模块的完整定义。
        existing_nodes (list): 芯片图中已存在的节点列表。
    """
    
    use_string = _uses_string_schema(existing_nodes)

    # 1) OperationType: 旧版为 int，新版为 str（常见为 module 的 nodename）
    module_id = module_info.get("id")
    if module_id is None:
        print(f"错误: 模块 '{module_name}' 的 'id' 缺失。")
        return None

    if use_string:
        if isinstance(module_id, str) and not module_id.strip().isdigit():
            op_type_code = module_id.strip()
        else:
            op_type_code = (
                module_info.get("source_info", {}).get("datatype_map_nodename")
                or module_info.get("source_info", {}).get("chip_names_friendly_name")
                or str(module_id)
            )
    else:
        # 新版本允许字符串 id，不再强制要求数字
        if isinstance(module_id, str) and not module_id.strip().isdigit():
            # 如果是字符串且不是数字，尝试使用 source_info 中的名称
            op_type_code = (
                module_info.get("source_info", {}).get("datatype_map_nodename")
                or module_info.get("source_info", {}).get("chip_names_friendly_name")
                or str(module_id)
            )
        else:
            # 如果是数字或可以转换为数字，使用数字
            try:
                op_type_code = int(str(module_id).strip())
            except Exception:
                # 如果转换失败，使用 source_info 中的名称
                op_type_code = (
                    module_info.get("source_info", {}).get("datatype_map_nodename")
                    or module_info.get("source_info", {}).get("chip_names_friendly_name")
                    or str(module_id)
                )

    # 2. 生成唯一的节点ID
    node_id = f"{module_name} : {uuid.uuid4()}"
    print(f"为新节点生成ID: {node_id}")

    # 3. 【修改】根据新的输入/输出格式创建端口
    inputs = []
    for port_info in module_info.get("inputs", []):
        port_type = port_info.get("type", "DECIMAL")
        port_name = port_info.get("name", "Input")
        port_id = f"{node_id}\\nInput : {port_name} {uuid.uuid4()}"
        dt_value = _coerce_type_value(port_type, use_string_types=use_string)
        inputs.append({
            "Id": port_id,
            "DataType": dt_value,
            "connectedOutputIdModel": None
        })

    # 4. 【修改】创建输出端口
    outputs = []
    for port_info in module_info.get("outputs", []):
        port_type = port_info.get("type", "DECIMAL")
        port_name = port_info.get("name", "Output")
        port_id = f"{node_id}\\nOutput : {port_name} {uuid.uuid4()}"
        dt_value = _coerce_type_value(port_type, use_string_types=use_string)
        outputs.append({
            "Id": port_id,
            "DataType": dt_value,
            "ConnectedInputsIds": []
        })
        
    # 5. 计算新节点的位置，避免重叠 (逻辑不变)
    max_y = -float('inf')
    if not existing_nodes:
        max_y = 0 
    else:
        for node in existing_nodes:
            y_pos = node.get("VisualPosition", {}).get("y", 0)
            if y_pos > max_y:
                max_y = y_pos
    
    new_y = max_y + Y_SPACING if existing_nodes else 180.0
    new_position = {
        "x": DEFAULT_X_POS,
        "y": new_y
    }

    # 6. 【修改】直接从 module_info 获取 GateDataType
    raw_gate_type = module_info.get("gate_data_type", 2) # 提供一个默认值以防万一
    gate_data_type = _coerce_type_value(raw_gate_type, use_string_types=use_string)

    # 7. 组装完整的节点对象 (逻辑不变, 删除了不必要的字段)
    new_node = {
        "Id": node_id,
        "ModelVersion": 1,
        "Version": "0.1",
        "OperationType": op_type_code,
        "Inputs": inputs,
        "Outputs": outputs,
        "VisualPosition": new_position,
        "VisualCollapsed": False,
        "MechanicConnectionId": None,
        "GateDataType": gate_data_type,
        "SaveData": None
    }
    
    return new_node

def main():
    """主执行函数（用于独立测试）"""
    try:
        # 【修改】加载文件，现在只需要 data.json 和新的 moduledef.json
        with open('data.json', 'r', encoding='utf-8') as f:
            game_data = json.load(f)
        with open('moduledef.json', 'r', encoding='utf-8') as f:
            module_definitions = json.load(f)
            
    except FileNotFoundError as e:
        print(f"错误: 找不到文件 {e.filename}。请确保 data.json 和 moduledef.json 与脚本在同一目录下。")
        return
    except json.JSONDecodeError as e:
        print(f"错误: JSON文件格式不正确 - {e}")
        return

    # 【新增】动态构建 ViewModel 名称到模块信息的映射
    viewmodel_to_module_map = {}
    for mod_id, mod_data in module_definitions.items():
        viewmodel_name = mod_data.get("source_info", {}).get("allmod_viewmodel")
        if viewmodel_name:
            mod_data['id'] = mod_id  # 确保模块数据中包含其自身的ID
            viewmodel_to_module_map[viewmodel_name] = mod_data
        else:
            print(f"警告: moduledef.json 中 ID 为 '{mod_id}' 的条目缺少 'allmod_viewmodel'，将无法通过名称添加。")

    # 获取用户输入
    print("可用模块 (存档名):")
    for name in sorted(viewmodel_to_module_map.keys()):
        print(f"- {name}")
    module_to_add = input("\n请输入要添加的模块的准确存档名: ")

    # 【修改】使用新的映射来验证用户输入并获取模块信息
    if module_to_add not in viewmodel_to_module_map:
        print(f"错误: 在 moduledef.json 中找不到存档名为 '{module_to_add}' 的模块。")
        return

    module_info = viewmodel_to_module_map[module_to_add]
    
    # 定位 chip_graph (逻辑不变)
    chip_graph_meta = None
    for container in game_data.get("saveObjectContainers", []):
        for meta in container.get("saveObjects", {}).get("saveMetaDatas", []):
            if meta.get("key") == "chip_graph":
                chip_graph_meta = meta
                break
        if chip_graph_meta:
            break

    if not chip_graph_meta:
        print("错误: 在 data.json 中找不到 'chip_graph'。")
        return

    chip_graph_data = json.loads(chip_graph_meta["stringValue"])
    
    # 【修改】调用更新后的 create_new_node 函数
    new_node = create_new_node(module_to_add, module_info, chip_graph_data["Nodes"])

    if new_node is None:
        return

    chip_graph_data["Nodes"].append(new_node)
    chip_graph_meta["stringValue"] = json.dumps(chip_graph_data, indent=2)

    try:
        with open('data_modified.json', 'w', encoding='utf-8') as f:
            json.dump(game_data, f, indent=4)
        print("\n成功!")
        print(f"已将新模块 '{module_to_add}' 添加完毕。")
        print("结果已保存到 data_modified.json 文件中。")
    except Exception as e:
        print(f"保存文件时发生错误: {e}")


if __name__ == "__main__":
    main()

# --- END OF FILE add_module.py ---
