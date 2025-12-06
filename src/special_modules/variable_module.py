#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Variable 节点的模块生成逻辑。

从原 main.py 的 parse_graph_v2 中拆出，与其它逻辑解耦。
"""

from typing import Any, Dict, Set
import sys


def build_variable_module(
    node: Dict[str, Any],
    chip_info: Dict[str, Any],
    *,
    var_defs_by_key: Dict[str, Dict[str, Any]],
    var_key_for_node: Dict[str, str],
    var_instance_count: Dict[str, int],
    used_var_keys: Set[str],
) -> Dict[str, Any]:
    """
    为单个 VARIABLE 节点生成模块描述 dict：
        {"type": "variable", "key": ..., "gateDataType": ..., "value": ...}

    逻辑与原 main.py 中 parse_graph_v2 内对应分支保持一致：
    - 优先使用 var_key_for_node 提供的 Key
    - 若未推断出 Key，则从 var_defs_by_key 中找“尚未使用”的定义
    - 同一 Key 的第一个实例使用变量定义中的 Value 作为初始值，其余实例 value=None
    """
    nid = node["id"]
    var_key = var_key_for_node.get(nid)
    var_def = None

    if var_key is not None:
        var_def = var_defs_by_key.get(var_key)

    # 若无法从连线/属性中推断，则回退到“按顺序取尚未使用的定义”
    if var_def is None:
        fallback_key = None
        for k in var_defs_by_key.keys():
            if k not in used_var_keys:
                fallback_key = k
                break
        if fallback_key is None:
            sys.exit(
                "错误：DSL 中存在 VARIABLE 节点，但未找到足够、且可匹配的变量定义 "
                '(形如 {"Key": "...", "GateDataType": "...", "Value": ...})'
            )
        var_key = fallback_key
        var_def = var_defs_by_key[var_key]

    used_var_keys.add(var_key)

    # 同一个变量可以对应多个 VARIABLE 节点：
    #   - 第 1 个实例：使用变量定义中的 Value 作为初始值
    #   - 之后的实例：不再改动变量定义（value=None，避免覆盖）
    count = var_instance_count.get(var_key, 0)
    if count == 0:
        init_value = var_def.get("Value")
    else:
        init_value = None
    var_instance_count[var_key] = count + 1

    return {
        "type": "variable",
        "key": var_key,
        "gateDataType": var_def.get("GateDataType"),
        "value": init_value,
    }


def append_unused_variable_definitions(
    modules: list,
    var_defs_by_key: Dict[str, Dict[str, Any]],
    used_var_keys: Set[str],
) -> None:
    """
    对于“完全未被 VARIABLE 节点使用”的变量定义，为每个定义追加一个“孤立变量模块”。

    逻辑与原 main.py 中最后的 for k, var_def in var_defs_by_key.items() 保持一致。
    """
    for key, var_def in var_defs_by_key.items():
        if key in used_var_keys:
            continue
        modules.append(
            {
                "type": "variable",
                "key": var_def.get("Key"),
                "gateDataType": var_def.get("GateDataType"),
                "value": var_def.get("Value"),
            }
        )


__all__ = ["build_variable_module", "append_unused_variable_definitions"]

