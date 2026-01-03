#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
带常量去重功能的转换器
在DSL解析阶段就避免创建重复的常量节点
"""

import json
from typing import Any, Dict

from src.converter.logical_converter import LogicalConverter


class DedupConverter(LogicalConverter):
    """
    扩展 LogicalConverter，添加常量节点去重功能。
    相同值的常量节点只会被创建一次，后续引用会复用已存在的节点。
    """

    def __init__(self) -> None:
        super().__init__()
        # 常量值到节点ID的映射表
        # 使用 JSON 序列化作为 key，确保不同类型的值不会冲突
        self._constant_cache: Dict[str, str] = {}

    def _emit_constant_node(self, lit: Any) -> str:
        """
        创建常量节点，如果相同值的常量已存在则复用。

        Args:
            lit: 常量值，可以是 int, float, str, dict (vector) 等

        Returns:
            常量节点的 ID
        """
        # 生成常量的唯一标识符
        # 使用 JSON 序列化确保不同类型的值不会冲突
        # 例如：1 (int) vs "1" (str) vs True (bool)
        try:
            cache_key = json.dumps(lit, sort_keys=True, ensure_ascii=False)
        except Exception:
            # 如果序列化失败，使用字符串表示作为 fallback
            cache_key = str(lit)

        # 检查缓存中是否已存在相同值的常量
        if cache_key in self._constant_cache:
            existing_nid = self._constant_cache[cache_key]
            # 确保节点确实存在
            if any(node.get("id") == existing_nid for node in self.g.nodes):
                return existing_nid

        # 创建新的常量节点
        nid = super()._emit_constant_node(lit)

        # 将新节点加入缓存
        self._constant_cache[cache_key] = nid

        return nid


__all__ = ["DedupConverter"]
