from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from src.converter.dedup_converter import DedupConverter
from src.error_handler import DSLError, FileIOError, ASTError, handle_error


def convert_dsl_to_graph(dsl_script_path: Path | str, output_path: Path | str) -> None:
    """
    使用 AST 转换器将 DSL 转为 graph.json（不需要 module_defs）。
    """
    try:
        # Windows 上常见的 UTF-8 BOM 会导致 ast.parse 报 U+FEFF；用 utf-8-sig 自动剥离 BOM。
        code = Path(dsl_script_path).read_text(encoding="utf-8-sig")
    except Exception as e:
        raise FileIOError(
            f"读取 DSL 文件失败",
            file_path=str(dsl_script_path),
            original_error=e
        )

    try:
        tree = ast.parse(code, filename=str(dsl_script_path))
        cvt = DedupConverter()
        cvt.visit(tree)
        cvt.resolve_unresolved()
        cvt.finalize_outputs()
    except ASTError:
        # ASTError 已经包含了模块信息，直接抛出
        raise
    except Exception as e:  # noqa: BLE001
        error_msg = str(e)

        if "name" in error_msg and "is not defined" in error_msg:
            import re as _re

            match = _re.search(r"name '(\w+)' is not defined", error_msg)
            if match:
                undefined_var = match.group(1)
                raise DSLError(
                    f"变量 '{undefined_var}' 未定义。在使用变量前，请先通过函数调用或赋值来定义它，例如: {undefined_var} = SOME_FUNCTION(...)",
                    context={"variable": undefined_var, "file": str(dsl_script_path)},
                    original_error=e
                )

        if isinstance(e, TypeError):
            raise DSLError(
                f"DSL 参数错误: {error_msg}",
                context={"file": str(dsl_script_path)},
                original_error=e
            )

        raise DSLError(
            f"DSL 执行错误: {error_msg}",
            context={"file": str(dsl_script_path)},
            original_error=e
        )

    try:
        out = cvt.g.to_dict()
        Path(output_path).write_text(
            json.dumps(out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:  # noqa: BLE001
        raise FileIOError(
            f"写入 graph JSON 失败",
            file_path=str(output_path),
            original_error=e
        )


__all__ = ["convert_dsl_to_graph"]
