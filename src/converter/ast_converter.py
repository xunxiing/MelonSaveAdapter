from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from src.converter.graph import Graph
from src.converter.utils import _ast_is_none, _auto_label, _func_name
from src.error_handler import ASTError, ErrorModule


@dataclass(frozen=True)
class _ValueRef:
    kind: str  # "node" | "var"
    value: str
    port: str


class Converter(ast.NodeVisitor):
    """
    只做 AST 静态转换：读取 DSL 语法树，不执行代码。
    """

    def __init__(self) -> None:
        self.g = Graph()
        self.var2node: Dict[str, str] = {}  # 变量名 -> 节点ID（首次定义为准）
        self.inputs_seen: Dict[str, List[str]] = {}  # 节点ID -> 输入端口顺序
        self.outputs_seen: Dict[str, Set[str]] = {}  # 节点ID -> 被引用到的输出端口名集合
        # unresolved: (上游变量名, 上游端口标识, 下游节点ID, 下游端口名)
        self.unresolved: List[Tuple[str, str, str, str]] = []
        # 端口别名表： alias_var -> (up_var, up_port_str)
        self.alias_outputs: Dict[str, Tuple[str, str]] = {}

    @staticmethod
    def _canonical_type_name(type_name: str) -> str:
        if not isinstance(type_name, str):
            return str(type_name)
        raw = type_name.strip()
        if not raw:
            return type_name

        base = raw.split(".")[-1].strip()
        key = base.lower()
        alias = {
            "abs": "Positive",
            "positive": "Positive",
            "sqrt": "Sqrt",
            "ceil": "Ceiling",
            "ceiling": "Ceiling",
            "pow": "Power",
            "power": "Power",
            "exp": "Exponent",
            "exponent": "Exponent",
            "log": "Logarithm",
            "logarithm": "Logarithm",
            "random": "Random",
            "remainder": "Remainder",
            "round": "Round",
            "floor": "Floor",
            "clamp": "Clamp",
            "clamp01": "Clamp01",
            "inverse": "Inverse",
            "sign": "Sign",
            "add": "Add",
            "subtract": "Subtract",
            "multiply": "Multiply",
            "divide": "Divide",
            "negate": "Negate",
            "average": "Average",
            "max": "Max",
            # Min/Square is macro and may not exist as a chip
            "min": "Min",
            "square": "Square",
        }
        return alias.get(key, base)

    def _value_ref_for_name(self, name: str, *, default_port: str = "__auto__") -> _ValueRef:
        if name in self.alias_outputs:
            up_var, up_port = self.alias_outputs[name]
            if up_var in self.var2node:
                return _ValueRef("node", self.var2node[up_var], up_port)
            return _ValueRef("var", up_var, up_port)

        if name in self.var2node:
            return _ValueRef("node", self.var2node[name], default_port)
        return _ValueRef("var", name, default_port)

    def _add_edge_from_ref(self, ref: _ValueRef, to_nid: str, to_port: str) -> None:
        if ref.kind == "node":
            self.g.add_edge(ref.value, ref.port, to_nid, to_port)
            self.outputs_seen.setdefault(ref.value, set()).add(ref.port)
            return
        self.unresolved.append((ref.value, ref.port, to_nid, to_port))

    @staticmethod
    def _literal_kind(expr: ast.AST) -> str | None:
        try:
            lit = ast.literal_eval(expr)
        except Exception:
            return None
        if isinstance(lit, (int, float)):
            return "number"
        if isinstance(lit, str):
            return "string"
        if isinstance(lit, dict) and all(k in lit for k in ("x", "y", "z")):
            return "vector"
        if lit is None:
            return "none"
        return "other"

    def _emit_expr_as_ref(self, expr: ast.AST) -> _ValueRef:
        if isinstance(expr, ast.Name):
            return self._value_ref_for_name(expr.id)

        if isinstance(expr, ast.Subscript):
            if isinstance(expr.value, ast.Name):
                up_var = expr.value.id
                sl = expr.slice
                if isinstance(sl, ast.Constant):
                    up_port = sl.value
                else:
                    up_port = ast.literal_eval(sl)
                if not isinstance(up_port, (str, int)):
                    raise ASTError(
                        "端口下标必须是字符串或整数字面量",
                        context={"variable": up_var, "port": str(up_port)}
                    )
                up_port_str = str(up_port)
                if up_var in self.var2node:
                    return _ValueRef("node", self.var2node[up_var], up_port_str)
                return _ValueRef("var", up_var, up_port_str)

            if isinstance(expr.value, ast.Call):
                up_ref = self._emit_expr_as_ref(expr.value)
                if up_ref.kind != "node":
                    raise ASTError(
                        "无法对非节点表达式进行下标访问",
                        context={"node_id": up_ref.value if hasattr(up_ref, 'value') else "unknown"}
                    )
                sl = expr.slice
                if isinstance(sl, ast.Constant):
                    up_port = sl.value
                else:
                    up_port = ast.literal_eval(sl)
                if not isinstance(up_port, (str, int)):
                    raise ASTError(
                        "端口下标必须是字符串或整数字面量",
                        context={"node_id": up_ref.value}
                    )
                return _ValueRef("node", up_ref.value, str(up_port))

        try:
            lit = ast.literal_eval(expr)
        except Exception:
            lit = None
        if isinstance(lit, (int, float, str)) or (
            isinstance(lit, dict) and all(k in lit for k in ("x", "y", "z"))
        ):
            up_nid = self._emit_constant_node(lit)
            return _ValueRef("node", up_nid, "Output")

        if isinstance(expr, ast.BinOp):
            k_left = self._literal_kind(expr.left)
            k_right = self._literal_kind(expr.right)

            if isinstance(expr.op, ast.Add):
                if k_left and k_right and k_left != k_right:
                    if "vector" in (k_left, k_right):
                        raise ASTError("向量加法只支持 vector + vector")
                    if "string" in (k_left, k_right):
                        raise ASTError("字符串相加只支持 string + string")
                type_name, a_name, b_name = "Add", "A", "B"
            elif isinstance(expr.op, ast.Sub):
                if k_left and k_right and k_left != k_right and "vector" in (k_left, k_right):
                    raise ASTError("向量减法只支持 vector - vector")
                if k_left in ("string",) or k_right in ("string",):
                    raise ASTError("Subtract 不支持字符串类型")
                type_name, a_name, b_name = "Subtract", "A", "B"
            elif isinstance(expr.op, ast.Mult):
                if k_left and k_right and k_left != k_right and "vector" in (k_left, k_right):
                    raise TypeError("向量乘法只支持 vector * vector（不允许 vector * number）")
                if k_left in ("string",) or k_right in ("string",):
                    raise TypeError("Multiply 不支持字符串类型")
                type_name, a_name, b_name = "Multiply", "A", "B"
            elif isinstance(expr.op, ast.Div):
                if k_left and k_right and k_left != k_right and "vector" in (k_left, k_right):
                    raise TypeError("向量除法只支持 vector / vector（不允许 vector / number）")
                if k_left in ("string",) or k_right in ("string",):
                    raise TypeError("Divide 不支持字符串类型")
                type_name, a_name, b_name = "Divide", "A", "B"
            elif isinstance(expr.op, ast.Mod):
                if k_left in ("vector", "string") or k_right in ("vector", "string"):
                    raise TypeError("Remainder 只支持 DECIMAL % DECIMAL")
                type_name, a_name, b_name = "Remainder", "Dividend", "Divider"
            elif isinstance(expr.op, ast.Pow):
                if k_left in ("vector", "string") or k_right in ("vector", "string"):
                    raise TypeError("Power 只支持 DECIMAL ** DECIMAL")
                type_name, a_name, b_name = "Power", "Value", "Power"
            else:
                raise TypeError("unsupported binary operator")

            call = ast.Call(
                func=ast.Name(id=type_name, ctx=ast.Load()),
                args=[],
                keywords=[
                    ast.keyword(arg=a_name, value=expr.left),
                    ast.keyword(arg=b_name, value=expr.right),
                ],
            )
            nid = self._emit_call_as_node(call)
            return _ValueRef("node", nid, "__auto__")

        if isinstance(expr, ast.UnaryOp):
            if isinstance(expr.op, ast.USub):
                call = ast.Call(
                    func=ast.Name(id="Negate", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=expr.operand)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")
            if isinstance(expr.op, ast.UAdd):
                return self._emit_expr_as_ref(expr.operand)
            raise TypeError("unsupported unary operator")

        if isinstance(expr, ast.Call):
            fn = self._canonical_type_name(_func_name(expr.func))
            fn_l = fn.lower()

            def _kw_map(keys: List[str]) -> Dict[str, ast.AST]:
                out: Dict[str, ast.AST] = {}
                for kw in expr.keywords or []:
                    if kw.arg is None:
                        continue
                    out[kw.arg.lower()] = kw.value
                args = list(expr.args or [])
                for i, k in enumerate(keys):
                    if i < len(args) and k not in out:
                        out[k] = args[i]
                return out

            if fn_l in ("abs", "positive"):
                kw = _kw_map(["input"])
                arg = kw.get("input") or kw.get("a")
                if arg is None:
                    raise ASTError("abs/Positive 缺少参数", context={"node_type": "Positive"})
                if self._literal_kind(arg) in ("vector", "string"):
                    raise ASTError("ABS/Positive 只支持 DECIMAL 输入", context={"node_type": "Positive"})
                call = ast.Call(
                    func=ast.Name(id="Positive", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=arg)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "sqrt":
                kw = _kw_map(["input"])
                arg = kw.get("input") or kw.get("a")
                if arg is None:
                    raise TypeError("sqrt 缺少参数")
                if self._literal_kind(arg) in ("vector", "string"):
                    raise TypeError("SQRT 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Sqrt", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=arg)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l in ("round", "floor", "ceiling", "ceil"):
                kw = _kw_map(["input"])
                arg = kw.get("input") or kw.get("a")
                if arg is None:
                    raise TypeError(f"{fn_l} 缺少参数")
                if self._literal_kind(arg) in ("string",):
                    raise TypeError(f"{fn_l} 不支持 STRING 输入")
                mod = {"round": "Round", "floor": "Floor", "ceiling": "Ceiling", "ceil": "Ceiling"}[fn_l]
                call = ast.Call(
                    func=ast.Name(id=mod, ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=arg)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "clamp01":
                kw = _kw_map(["input"])
                arg = kw.get("input") or kw.get("a")
                if arg is None:
                    raise TypeError("clamp01 缺少参数")
                if self._literal_kind(arg) in ("vector", "string"):
                    raise TypeError("Clamp01 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Clamp01", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=arg)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "clamp":
                kw = _kw_map(["input", "min", "max"])
                a = kw.get("input") or kw.get("a")
                mn = kw.get("min")
                mx = kw.get("max")
                if a is None or mn is None or mx is None:
                    raise TypeError("clamp 需要 3 个参数：input/min/max")
                if self._literal_kind(a) in ("vector", "string"):
                    raise TypeError("Clamp 只支持 DECIMAL Input")
                if self._literal_kind(mn) in ("vector", "string") or self._literal_kind(mx) in ("vector", "string"):
                    raise TypeError("Clamp 的 Min/Max 只支持 DECIMAL")
                call = ast.Call(
                    func=ast.Name(id="Clamp", ctx=ast.Load()),
                    args=[],
                    keywords=[
                        ast.keyword(arg="Input", value=a),
                        ast.keyword(arg="Min", value=mn),
                        ast.keyword(arg="Max", value=mx),
                    ],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "average":
                kw = _kw_map(["a", "b"])
                a = kw.get("a") or kw.get("input")
                b = kw.get("b")
                if a is None or b is None:
                    raise TypeError("average 需要 2 个参数")
                if self._literal_kind(a) in ("vector", "string") or self._literal_kind(b) in ("vector", "string"):
                    raise TypeError("AVERAGE 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Average", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="A", value=a), ast.keyword(arg="B", value=b)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "max":
                kw = _kw_map(["a", "b"])
                a = kw.get("a") or kw.get("input")
                b = kw.get("b")
                if a is None or b is None:
                    raise TypeError("max 需要 2 个参数")
                if self._literal_kind(a) in ("vector", "string") or self._literal_kind(b) in ("vector", "string"):
                    raise TypeError("MAX 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Max", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="A", value=a), ast.keyword(arg="B", value=b)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "min":
                kw = _kw_map(["a", "b"])
                a = kw.get("a") or kw.get("input")
                b = kw.get("b")
                if a is None or b is None:
                    raise TypeError("min 需要 2 个参数")
                if self._literal_kind(a) in ("vector", "string") or self._literal_kind(b) in ("vector", "string"):
                    raise TypeError("MIN 只支持 DECIMAL 输入")
                na = ast.Call(
                    func=ast.Name(id="Negate", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=a)],
                )
                nb = ast.Call(
                    func=ast.Name(id="Negate", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=b)],
                )
                m = ast.Call(
                    func=ast.Name(id="Max", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="A", value=na), ast.keyword(arg="B", value=nb)],
                )
                out_call = ast.Call(
                    func=ast.Name(id="Negate", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=m)],
                )
                nid = self._emit_call_as_node(out_call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "square":
                kw = _kw_map(["a"])
                a = kw.get("a") or kw.get("input")
                call = ast.Call(
                    func=ast.Name(id="Multiply", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="A", value=a), ast.keyword(arg="B", value=a)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "inverse":
                kw = _kw_map(["a"])
                a = kw.get("a") or kw.get("input")
                if a is None:
                    raise TypeError("inverse 缺少参数")
                if self._literal_kind(a) in ("vector", "string"):
                    raise TypeError("Inverse 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Inverse", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="A", value=a)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "sign":
                kw = _kw_map(["input"])
                arg = kw.get("input") or kw.get("a")
                if arg is None:
                    raise TypeError("sign 缺少参数")
                if self._literal_kind(arg) in ("vector", "string"):
                    raise TypeError("SIGN 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Sign", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=arg)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "exp":
                kw = _kw_map(["input"])
                arg = kw.get("input") or kw.get("a")
                if arg is None:
                    raise TypeError("exp 缺少参数")
                if self._literal_kind(arg) in ("vector", "string"):
                    raise TypeError("Exp/Exponent 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Exponent", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Input", value=arg)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l in ("log", "logarithm"):
                kw = _kw_map(["value", "base"])
                val = kw.get("value") or kw.get("a") or kw.get("input")
                base = kw.get("base") or kw.get("b")
                if val is None or base is None:
                    raise TypeError("log 需要 2 个参数：value/base")
                if self._literal_kind(val) in ("vector", "string") or self._literal_kind(base) in ("vector", "string"):
                    raise TypeError("LOGARITHM 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Logarithm", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Value", value=val), ast.keyword(arg="Base", value=base)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "random":
                kw = _kw_map(["min", "max"])
                mn = kw.get("min") or kw.get("a")
                mx = kw.get("max") or kw.get("b")
                if mn is None or mx is None:
                    raise TypeError("random 需要 2 个参数：min/max")
                if self._literal_kind(mn) in ("vector", "string") or self._literal_kind(mx) in ("vector", "string"):
                    raise TypeError("Random 只支持 DECIMAL Min/Max")
                call = ast.Call(
                    func=ast.Name(id="Random", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Min", value=mn), ast.keyword(arg="Max", value=mx)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l in ("pow", "power"):
                kw = _kw_map(["value", "power"])
                val = kw.get("value") or kw.get("a")
                pw = kw.get("power") or kw.get("b")
                if val is None or pw is None:
                    raise TypeError("pow/power 需要 2 个参数")
                if self._literal_kind(val) in ("vector", "string") or self._literal_kind(pw) in ("vector", "string"):
                    raise TypeError("POWER 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Power", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Value", value=val), ast.keyword(arg="Power", value=pw)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if fn_l == "remainder":
                kw = _kw_map(["dividend", "divider"])
                dv = kw.get("dividend") or kw.get("a")
                dr = kw.get("divider") or kw.get("b")
                if dv is None or dr is None:
                    raise TypeError("remainder 需要 2 个参数")
                if self._literal_kind(dv) in ("vector", "string") or self._literal_kind(dr) in ("vector", "string"):
                    raise TypeError("Remainder 只支持 DECIMAL 输入")
                call = ast.Call(
                    func=ast.Name(id="Remainder", ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg="Dividend", value=dv), ast.keyword(arg="Divider", value=dr)],
                )
                nid = self._emit_call_as_node(call)
                return _ValueRef("node", nid, "__auto__")

            if expr.args:
                raise ASTError(
                    f"DSL 节点调用不支持位置参数，请使用关键字端口如 A=..., B=...",
                    context={"node_type": fn}
                )

            nid = self._emit_call_as_node(expr)
            return _ValueRef("node", nid, "__auto__")

        try:
            expr_s = ast.unparse(expr)  # type: ignore[attr-defined]
        except Exception:
            expr_s = str(expr)
        raise ASTError(f"不支持的表达式: {expr_s}")

    def _emit_constant_node(self, lit: Any) -> str:
        nid = self.g.next_id("Constant")
        attrs = {"value": lit}
        node_rec = {
            "id": nid,
            "type": "Constant",
            "label": _auto_label("Constant", attrs),
            "attrs": attrs,
            "inputs": [],
            "outputs": [],
        }
        self.g.add_node(node_rec)
        self.inputs_seen.setdefault(nid, [])
        self.outputs_seen.setdefault(nid, set())
        return nid

    def _register_variable_def(
        self,
        lit: Dict[str, Any],
        alias_var: str | None,
        from_var_call: bool = False,
    ) -> None:
        key = lit.get("Key")
        gate_type = lit.get("GateDataType")
        if not isinstance(key, str) or not isinstance(gate_type, str):
            return

        rec: Dict[str, Any] = {
            "Key": key,
            "GateDataType": gate_type,
            "Value": lit.get("Value"),
        }
        if alias_var:
            rec["dsl_name"] = alias_var

        self.g.variables.append(rec)

        if alias_var and not from_var_call:
            try:
                none_expr = ast.Constant(value=None)
                call = ast.Call(
                    func=ast.Name(id="VARIABLE", ctx=ast.Load()),
                    args=[],
                    keywords=[
                        ast.keyword(arg="Value", value=none_expr),
                        ast.keyword(arg="Set", value=none_expr),
                    ],
                )
                nid = self._emit_call_as_node(call)

                for node_rec in reversed(self.g.nodes):
                    if node_rec.get("id") == nid:
                        attrs = node_rec.get("attrs") or {}
                        if "dsl_name" not in attrs:
                            attrs["dsl_name"] = alias_var
                        node_rec["attrs"] = attrs
                        break

                if alias_var not in self.var2node:
                    self.var2node[alias_var] = nid
            except Exception:
                pass

    def visit_Assign(self, node: ast.Assign) -> None:
        if (
            isinstance(node.value, ast.Call)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            var = node.targets[0].id
            call = node.value
            func_name = _func_name(call.func)
            ref = self._emit_expr_as_ref(call)
            if ref.kind == "node" and var not in self.var2node:
                self.var2node[var] = ref.value

            if func_name.upper() == "VARIABLE":
                has_existing = any(vd.get("Key") == var for vd in self.g.variables)
                if not has_existing:
                    value_lit = None
                    for kw in call.keywords or []:
                        if kw.arg == "Value":
                            try:
                                value_lit = ast.literal_eval(kw.value)
                            except Exception:
                                value_lit = None
                            break

                    if value_lit is not None:
                        if isinstance(value_lit, (int, float)):
                            gate_type = "Number"
                        elif isinstance(value_lit, str):
                            gate_type = "String"
                        elif isinstance(value_lit, dict) and all(
                            k in value_lit for k in ("x", "y", "z")
                        ):
                            gate_type = "Vector"
                        else:
                            gate_type = "Number"

                        lit_def = {
                            "Key": var,
                            "GateDataType": gate_type,
                            "Value": value_lit,
                        }
                        self._register_variable_def(lit_def, alias_var=var, from_var_call=True)

                try:
                    for node_rec in reversed(self.g.nodes):
                        if node_rec.get("id") == self.var2node.get(var):
                            attrs = node_rec.get("attrs") or {}
                            if "dsl_name" not in attrs:
                                attrs["dsl_name"] = var
                            node_rec["attrs"] = attrs
                            break
                except Exception:
                    pass

        elif (
            isinstance(node.value, ast.Subscript)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            target = node.targets[0].id
            sub = node.value
            sl = sub.slice
            if isinstance(sl, ast.Constant):
                up_port = sl.value
            else:
                try:
                    up_port = ast.literal_eval(sl)
                except Exception:
                    up_port = None

            if isinstance(up_port, (str, int)):
                up_port_str = str(up_port)

                # alias = some_var["PORT"]
                if isinstance(sub.value, ast.Name):
                    up_var = sub.value.id
                    self.alias_outputs[target] = (up_var, up_port_str)
                    return

                # alias = SomeNodeCall(... )["PORT"]
                if isinstance(sub.value, ast.Call):
                    ref = self._emit_expr_as_ref(sub.value)
                    if ref.kind == "node":
                        # trick: make alias_outputs resolvable via var2node by pointing to itself
                        if target not in self.var2node:
                            self.var2node[target] = ref.value
                        self.alias_outputs[target] = (target, up_port_str)
                    return

        elif len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                lit = ast.literal_eval(node.value)
            except Exception:
                lit = None

            if isinstance(lit, dict) and {"Key", "GateDataType", "Value"} <= set(lit.keys()):
                alias = node.targets[0].id
                self._register_variable_def(lit, alias)
            else:
                is_ok = isinstance(lit, (int, float, str)) or (
                    isinstance(lit, dict) and all(k in lit for k in ("x", "y", "z"))
                )
                if is_ok:
                    var = node.targets[0].id
                    nid = self._emit_constant_node(lit)
                    if var not in self.var2node:
                        self.var2node[var] = nid
                else:
                    # 一般表达式赋值：a = (b + c) * 2 / a = abs(x) ...
                    var = node.targets[0].id
                    try:
                        ref = self._emit_expr_as_ref(node.value)
                    except TypeError:
                        ref = None
                    if isinstance(ref, _ValueRef):
                        if ref.kind == "node":
                            if var not in self.var2node:
                                self.var2node[var] = ref.value
                        else:
                            self.alias_outputs[var] = (ref.value, ref.port)
                            if ref.value in self.var2node and var not in self.var2node:
                                self.var2node[var] = self.var2node[ref.value]

        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        try:
            lit = ast.literal_eval(node.value)
        except Exception:
            lit = None
        if isinstance(lit, dict) and {"Key", "GateDataType", "Value"} <= set(lit.keys()):
            self._register_variable_def(lit, alias_var=None)
            return

        if isinstance(node.value, ast.Call):
            self._emit_expr_as_ref(node.value)
        self.generic_visit(node)

    def _emit_call_as_node(self, call: ast.Call) -> str:
        type_name = self._canonical_type_name(_func_name(call.func))

        attrs: Dict[str, Any] = {}
        fixed_id: str | None = None
        label: str | None = None
        conns: List[Tuple[str, ast.AST]] = []

        for kw in call.keywords or []:
            if kw.arg is None:
                continue
            key = kw.arg
            if key == "attrs":
                try:
                    attrs_val = ast.literal_eval(kw.value)
                    attrs = attrs_val if isinstance(attrs_val, dict) else {}
                except Exception:
                    attrs = {}
            elif key == "id":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    fixed_id = kw.value.value
            elif key == "label":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    label = kw.value.value
            else:
                conns.append((key, kw.value))

        nid = fixed_id or self.g.next_id(type_name)
        if fixed_id and nid in self.g._used:
            nid = self.g.next_id(type_name)

        self.inputs_seen.setdefault(nid, [])
        self.outputs_seen.setdefault(nid, set())

        node_rec = {
            "id": nid,
            "type": type_name,
            "label": _auto_label(type_name, attrs) if label is None else label,
            "attrs": attrs,
            "inputs": [],
            "outputs": [],
        }
        self.g.add_node(node_rec)

        seen_inputs: List[str] = []

        for port_name, expr in conns:
            if _ast_is_none(expr):
                seen_inputs.append(port_name)
                continue
            ref = self._emit_expr_as_ref(expr)
            self._add_edge_from_ref(ref, nid, port_name)
            seen_inputs.append(port_name)

        node_rec["inputs"] = [{"name": p, "type": ""} for p in seen_inputs]
        return nid

    def resolve_unresolved(self) -> None:
        for up_var, up_port, to_nid, to_port in self.unresolved:
            if up_var not in self.var2node:
                raise ASTError(
                    f"引用了未定义变量 '{up_var}'（前向引用失败）",
                    context={"node_id": to_nid, "port": to_port, "variable": up_var}
                )
            up_nid = self.var2node[up_var]
            self.g.add_edge(up_nid, up_port, to_nid, to_port)
            self.outputs_seen.setdefault(up_nid, set()).add(up_port)
        self.unresolved.clear()

    def finalize_outputs(self) -> None:
        nid2rec = {n["id"]: n for n in self.g.nodes}
        for nid, outs in self.outputs_seen.items():
            nid2rec[nid]["outputs"] = [{"name": p, "type": ""} for p in sorted(outs, key=str)]


__all__ = ["Converter"]
