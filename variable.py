import json
import argparse
import os
import sys
import uuid # 必须引入 uuid 库来生成唯一的ID

# === 配置区域 ===

# 默认的变量属性
DEFAULT_SERIALIZED_VALUES = {
    "Number": {"Value": 0.0, "Default": 0.0, "Min": -3.40282347E+38, "Max": 3.40282347E+38, "IsCheckbox": False},
    "String": {"IsMultiline": False, "Value": "", "Default": None, "MaxLength": 2147483647},
    "Vector": {
        "Value": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0, "magnitude": 0.0, "sqrMagnitude": 0.0},
        "Default": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0, "magnitude": 0.0, "sqrMagnitude": 0.0},
        "MinVector": {"x": -3.40282347E+38, "y": -3.40282347E+38, "z": -3.40282347E+38, "w": -3.40282347E+38},
        "MaxVector": {"x": 3.40282347E+38, "y": 3.40282347E+38, "z": 3.40282347E+38, "w": 3.40282347E+38}
    },
    "Entity": None,
    "ArrayNumber": {"Value": [], "Default": []},
    "ArrayString": {"Value": [], "Default": []},
    "ArrayVector": {"Value": [], "Default": []},
    "ArrayEntity": {"Value": [], "Default": []}
}

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    print(f"[成功] 文件已保存至: {file_path}")

def find_meta_data(data, target_key):
    """查找 saveMetaDatas 中指定 key 的项目"""
    try:
        containers = data.get("saveObjectContainers", [])
        if not containers: return None, None
        save_objects = containers[0].get("saveObjects", {})
        meta_datas = save_objects.get("saveMetaDatas", [])
        
        for index, item in enumerate(meta_datas):
            if item.get("key") == target_key:
                return meta_datas, index
        return None, None
    except Exception:
        return None, None

def create_variable_definition(key, data_name, data_type):
    """创建变量定义 (在 chip_variables 中使用)"""
    default_val = DEFAULT_SERIALIZED_VALUES.get(data_type)
    serialized_str = json.dumps(default_val) if default_val is not None else None
        
    return {
        "Key": key,
        "DataName": data_name if data_name else f"#{key.capitalize()}",
        "SerializedValue": serialized_str,
        "IsSaveBetweenSession": False,
        "GateDataType": data_type
    }

def create_graph_node(var_key, data_type, pos_x=0.0, pos_y=0.0):
    """创建可视化节点对象 (在 chip_graph 中使用)"""
    
    # 1. 生成各种 UUID
    node_guid = str(uuid.uuid4())
    input_val_guid = str(uuid.uuid4())
    input_set_guid = str(uuid.uuid4())
    output_guid = str(uuid.uuid4())
    
    # 2. 构造复杂的 ID 字符串 (这是游戏识别节点的关键格式)
    # 格式通常是: VariableNodeViewModel : {GUID}
    node_id = f"VariableNodeViewModel : {node_guid}"
    
    # 输入端口 ID 格式: {NodeID}\nInput : {Type} {GUID}
    input_val_id = f"{node_id}\nInput : {data_type} {input_val_guid}"
    input_set_id = f"{node_id}\nInput : Number {input_set_guid}" # 第二个输入总是 Number (用于激活)
    
    # 输出端口 ID 格式: {NodeID}\nOutput : {Type} {GUID}
    output_id = f"{node_id}\nOutput : {data_type} {output_guid}"
    
    # 3. 组装节点对象
    new_node = {
        "Id": node_id,
        "ModelVersion": 2,
        "Version": "0.1",
        "OperationType": "Variable",
        "Inputs": [
            {
                "Id": input_val_id,
                "DataType": data_type,
                "connectedOutputIdModel": None
            },
            {
                "Id": input_set_id,
                "DataType": "Number", # Set 端口总是 Number
                "connectedOutputIdModel": None
            }
        ],
        "Outputs": [
            {
                "Id": output_id,
                "DataType": data_type,
                "ConnectedInputsIds": []
            }
        ],
        "VisualPosition": {"x": pos_x, "y": pos_y}, # 放置在画布的位置
        "VisualCollapsed": False,
        "MechanicConnectionId": var_key, # 关键：这里连接到变量定义
        "GateDataType": data_type,
        "SaveData": None
    }
    return new_node

def main():
    parser = argparse.ArgumentParser(description="自动添加变量并生成节点到画布")
    parser.add_argument("file", help="输入存档文件路径")
    parser.add_argument("--key", required=True, help="变量ID (例如: my_var)")
    parser.add_argument("--type", required=True, choices=DEFAULT_SERIALIZED_VALUES.keys(), help="变量类型")
    parser.add_argument("--name", help="显示名称", default=None)
    parser.add_argument("--x", type=float, default=0.0, help="画布 X 坐标")
    parser.add_argument("--y", type=float, default=0.0, help="画布 Y 坐标")
    
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"[错误] 文件未找到: {args.file}")
        sys.exit(1)

    data = load_json(args.file)
    
    # === 第一步：添加变量定义 (chip_variables) ===
    meta_datas, var_index = find_meta_data(data, "chip_variables")
    if meta_datas is None:
        print("[错误] 找不到 chip_variables")
        sys.exit(1)

    # 解析当前变量列表
    raw_var_str = meta_datas[var_index]["stringValue"]
    variables_list = json.loads(raw_var_str) if raw_var_str else []
    
    # 检查是否已存在
    if any(v["Key"] == args.key for v in variables_list):
        print(f"[警告] 变量定义的 Key '{args.key}' 已存在。")
        # 即使存在，我们也可以继续尝试添加节点(如果用户想补全节点的话)
    else:
        new_var_def = create_variable_definition(args.key, args.name, args.type)
        variables_list.append(new_var_def)
        # 保存回 stringValue
        meta_datas[var_index]["stringValue"] = json.dumps(variables_list)
        print(f"[1/2] 变量定义已添加: {args.key}")

    # === 第二步：在画布上生成节点 (chip_graph) ===
    meta_datas_graph, graph_index = find_meta_data(data, "chip_graph")
    if meta_datas_graph is None:
        print("[错误] 找不到 chip_graph")
        sys.exit(1)
        
    # 解析当前的图表数据
    raw_graph_str = meta_datas_graph[graph_index]["stringValue"]
    if not raw_graph_str:
        print("[错误] chip_graph 为空，无法添加节点")
        sys.exit(1)
        
    graph_data = json.loads(raw_graph_str)
    
    # 创建新节点
    new_node = create_graph_node(args.key, args.type, args.x, args.y)
    
    # 添加到 Nodes 列表
    if "Nodes" not in graph_data:
        graph_data["Nodes"] = []
    
    graph_data["Nodes"].append(new_node)
    
    # 保存回 stringValue
    meta_datas_graph[graph_index]["stringValue"] = json.dumps(graph_data)
    print(f"[2/2] 变量节点已生成于坐标 ({args.x}, {args.y})")

    # === 保存文件 ===
    save_json(data, args.file)

if __name__ == "__main__":
    main()