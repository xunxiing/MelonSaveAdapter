#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Constant 节点的模块生成逻辑。
"""

from typing import Any, Dict


def build_constant_module(node: Dict[str, Any], chip_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据 graph.json 中的 Constant 节点，生成 batch_add_modules 期望的 dict：
        {"type": "constant", "name": 自定义名称或友好名}

    dataType / value 等后续会在数据类型修改与常量修改阶段处理，
    这里保持与原 main.py 一致，仅关注名称。
    """
    attrs = node.get("attrs", {}) or {}
    custom_name = attrs.get("name", chip_info.get("friendly_name", "Constant"))
    return {"type": "constant", "name": custom_name}


__all__ = ["build_constant_module"]

