import json
import os

# --- 默认值生成器 ---
# 这些函数现在会为所有三个位置生成正确的默认值格式

def get_default_save_data(data_type):
    """(用于 chip_graph) 生成 SaveData 字符串"""
    VECTOR_VAL = json.dumps({"x":0.0,"y":0.0,"z":0.0,"w":0.0,"magnitude":0.0,"sqrMagnitude":0.0})
    values = {1: None, 2: "0.0", 4: "", 8: VECTOR_VAL}
    
    value = values.get(data_type)
    if value is None and data_type == 1: return None
    return json.dumps({"DataValue": value}, separators=(',', ':')) if data_type in values else None

def get_default_serialized_value(data_type):
    """(用于 chip_inputs/outputs) 生成 SerializedValue 字符串"""
    VECTOR_OBJ = {"x":0.0,"y":0.0,"z":0.0,"w":0.0,"magnitude":0.0,"sqrMagnitude":0.0}
    values = {
        1: None,
        2: json.dumps({"Value":0.0,"Default":0.0,"Min":-3.40282347E+38,"Max":3.40282347E+38,"IsCheckbox":False}),
        4: json.dumps({"Value":"","Default":None,"MaxLength":2147483647}),
        8: json.dumps({"Value":VECTOR_OBJ,"Default":VECTOR_OBJ}) # Simplified based on common patterns
    }
    return values.get(data_type)

def get_default_gate_data(data_type):
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

def modify_chip_data_final(data_file_path, input_file_path, output_file_path):
    """
    读取、修改并保存芯片数据，完全同步所有相关部分。
    """
    print(f"正在读取主数据文件: {data_file_path}")
    with open(data_file_path, 'r', encoding='utf-8') as f:
        main_data = json.load(f)

    print(f"正在读取修改指令文件: {input_file_path}")
    with open(input_file_path, 'r', encoding='utf-8') as f:
        mod_instructions = json.load(f)

    connections_to_update = {}
    modification_made = False
    
    for container in main_data.get('saveObjectContainers', []):
        save_objects = container.get('saveObjects', {})
        meta_datas = save_objects.get('saveMetaDatas', [])
        mechanic_data_list = save_objects.get('mechanicData', [])

        if not meta_datas: continue

        print("\n--- 阶段 1: 分析并修改 chip_graph ---")
        for meta_data in meta_datas:
            if meta_data.get('key') == 'chip_graph':
                graph_string = meta_data.get('stringValue')
                if not graph_string: continue
                
                graph_data = json.loads(graph_string)
                for instruction in mod_instructions:
                    node_id, new_type = instruction['node_id'], instruction['new_data_type']
                    for node in graph_data.get('Nodes', []):
                        if node.get('Id') == node_id:
                            print(f"  -> 找到节点: {node_id}, 准备更新类型为 {new_type}")
                            node['GateDataType'] = new_type
                            
                            # 更新输出端口
                            if 'Outputs' in node:
                                for output in node['Outputs']: 
                                    output['DataType'] = new_type
                            
                            # ---【关键修复】---
                            # 新增: 更新输入端口
                            if 'Inputs' in node:
                                for input_port in node['Inputs']:
                                    input_port['DataType'] = new_type
                            # ---【修复结束】---

                            node['SaveData'] = get_default_save_data(new_type)
                            modification_made = True
                            conn_id = node.get('MechanicConnectionId')
                            if conn_id:
                                print(f"     发现外部连接 '{conn_id}'。将加入同步列表。")
                                connections_to_update[conn_id] = new_type
                            break
                meta_data['stringValue'] = json.dumps(graph_data, indent=2)
                break

        if not connections_to_update:
            print("\n警告: 未找到需要同步的外部连接。可能修改的是非IO节点。")
        
        # --- 阶段 2: 同步 chip_inputs 和 chip_outputs ---
        print("\n--- 阶段 2: 同步 chip_inputs / chip_outputs (编辑器UI) ---")
        for meta_data in meta_datas:
            if meta_data.get('key') in ['chip_inputs', 'chip_outputs']:
                key_name = meta_data['key']
                io_list_str = meta_data.get('stringValue')
                if not io_list_str: continue

                io_list = json.loads(io_list_str)
                for item in io_list:
                    if item.get('Key') in connections_to_update:
                        new_type = connections_to_update[item.get('Key')]
                        print(f"  -> 在 {key_name} 中更新 '{item.get('Key')}' 的类型为 {new_type}")
                        item['GateDataType'] = new_type
                        item['SerializedValue'] = get_default_serialized_value(new_type)
                        modification_made = True
                meta_data['stringValue'] = json.dumps(io_list, indent=2)

        # --- 阶段 3: 同步 mechanicSerializedInputs (核心运行时) ---
        print("\n--- 阶段 3: 同步 mechanicSerializedInputs (游戏运行时) ---")
        for mechanic_item in mechanic_data_list:
            mech_inputs_str = mechanic_item.get('mechanicSerializedInputs')
            if not mech_inputs_str: continue

            mech_inputs = json.loads(mech_inputs_str)
            for item in mech_inputs:
                if item.get('Key') in connections_to_update:
                    new_type = connections_to_update[item.get('Key')]
                    print(f"  -> 在 mechanicSerializedInputs 中更新 '{item.get('Key')}' 的类型为 {new_type}")
                    item['DataType'] = new_type
                    item['GateData'] = get_default_gate_data(new_type)
                    modification_made = True
            mechanic_item['mechanicSerializedInputs'] = json.dumps(mech_inputs)


    # --- 阶段 4: 保存结果 ---
    print("\n--- 阶段 4: 保存文件 ---")
    if modification_made:
        print(f"修改完成，正在保存到: {output_file_path}")
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, indent=4)
        print("文件已成功保存！")
    else:
        print("没有执行任何修改。")


# --- 程序主入口 ---
if __name__ == "__main__":
    data_json_path = 'data_modified_batch.json'
    input_json_path = 'input.json'
    output_json_path = 'Data_modified.json'

    if not os.path.exists(data_json_path) or not os.path.exists(input_json_path):
        print(f"错误: 请确保 '{data_json_path}' 和 '{input_json_path}' 文件与脚本在同一目录下。")
    else:
        modify_chip_data_final(data_json_path, input_json_path, output_json_path)