#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量添加端口连接脚本
---------------------------------------------
可以作为独立脚本运行，也可以作为模块被其他脚本导入调用。
【已修改】增加了ID归一化逻辑，以处理空格不一致的问题。
"""

import json
import os
import re  # <-- 导入正则表达式模块
import sys
from typing import Dict, Any

# ------------ 配置区（仅在独立运行时生效）------------
GRAPH_IN      = "Data_modified.json"
GRAPH_OUT     = "ungraph.json"
CONNECT_IN    = "output.json"
# ----------------------------------------------------

# ======================= 新增工具函数 =======================
def normalize_id(node_id_str: str) -> str:
    """
    归一化节点ID字符串，移除所有空白字符，以确保匹配的健壮性。
    例如：'Class : UUID' -> 'Class:UUID'
    """
    return re.sub(r'\s+', '', node_id_str)

# -----------------------------------------------------------

def find_chip_graph(data: Dict[str, Any]) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    """在复杂 JSON 中提取 chip_graph 数据及其所在的 meta_data 引用"""
    for container in data.get("saveObjectContainers", []):
        for meta in container.get("saveObjects", {}).get("saveMetaDatas", []):
            if meta.get("key") == "chip_graph":
                graph_str = meta.get("stringValue", "")
                try:
                    return json.loads(graph_str), meta
                except json.JSONDecodeError:
                    return None, None
    return None, None


def build_node_lookup(graph_data: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    构建节点索引。
    【已修改】使用归一化后的ID作为键，以避免空格问题。
    """
    nodes = {}
    ports = {}
    for node in graph_data.get("Nodes", []):
        # 使用归一化后的ID作为字典的键
        node_key = normalize_id(node['Id'])
        nodes[node_key] = node
        # 端口部分不变
        for p in node.get("Inputs", []):
            ports[p["Id"]] = p
        for p in node.get("Outputs", []):
            ports[p["Id"]] = p
    return nodes, ports


def read_json(path: str, desc: str) -> Dict[str, Any]:
    """读取 JSON 辅助函数，失败时输出中文提示并退出"""
    if not os.path.exists(path):
        print(f"错误：未找到 {desc} 文件 “{path}”")
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误：{desc} 文件 “{path}” 解析失败：{e}")
        sys.exit(1)
    return {}


# ======================= 核心逻辑函数 (已修改) =======================
def apply_connections(input_graph_path: str, connections_path: str, output_graph_path: str) -> bool:
    """
    读取存档文件和连接指令，应用连接，并写回存档。
    """
    data = read_json(input_graph_path, "图数据")
    connections = read_json(connections_path, "连接指令")

    graph_data, graph_meta = find_chip_graph(data)
    if graph_data is None:
        print(f"错误：未在 '{input_graph_path}' 中找到 chip_graph 字段")
        return False

    node_lookup, _ = build_node_lookup(graph_data)

    success_count = 0
    for idx, conn in enumerate(connections, 1):
        # 保存原始ID用于打印日志
        original_f_node_id = conn["from_node_id"]
        original_t_node_id = conn["to_node_id"]

        try:
            # 【已修改】在查找前，对指令中的ID进行同样的归一化处理
            f_node_key = normalize_id(original_f_node_id)
            t_node_key = normalize_id(original_t_node_id)
            f_port_idx = conn["from_port_index"]
            t_port_idx = conn["to_port_index"]

            if f_node_key not in node_lookup or t_node_key not in node_lookup:
                # 【已修改】在错误信息中使用原始ID，方便调试
                raise KeyError(f"节点ID不存在: from='{original_f_node_id}' or to='{original_t_node_id}'")

            from_node = node_lookup[f_node_key]
            to_node = node_lookup[t_node_key]

            from_port = from_node["Outputs"][f_port_idx]
            to_port = to_node["Inputs"][t_port_idx]

            to_port["connectedOutputIdModel"] = {"Id": from_port["Id"], "NodeId": from_node["Id"]}
            from_port.setdefault("ConnectedInputsIds", []).append({"Id": to_port["Id"], "NodeId": to_node["Id"]})
            
            # 打印日志时，可以使用更简洁的名称
            f_name = original_f_node_id.split(':')[0].strip()
            t_name = original_t_node_id.split(':')[0].strip()
            print(f"  第 {idx} 条连接成功: {f_name}[{f_port_idx}] → {t_name}[{t_port_idx}]")
            success_count += 1

        except (KeyError, IndexError) as e:
            # 错误信息现在会显示原始ID，更易于理解
            print(f"  第 {idx} 条连接失败: 指令 {conn} -> 错误: {e}")

    graph_meta["stringValue"] = json.dumps(graph_data, ensure_ascii=False)
    with open(output_graph_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    print(f"\n批量连接完成, {success_count}/{len(connections)} 条成功。结果已写入 “{output_graph_path}”")
    return True


def main():
    """独立运行脚本时的主函数"""
    print("--- 以独立脚本模式运行批量连线 ---")
    if not os.path.exists(GRAPH_IN) and os.path.exists(GRAPH_OUT):
         print(f"提示：未找到输入文件 '{GRAPH_IN}'，将使用输出文件 '{GRAPH_OUT}' 作为输入。")
         input_file = GRAPH_OUT
    else:
         input_file = GRAPH_IN

    apply_connections(input_file, CONNECT_IN, GRAPH_OUT)


if __name__ == "__main__":
    main()