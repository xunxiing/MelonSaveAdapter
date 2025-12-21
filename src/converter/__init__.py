#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.converter
=============

DSL(AST) -> graph.json 的转换实现（从旧版 converter_v2.py 拆分出来）。
"""

from src.converter.api import convert_dsl_to_graph

__all__ = ["convert_dsl_to_graph"]

