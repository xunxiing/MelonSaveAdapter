#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.special_modules
===================
针对 DSL / graph 中“有特殊需求”的节点类型，提供独立的处理模块。

目前支持的特殊类型：
- input
- output
- constant
- variable
"""

from .input_module import build_input_module
from .output_module import build_output_module
from .constant_module import build_constant_module
from .variable_module import build_variable_module, append_unused_variable_definitions

from typing import Any, Dict, List, Set


def build_special_module(
    node_type_lower: str,
    node: Dict[str, Any],
    chip_info: Dict[str, Any],
    *,
    var_defs_by_key: Dict[str, Dict[str, Any]] | None = None,
    var_key_for_node: Dict[str, str] | None = None,
    var_instance_count: Dict[str, int] | None = None,
    used_var_keys: Set[str] | None = None,
) -> Any:
    """
    调度函数：根据节点类型调用对应的特殊模块构造函数。

    返回值会被直接 append 到 modules 列表中，结构需与原 main.py 中保持一致：
    - input/output/constant: {"type": "...", "name": "..."}
    - variable: {"type": "variable", "key": "...", "gateDataType": "...", "value": ...}
    """
    t = node_type_lower
    if t == "input":
        return build_input_module(node, chip_info)
    if t == "output":
        return build_output_module(node, chip_info)
    if t == "constant":
        return build_constant_module(node, chip_info)
    if t == "variable":
        if (
            var_defs_by_key is None
            or var_key_for_node is None
            or var_instance_count is None
            or used_var_keys is None
        ):
            raise ValueError("variable 模块构建需要提供变量相关上下文参数")
        return build_variable_module(
            node=node,
            chip_info=chip_info,
            var_defs_by_key=var_defs_by_key,
            var_key_for_node=var_key_for_node,
            var_instance_count=var_instance_count,
            used_var_keys=used_var_keys,
        )
    raise KeyError(f"未注册的特殊模块类型: {node_type_lower}")


__all__ = [
    "build_special_module",
    "append_unused_variable_definitions",
]

