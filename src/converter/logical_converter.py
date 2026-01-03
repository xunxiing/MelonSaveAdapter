from __future__ import annotations

import ast
from typing import Any, Dict

from src.converter.ast_converter import Converter, _ValueRef
from src.error_handler import ASTError


class LogicalConverter(Converter):
    """
    扩展 Converter 类，添加布尔逻辑和数值比较运算符的语法糖支持。
    """

    def _emit_expr_as_ref(self, expr: ast.AST) -> _ValueRef:
        # 先处理布尔运算符
        if isinstance(expr, ast.BoolOp):
            return self._emit_bool_op(expr)

        # 处理比较运算符
        if isinstance(expr, ast.Compare):
            return self._emit_compare_op(expr)

        # 处理一元运算符（包括 not）
        if isinstance(expr, ast.UnaryOp):
            if isinstance(expr.op, ast.Not):
                return self._emit_not_op(expr)
            # 其他一元运算符交给父类处理
            return super()._emit_expr_as_ref(expr)

        # 其他情况交给父类处理
        return super()._emit_expr_as_ref(expr)

    def _emit_bool_op(self, expr: ast.BoolOp) -> _ValueRef:
        """
        处理布尔运算符：and, or
        """
        if isinstance(expr.op, ast.And):
            return self._emit_and_op(expr)
        elif isinstance(expr.op, ast.Or):
            return self._emit_or_op(expr)
        else:
            raise ASTError(f"不支持的布尔运算符: {type(expr.op).__name__}")

    def _emit_and_op(self, expr: ast.BoolOp) -> _ValueRef:
        """
        处理 and 运算符，转换为 AND 芯点
        输入: A and B and C
        输出: AND(AND(A, B), C) - 链式调用
        """
        values = expr.values
        if len(values) < 2:
            raise ASTError("and 运算符至少需要 2 个操作数")

        # 从左到右处理链式 and
        result_ref = self._emit_expr_as_ref(values[0])

        for value in values[1:]:
            right_ref = self._emit_expr_as_ref(value)
            result_ref = self._create_binary_logic_node("AND", result_ref, right_ref)

        return result_ref

    def _emit_or_op(self, expr: ast.BoolOp) -> _ValueRef:
        """
        处理 or 运算符，转换为 OR 芯点
        输入: A or B or C
        输出: OR(OR(A, B), C) - 链式调用
        """
        values = expr.values
        if len(values) < 2:
            raise ASTError("or 运算符至少需要 2 个操作数")

        # 从左到右处理链式 or
        result_ref = self._emit_expr_as_ref(values[0])

        for value in values[1:]:
            right_ref = self._emit_expr_as_ref(value)
            result_ref = self._create_binary_logic_node("OR", result_ref, right_ref)

        return result_ref

    def _emit_not_op(self, expr: ast.UnaryOp) -> _ValueRef:
        """
        处理 not 运算符，转换为 NOT 芯点
        """
        operand_ref = self._emit_expr_as_ref(expr.operand)

        call = ast.Call(
            func=ast.Name(id="NOT", ctx=ast.Load()),
            args=[],
            keywords=[ast.keyword(arg="A", value=ast.Constant(value=1))],  # 占位符
        )

        # 创建节点
        nid = self._emit_call_as_node(call)

        # 手动添加边
        self._add_edge_from_ref(operand_ref, nid, "A")

        return _ValueRef("node", nid, "__auto__")

    def _emit_compare_op(self, expr: ast.Compare) -> _ValueRef:
        """
        处理比较运算符：>, <, >=, <=, ==, !=
        支持链式比较：a < b < c 会被转换为 (a < b) and (b < c)
        """
        if len(expr.comparators) != 1:
            # 链式比较，如 a < b < c
            return self._emit_chained_compare(expr)

        op = expr.ops[0]
        left = expr.left
        right = expr.comparators[0]

        left_ref = self._emit_expr_as_ref(left)
        right_ref = self._emit_expr_as_ref(right)

        if isinstance(op, ast.Gt):
            return self._create_compare_node("GREATER THAN", left_ref, right_ref)
        elif isinstance(op, ast.Lt):
            return self._create_compare_node("LESS THAN", left_ref, right_ref)
        elif isinstance(op, ast.GtE):
            return self._create_compare_node("GREATER OR EQUAL", left_ref, right_ref)
        elif isinstance(op, ast.LtE):
            return self._create_compare_node("LESS OR EQUAL", left_ref, right_ref)
        elif isinstance(op, ast.Eq):
            return self._create_compare_node("EQUAL", left_ref, right_ref)
        elif isinstance(op, ast.NotEq):
            return self._create_compare_node("NOT EQUAL", left_ref, right_ref)
        else:
            raise ASTError(f"不支持的比较运算符: {type(op).__name__}")

    def _emit_chained_compare(self, expr: ast.Compare) -> _ValueRef:
        """
        处理链式比较，如 a < b < c
        转换为 (a < b) and (b < c)
        """
        # a < b < c 转换为 (a < b) and (b < c)
        comparisons = []

        # 第一个比较
        left = expr.left
        for i, (op, right) in enumerate(zip(expr.ops, expr.comparators)):
            # 创建比较节点
            left_ref = self._emit_expr_as_ref(left)
            right_ref = self._emit_expr_as_ref(right)

            if isinstance(op, ast.Gt):
                comp_ref = self._create_compare_node("GREATER THAN", left_ref, right_ref)
            elif isinstance(op, ast.Lt):
                comp_ref = self._create_compare_node("LESS THAN", left_ref, right_ref)
            elif isinstance(op, ast.GtE):
                comp_ref = self._create_compare_node("GREATER OR EQUAL", left_ref, right_ref)
            elif isinstance(op, ast.LtE):
                comp_ref = self._create_compare_node("LESS OR EQUAL", left_ref, right_ref)
            elif isinstance(op, ast.Eq):
                comp_ref = self._create_compare_node("EQUAL", left_ref, right_ref)
            elif isinstance(op, ast.NotEq):
                comp_ref = self._create_compare_node("NOT EQUAL", left_ref, right_ref)
            else:
                raise ASTError(f"不支持的比较运算符: {type(op).__name__}")

            comparisons.append(comp_ref)
            left = right  # 下一个比较的左操作数是当前比较的右操作数

        # 将所有比较结果用 AND 连接
        result_ref = comparisons[0]
        for comp_ref in comparisons[1:]:
            result_ref = self._create_binary_logic_node("AND", result_ref, comp_ref)

        return result_ref

    def _create_binary_logic_node(self, op_type: str, left_ref: _ValueRef, right_ref: _ValueRef) -> _ValueRef:
        """
        创建二元逻辑运算节点（AND, OR, XOR, NAND, NOR, NXOR）
        """
        call = ast.Call(
            func=ast.Name(id=op_type, ctx=ast.Load()),
            args=[],
            keywords=[
                ast.keyword(arg="A", value=ast.Constant(value=1)),  # 占位符
                ast.keyword(arg="B", value=ast.Constant(value=1)),  # 占位符
            ],
        )

        nid = self._emit_call_as_node(call)

        # 手动添加边
        self._add_edge_from_ref(left_ref, nid, "A")
        self._add_edge_from_ref(right_ref, nid, "B")

        return _ValueRef("node", nid, "__auto__")

    def _create_compare_node(self, op_type: str, left_ref: _ValueRef, right_ref: _ValueRef) -> _ValueRef:
        """
        创建比较运算节点（GREATER THAN, LESS THAN, EQUAL 等）
        """
        call = ast.Call(
            func=ast.Name(id=op_type, ctx=ast.Load()),
            args=[],
            keywords=[
                ast.keyword(arg="A", value=ast.Constant(value=1)),  # 占位符
                ast.keyword(arg="B", value=ast.Constant(value=1)),  # 占位符
            ],
        )

        nid = self._emit_call_as_node(call)

        # 手动添加边
        self._add_edge_from_ref(left_ref, nid, "A")
        self._add_edge_from_ref(right_ref, nid, "B")

        return _ValueRef("node", nid, "__auto__")


__all__ = ["LogicalConverter"]
