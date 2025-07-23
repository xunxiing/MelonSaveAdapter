#!/usr/bin/env python3
"""
批量添加模块脚本 (batch_add_modules.py)
=================================================
更新：现在 **所有参数都有默认值**，直接双击/运行脚本即可。

- 不带参数：默认读取同目录下
  - `modules.json`  (要添加的模块列表)
  - `data.json`     (游戏存档)
  - `allmod.json`   (所有模块定义)
  并输出 `data_modified_batch.json`。
- 仍可通过命令行覆盖默认路径。

示例：
```bash
python batch_add_modules.py             # 使用默认文件名
python batch_add_modules.py -m mods.json -d save.json -a defs.json -o out.json -c 0.7
```

更新记录：
- 2025-07-23：加入 **大小写无关** 的模糊匹配逻辑。
- 2025-07-23：支持按 *display_name* 匹配，内部仍使用复杂名称；改动极小。
"""

import argparse
import importlib
import json
import sys
from difflib import get_close_matches
from pathlib import Path
from typing import List

# 动态导入 add_module，确保与本脚本同目录
try:
    add_module = importlib.import_module("add_module")
except ModuleNotFoundError:
    print(" 无法找到 add_module.py，请确保它与本脚本位于同一目录。")
    sys.exit(1)

# 复用 add_module 中的工具
create_new_node = add_module.create_new_node
DATA_TYPE_MAP = add_module.DATA_TYPE_MAP  # noqa: F401
OPERATION_TYPE_MAP = add_module.OPERATION_TYPE_MAP  # noqa: F401

# ------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------

def fuzzy_best_match(name: str, candidates: List[str], cutoff: float = 0.5) -> str | None:
    """返回与 ``name`` 最接近的候选者（**忽略大小写**）；若匹配度低于 ``cutoff`` 返回 ``None``。"""
    name_lower = name.lower()
    match_lower = get_close_matches(name_lower, candidates, n=1, cutoff=cutoff)
    return match_lower[0] if match_lower else None


def add_modules(
    modules_wanted: List[str],
    data_path: Path,
    allmod_path: Path,
    output_path: Path,
    cutoff: float = 0.5,
) -> None:
    """批量添加模块核心逻辑。"""
    # 1. 加载数据文件
    try:
        with data_path.open("r", encoding="utf-8") as f:
            game_data = json.load(f)
        with allmod_path.open("r", encoding="utf-8") as f:
            all_modules = json.load(f)
    except Exception as exc:
        print(f" 加载文件失败: {exc}")
        sys.exit(1)

    # 2. 构建候选映射：内部名 + display_name → 内部名
    candidate_map: dict[str, str] = {}
    for internal_key, info in all_modules.items():
        candidate_map[internal_key.lower()] = internal_key
        friendly = str(info.get("display_name", "")).strip()
        if friendly:
            candidate_map[friendly.lower()] = internal_key

    candidate_names = list(candidate_map.keys())  # 均为小写字符串

    # 3. 定位 chip_graph
    chip_graph_meta = None
    for container in game_data.get("saveObjectContainers", []):
        for meta in container.get("saveObjects", {}).get("saveMetaDatas", []):
            if meta.get("key") == "chip_graph":
                chip_graph_meta = meta
                break
        if chip_graph_meta:
            break

    if chip_graph_meta is None:
        print(" 在 data.json 中找不到 'chip_graph'，请确认存档文件正确。")
        sys.exit(1)

    chip_graph_data = json.loads(chip_graph_meta["stringValue"])
    existing_nodes = chip_graph_data["Nodes"]

    # 4. 开始批量处理
    success, fail = [], []

    for raw_name in modules_wanted:
        match_key_lower = fuzzy_best_match(raw_name, candidate_names, cutoff)
        if match_key_lower is None:
            print(f"️ 未找到与 '{raw_name}' 相近的模块，跳过。")
            fail.append(raw_name)
            continue

        internal_key = candidate_map[match_key_lower]  # 使用内部复杂名称
        module_info = all_modules[internal_key]
        new_node = create_new_node(internal_key, module_info, existing_nodes)
        if new_node is None:
            print(f"️ 创建节点 '{internal_key}' 失败，跳过。")
            fail.append(raw_name)
            continue

        existing_nodes.append(new_node)
        success.append(internal_key)
        print(f" 已添加: {internal_key}")

    # 5. 保存结果
    chip_graph_meta["stringValue"] = json.dumps(
        chip_graph_data, ensure_ascii=False, indent=2
    )
    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(game_data, f, ensure_ascii=False, indent=4)
        print("\n 全部处理完成!")
        print(f"   成功添加 {len(success)} 个模块 → {output_path}")
        if fail:
            print(f"   ️ 有 {len(fail)} 个模块未处理: {', '.join(fail)}")
    except Exception as exc:
        print(f" 保存输出文件失败: {exc}")
        sys.exit(1)


# ------------------------------------------------------------
# CLI 入口
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量添加模块到芯片图 (基于 add_module.py)"
    )
    parser.add_argument(
        "-m",
        "--modules",
        type=Path,
        default=Path("modules.json"),
        help="包含待添加模块名数组的 JSON 文件路径 (默认: ./modules.json)",
    )
    parser.add_argument(
        "-d",
        "--data",
        default=Path("data.json"),
        type=Path,
        help="游戏存档 data.json 路径 (默认: ./data.json)",
    )
    parser.add_argument(
        "-a",
        "--allmod",
        default=Path("allmod.json"),
        type=Path,
        help="所有模块定义 allmod.json 路径 (默认: ./allmod.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=Path("data_modified_batch.json"),
        type=Path,
        help="输出文件路径 (默认: ./data_modified_batch.json)",
    )
    parser.add_argument(
        "-c",
        "--cutoff",
        default=0.4,
        type=float,
        help="模糊匹配阈值 (0~1)，越高越严格 (默认: 0.1)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 读取目标模块列表
    try:
        with args.modules.open("r", encoding="utf-8") as f:
            modules_wanted = json.load(f)
        if not isinstance(modules_wanted, list):
            raise ValueError("模块文件应是字符串数组！")
    except Exception as exc:
        print(f" 加载模块列表失败: {exc}")
        sys.exit(1)

    add_modules(
        modules_wanted, args.data, args.allmod, args.output, args.cutoff
    )


if __name__ == "__main__":
    main()
