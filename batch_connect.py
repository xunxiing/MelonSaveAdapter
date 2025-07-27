#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量添加端口连接脚本
---------------------------------------------
假设目录中已有：
  - Data.json               原始图数据（结构与现有 connect_ports.py 相同）
  - connect.json            连接指令（上面示例）
脚本执行完毕后会生成：
  - Data_modified.json      已写入新连接的图数据
使用方法：
  python connect_batch.py
"""

import json
import os
import sys

# ------------ 配置区（必要时可改）------------
GRAPH_IN      = "Data_modified.json"          # 原始图数据
GRAPH_OUT     = "ungraph.json" # 输出文件
CONNECT_IN    = "output.json"       # 连接指令
# -------------------------------------------


# ---------- 与现有脚本相同的工具函数 ----------
def find_chip_graph(data: dict):
    """在复杂 JSON 中提取 chip_graph 数据及其所在的 meta_data 引用"""
    for container in data.get("saveObjectContainers", []):
        for meta in container.get("saveObjects", {}).get("saveMetaDatas", []):
            if meta.get("key") == "chip_graph":
                graph_str = meta.get("stringValue", "")
                return json.loads(graph_str), meta
    return None, None


def build_node_lookup(graph_data: dict):
    """
    构建两个索引：
      1. 节点字典：{'ClassName : NodeId' : node_dict}
      2. 端口 ID 到端口对象的映射（查重、调试时有用）
    """
    nodes = {}
    ports = {}
    for node in graph_data.get("Nodes", []):
        # 节点的“类型 : Id” 形式，方便与指令中的 node_id 对齐
        node_key = node['Id']  
        nodes[node_key] = node
        # 收集输入输出端口，便于 debug
        for p in node.get("Inputs", []):
            ports[p["Id"]] = p
        for p in node.get("Outputs", []):
            ports[p["Id"]] = p
    return nodes, ports
# -------------------------------------------


def read_json(path: str, desc: str):
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


def main():
    # 1️⃣ 载入 Data.json 和 connect.json
    data         = read_json(GRAPH_IN, "图数据")
    connections  = read_json(CONNECT_IN, "连接指令")

    # 2️⃣ 提取 chip_graph（核心拓扑）
    graph_data, graph_meta = find_chip_graph(data)
    if graph_data is None:
        print("错误：未在图数据中找到 chip_graph 字段")
        sys.exit(1)

    # 3️⃣ 构建节点与端口索引
    node_lookup, port_lookup = build_node_lookup(graph_data)

    # 4️⃣ 遍历连接指令，逐条写入
    for idx, conn in enumerate(connections, 1):
        try:
            f_node_key   = conn["from_node_id"]
            t_node_key   = conn["to_node_id"]
            f_port_idx   = conn["from_port_index"]
            t_port_idx   = conn["to_port_index"]

            # ------ 获取节点对象 ------
            if f_node_key not in node_lookup or t_node_key not in node_lookup:
                raise KeyError("node_id 不存在于图中")

            from_node = node_lookup[f_node_key]
            to_node   = node_lookup[t_node_key]

            # ------ 获取端口对象 ------
            try:
                from_port = from_node["Outputs"][f_port_idx]
            except IndexError:
                raise IndexError("from_port_index 超出范围")

            try:
                to_port   = to_node["Inputs"][t_port_idx]
            except IndexError:
                raise IndexError("to_port_index 超出范围")

            # ------ 写入连接 ------
            # 在目标输入端口记录来源
            to_port["connectedOutputIdModel"] = {
                "Id":     from_port["Id"],
                "NodeId": from_node["Id"],
            }

            # 在源输出端口追加新连接（确保列表存在）
            from_port.setdefault("ConnectedInputsIds", []).append({
                "Id":     to_port["Id"],
                "NodeId": to_node["Id"],
            })

            print(f" 第 {idx} 条连接成功：{f_node_key}[{f_port_idx}] → {t_node_key}[{t_port_idx}]")

        except (KeyError, IndexError) as e:
            print(f" 第 {idx} 条连接失败：{e}")

    # 5️⃣ 更新 chip_graph 串并保存
    graph_meta["stringValue"] = json.dumps(graph_data, ensure_ascii=False)
    with open(GRAPH_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"\n 批量连接完成，结果已写入 “{GRAPH_OUT}”")


if __name__ == "__main__":
    main()
