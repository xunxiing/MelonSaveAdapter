import json
import uuid
import sys

# --- 配置 ---

# 模块类型名 -> 游戏内部数据类型代码的映射
# 根据您的要求进行了更新和扩展
DATA_TYPE_MAP = {
    "Entity": 1,
    "Number": 2,
    "String": 4,  # 已根据您的要求更新
    "Vector": 8,
    # "Bool": 4, # 如果需要，可以取消注释
}

# 模块存档名 -> 游戏内部操作类型代码的映射
# 这是个关键信息，需要根据游戏数据进行补充
# 我根据您提供的例子预填了一部分
OPERATION_TYPE_MAP = {
    "ConstantNodeViewModel": 257,
    "TimeNodeViewModel": 260,
    "IdentityNodeViewModel": 1,
    "AbsNodeViewModel": 2324,
    "AddNumbersNodeViewModel": 2304,
    "AverageNumberNodeViewModel": 2309,
    "CeilNodeViewModel": 2310,
    "ClampValueNodeViewModel": 2311,
    "Clamp01NodeViewModel": 2312,
    "DivideNodeViewModel": 2307,
    "ExpNodeViewModel": 2308,
    "ENodeViewModel": 259,
    "ExpPowNumberNodeViewModel": 2314,
    "NegateNodeViewModel": 2315,
    "PercentNumberNodeViewModel": 2316,
    "PiNodeViewModel": 258,
    "RandomNodeViewModel": 261,
    "RoundNodeViewModel": 2326,
    "SignNodeViewModel": 2318,
    "SqrNodeViewModel": 2321,
    "SqrtNodeViewModel": 2322,
    "SubtractNumbersNodeViewModel": 2305,
    "FloorNodeViewModel": 2319,
    "InverseNodeViewModel": 2320,
    "LerpNodeViewModel": 2328,
    "LogNumberNodeViewModel": 2323,
    "RemainderNumberNodeViewModel": 2327,
    "MultiplyNumbersNodeViewModel": 2306,
    "PowNumberNodeViewModel": 2325,
    "DeltaAngleNodeViewModel": 2059,
    "AcosNodeViewModel": 2052,
    "AsinNodeViewModel": 2051,
    "AtanNodeViewModel": 2054,
    "ArcCTanNodeViewModel": 2056,
    "CosNodeViewModel": 2050,
    "SinNodeViewModel": 2049,
    "TanNodeViewModel": 2053,
    "CTanNodeViewModel": 2055,
    "DegToRadSameNodeViewModel": 2057,
    "RadToDegSameNodeViewModel": 2058,
    "CosineFormulaSideNodeViewModel": 2060,
    "CosineFormulaAngleNodeViewModel": 2061,
    "PythagoreanCathetusNodeViewModel": 2062,
    "PythagoreanSideNodeViewModel": 2063,
    "AndNodeViewModel": 2560,
    "BranchNodeViewModel": 2567,
    "OrNodeViewModel": 2561,
    "NotAndNodeViewModel": 2562,
    "NotOrNodeViewModel": 2563,
    "NotSameNodeViewModel": 2564,
    "XorNodeViewModel": 2565,
    "NotXorNodeViewModel": 2566,
    "EqualNodeViewModel": 2816,
    "NotEqualNodeViewModel": 2817,
    "GreaterOrEqualNodeViewModel": 2818,
    "GreaterNodeViewModel": 2820,
    "LessOrEqualNodeViewModel": 2819,
    "LessNodeViewModel": 2821,
    "InRangeExclusiveNodeViewModel": 2823,
    "InRangeInclusiveNodeViewModel": 2822,
    "BitAndNodeViewModel": 3073,
    "BitNotNodeViewModel": 3074,
    "BitOrNodeViewModel": 3075,
    "BitXorNodeViewModel": 3076,
    "BitShiftLeftNodeViewModel": 3077,
    "BitShiftRightNodeViewModel": 3078,
    "BitRotateLeftNodeViewModel": 3079,
    "BitRotateRightNodeViewModel": 3080,
    "MinNumbersNodeViewModel": 3081,
    "MaxNumbersNodeViewModel": 3082,
    "ClampIntValueNodeViewModel": 3083,
    "AbsIntNodeViewModel": 3084,
    "SignIntNodeViewModel": 3085,
    "IncrementNodeViewModel": 3086,
    "DecrementNodeViewModel": 3087,
    "NegateIntNodeViewModel": 3088,
    "SqrIntNodeViewModel": 3089,
    "SqrtIntNodeViewModel": 3090,
    "RandomIntNodeViewModel": 3091,
    "ModuloNodeViewModel": 3092,
    "PercentIntNumberNodeViewModel": 3093,
    "IsPowerOfTwoNodeViewModel": 3094,
    "NextPowerOfTwoNodeViewModel": 3095,
    "PreviousPowerOfTwoNodeViewModel": 3096,
    "DeltaIntNodeViewModel": 3097,
    "AverageIntNodeViewModel": 3098,
    "MedianIntNodeViewModel": 3099,
    "ModeIntNodeViewModel": 3100,
    "VarianceIntNodeViewModel": 3101,
    "StdDevIntNodeViewModel": 3102,
    "SkewnessIntNodeViewModel": 3103,
    "KurtosisIntNodeViewModel": 3104,
    "CorrelationIntNodeViewModel": 3105,
    "CovarianceIntNodeViewModel": 3106,
    "MinFloatNodeViewModel": 3107,
    "MaxFloatNodeViewModel": 3108,
    "ClampFloatNodeViewModel": 3109,
    "AbsFloatNodeViewModel": 3110,
    "SignFloatNodeViewModel": 3111,
    "IncrementFloatNodeViewModel": 3112,
    "DecrementFloatNodeViewModel": 3113,
    "NegateFloatNodeViewModel": 3114,
    "SqrFloatNodeViewModel": 3115,
    "SqrtFloatNodeViewModel": 3116,
    "RandomFloatNodeViewModel": 3117,
    "ModuloFloatNodeViewModel": 3118,
    "PercentFloatNumberNodeViewModel": 3119,
    "IsEvenNodeViewModel": 3120,
    "IsOddNodeViewModel": 3121,
    "IsPrimeNodeViewModel": 3122,
    "IsCompositeNodeViewModel": 3123,
    "FactorialNodeViewModel": 3124,
    "PermutationNodeViewModel": 3125,
    "CombinationNodeViewModel": 3126,
    "GammaNodeViewModel": 3127,
    "BetaNodeViewModel": 3128,
    "LogGammaNodeViewModel": 3129,
    "DigammaNodeViewModel": 3130,
    "TrigammaNodeViewModel": 3131,
    "TetragammaNodeViewModel": 3132,
    "PentagammaNodeViewModel": 3133,
    "HexagammaNodeViewModel": 3134,
    "LogBetaNodeViewModel": 3135,
    "DirichletNodeViewModel": 3136,
    "ZetaNodeViewModel": 3137,
    "PolyGammaNodeViewModel": 3138,
    "BernoulliNodeViewModel": 3139,
    "EulerNodeViewModel": 3140,
    "StirlingNodeViewModel": 3141,
    "BellNodeViewModel": 3142,
    "CatalanNodeViewModel": 3143,
    "FibonacciNodeViewModel": 3144,
    "CollisionEntityNodeViewModel": 1574,
    "DeleteEntityNodeViewModel": 1577,
    "FindStringNodeViewModel": 3586,
    "LengthStringNodeViewModel": 3587,
    "LowercaseStringNodeViewModel": 3588,
    "UppercaseStringNodeViewModel": 3589,
    "ReverseStringNodeViewModel": 3590,
    "RepeatStringNodeViewModel": 3591,
    "ReplaceStringNodeViewModel": 3592,
    "SubstringNodeViewModel": 3593,
    "TrimStringNodeViewModel": 3594,
    "ToStringNodeViewModel": 3595,
    "SymbolToAsciiNumberNodeViewModel": 3596,
    "StickerNodeViewModel": 5,
    "MagnitudeVectorNodeViewModel": 1283,
    "VectorDotProductNodeViewModel": 1288,
}

# 新节点在编辑器中的垂直间距
Y_SPACING = 200
DEFAULT_X_POS = -120.0

# --- 核心功能 ---

def create_new_node(module_name, module_info, existing_nodes, datatype_map):
    """根据模块信息，创建一个新的、带有唯一ID的节点字典"""
    
    # 1. 检查 OperationType 是否已知
    if module_name not in OPERATION_TYPE_MAP:
        print(f"错误: 模块 '{module_name}' 的 OperationType 未知。")
        print("请在脚本的 OPERATION_TYPE_MAP 字典中添加它。")
        return None
        
    op_type_code = OPERATION_TYPE_MAP[module_name]

    # 2. 生成唯一的节点ID
    node_id = f"{module_name} : {uuid.uuid4()}"
    print(f"为新节点生成ID: {node_id}")

    # 3. 创建输入端口
    inputs = []
    for input_type in module_info.get("inputs", []):
        port_id = f"{node_id}\\nInput : {input_type} {uuid.uuid4()}"
        inputs.append({
            "Id": port_id,
            "DataType": DATA_TYPE_MAP.get(input_type, 0),
            "connectedOutputIdModel": None
        })

    # 4. 创建输出端口
    outputs = []
    for output_type in module_info.get("outputs", []):
        port_id = f"{node_id}\\nOutput : {output_type} {uuid.uuid4()}"
        outputs.append({
            "Id": port_id,
            "DataType": DATA_TYPE_MAP.get(output_type, 0),
            "ConnectedInputsIds": []
        })
        
    # 5. 计算新节点的位置，避免重叠
    max_y = -float('inf')
    if not existing_nodes:
        max_y = 0 # 如果没有节点，从0开始
    else:
        for node in existing_nodes:
            y_pos = node.get("VisualPosition", {}).get("y", 0)
            if y_pos > max_y:
                max_y = y_pos
    
    new_y = max_y + Y_SPACING if existing_nodes else 180.0
    new_position = {
        "x": DEFAULT_X_POS,
        "y": new_y,
        "normalized": {"x": 0.0, "y": 0.0, "magnitude": 0.0, "sqrMagnitude": 0.0},
        "magnitude": 0.0,
        "sqrMagnitude": 0.0
    }

    # 6. 【核心修改】从 datatype_map.json 中查找 GateDataType
    gate_data_type = 2 # 默认值
    op_type_code_str = str(op_type_code)
    if op_type_code_str in datatype_map:
        gate_data_type = datatype_map[op_type_code_str].get("GateDataType", 2)
    else:
        print(f"警告: 在 datatype_map.json 中未找到 OperationType '{op_type_code_str}'。GateDataType 将默认为 {gate_data_type}。")


    # 7. 组装完整的节点对象
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
        "GateDataType": gate_data_type, # 使用从map中查找到的值
        "SaveData": None
    }
    
    return new_node

def main():
    """主执行函数"""
    try:
        # 加载文件
        with open('data.json', 'r', encoding='utf-8') as f:
            game_data = json.load(f)
        with open('allmod.json', 'r', encoding='utf-8') as f:
            all_modules = json.load(f)
        # 【新增】加载 datatype_map.json
        with open('datatype_map.json', 'r', encoding='utf-8') as f:
            datatype_map = json.load(f)
    except FileNotFoundError as e:
        print(f"错误: 找不到文件 {e.filename}。请确保 data.json, allmod.json 和 datatype_map.json 文件与脚本在同一目录下。")
        return
    except json.JSONDecodeError as e:
        print(f"错误: JSON文件格式不正确 - {e}")
        return

    # 获取用户输入
    print("可用模块 (存档名):")
    for name in all_modules.keys():
        print(f"- {name}")
    module_to_add = input("\n请输入要添加的模块的准确存档名: ")

    if module_to_add not in all_modules:
        print(f"错误: 在 allmod.json 中找不到名为 '{module_to_add}' 的模块。")
        return

    module_info = all_modules[module_to_add]
    
    # 定位 chip_graph
    chip_graph_meta = None
    for container in game_data.get("saveObjectContainers", []):
        for meta in container.get("saveObjects", {}).get("saveMetaDatas", []):
            if meta.get("key") == "chip_graph":
                chip_graph_meta = meta
                break
        if chip_graph_meta:
            break

    if not chip_graph_meta:
        print("错误: 在 data.json 中找不到 'chip_graph'。请检查文件是否为包含芯片的存档。")
        return

    # 解析 chip_graph 字符串
    chip_graph_data = json.loads(chip_graph_meta["stringValue"])
    
    # 创建新节点，【新增】传入 datatype_map
    new_node = create_new_node(module_to_add, module_info, chip_graph_data["Nodes"], datatype_map)

    if new_node is None:
        # 创建节点时发生错误，终止执行
        return

    # 将新节点添加到图中
    chip_graph_data["Nodes"].append(new_node)
    
    # 将修改后的图转换回JSON字符串，并更新到主数据结构中
    chip_graph_meta["stringValue"] = json.dumps(chip_graph_data, indent=2)

    # 保存到新文件
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