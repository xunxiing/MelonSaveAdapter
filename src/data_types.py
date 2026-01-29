# -*- coding: utf-8 -*-
from enum import IntEnum, unique

@unique
class GateDataType(IntEnum):
    """
    游戏内部使用的数据类型枚举。
    对应 moduledef.json 或 datatype_map.json 中的 GateDataType 值。
    """
    Unknown = 0
    Entity = 1
    Number = 2
    String = 4
    Vector = 8
    # 数组类型通常是基础类型位移或特定值，需确认
    # 这里根据 add_module.py 中的定义
    ArrayNumber = 128
    ArrayString = 256
    ArrayVector = 512
    ArrayEntity = 1024

    @classmethod
    def from_string(cls, type_str: str) -> "GateDataType":
        """
        从字符串名称（如 "Number", "DECIMAL"）转换为枚举值。
        不区分大小写。
        """
        if not isinstance(type_str, str):
            return cls.Unknown
        
        s = type_str.strip().lower()
        if s in ("number", "decimal", "float", "int", "integer"):
            return cls.Number
        if s in ("string", "str", "text"):
            return cls.String
        if s in ("vector", "vec3", "vector3"):
            return cls.Vector
        if s in ("entity", "object", "gameobject", "signal"):
            return cls.Entity
        if s in ("arraynumber", "list[number]", "number[]"):
            return cls.ArrayNumber
        if s in ("arraystring", "list[string]", "string[]"):
            return cls.ArrayString
        if s in ("arrayvector", "list[vector]", "vector[]"):
            return cls.ArrayVector
        if s in ("arrayentity", "list[entity]", "entity[]"):
            return cls.ArrayEntity
            
        return cls.Unknown

    @classmethod
    def to_serialized_key(cls, val: int) -> str | None:
        """
        获取对应的 DEFAULT_SERIALIZED_VALUES 键名（如 "Number"）。
        用于查找默认值模板。
        """
        mapping = {
            cls.Number: "Number",
            cls.String: "String",
            cls.Vector: "Vector",
            cls.Entity: "Entity",
            cls.ArrayNumber: "ArrayNumber",
            cls.ArrayString: "ArrayString",
            cls.ArrayVector: "ArrayVector",
            cls.ArrayEntity: "ArrayEntity"
        }
        return mapping.get(val)
