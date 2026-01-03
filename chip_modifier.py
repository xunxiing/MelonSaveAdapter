import json
import uuid
import re

# 新旧存档兼容：旧版 chip_graph 使用 int 类型码，新版使用字符串类型名
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


def _coerce_gate_type_value(data_type, *, use_string_schema: bool):
    if use_string_schema:
        if isinstance(data_type, int):
            return TYPE_INT_TO_STR.get(data_type, data_type)
        return data_type
    if isinstance(data_type, str) and data_type.strip() in TYPE_STR_TO_INT:
        return TYPE_STR_TO_INT[data_type.strip()]
    return data_type


def _gate_type_label(data_type, *, use_string_schema: bool) -> str:
    if use_string_schema:
        if isinstance(data_type, int):
            return TYPE_INT_TO_STR.get(data_type, "Number")
        if isinstance(data_type, str) and data_type.strip():
            return data_type.strip()
        return "Number"
    return "Number"

# --- 辅助函数 ---

def find_meta_data(meta_datas, key):
    """在 saveMetaDatas 数组中查找指定key的条目"""
    for item in meta_datas:
        if item.get("key") == key:
            return item
    # 如果找不到，就创建一个空的（这在处理非常基础的芯片时有用）
    new_item = {"key": key, "stringValue": "[]"}
    if key == "chip_graph":
        new_item["stringValue"] = '{"ValidationState":1,"Nodes":[]}'
    meta_datas.append(new_item)
    return new_item

def create_safe_key(name):
    """根据显示名称创建一个安全的内部Key"""
    # 转换为小写，用下划线替换空格和非字母数字字符
    s = name.lower()
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^a-z0-9_]', '', s)
    # 加上一个唯一后缀以防重名
    s += '_' + str(uuid.uuid4())[:4]
    return s

def add_node_to_graph(chip_graph_data, node_data, new_node_y_pos):
    """向图形中添加一个新节点并分配位置"""
    node_data["VisualPosition"] = {
        "x": 1000.0,  # 将新节点放在右侧较远的位置
        "y": new_node_y_pos,
    }
    node_data["VisualCollapsed"] = False
    # 保留调用方已经设置好的 ModelVersion / Version，避免覆盖 Variable 等特殊节点的版本号
    if "ModelVersion" not in node_data:
        node_data["ModelVersion"] = 1
    if "Version" not in node_data:
        node_data["Version"] = "0.1"
    chip_graph_data["Nodes"].append(node_data)
    return new_node_y_pos + 200 # 为下一个节点增加Y坐标，防止重叠

# --- 节点创建函数 ---

def create_input_node(name, data_type, *, use_string_schema: bool = False):
    """创建输入节点所需的所有数据结构"""
    key = create_safe_key(name)
    node_guid = str(uuid.uuid4())
    pin_guid = str(uuid.uuid4())
    gate_value = _coerce_gate_type_value(data_type, use_string_schema=use_string_schema)
    label = _gate_type_label(data_type, use_string_schema=use_string_schema)

    # 1. chip_inputs 的条目
    input_entry = {
      "Key": key,
      "DataName": f"#{name}",
      "SerializedValue": '{"Value":0.0,"Default":0.0,"Min":-3.40282347E+38,"Max":3.40282347E+38,"IsCheckbox":false}',
      "GateDataType": gate_value
    }

    # 2. chip_graph 的节点
    graph_node = {
      "Id": f"RootNodeViewModel : {node_guid}",
      "OperationType": "Root" if use_string_schema else 256,
      "Inputs": [],
      "Outputs": [
        {
          "Id": f"RootNodeViewModel : {node_guid}\nOutput : {label} {pin_guid}",
          "DataType": gate_value,
          "ConnectedInputsIds": []
        }
      ],
      "MechanicConnectionId": key, # 核心关联
      "GateDataType": gate_value,
      "SaveData": None
    }
    return input_entry, graph_node

def create_output_node(name, data_type, *, use_string_schema: bool = False):
    """创建输出节点所需的所有数据结构"""
    key = create_safe_key(name)
    node_guid = str(uuid.uuid4())
    pin_guid = str(uuid.uuid4())
    gate_value = _coerce_gate_type_value(data_type, use_string_schema=use_string_schema)
    label = _gate_type_label(data_type, use_string_schema=use_string_schema)
    
    # 1. chip_outputs 的条目
    output_entry = {
      "Key": key,
      "DataName": f"#{name}",
      "SerializedValue": '{"Value":0.0,"Default":0.0,"Min":-3.40282347E+38,"Max":3.40282347E+38,"IsCheckbox":false}',
      "GateDataType": gate_value
    }

    # 2. chip_graph 的节点
    graph_node = {
      "Id": f"ExitNodeViewModel : {node_guid}",
      "OperationType": "Exit" if use_string_schema else 512,
      "Inputs": [
        {
          "Id": f"ExitNodeViewModel : {node_guid}\nInput : {label} {pin_guid}",
          "DataType": gate_value,
          "connectedOutputIdModel": None
        }
      ],
      "Outputs": [],
      "MechanicConnectionId": key, # 核心关联
      "GateDataType": gate_value,
      "SaveData": None
    }
    return output_entry, graph_node

def create_constant_node(value, data_type, *, use_string_schema: bool = False):
    """创建常量节点所需的所有数据结构"""
    node_guid = str(uuid.uuid4())
    pin_guid = str(uuid.uuid4())
    gate_value = _coerce_gate_type_value(data_type, use_string_schema=use_string_schema)
    label = _gate_type_label(data_type, use_string_schema=use_string_schema)

    # SaveData 是一个被转义的JSON字符串
    save_data_inner_dict = {"DataValue": str(value)}
    save_data_string = json.dumps(save_data_inner_dict, separators=(',', ':'))

    graph_node = {
      "Id": f"ConstantNodeViewModel : {node_guid}",
      "OperationType": "Constant" if use_string_schema else 257,
      "Inputs": [],
      "Outputs": [
        {
          "Id": f"ConstantNodeViewModel : {node_guid}\nOutput : {label} {pin_guid}",
          "DataType": gate_value,
          "ConnectedInputsIds": []
        }
      ],
      "MechanicConnectionId": None, # 常量没有外部连接
      "GateDataType": gate_value,
      "SaveData": save_data_string
    }
    return graph_node


# --- 主处理函数 ---

def process_chip_file(chip_data, new_nodes_data):
    """主函数，负责读取、修改和整合数据"""
    try:
        # 定位到核心数据区域
        save_objects = chip_data["saveObjectContainers"][0]["saveObjects"]
        meta_datas = save_objects["saveMetaDatas"]

        # 1. 查找并解析现有的 inputs, outputs, 和 graph
        chip_inputs_meta = find_meta_data(meta_datas, "chip_inputs")
        chip_outputs_meta = find_meta_data(meta_datas, "chip_outputs")
        chip_graph_meta = find_meta_data(meta_datas, "chip_graph")

        chip_inputs_data = json.loads(chip_inputs_meta["stringValue"])
        chip_outputs_data = json.loads(chip_outputs_meta["stringValue"])
        chip_graph_data = json.loads(chip_graph_meta["stringValue"])
        existing_nodes = chip_graph_data.get("Nodes", []) or []
        use_string_schema = any(isinstance(n.get("OperationType"), str) for n in existing_nodes)

        # 2. 遍历新节点定义，并添加到相应的数据结构中
        y_pos_counter = 400.0 # 新节点的起始Y坐标，避免与现有节点重叠
        for node_def in new_nodes_data:
            node_type = node_def.get("type")
            data_type = node_def.get("dataType", 2) # 默认为2 (Number)

            if node_type == "input":
                name = node_def.get("name", "Unnamed Input")
                input_entry, graph_node = create_input_node(name, data_type, use_string_schema=use_string_schema)
                chip_inputs_data.append(input_entry)
                y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)
                
            elif node_type == "output":
                name = node_def.get("name", "Unnamed Output")
                output_entry, graph_node = create_output_node(name, data_type, use_string_schema=use_string_schema)
                chip_outputs_data.append(output_entry)
                y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)

            elif node_type == "constant":
                value = node_def.get("value", "0")
                graph_node = create_constant_node(value, data_type, use_string_schema=use_string_schema)
                y_pos_counter = add_node_to_graph(chip_graph_data, graph_node, y_pos_counter)

        # 3. 将更新后的Python对象重新序列化为JSON字符串
        # 注意：chip_graph 需要进行“双重”序列化
        chip_inputs_meta["stringValue"] = json.dumps(chip_inputs_data, separators=(',', ':'))
        chip_outputs_meta["stringValue"] = json.dumps(chip_outputs_data, separators=(',', ':'))
        chip_graph_meta["stringValue"] = json.dumps(chip_graph_data, separators=(',', ':')) # 这是最关键的一步，生成转义的JSON字符串

        return chip_data

    except (KeyError, IndexError) as e:
        print(f"错误: 输入的JSON文件结构不正确。缺少关键字段: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"错误: 解析JSON时出错。请检查文件格式: {e}")
        return None


# --- 执行入口 ---

if __name__ == "__main__":
    try:
        # 读取原始芯片文件
        with open("Data.json", "r", encoding="utf-8") as f:
            original_chip_data = json.load(f)

        # 读取新节点定义文件
        with open("new_nodes.json", "r", encoding="utf-8") as f:
            new_nodes_definitions = json.load(f)

        # 处理数据
        print("正在向芯片添加新模块...")
        modified_chip_data = process_chip_file(original_chip_data, new_nodes_definitions)

        # 如果处理成功，保存到新文件
        if modified_chip_data:
            with open("output.json", "w", encoding="utf-8") as f:
                # 使用 indent=4 使输出文件可读
                json.dump(modified_chip_data, f, indent=4)
            print("成功！已生成 'output.json' 文件。")
            print("你可以将 'output.json' 的内容复制或重命名为 .json 文件，然后在People Playground中生成它。")

    except FileNotFoundError as e:
        print(f"错误: 找不到文件 {e.filename}。请确保文件存在于脚本所在的同一目录中。")
