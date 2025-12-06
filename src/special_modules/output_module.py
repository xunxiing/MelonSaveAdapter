#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Output 节点的模块生成逻辑。
"""

from typing import Any, Dict


def build_output_module(node: Dict[str, Any], chip_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据 graph.json 中的 Output 节点，生成 batch_add_modules 期望的 dict：
        {"type": "output", "name": 自定义名称或友好名}
    """
    attrs = node.get("attrs", {}) or {}
    custom_name = attrs.get("name", chip_info.get("friendly_name", "Output"))
    return {"type": "output", "name": custom_name}


__all__ = ["build_output_module"]

