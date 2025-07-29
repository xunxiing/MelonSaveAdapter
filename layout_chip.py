import json
from collections import defaultdict
from typing import List, Dict, Any

# --- 布局配置 ---
# 您可以根据最终效果微调这些值
X_SPACING = 800.0  # 节点“列”之间的水平距离
Y_SPACING = 600.0  # 同一列中节点之间的最小垂直距离
GLOBAL_X_OFFSET = -11000.0 # 整体向左平移，以适应画布

# --- 文件名 (仅在独立运行时使用) ---
INPUT_FILENAME = 'ungraph.json'
OUTPUT_FILENAME = 'ungraph_layouted_ultimate.json'


# --- 全新的“ALAP + 质心迭代”布局引擎 ---

def parse_graph(nodes: List[Dict[str, Any]]) -> tuple:
    """解析节点列表，构建布局所需的数据结构。"""
    predecessors = defaultdict(list)
    successors = defaultdict(list)
    node_map = {node['Id']: node for node in nodes}

    for node_id, node in node_map.items():
        for input_port in node.get('Inputs', []):
            connection = input_port.get('connectedOutputIdModel')
            if connection and 'NodeId' in connection:
                source_id = connection['NodeId']
                if source_id in node_map:
                    successors[source_id].append(node_id)
                    predecessors[node_id].append(source_id)
    return predecessors, successors, list(node_map.keys())

def calculate_alap_layers(node_ids: list, predecessors: dict, successors: dict) -> dict:
    """
    核心升级：使用 ALAP (As Late As Possible) 算法分层。
    这会将节点尽可能地向右推，避免在第一层堆积。
    """
    # 1. 先进行一次ASAP（从左到右）分层，以确定图的总深度
    asap_layers = {}
    q = [n for n in node_ids if not predecessors[n]]
    for node_id in q: asap_layers[node_id] = 0
    
    head = 0
    processed_in_asap = set(q)
    while head < len(q):
        u = q[head]; head += 1
        for v in successors[u]:
            if v not in asap_layers:
                asap_layers[v] = 0
            asap_layers[v] = max(asap_layers[v], asap_layers[u] + 1)
            if v not in processed_in_asap:
                q.append(v)
                processed_in_asap.add(v)
    
    max_layer = max(asap_layers.values()) if asap_layers else 0

    # 2. 进行ALAP（从右到左）分层
    alap_layers = {}
    q = [n for n in node_ids if not successors[n]]
    for node_id in q: alap_layers[node_id] = max_layer
    
    head = 0
    processed_in_alap = set(q)
    while head < len(q):
        u = q[head]; head += 1
        for v in predecessors[u]:
            if v not in alap_layers:
                alap_layers[v] = max_layer
            alap_layers[v] = min(alap_layers[v], alap_layers[u] - 1)
            if v not in processed_in_alap:
                q.append(v)
                processed_in_alap.add(v)
            
    # 将层信息组织成字典
    layers_map = defaultdict(list)
    for node_id, layer in alap_layers.items():
        layers_map[layer].append(node_id)
        
    return layers_map

def iterative_barycenter_positioning(layers: dict, predecessors: dict, successors: dict) -> dict:
    """
    核心升级：使用多轮质心迭代优化垂直位置，以最大程度减少线条交叉。
    """
    positions = {}
    # 初始化Y坐标
    for i in sorted(layers.keys()):
        for j, node_id in enumerate(layers[i]):
            positions[node_id] = {'y': j * Y_SPACING}

    # 进行多轮迭代优化
    for _ in range(10): # 10轮迭代通常足够收敛
        # 从左到右 pass (基于父节点)
        for i in sorted(layers.keys()):
            for node_id in layers[i]:
                parent_ys = [positions[p]['y'] for p in predecessors[node_id] if p in positions]
                if parent_ys:
                    positions[node_id]['y'] = sum(parent_ys) / len(parent_ys)
        
        # 从右到左 pass (基于子节点)
        for i in sorted(layers.keys(), reverse=True):
            for node_id in layers[i]:
                child_ys = [positions[s]['y'] for s in successors[node_id] if s in positions]
                if child_ys:
                    positions[node_id]['y'] = sum(child_ys) / len(child_ys)

    return positions

def resolve_overlaps_and_finalize(layers: dict, temp_positions: dict) -> dict:
    """最后一步：解决重叠，并最终确定X,Y坐标。"""
    final_positions = {}
    for i in sorted(layers.keys()):
        # 过滤掉不在 temp_positions 中的节点，以防万一
        nodes_in_layer = sorted(
            [n for n in layers[i] if n in temp_positions],
            key=lambda n: temp_positions[n]['y']
        )
        
        # 解决重叠
        for j in range(1, len(nodes_in_layer)):
            prev_node, curr_node = nodes_in_layer[j-1], nodes_in_layer[j]
            min_y = temp_positions[prev_node]['y'] + Y_SPACING
            if temp_positions[curr_node]['y'] < min_y:
                temp_positions[curr_node]['y'] = min_y
                
        # 分配最终坐标
        for node_id in nodes_in_layer:
            final_positions[node_id] = {'x': i * X_SPACING, 'y': temp_positions[node_id]['y']}
            
    # 垂直居中整个布局
    all_ys = [pos['y'] for pos in final_positions.values()]
    if all_ys:
        center_offset = (min(all_ys) + max(all_ys)) / 2.0
        for node_id in final_positions:
            final_positions[node_id]['y'] -= center_offset
            
    return final_positions


def find_and_update_chip_graph(data: dict, final_positions: dict) -> bool:
    """在JSON中找到芯片图数据并更新节点坐标。"""
    try:
        # 路径可能因存档结构而异，这里假设是标准结构
        save_obj = data['saveObjectContainers'][0]['saveObjects']
        for meta_data in save_obj['saveMetaDatas']:
            if meta_data.get('key') == 'chip_graph':
                graph_data = json.loads(meta_data['stringValue'])
                nodes_updated = 0
                for node in graph_data.get('Nodes', []):
                    if node['Id'] in final_positions:
                        pos = final_positions[node['Id']]
                        node['VisualPosition']['x'] = pos['x'] + GLOBAL_X_OFFSET
                        node['VisualPosition']['y'] = pos['y']
                        nodes_updated += 1
                
                if nodes_updated > 0:
                    meta_data['stringValue'] = json.dumps(graph_data, separators=(',', ':'))
                    print(f"   在'chip_graph'中更新了 {nodes_updated} 个节点的位置。")
                    return True
        print("   警告: 在JSON中找到了'chip_graph'，但没有需要更新坐标的匹配节点。")
        return False
    except (KeyError, IndexError, TypeError) as e:
        print(f"错误：导航JSON结构时出错: {e}。请检查存档文件结构是否正确。")
        return False

# --- 新增：可供外部调用的主函数 ---
def run_layout_engine(chip_nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    接收节点列表，执行完整的布局算法，并返回最终位置。
    这是被 main.py 调用的核心入口。
    """
    print("1. 核心步骤: 执行 ALAP 分层...")
    predecessors, successors, node_ids = parse_graph(chip_nodes)
    layers = calculate_alap_layers(node_ids, predecessors, successors)
    print(f"   完成。图被分为 {len(layers)} 个层级。")

    print("2. 核心步骤: 执行多轮质心迭代...")
    temp_positions = iterative_barycenter_positioning(layers, predecessors, successors)
    print("   完成。")
    
    print("3. 最终整理: 解决重叠并垂直居中...")
    final_positions = resolve_overlaps_and_finalize(layers, temp_positions)
    print("   完成。")
    
    return final_positions

# --- 主执行流程 (用于独立运行) ---
if __name__ == '__main__':
    print("🚀 启动终极布局算法 (独立运行模式)...")
    
    try:
        with open(INPUT_FILENAME, 'r', encoding='utf-8') as f:
            full_data = json.load(f)
        chip_graph_str = next(md['stringValue'] for md in full_data['saveObjectContainers'][0]['saveObjects']['saveMetaDatas'] if md['key'] == 'chip_graph')
        chip_nodes = json.loads(chip_graph_str).get('Nodes', [])
    except Exception as e:
        print(f"❌ 错误: 无法在 '{INPUT_FILENAME}' 中读取或找到芯片数据。详情: {e}")
        exit()

    print(f"✅ 找到 {len(chip_nodes)} 个节点。")
    
    # 调用新的核心函数
    final_positions = run_layout_engine(chip_nodes)

    print("4. 使用新坐标更新JSON文件...")
    if find_and_update_chip_graph(full_data, final_positions):
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=4) # 独立运行时使用 indent=4 方便查看
        print(f"\n🎉 成功！已生成终极布局文件: '{OUTPUT_FILENAME}'")
    else:
        print("❌ 致命错误: 无法在JSON文件中找到 'chip_graph' 以进行更新。")