#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py
=======

程序入口。

职责：
- 处理与运行环境相关的事项（例如 Windows 控制台编码）
- 调用 `src.pipeline.run_full_pipeline` 执行完整 DSL -> .melsave 流水线

具体的 DSL 解析、graph 处理与存档生成逻辑已全部迁移到 `src/` 下的模块中，
方便后续维护和扩展，不再在 main.py 中堆积业务代码。
"""

import os
import sys

from src.pipeline import run_full_pipeline


# Windows 下确保控制台能正常打印 UTF-8
if os.name == "nt":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # 旧版 Python 可能没有 reconfigure，静默忽略
        pass


def main() -> None:
    """命令行入口：委托给 src.pipeline.run_full_pipeline。"""
    run_full_pipeline()


if __name__ == "__main__":
    main()

