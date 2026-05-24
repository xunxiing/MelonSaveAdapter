from __future__ import annotations

import ast
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Set

from src.converter.ast_converter import Converter, _ValueRef
from src.converter.utils import _func_name
from src.error_handler import ASTError


@dataclass
class _BranchAssignment:
    name: str
    ref: _ValueRef
    type_name: str | None
    line: int | None


@dataclass
class _BranchState:
    assignments: Dict[str, _BranchAssignment]
    assigned_order: List[str]


class IfElseConverter(Converter):
    """Compile restricted Python if/else syntax into Branch nodes."""

    def __init__(self) -> None:
        super().__init__()
        self._module_output_types: Dict[str, str | None] | None = None

    @staticmethod
    def _normalize_type_name(type_name: Any) -> str | None:
        if isinstance(type_name, bool) or type_name is None:
            return None
        if isinstance(type_name, int):
            return {
                1: "Entity",
                2: "Number",
                4: "String",
                8: "Vector",
                128: "ArrayNumber",
                256: "ArrayString",
                512: "ArrayVector",
                1024: "ArrayEntity",
            }.get(type_name)
        if not isinstance(type_name, str):
            return None
        return {
            "entity": "Entity",
            "signal": "Entity",
            "number": "Number",
            "decimal": "Number",
            "integer": "Number",
            "integernumber": "Number",
            "string": "String",
            "vector": "Vector",
            "arraynumber": "ArrayNumber",
            "arraystring": "ArrayString",
            "arrayvector": "ArrayVector",
            "arrayentity": "ArrayEntity",
        }.get(type_name.strip().lower())

    @staticmethod
    def _type_key(type_name: str) -> str:
        return "".join(ch for ch in type_name.lower() if ch.isalnum())

    def _load_module_output_types(self) -> Dict[str, str | None]:
        if self._module_output_types is not None:
            return self._module_output_types

        out: Dict[str, str | None] = {}
        moduledef_path = Path(__file__).resolve().parents[2] / "moduledef.json"
        try:
            data = json.loads(moduledef_path.read_text(encoding="utf-8"))
        except Exception:
            self._module_output_types = out
            return out

        if isinstance(data, dict):
            for key, rec in data.items():
                if not isinstance(rec, dict):
                    continue
                outputs = rec.get("outputs") or []
                out_type = None
                if isinstance(outputs, list) and outputs:
                    first = outputs[0]
                    if isinstance(first, dict):
                        out_type = self._normalize_type_name(first.get("type"))

                names = [key, rec.get("id")]
                source = rec.get("source_info")
                if isinstance(source, dict):
                    names.extend(
                        [
                            source.get("datatype_map_nodename"),
                            source.get("chip_names_friendly_name"),
                        ]
                    )
                for name in names:
                    if isinstance(name, str) and name.strip():
                        out[self._type_key(self._canonical_type_name(name))] = out_type

        self._module_output_types = out
        return out

    def _module_output_type(self, type_name: str) -> str | None:
        return self._load_module_output_types().get(
            self._type_key(self._canonical_type_name(type_name))
        )

    def _literal_type_name(self, expr: ast.AST) -> str | None:
        try:
            lit = ast.literal_eval(expr)
        except Exception:
            return None
        if isinstance(lit, bool):
            return "Number"
        if isinstance(lit, (int, float)):
            return "Number"
        if isinstance(lit, str):
            return "String"
        if isinstance(lit, dict) and all(k in lit for k in ("x", "y", "z")):
            return "Vector"
        if isinstance(lit, (list, tuple)):
            if not lit:
                return None
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in lit):
                return "ArrayNumber"
            if all(isinstance(x, str) for x in lit):
                return "ArrayString"
            if all(isinstance(x, dict) and all(k in x for k in ("x", "y", "z")) for x in lit):
                return "ArrayVector"
        return None

    def _infer_expr_type(self, expr: ast.AST | None) -> str | None:
        if expr is None:
            return None
        if isinstance(expr, ast.Name):
            return self.name_types.get(expr.id)
        if isinstance(expr, ast.Subscript) and isinstance(expr.value, ast.Name):
            return self.name_types.get(expr.value.id)
        if isinstance(expr, (ast.Compare, ast.BoolOp)):
            return "Number"
        if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
            return "Number"

        lit_type = self._literal_type_name(expr)
        if lit_type:
            return lit_type

        if isinstance(expr, ast.BinOp):
            left = self._infer_expr_type(expr.left)
            right = self._infer_expr_type(expr.right)
            if left == "Vector" or right == "Vector":
                if isinstance(expr.op, (ast.Add, ast.Sub)):
                    return "Vector" if left == right == "Vector" else None
                if isinstance(expr.op, (ast.Mult, ast.Div)):
                    return "Vector" if "Number" in (left, right) else None
                return None
            if left == "String" or right == "String":
                return "String" if isinstance(expr.op, ast.Add) and left == right == "String" else None
            if left == "Number" or right == "Number":
                return "Number"
            return None

        if isinstance(expr, ast.UnaryOp):
            return self._infer_expr_type(expr.operand)

        if isinstance(expr, ast.IfExp):
            return self._merge_type(
                self._infer_expr_type(expr.body),
                self._infer_expr_type(expr.orelse),
                None,
                getattr(expr, "lineno", None),
            )

        if isinstance(expr, ast.Call):
            fn = self._canonical_type_name(_func_name(expr.func))
            fn_l = fn.lower()
            if fn_l == "input":
                for kw in expr.keywords or []:
                    if kw.arg and kw.arg.lower() in {"data_type", "datatype"}:
                        try:
                            val = ast.literal_eval(kw.value)
                        except Exception:
                            val = kw.value.id if isinstance(kw.value, ast.Name) else None
                        return self._normalize_type_name(val)
                if len(expr.args or []) >= 2:
                    try:
                        val = ast.literal_eval(expr.args[1])
                    except Exception:
                        val = expr.args[1].id if isinstance(expr.args[1], ast.Name) else None
                    return self._normalize_type_name(val)
                return None
            if fn_l == "set" and expr.args:
                target = expr.args[0]
                return self.name_types.get(target.id) if isinstance(target, ast.Name) else None
            if fn_l == "branch":
                args = list(expr.args or [])
                kws = {kw.arg: kw.value for kw in expr.keywords or [] if kw.arg}
                a_expr = kws.get("A") or (args[1] if len(args) > 1 else None)
                b_expr = kws.get("B") or (args[2] if len(args) > 2 else None)
                return self._merge_type(
                    self._infer_expr_type(a_expr),
                    self._infer_expr_type(b_expr),
                    None,
                    getattr(expr, "lineno", None),
                )
            return self._module_output_type(fn)

        return None

    def _merge_type(
        self,
        left: str | None,
        right: str | None,
        target: str | None,
        line: int | None,
    ) -> str | None:
        left = self._normalize_type_name(left)
        right = self._normalize_type_name(right)
        target = self._normalize_type_name(target)
        known = [t for t in (left, right, target) if t]
        if not known:
            return None
        first = known[0]
        for t in known[1:]:
            if t != first:
                raise ASTError(
                    f"if/else branches have incompatible types: {left or 'unknown'} vs {right or 'unknown'}",
                    context={"line": line, "left_type": left, "right_type": right, "target_type": target},
                )
        return first

    @staticmethod
    def _empty_literal_for_type(type_name: str) -> Any:
        if type_name == "Entity":
            return None
        if type_name == "String":
            return ""
        if type_name == "Vector":
            return {"x": 0.0, "y": 0.0, "z": 0.0}
        if type_name.startswith("Array"):
            return []
        return 0.0

    def _emit_typed_empty_ref(self, type_name: str) -> _ValueRef:
        nid = self._emit_constant_node(
            self._empty_literal_for_type(type_name),
            data_type=type_name,
        )
        self.node_types[nid] = type_name
        return _ValueRef("node", nid, "Output")

    def _emit_branch_from_refs(
        self,
        cond_ref: _ValueRef,
        true_ref: _ValueRef,
        false_ref: _ValueRef,
        type_name: str,
        line: int | None,
    ) -> _ValueRef:
        none_expr = ast.Constant(value=None)
        call = ast.Call(
            func=ast.Name(id="Branch", ctx=ast.Load()),
            args=[],
            keywords=[
                ast.keyword(arg="If", value=none_expr),
                ast.keyword(arg="A", value=none_expr),
                ast.keyword(arg="B", value=none_expr),
            ],
        )
        nid = self._emit_call_as_node(call)
        self._set_node_data_type_attr(nid, type_name)
        self.node_types[nid] = type_name
        self._add_edge_from_ref(cond_ref, nid, "If", line=line)
        self._add_edge_from_ref(true_ref, nid, "A", line=line)
        self._add_edge_from_ref(false_ref, nid, "B", line=line)
        return _ValueRef("node", nid, "__auto__")

    @staticmethod
    def _branch_assignment_stmts(stmts: List[ast.stmt], line: int | None) -> List[ast.Assign]:
        assignments: List[ast.Assign] = []
        seen: Set[str] = set()
        for stmt in stmts:
            if isinstance(stmt, ast.Pass):
                continue
            if not (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
            ):
                raise ASTError(
                    "if/else currently supports only simple assignments in branches",
                    context={"line": getattr(stmt, "lineno", line)},
                )
            name = stmt.targets[0].id
            if name in seen:
                raise ASTError(
                    f"Duplicate assignment to '{name}' in the same if/else branch",
                    context={"variable": name, "line": getattr(stmt, "lineno", line)},
                )
            seen.add(name)
            assignments.append(stmt)
        return assignments

    def _snapshot_branch_env(self) -> tuple[Dict[str, str], Dict[str, tuple[str, str]], Dict[str, str]]:
        return dict(self.var2node), dict(self.alias_outputs), dict(self.name_types)

    def _restore_branch_env(
        self,
        snapshot: tuple[Dict[str, str], Dict[str, tuple[str, str]], Dict[str, str]],
    ) -> None:
        self.var2node, self.alias_outputs, self.name_types = (
            dict(snapshot[0]),
            dict(snapshot[1]),
            dict(snapshot[2]),
        )

    def _bind_branch_assignment(self, name: str, ref: _ValueRef, type_name: str | None) -> None:
        if ref.kind == "node":
            self.var2node[name] = ref.value
            self.alias_outputs.pop(name, None)
            if type_name:
                self.name_types[name] = type_name
                self.node_types[ref.value] = type_name
            return

        self.alias_outputs[name] = (ref.value, ref.port)
        if ref.value in self.var2node:
            self.var2node[name] = self.var2node[ref.value]
        else:
            self.var2node.pop(name, None)
        inferred_type = type_name or self.name_types.get(ref.value)
        if inferred_type:
            self.name_types[name] = inferred_type
            nid = self.var2node.get(name)
            if nid:
                self.node_types[nid] = inferred_type

    def _compile_branch_state(
        self,
        stmts: List[ast.stmt],
        base_snapshot: tuple[Dict[str, str], Dict[str, tuple[str, str]], Dict[str, str]],
        line: int | None,
    ) -> _BranchState:
        self._restore_branch_env(base_snapshot)
        assignments: Dict[str, _BranchAssignment] = {}
        assigned_order: List[str] = []

        for stmt in self._branch_assignment_stmts(stmts, line):
            name = stmt.targets[0].id
            expr = stmt.value
            expr_type = self._infer_expr_type(expr)
            ref = self._emit_expr_as_ref(expr)
            self._bind_branch_assignment(name, ref, expr_type)
            assignments[name] = _BranchAssignment(
                name=name,
                ref=ref,
                type_name=expr_type,
                line=getattr(stmt, "lineno", line),
            )
            assigned_order.append(name)

        return _BranchState(assignments=assignments, assigned_order=assigned_order)

    def _emit_if_expression(self, expr: ast.IfExp) -> _ValueRef:
        cond_ref = self._emit_expr_as_ref(expr.test)
        true_ref = self._emit_expr_as_ref(expr.body)
        false_ref = self._emit_expr_as_ref(expr.orelse)
        type_name = self._merge_type(
            self._infer_expr_type(expr.body),
            self._infer_expr_type(expr.orelse),
            None,
            getattr(expr, "lineno", None),
        )
        if type_name is None:
            raise ASTError(
                "Cannot infer result type for conditional expression",
                context={"line": getattr(expr, "lineno", None)},
            )
        return self._emit_branch_from_refs(
            cond_ref,
            true_ref,
            false_ref,
            type_name,
            getattr(expr, "lineno", None),
        )

    def _emit_expr_as_ref(self, expr: ast.AST) -> _ValueRef:
        if isinstance(expr, ast.IfExp):
            return self._emit_if_expression(expr)
        return super()._emit_expr_as_ref(expr)

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        if self._is_main_guard_test(node.test):
            self.generic_visit(node)
            return

        if any(isinstance(stmt, ast.If) for stmt in [*node.body, *node.orelse]):
            raise ASTError(
                "Nested if/else is not supported yet",
                context={"line": getattr(node, "lineno", None)},
            )

        line = getattr(node, "lineno", None)
        # 先发射条件表达式（在分支编译前，使用当前环境状态）
        cond_ref = self._emit_expr_as_ref(node.test)
        base_snapshot = self._snapshot_branch_env()
        true_state = self._compile_branch_state(node.body, base_snapshot, line)
        false_state = self._compile_branch_state(node.orelse, base_snapshot, line)
        self._restore_branch_env(base_snapshot)

        if not true_state.assignments and not false_state.assignments:
            return

        merge_order: List[str] = []
        for name in [*true_state.assigned_order, *false_state.assigned_order]:
            if name not in merge_order:
                merge_order.append(name)

        for name in merge_order:
            true_assignment = true_state.assignments.get(name)
            false_assignment = false_state.assignments.get(name)

            merged_type = self._merge_type(
                true_assignment.type_name if true_assignment else None,
                false_assignment.type_name if false_assignment else None,
                self.name_types.get(name),
                line,
            )
            if merged_type is None:
                raise ASTError(
                    f"Cannot infer if/else merge type for '{name}'",
                    context={"variable": name, "line": line},
                )

            true_ref = (
                true_assignment.ref
                if true_assignment is not None
                else self._emit_typed_empty_ref(merged_type)
            )
            false_ref = (
                false_assignment.ref
                if false_assignment is not None
                else self._emit_typed_empty_ref(merged_type)
            )
            merged_ref = self._emit_branch_from_refs(
                cond_ref,
                true_ref,
                false_ref,
                merged_type,
                line,
            )

            is_declared_var = any(
                vd.get("Key") == name or vd.get("dsl_name") == name
                for vd in (self.g.variables or [])
                if isinstance(vd, dict)
            )
            if is_declared_var and self._has_main_guard and self._in_main_block:
                self._emit_set_from_ref(name, merged_ref, None, line)
            else:
                self.var2node[name] = merged_ref.value
                self.name_types[name] = merged_type
                self.node_types[merged_ref.value] = merged_type


__all__ = ["IfElseConverter"]
