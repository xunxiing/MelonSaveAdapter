import json
import argparse
import os
import sys
import uuid # 必须引入 uuid 库来生成唯一的ID

# 引入核心管理器
try:
    from src.variable_manager import VariableManager
except ImportError:
    # 尝试添加当前目录到 sys.path (用于独立运行时)
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from src.variable_manager import VariableManager
    except ImportError:
        print("[错误] 无法导入 src.variable_manager。请确保 src 目录完整。")
        sys.exit(1)

# === 配置区域 ===

# 为了兼容旧代码引用，保留引用但指向 Manager
DEFAULT_SERIALIZED_VALUES = VariableManager.DEFAULT_SERIALIZED_VALUES

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

def create_variable_definition(key, data_name, data_type, *, use_string_schema: bool):
    """
    创建变量定义 (在 chip_variables 中使用)。
    现在委托给 VariableManager，并根据存档 schema 输出 GateDataType(int/str)。
    """
    return VariableManager.create_definition(
        key,
        data_type,
        data_name=data_name,
        use_string_schema=use_string_schema,
    )

def create_graph_node(var_key, data_type, pos_x=0.0, pos_y=0.0, *, use_string_schema: bool):
    """
    创建可视化节点对象 (在 chip_graph 中使用)。
    现在委托给 VariableManager，并根据存档 schema 输出 DataType(int/str)。
    """
    return VariableManager.create_node(
        var_key,
        data_type,
        {"x": pos_x, "y": pos_y},
        use_string_schema=use_string_schema,
    )


def detect_string_schema(nodes: list) -> bool:
    """
    判断当前 chip_graph 使用的 schema：
    - 旧版：OperationType/GateDataType/DataType 多为 int
    - 新版：以上字段可能为 str

    注意：VariableNodeViewModel 往往天然是 OperationType="Variable"(str)，单靠它可能误判。
    """
    # 第一轮：忽略 Variable 节点（避免误判）
    saw_non_variable = False
    for n in nodes or []:
        op = n.get("OperationType")
        if isinstance(op, str) and op.strip().lower() == "variable":
            continue
        saw_non_variable = True
        if isinstance(op, str) or isinstance(n.get("GateDataType"), str):
            return True
        for p in (n.get("Inputs") or []) + (n.get("Outputs") or []):
            if isinstance(p.get("DataType"), str):
                return True

    # 第二轮：如果图里只有 Variable 节点，则用它作为兜底判断
    if not saw_non_variable:
        for n in nodes or []:
            if isinstance(n.get("GateDataType"), str):
                return True
            for p in (n.get("Inputs") or []) + (n.get("Outputs") or []):
                if isinstance(p.get("DataType"), str):
                    return True

    return False

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
    # Variable 节点/定义在很多存档里天然使用 string schema（即使整体 chip_graph 仍是旧版 int schema）。
    # 这里固定用 string schema，避免插入变量后游戏侧解析失败。
    use_string_schema = True

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
        new_var_def = create_variable_definition(
            args.key,
            args.name,
            args.type,
            use_string_schema=use_string_schema,
        )
        variables_list.append(new_var_def)
        # 保存回 stringValue
        meta_datas[var_index]["stringValue"] = json.dumps(variables_list)
        print(f"[1/2] 变量定义已添加: {args.key}")

    # 创建新节点
    new_node = create_graph_node(
        args.key,
        args.type,
        args.x,
        args.y,
        use_string_schema=use_string_schema,
    )
    
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
