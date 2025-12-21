from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from src.converter.ast_converter import Converter


def convert_dsl_to_graph(dsl_script_path: Path | str, output_path: Path | str) -> None:
    """
    使用 AST 转换器将 DSL 转为 graph.json（不需要 module_defs）。
    """
    try:
        # Windows 上常见的 UTF-8 BOM 会导致 ast.parse 报 U+FEFF；用 utf-8-sig 自动剥离 BOM。
        code = Path(dsl_script_path).read_text(encoding="utf-8-sig")
    except Exception as e:
        sys.exit(f"Failed to read DSL '{dsl_script_path}': {e}")

    try:
        tree = ast.parse(code, filename=str(dsl_script_path))
        cvt = Converter()
        cvt.visit(tree)
        cvt.resolve_unresolved()
        cvt.finalize_outputs()
    except Exception as e:  # noqa: BLE001
        error_msg = str(e)

        if "name" in error_msg and "is not defined" in error_msg:
            import re as _re

            match = _re.search(r"name '(\w+)' is not defined", error_msg)
            if match:
                undefined_var = match.group(1)
                sys.exit(
                    f"DSL语法错误: 变量 '{undefined_var}' 未定义\n"
                    f"提示: 在使用变量前，请先通过函数调用或赋值来定义它\n"
                    f"例如: {undefined_var} = SOME_FUNCTION(...)"
                )

        if isinstance(e, TypeError):
            sys.exit(f"DSL参数错误: {error_msg}")

        sys.exit(f"DSL执行错误: {error_msg}")

    try:
        out = cvt.g.to_dict()
        Path(output_path).write_text(
            json.dumps(out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Failed to write graph JSON '{output_path}': {e}")


__all__ = ["convert_dsl_to_graph"]
