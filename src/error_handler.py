#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.error_handler
=================

统一的错误处理模块，提供带模块上下文的错误信息。

功能：
1. 定义自定义异常类，包含模块信息
2. 提供错误格式化工具
3. 支持错误链追踪
"""

from __future__ import annotations

import sys
import traceback
from enum import Enum
from typing import Any, Optional


class ErrorModule(Enum):
    """错误来源模块枚举"""
    
    # DSL 转换相关
    DSL_PARSER = "DSL解析器"
    AST_CONVERTER = "AST转换器"
    GRAPH_BUILDER = "图构建器"
    
    # Pipeline 阶段
    PIPELINE = "流水线"
    MODULE_ADDER = "模块添加器"
    CONNECTOR = "连线器"
    LAYOUT_ENGINE = "布局引擎"
    ARCHIVE_CREATOR = "归档创建器"
    
    # 数据处理
    TYPE_INFERENCE = "类型推断"
    CONSTANT_MODIFIER = "常量修改器"
    DATA_TYPE_MODIFIER = "数据类型修改器"
    
    # 特殊模块
    SPECIAL_MODULE = "特殊模块处理器"
    VARIABLE_HANDLER = "变量处理器"
    
    # 工具类
    FUZZY_MATCHER = "模糊匹配器"
    UTILS = "工具函数"
    
    # 文件 I/O
    FILE_IO = "文件读写"
    
    # 通用
    UNKNOWN = "未知模块"


class ChipSynthesisError(Exception):
    """
    基础异常类，所有自定义异常的父类。
    
    属性：
        message: 错误消息
        module: 错误来源模块
        context: 错误上下文信息（如节点ID、行号等）
        original_error: 原始异常（如果有）
    """
    
    def __init__(
        self,
        message: str,
        module: ErrorModule = ErrorModule.UNKNOWN,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.module = module
        self.context = context or {}
        self.original_error = original_error
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """格式化错误消息，包含模块信息"""
        parts = [f"[{self.module.value}]"]
        
        # 添加上下文信息
        if self.context:
            context_parts = []
            if "node_id" in self.context:
                context_parts.append(f"节点: {self.context['node_id']}")
            if "node_type" in self.context:
                context_parts.append(f"类型: {self.context['node_type']}")
            if "line" in self.context:
                context_parts.append(f"行号: {self.context['line']}")
            if "file" in self.context:
                context_parts.append(f"文件: {self.context['file']}")
            if "port" in self.context:
                context_parts.append(f"端口: {self.context['port']}")
            if "variable" in self.context:
                context_parts.append(f"变量: {self.context['variable']}")
            
            if context_parts:
                parts.append("(".join(context_parts) + ")")
        
        parts.append(self.message)
        return " ".join(parts)
    
    def __str__(self) -> str:
        return self._format_message()


class DSLError(ChipSynthesisError):
    """DSL 相关错误"""
    
    def __init__(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            module=ErrorModule.DSL_PARSER,
            context=context,
            original_error=original_error
        )


class ASTError(ChipSynthesisError):
    """AST 转换错误"""
    
    def __init__(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            module=ErrorModule.AST_CONVERTER,
            context=context,
            original_error=original_error
        )


class GraphError(ChipSynthesisError):
    """图构建错误"""
    
    def __init__(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            module=ErrorModule.GRAPH_BUILDER,
            context=context,
            original_error=original_error
        )


class PipelineError(ChipSynthesisError):
    """流水线执行错误"""
    
    def __init__(
        self,
        message: str,
        stage: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        if context is None:
            context = {}
        if stage:
            context["stage"] = stage
        super().__init__(
            message=message,
            module=ErrorModule.PIPELINE,
            context=context,
            original_error=original_error
        )


class ModuleAddError(ChipSynthesisError):
    """模块添加错误"""
    
    def __init__(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            module=ErrorModule.MODULE_ADDER,
            context=context,
            original_error=original_error
        )


class ConnectionError(ChipSynthesisError):
    """连线错误"""
    
    def __init__(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            module=ErrorModule.CONNECTOR,
            context=context,
            original_error=original_error
        )


class TypeInferenceError(ChipSynthesisError):
    """类型推断错误"""
    
    def __init__(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            module=ErrorModule.TYPE_INFERENCE,
            context=context,
            original_error=original_error
        )


class FileIOError(ChipSynthesisError):
    """文件读写错误"""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        if context is None:
            context = {}
        if file_path:
            context["file"] = file_path
        super().__init__(
            message=message,
            module=ErrorModule.FILE_IO,
            context=context,
            original_error=original_error
        )


def format_error_trace(error: Exception) -> str:
    """
    格式化错误追踪信息，包含完整的调用栈。
    
    Args:
        error: 异常对象
        
    Returns:
        格式化后的错误信息字符串
    """
    lines = []
    lines.append("=" * 60)
    lines.append(f"错误类型: {type(error).__name__}")
    
    if isinstance(error, ChipSynthesisError):
        lines.append(f"错误消息: {error.message}")
        lines.append(f"来源模块: {error.module.value}")
        if error.context:
            lines.append("上下文信息:")
            for key, value in error.context.items():
                lines.append(f"  - {key}: {value}")
    else:
        lines.append(f"错误消息: {str(error)}")
    
    if isinstance(error, ChipSynthesisError) and error.original_error:
        lines.append("\n原始异常:")
        lines.append(f"  类型: {type(error.original_error).__name__}")
        lines.append(f"  消息: {str(error.original_error)}")
    
    lines.append("\n调用栈:")
    tb_lines = traceback.format_tb(error.__traceback__)
    for line in tb_lines:
        lines.append(line.rstrip())
    
    lines.append("=" * 60)
    return "\n".join(lines)


def handle_error(error: Exception, exit_code: int = 1) -> None:
    """
    统一的错误处理函数，打印错误信息并退出程序。
    
    只在发生错误时输出，不污染正常日志。
    
    Args:
        error: 异常对象
        exit_code: 退出码
    """
    # 构建简洁的错误消息
    error_lines = []
    
    if isinstance(error, ChipSynthesisError):
        # 自定义错误：显示模块信息和上下文
        error_lines.append(f"\n❌ [{error.module.value}] {error.message}")
        
        # 添加上下文信息
        if error.context:
            context_items = []
            for key, value in error.context.items():
                if key == "stage":
                    context_items.append(f"阶段: {value}")
                elif key == "node_id":
                    context_items.append(f"节点: {value}")
                elif key == "node_type":
                    context_items.append(f"类型: {value}")
                elif key == "port":
                    context_items.append(f"端口: {value}")
                elif key == "variable":
                    context_items.append(f"变量: {value}")
                elif key == "file":
                    context_items.append(f"文件: {value}")
                elif key == "line":
                    context_items.append(f"行号: {value}")
            
            if context_items:
                error_lines.append(f"   上下文: {' | '.join(context_items)}")
        
        # 如果有原始异常，显示原始错误信息
        if error.original_error and error.original_error != error:
            error_lines.append(f"   原因: {type(error.original_error).__name__}: {error.original_error}")
    else:
        # 普通异常
        error_lines.append(f"\n❌ 错误: {type(error).__name__}: {str(error)}")
    
    # 输出到 stderr
    for line in error_lines:
        print(line, file=sys.stderr)
    
    sys.exit(exit_code)


def wrap_error(
    error: Exception,
    message: str,
    module: ErrorModule = ErrorModule.UNKNOWN,
    context: Optional[dict[str, Any]] = None
) -> ChipSynthesisError:
    """
    将普通异常包装为带模块信息的自定义异常。
    
    Args:
        error: 原始异常
        message: 新的错误消息
        module: 错误来源模块
        context: 错误上下文
        
    Returns:
        包装后的 ChipSynthesisError
    """
    if isinstance(error, ChipSynthesisError):
        # 如果已经是自定义异常，只更新消息和上下文
        return ChipSynthesisError(
            message=message,
            module=module,
            context={**error.context, **(context or {})},
            original_error=error.original_error or error
        )
    else:
        return ChipSynthesisError(
            message=message,
            module=module,
            context=context,
            original_error=error
        )


__all__ = [
    "ErrorModule",
    "ChipSynthesisError",
    "DSLError",
    "ASTError",
    "GraphError",
    "PipelineError",
    "ModuleAddError",
    "ConnectionError",
    "TypeInferenceError",
    "FileIOError",
    "format_error_trace",
    "handle_error",
    "wrap_error",
]
