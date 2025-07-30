import json
import argparse
from typing import Dict, List, Any, Optional

# --- 数据类型常量 ---
# 便于理解和维护
DATA_TYPE_MAP = {
    1: "entity",
    2: "Decimal",
    4: "String",
    8: "Vector"
}
# 需要被忽略特殊处理的模块 OperationType
# 256: Input, 257: Constant, 512: Output
IGNORED_OPERATION_TYPES = {256, 512}


# --- 默认值生成器 (无变化) ---
# 这些函数为不同位置生成正确的默认值字符串
# --- 默认值生成器 (已修正) ---
def get_default_save_data(data_type: int) -> Optional[str]:
    """(用于 chip_graph) 生成 SaveData 字符串"""
    
    # --- 逻辑修正点 ---
    # 对于 Vector 类型，它的 DataValue 必须是“一个JSON对象的字符串表示”
    # 所以我们先把它序列化一次
    VECTOR_VAL_STRING = json.dumps(
        {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0, "magnitude": 0.0, "sqrMagnitude": 0.0},
        separators=(',', ':')
    )

    values = {
        1: None,          # Signal 通常没有 SaveData, 返回 None
        2: "0.0",         # Decimal 的 DataValue 是一个数字字符串
        4: "",            # String 的 DataValue 是一个空字符串
        8: VECTOR_VAL_STRING  # Vector 的 DataValue 是一个JSON字符串
    }
    
    value = values.get(data_type)

    # Signal/Boolean 类型 (1) 的 SaveData 字段本身就是 null
    if data_type == 1:
        return None

    # 对于其他类型，将 {"DataValue": value} 整体序列化
    # separators=(',', ':') 用于生成最紧凑的JSON，符合游戏存档格式
    return json.dumps({"DataValue": value}, separators=(',', ':')) if data_type in values else None

# 其他两个 get_default_... 函数不需要修改，它们的格式是正确的。

def get_default_serialized_value(data_type: int) -> Optional[str]:
    """(用于 chip_inputs/outputs) 生成 SerializedValue 字符串"""
    VECTOR_OBJ = {"x":0.0,"y":0.0,"z":0.0,"w":0.0,"magnitude":0.0,"sqrMagnitude":0.0}
    values = {
        1: None, # Signal 在此也通常为 null
        2: json.dumps({"Value":0.0,"Default":0.0,"Min":-3.40282347E+38,"Max":3.40282347E+38,"IsCheckbox":False}),
        4: json.dumps({"Value":"","Default":None,"MaxLength":2147483647}),
        8: json.dumps({"Value":VECTOR_OBJ,"Default":VECTOR_OBJ})
    }
    return values.get(data_type)

def get_default_gate_data(data_type: int) -> Optional[str]:
    """(用于 mechanicSerializedInputs) 生成 GateData 字符串"""
    VECTOR_OBJ = {"x":0.0,"y":0.0,"z":0.0,"w":0.0,"magnitude":0.0,"sqrMagnitude":0.0}
    MIN_VEC = {"x":-3.40282347E+38,"y":-3.40282347E+38,"z":-3.40282347E+38,"w":-3.40282347E+38,"normalized":{"x":0.0,"y":0.0,"z":0.0,"w":0.0,"magnitude":0.0,"sqrMagnitude":0.0},"magnitude":"Infinity","sqrMagnitude":"Infinity"}
    MAX_VEC = {"x":3.40282347E+38,"y":3.40282347E+38,"z":3.40282347E+38,"w":3.40282347E+38,"normalized":{"x":0.0,"y":0.0,"z":0.0,"w":0.0,"magnitude":0.0,"sqrMagnitude":0.0},"magnitude":"Infinity","sqrMagnitude":"Infinity"}
    values = {
        1: None,
        2: json.dumps({"Value":0.0,"Default":0.0,"Min":-3.40282347E+38,"Max":3.40282347E+38,"IsCheckbox":False}),
        4: json.dumps({"Value":"","Default":None,"MaxLength":2147483647}),
        8: json.dumps({"Value":VECTOR_OBJ,"Default":VECTOR_OBJ,"MinVector":MIN_VEC,"MaxVector":MAX_VEC})
    }
    return values.get(data_type)


def get_friendly_type_name(data_type: int) -> str:
    """将数据类型数字转换为可读字符串"""
    return DATA_TYPE_MAP.get(data_type, f"Unknown({data_type})")

def get_friendly_module_name(op_type: int, module_defs: Dict) -> str:
    """从 moduledef 获取模块友好名称"""
    return module_defs.get(str(op_type), {}).get("source_info", {}).get("datatype_map_nodename", f"OpType({op_type})")


# --- 【核心修改函数】 ---
# --- 【核心修改函数】(已修正) ---
def apply_data_type_modifications(
    game_data: Dict[str, Any],
    mod_instructions: List[Dict[str, Any]],
    rules: Dict[str, Any],
    module_defs: Dict[str, Any]
) -> Dict[str, Any]:
    """
    根据规则文件，读取游戏数据和修改指令，并应用数据类型修改。
    """
    connections_to_update = {}
    modification_made = False

    main_data = game_data

    for container in main_data.get('saveObjectContainers', []):
        save_objects = container.get('saveObjects', {})
        meta_datas = save_objects.get('saveMetaDatas', [])
        mechanic_data_list = save_objects.get('mechanicData', [])

        if not meta_datas:
            continue

        print("\n--- 阶段 1: 分析并修改 chip_graph ---")
        for meta_data in meta_datas:
            if meta_data.get('key') == 'chip_graph':
                graph_string = meta_data.get('stringValue')
                if not graph_string:
                    continue

                graph_data = json.loads(graph_string)
                nodes_list = graph_data.get('Nodes', [])

                for instruction in mod_instructions:
                    node_id = instruction['node_id']
                    new_node_type = instruction['new_data_type']

                    node_found = next((n for n in nodes_list if n.get('Id') == node_id), None)

                    if not node_found:
                        continue
                    
                    print(f"  -> 找到节点: {node_id}")
                    op_type = node_found.get('OperationType')
                    module_name = get_friendly_module_name(op_type, module_defs)

                    # --- 逻辑修正点 ---
                    # 1. 无论节点类型如何，只要它是外部IO，就必须先记录下来以便同步
                    conn_id = node_found.get('MechanicConnectionId')
                    if conn_id:
                        print(f"     发现外部连接 '{conn_id}'。将加入同步列表。")
                        connections_to_update[conn_id] = new_node_type
                        modification_made = True # 只要有IO连接要更新，就视为有修改

                    # 2. 现在再判断是否要跳过对节点内部的修改
                    if op_type in IGNORED_OPERATION_TYPES:
                        print(f"     跳过对特殊模块 '{module_name}' (ID: {node_id}) 的内部修改。外部连接已记录。")
                        # (可选) 对于 Input/Output，可以只更新它们在chip_graph中的主类型，因为这有时是必要的
                        node_found['GateDataType'] = new_node_type
                        # 简单的IO节点通常只有一个输出/输入，可以安全地也更新一下
                        for port in node_found.get('Outputs', []): port['DataType'] = new_node_type
                        for port in node_found.get('Inputs', []): port['DataType'] = new_node_type
                        continue # 跳过后续复杂的规则应用

                    # --- 原有逻辑 (适用于普通模块) ---
                    print(f"     模块类型: '{module_name}' (OpType: {op_type}), 准备更新主类型为 {get_friendly_type_name(new_node_type)}")

                    # 更新节点本身的主数据类型和存档数据
                    node_found['GateDataType'] = new_node_type
                    node_found['SaveData'] = get_default_save_data(new_node_type)
                    modification_made = True

                    # 根据规则更新端口
                    rule = rules.get(str(op_type))
                    if rule:
                        print(f"     应用 '{rule.get('module_name', '未知')}' 规则:")
                        # 更新输入端口
                        if 'Inputs' in node_found and 'inputs' in rule:
                            for i, port in enumerate(node_found['Inputs']):
                                if i < len(rule['inputs']):
                                    port_rule = rule['inputs'][i]
                                    final_type = new_node_type if port_rule == "same" else port_rule
                                    port['DataType'] = final_type
                                    print(f"       - 输入端口 {i}: 规则='{port_rule}', 更新为 -> {get_friendly_type_name(final_type)}")

                        # 更新输出端口
                        if 'Outputs' in node_found and 'outputs' in rule:
                            for i, port in enumerate(node_found['Outputs']):
                                if i < len(rule['outputs']):
                                    port_rule = rule['outputs'][i]
                                    final_type = new_node_type if port_rule == "same" else port_rule
                                    port['DataType'] = final_type
                                    print(f"       - 输出端口 {i}: 规则='{port_rule}', 更新为 -> {get_friendly_type_name(final_type)}")
                    else:
                        # 如果没有找到规则，执行旧的“全部统一”逻辑
                        print(f"     警告: 未找到 OpType {op_type} 的特定规则。将所有端口类型统一为 {get_friendly_type_name(new_node_type)}。")
                        for port in node_found.get('Inputs', []):
                            port['DataType'] = new_node_type
                        for port in node_found.get('Outputs', []):
                            port['DataType'] = new_node_type
                    
                    # (这部分逻辑已移到前面)
                    # conn_id = node_found.get('MechanicConnectionId') ...

                meta_data['stringValue'] = json.dumps(graph_data, separators=(',', ':'))
                break 

        if not connections_to_update and modification_made:
            print("\n警告: 进行了内部修改，但未找到需要同步的外部连接。可能修改的是非IO节点。")

        # ... 后续的 阶段 2 和 阶段 3 无需改动 ...
        print("\n--- 阶段 2: 同步 chip_inputs / chip_outputs (编辑器UI) ---")
        # ... (代码不变)
        for meta_data in meta_datas:
            if meta_data.get('key') in ['chip_inputs', 'chip_outputs']:
                key_name = meta_data['key']
                io_list_str = meta_data.get('stringValue')
                if not io_list_str: continue

                io_list = json.loads(io_list_str)
                updated = False
                for item in io_list:
                    if item.get('Key') in connections_to_update:
                        new_type = connections_to_update[item.get('Key')]
                        print(f"  -> 在 {key_name} 中更新 '{item.get('Key')}' 的类型为 {get_friendly_type_name(new_type)}")
                        item['GateDataType'] = new_type
                        item['SerializedValue'] = get_default_serialized_value(new_type)
                        updated = True
                if updated:
                    # 注意：chip_inputs/outputs最好保持格式化，方便阅读
                    meta_data['stringValue'] = json.dumps(io_list, indent=2)

        print("\n--- 阶段 3: 同步 mechanicSerializedInputs (游戏运行时) ---")
        # ... (代码不变)
        for mechanic_item in mechanic_data_list:
            mech_inputs_str = mechanic_item.get('mechanicSerializedInputs')
            if not mech_inputs_str: continue

            mech_inputs = json.loads(mech_inputs_str)
            updated = False
            for item in mech_inputs:
                if item.get('Key') in connections_to_update:
                    new_type = connections_to_update[item.get('Key')]
                    print(f"  -> 在 mechanicSerializedInputs 中更新 '{item.get('Key')}' 的类型为 {get_friendly_type_name(new_type)}")
                    item['DataType'] = new_type
                    item['GateData'] = get_default_gate_data(new_type)
                    updated = True
            if updated:
                # 这个通常不需要格式化
                mechanic_item['mechanicSerializedInputs'] = json.dumps(mech_inputs)


    if not modification_made:
        print("警告: 根据指令，没有执行任何修改。请检查节点ID是否正确。")

    return main_data

# --- 程序主入口 (用于独立运行) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="根据规则智能修改游戏存档中的芯片数据类型。")
    parser.add_argument("-d", "--data", default='Data.json', help="主数据文件路径。")
    parser.add_argument("-i", "--instructions", default='instructions.json', help="修改指令文件路径。")
    parser.add_argument("-r", "--rules", default='data_type_rules.json', help="模块端口数据类型规则文件路径。")
    parser.add_argument("-m", "--moduledef", default='moduledef.json', help="模块定义文件路径。")
    parser.add_argument("-o", "--output", default='Data_modified.json', help="修改后文件的保存路径。")
    args = parser.parse_args()

    try:
        print(f"正在读取主数据文件: {args.data}")
        with open(args.data, 'r', encoding='utf-8') as f:
            game_data_content = json.load(f)

        print(f"正在读取修改指令文件: {args.instructions}")
        with open(args.instructions, 'r', encoding='utf-8') as f:
            mod_instructions_content = json.load(f)

        print(f"正在读取类型规则文件: {args.rules}")
        with open(args.rules, 'r', encoding='utf-8') as f:
            rules_content = json.load(f)

        print(f"正在读取模块定义文件: {args.moduledef}")
        with open(args.moduledef, 'r', encoding='utf-8') as f:
            moduledef_content = json.load(f)

        # 调用核心函数
        modified_data = apply_data_type_modifications(
            game_data_content,
            mod_instructions_content,
            rules_content,
            moduledef_content
        )

        print("\n--- 阶段 4: 保存文件 ---")
        print(f"修改完成，正在保存到: {args.output}")
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(modified_data, f, indent=4, ensure_ascii=False)
        print("文件已成功保存！")

    except FileNotFoundError as e:
        print(f"错误: 找不到文件 {e.filename}。请检查路径是否正确。")
    except json.JSONDecodeError as e:
        print(f"错误: 解析JSON文件时出错 - {e}。请检查文件格式是否正确。")
    except Exception as e:
        print(f"处理过程中发生未知错误: {e}")