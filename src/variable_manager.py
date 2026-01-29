# -*- coding: utf-8 -*-
import json
import uuid
import copy
from typing import Any, Dict, List, Optional, Union

from src.data_types import GateDataType

class VariableManager:
    """
    负责处理游戏内的 Variable 模块：
    1. 定义 (Definition): 存储在 chip_variables 中，相当于声明变量。
    2. 节点 (Node): 存储在 chip_graph 中，相当于变量的读写接口。
    """

    # 默认序列化值模板
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

    @staticmethod
    def create_definition(
        key: str,
        type_str_or_int: Union[str, int],
        init_value: Any = None,
        *,
        data_name: str | None = None,
        use_string_schema: bool = False,
    ) -> Dict[str, Any]:
        """
        创建一个变量定义对象 (用于添加到 chip_variables)。
        
        Args:
            key: 变量唯一标识符
            type_str_or_int: 类型字符串 ("Number", "String"...) 或整数枚举值
            init_value: 初始值 (Python 原生类型)，用于覆盖默认值
        """
        # 1. 解析类型
        if isinstance(type_str_or_int, int):
            gate_type_enum = GateDataType(type_str_or_int)
        else:
            gate_type_enum = GateDataType.from_string(str(type_str_or_int))
            
        if gate_type_enum == GateDataType.Unknown:
            # 默认回退到 Number
            gate_type_enum = GateDataType.Number
            
        # 2. 获取模板键名 (用于查找默认 JSON 结构)
        template_key = GateDataType.to_serialized_key(gate_type_enum) or "Number"
        
        # 3. 构建 SerializedValue
        serialized_str = VariableManager._build_serialized_value(template_key, init_value)

        display = (data_name or key.capitalize()).strip()
        if display and not display.startswith("#"):
            display = f"#{display}"
        if not display:
            display = f"#{key.capitalize()}"

        if use_string_schema:
            gate_type_value: object = GateDataType.to_serialized_key(gate_type_enum) or "Number"
        else:
            gate_type_value = int(gate_type_enum)

        return {
            "Key": key,
            "DataName": display,
            "SerializedValue": serialized_str,
            "IsSaveBetweenSession": False,
            "GateDataType": gate_type_value,
        }

    @staticmethod
    def create_node(
        key: str,
        type_str_or_int: Union[str, int],
        pos: Dict[str, float],
        *,
        use_string_schema: bool = False,
    ) -> Dict[str, Any]:
        """
        创建一个变量节点对象 (用于添加到 chip_graph)。
        """
        # 1. 解析类型
        if isinstance(type_str_or_int, int):
            gate_type_enum = GateDataType(type_str_or_int)
        else:
            gate_type_enum = GateDataType.from_string(str(type_str_or_int))
            
        if gate_type_enum == GateDataType.Unknown:
            gate_type_enum = GateDataType.Number

        gate_type_int = int(gate_type_enum)
        gate_type_str = GateDataType.to_serialized_key(gate_type_enum) or "Number"

        gate_type_value: object = gate_type_str if use_string_schema else gate_type_int
        set_type_value: object = "Number" if use_string_schema else int(GateDataType.Number)
        # 端口 ID 中的类型 token 在旧版/新版存档里通常都是类型名字符串（例如 "Number"），
        # 即使 DataType 本身是 int（旧版 schema）。
        port_id_type_token: object = gate_type_str
        
        # 2. 生成各种 UUID
        node_guid = str(uuid.uuid4())
        input_val_guid = str(uuid.uuid4())
        input_set_guid = str(uuid.uuid4())
        output_guid = str(uuid.uuid4())
        
        node_id = f"VariableNodeViewModel : {node_guid}"
        
        # 3. 构建节点结构
        # Variable 节点的端口 DataType 通常也是 int
        # Input 0: Value (读取/写入值) - 类型随变量
        # Input 1: Set (触发写入) - 类型总是 Number (2)
        # Output 0: Value (输出当前值) - 类型随变量
        
        return {
            "Id": node_id,
            "ModelVersion": 2,
            "Version": "0.1",
            "OperationType": "Variable", # Variable 节点的 OperationType 特殊，通常是字符串 "Variable"
            "Inputs": [
                {
                    "Id": f"{node_id}\nInput : {port_id_type_token} {input_val_guid}",
                    "DataType": gate_type_value,
                    "connectedOutputIdModel": None
                },
                {
                    "Id": f"{node_id}\nInput : Number {input_set_guid}",
                    "DataType": set_type_value,
                    "connectedOutputIdModel": None
                }
            ],
            "Outputs": [
                {
                    "Id": f"{node_id}\nOutput : {port_id_type_token} {output_guid}",
                    "DataType": gate_type_value,
                    "ConnectedInputsIds": []
                }
            ],
            "VisualPosition": {"x": pos.get("x", 0.0), "y": pos.get("y", 0.0)},
            "VisualCollapsed": False,
            "MechanicConnectionId": key,
            "GateDataType": gate_type_value,
            "SaveData": None
        }

    @staticmethod
    def _build_serialized_value(template_key: str, value: Any) -> Optional[str]:
        """根据模板和给定的值生成 JSON 字符串"""
        base = VariableManager.DEFAULT_SERIALIZED_VALUES.get(template_key)
        if base is None:
            return None
            
        if value is None:
            # 使用默认值
            return json.dumps(base)
            
        payload = copy.deepcopy(base)
        
        # 根据不同类型填充 Value 和 Default
        try:
            if template_key == "Number":
                v = float(value)
                payload["Value"] = v
                payload["Default"] = v
            elif template_key == "String":
                s = str(value)
                payload["Value"] = s
                payload["Default"] = s
            elif template_key == "Vector":
                if isinstance(value, dict):
                    for k in ("x", "y", "z", "w"):
                        if k in value:
                            payload["Value"][k] = float(value[k])
                            payload["Default"][k] = float(value[k])
            elif template_key.startswith("Array"):
                if isinstance(value, list):
                    # 简单处理数组，这里假设 value 已经是合适的格式
                    payload["Value"] = value
                    payload["Default"] = value
        except Exception:
            # 如果转换失败，返回默认值
            pass
            
        return json.dumps(payload, separators=(",", ":"))
