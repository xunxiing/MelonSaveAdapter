# constantvalue.py (已重构)

import json
import math
from typing import Dict, List, Any, Union, Tuple

# --- 辅助函数 (无变化) ---

def create_vector_json_string(x: float, y: float, z: float) -> str:
    """
    根据x, y, z坐标创建一个符合游戏格式的复杂向量JSON字符串。
    """
    w = 0.0
    sqr_magnitude = x*x + y*y + z*z
    magnitude = math.sqrt(sqr_magnitude)

    norm_x, norm_y, norm_z = (0.0, 0.0, 0.0)
    if magnitude > 1e-9:
        norm_x = x / magnitude
        norm_y = y / magnitude
        norm_z = z / magnitude

    vector_data = {
        "x": x, "y": y, "z": z, "w": w,
        "normalized": {
            "x": norm_x, "y": norm_y, "z": norm_z, "w": w,
            "normalized": {
                "x": norm_x, "y": norm_y, "z": norm_z, "w": w,
                "magnitude": 1.0 if magnitude > 1e-9 else 0.0,
                "sqrMagnitude": 1.0 if magnitude > 1e-9 else 0.0
            },
            "magnitude": 1.0 if magnitude > 1e-9 else 0.0,
            "sqrMagnitude": 1.0 if magnitude > 1e-9 else 0.0,
        },
        "magnitude": magnitude,
        "sqrMagnitude": sqr_magnitude
    }
    return json.dumps(vector_data, separators=(',', ':'))


# --- 核心修改函数 (重构为内存操作) ---

def _modify_single_node(
    game_data: Dict[str, Any],
    node_id: str,
    new_value: Union[str, float, int, List[Any]],
    value_type: str
) -> bool:
    """
    修改 Constant 节点（含 ArrayXxx 和 DataType 更新）
    """
    try:
        save_object = game_data['saveObjectContainers'][0]['saveObjects']
        meta_datas = save_object['saveMetaDatas']

        chip_graph_meta = next((meta for meta in meta_datas if meta.get('key') == 'chip_graph'), None)
        if not chip_graph_meta:
            print("未找到 chip_graph")
            return False

        graph_data = json.loads(chip_graph_meta['stringValue'])
        nodes = graph_data.get('Nodes', [])

        target_node = next((n for n in nodes if node_id in n.get('Id','')), None)
        if not target_node:
            print(f"找不到节点 {node_id}")
            return False

        # ---- 先准备 DataType 的字符串名称 ----
        type_map = {
            "string": "String",
            "decimal": "Number",
            "vector": "Vector",
            "array_string": "ArrayString",
            "array_number": "ArrayNumber",
            "array_vector": "ArrayVector",
        }
        gate_type = type_map[value_type]

        # ---- 更新 GateDataType ----
        target_node["GateDataType"] = gate_type

        # ---- 更新输出端口类型 ----
        for port in target_node.get("Outputs", []):
            port["DataType"] = gate_type

        # ---- 解析原 SaveData ----
        save_data_obj = json.loads(target_node["SaveData"]) if target_node.get("SaveData") else {}

        # ==========================
        #   标量处理
        # ==========================
        if value_type == "string":
            save_data_obj["DataValue"] = str(new_value)

        elif value_type == "decimal":
            save_data_obj["DataValue"] = str(float(new_value))

        elif value_type == "vector":
            save_data_obj["DataValue"] = json.dumps({
                "x": new_value[0],
                "y": new_value[1],
                "z": new_value[2],
                "w": 0.0,
                "magnitude": 0.0,
                "sqrMagnitude": 0.0
            })

        # ==========================
        #     ArrayString
        # ==========================
        elif value_type == "array_string":
            save_data_obj["DataValue"] = json.dumps(new_value, ensure_ascii=False, indent=2)
            save_data_obj["IsMultiline"] = None

        # ==========================
        #     ArrayNumber
        # ==========================
        elif value_type == "array_number":
            arr = [float(v) for v in new_value]
            save_data_obj["DataValue"] = json.dumps(arr, ensure_ascii=False, indent=2)
            save_data_obj["IsMultiline"] = None

        # ==========================
        #     ArrayVector
        # ==========================
        elif value_type == "array_vector":
            vecs = []
            for v in new_value:
                if isinstance(v, dict):
                    x, y, z = v["x"], v["y"], v["z"]
                    w = v.get("w", 0.0)
                else:
                    # 支持3维或4维向量
                    if len(v) == 4:
                        x, y, z, w = v[0], v[1], v[2], v[3]
                    else:
                        x, y, z = v[0], v[1], v[2]
                        w = 0.0
                vecs.append({
                    "x": x, "y": y, "z": z, "w": w,
                    "magnitude": 0.0,
                    "sqrMagnitude": 0.0
                })
            save_data_obj["DataValue"] = json.dumps(vecs, ensure_ascii=False, indent=2)
            save_data_obj["IsMultiline"] = None

        # ---------------- 更新 SaveData ----------------
        target_node["SaveData"] = json.dumps(save_data_obj)
        chip_graph_meta["stringValue"] = json.dumps(graph_data, indent=2)

        return True

    except Exception as e:
        print("修改常量错误:", e)
        return False

    except (KeyError, IndexError, StopIteration) as e:
        print(f"处理JSON时发生错误：找不到预期的键或索引。路径可能不正确。错误详情: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"解析内嵌JSON字符串时出错。文件可能已损坏。错误详情: {e}")
        return False


def apply_constant_modifications(game_data: Dict[str, Any], instructions: List[Dict]) -> Dict[str, Any]:
    """
    根据指令列表，批量修改内存中的游戏存档数据。

    :param game_data: 游戏存档内容的Python字典。
    :param instructions: 一个指令列表，每个指令是包含 'node_id', 'new_value', 'value_type' 的字典。
    :return: 修改后的游戏存档字典。
    """
    num_success = 0
    for inst in instructions:
        print(f"  > 正在修改常量节点 {inst['node_id'][:8]}... 类型: {inst['value_type']}, 值: {inst['new_value']}")
        success = _modify_single_node(
            game_data=game_data,
            node_id=inst['node_id'],
            new_value=inst['new_value'],
            value_type=inst['value_type']
        )
        if success:
            num_success += 1
    
    print(f"常量修改完成: {num_success}/{len(instructions)} 个成功。")
    return game_data