import json
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Set

# --- 布局配置 ---
# 您可以根据最终效果微调这些值
X_SPACING = 800.0  # 节点“列”之间的水平距离
Y_SPACING = 600.0  # 同一列中节点之间的最小垂直距离
GLOBAL_X_OFFSET = -2000.0 # 整体向左平移，以适应画布

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

# —— 将跨多列的边"虚拟拆边"为相邻列边，并构建仅相邻列的前驱/后继映射 ——
def _insert_dummies_and_build_adj(predecessors, successors, col_node, cols):
    cols_aug = {c: list(arr) for c, arr in cols.items()}  # 每列包含真实节点，后续会加入 dummy
    pred_adj = defaultdict(list)  # 仅相邻列的前驱（含 dummy）
    succ_adj = defaultdict(list)
    dummy_id = 0

    def new_dummy():
        nonlocal dummy_id
        dummy_id += 1
        return f"__DUMMY__{dummy_id}"

    # 遍历每条有向边，按列差逐步"走过去"
    for u, outs in successors.items():
        cu = col_node.get(u)
        if cu is None: 
            continue
        for v in outs:
            cv = col_node.get(v)
            if cv is None or cv == cu: 
                continue
            step = 1 if cv > cu else -1
            prev = u
            for c in range(cu + step, cv + step, step):
                if c == cv:
                    succ_adj[prev].append(v)
                    pred_adj[v].append(prev)
                else:
                    d = new_dummy()
                    cols_aug.setdefault(c, []).append(d)
                    col_node[d] = c
                    succ_adj[prev].append(d)
                    pred_adj[d].append(prev)
                    prev = d
    return cols_aug, pred_adj, succ_adj

def _bary_sweeps_with_dummies(cols_aug, col_node, pred_adj, succ_adj, passes=4):
    # 多轮：Left→Right 用左邻列的中位秩；Right→Left 用右邻列的中位秩
    def order_maps(cols):
        return {c: {nid: i for i, nid in enumerate(cols.get(c, []))} for c in cols}

    col_keys = sorted(cols_aug.keys())
    for _ in range(passes):
        om = order_maps(cols_aug)
        # ---- L → R ----
        for c in col_keys[1:]:
            arr = cols_aug.get(c, [])
            if not arr: 
                continue
            left = om.get(c - 1, {})
            def bary_left(nid):
                idxs = [left[x] for x in pred_adj.get(nid, []) if x in left]
                return (sum(idxs) / len(idxs)) if idxs else om[c].get(nid, 0)
            arr.sort(key=lambda nid: (bary_left(nid), om[c][nid]))
            om[c] = {nid: i for i, nid in enumerate(arr)}
        # ---- R → L ----
        om = order_maps(cols_aug)
        for c in reversed(col_keys[:-1]):
            arr = cols_aug.get(c, [])
            if not arr: 
                continue
            right = om.get(c + 1, {})
            def bary_right(nid):
                idxs = [right[x] for x in succ_adj.get(nid, []) if x in right]
                return (sum(idxs) / len(idxs)) if idxs else om[c].get(nid, 0)
            arr.sort(key=lambda nid: (bary_right(nid), om[c][nid]))
            om[c] = {nid: i for i, nid in enumerate(arr)}

def iterative_barycenter_positioning(layers: dict, predecessors: dict, successors: dict) -> dict:
    """
    核心升级：使用虚拟拆边和双向多轮中位数扫掠优化垂直位置，以最大程度减少线条交叉。
    """
    positions = {}
    
    # 1) 列 → 节点
    cols: Dict[int, List[str]] = defaultdict(list)
    col_node = {}
    for layer, nodes in layers.items():
        for node_id in nodes:
            cols[layer].append(node_id)
            col_node[node_id] = layer
    for c in cols:
        cols[c].sort()  # 初始稳定序

    # 2) 先"虚拟拆边"为相邻列边，再做双向多轮中位数扫掠，得到更好的列内顺序
    col_node_aug = dict(col_node)  # 会加 dummy 的列号
    cols_aug, pred_adj, succ_adj = _insert_dummies_and_build_adj(
        predecessors, successors, col_node_aug, cols
    )
    _bary_sweeps_with_dummies(cols_aug, col_node_aug, pred_adj, succ_adj, passes=4)

    # 3) 扫掠完成后，只对"真实节点"赋 y（dummy 仅参与排序，不输出坐标）
    y_order: Dict[str, float] = {}
    for c in sorted(cols_aug.keys()):
        real_nodes = [nid for nid in cols_aug[c] if not str(nid).startswith("__DUMMY__")]
        for idx, nid in enumerate(real_nodes):
            y_order[nid] = idx * Y_SPACING

    # 转换为返回格式
    for node_id, y in y_order.items():
        positions[node_id] = {'y': y}

    return positions

# -------------------------------------------------------------
# 交替扫掠的加权重心消交叉（不插 dummy，按列距离 1/Δcol 衰减）
# -------------------------------------------------------------
def _rebuild_order_maps(cols: Dict[int, List[str]]) -> Dict[int, Dict[str, int]]:
    return {c: {nid: i for i, nid in enumerate(cols.get(c, []))} for c in cols}

def _weighted_bary_wrt_side(n: str, side: str,
                            col_of: Dict[str, int],
                            order_maps: Dict[int, Dict[str, int]],
                            predecessors: Dict[str, List[str]],
                            successors: Dict[str, List[str]]) -> float:
    cn = col_of[n]
    if side == "left":
        neis = [p for p in predecessors.get(n, []) if p in col_of and col_of[p] < cn]
        if not neis:
            return order_maps[cn].get(n, 0)
        s = wsum = 0.0
        for p in neis:
            cp = col_of[p]
            idx = order_maps.get(cp, {}).get(p)
            if idx is None: 
                continue
            w = 1.0 / (cn - cp)  # 越近权重越大
            s += w * idx; wsum += w
        return s / wsum if wsum > 0 else order_maps[cn][n]
    else:  # "right"
        neis = [q for q in successors.get(n, []) if q in col_of and col_of[q] > cn]
        if not neis:
            return order_maps[cn].get(n, 0)
        s = wsum = 0.0
        for q in neis:
            cq = col_of[q]
            idx = order_maps.get(cq, {}).get(q)
            if idx is None:
                continue
            w = 1.0 / (cq - cn)
            s += w * idx; wsum += w
        return s / wsum if wsum > 0 else order_maps[cn][n]

def _minimize_crossings_by_sweeps(cols: Dict[int, List[str]],
                                  col_of: Dict[str, int],
                                  predecessors: Dict[str, List[str]],
                                  successors: Dict[str, List[str]],
                                  passes: int = 4) -> None:
    if not cols:
        return
    col_keys = sorted(cols.keys())
    for _ in range(passes):
        # Left -> Right：看左侧邻居
        order_maps = _rebuild_order_maps(cols)
        for c in col_keys[1:]:
            if c not in cols or not cols[c]: 
                continue
            arr = cols[c]
            arr.sort(key=lambda nid: (_weighted_bary_wrt_side(nid, "left", col_of, order_maps, predecessors, successors),
                                      order_maps[c][nid]))
            # 更新该列的映射，便于同轮后面的列使用更准确的位置
            order_maps[c] = {nid: i for i, nid in enumerate(arr)}

        # Right -> Left：看右侧邻居
        order_maps = _rebuild_order_maps(cols)
        for c in reversed(col_keys[:-1]):
            if c not in cols or not cols[c]:
                continue
            arr = cols[c]
            arr.sort(key=lambda nid: (_weighted_bary_wrt_side(nid, "right", col_of, order_maps, predecessors, successors),
                                      order_maps[c][nid]))
            order_maps[c] = {nid: i for i, nid in enumerate(arr)}

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

# -------------------------------------------------------------
# 鱼群式局部交换阶段（Pairwise Swap, at most once per pair）
# -------------------------------------------------------------

def _build_cluster_columns_for_positions(cluster: List[str],
                                         final_positions: Dict[str, Dict[str, float]]
                                         ) -> Tuple[Dict[int, List[str]], Dict[str, int], Dict[int, Dict[str, int]]]:
    """
    依据最终坐标把 cluster 内节点分到“列”（column）里，并建立列内的 rank（按 y 从小到大）。
    - 列号按：col = round((x - min_x_cluster) / X_SPACING)
    返回：
      cols: {col -> [nodes ordered by y]}
      col_of: {node -> col}
      rank_maps: {col -> {node -> rank_index}}
    """
    xs = [final_positions[n]['x'] for n in cluster if n in final_positions]
    if not xs:
        return {}, {}, {}
    min_x = min(xs)
    cols: Dict[int, List[str]] = defaultdict(list)
    col_of: Dict[str, int] = {}

    for n in cluster:
        if n not in final_positions:
            continue
        x = final_positions[n]['x']
        c = int(round((x - min_x) / X_SPACING))
        cols[c].append(n)
        col_of[n] = c

    # 每列按 y 排序并建立 rank
    rank_maps: Dict[int, Dict[str, int]] = {}
    for c, arr in cols.items():
        arr.sort(key=lambda nid: final_positions[nid]['y'])
        rank_maps[c] = {nid: i for i, nid in enumerate(arr)}
    return cols, col_of, rank_maps


def _count_inversions(A: List[str], B: List[str], rank_map: Dict[str, int]) -> int:
    """统计集合 A 的端点是否“在 rank 上方于”集合 B 的端点（ra > rb）→ 表示存在交叉。"""
    inv = 0
    for a in A:
        ra = rank_map.get(a)
        if ra is None: 
            continue
        for b in B:
            rb = rank_map.get(b)
            if rb is None:
                continue
            if ra > rb:
                inv += 1
    return inv


def _median_or_bary_rank(neis: List[str], rank_map: Dict[str, int]) -> float | None:
    vals = [rank_map[n] for n in neis if n in rank_map]
    if not vals:
        return None
    vals.sort()
    m = len(vals)
    if m % 2:
        return float(vals[m // 2])
    return 0.5 * (vals[m // 2 - 1] + vals[m // 2])


def _score_delta_if_swap(u: str, v: str, cur_col: int,
                         predecessors: Dict[str, List[str]],
                         successors: Dict[str, List[str]],
                         col_of: Dict[str, int],
                         cols: Dict[int, List[str]],
                         rank_maps: Dict[int, Dict[str, int]],
                         w_c: float = 1.0, w_m: float = 0.5) -> float:
    """
    只比较与 u,v 相关的边与秩：交叉项 + 重心项。
    返回 Δscore = after - before（负表示更好）
    """
    # 当前列内 rank
    rank_cur = rank_maps[cur_col]
    pos_u, pos_v = rank_cur[u], rank_cur[v]

    # 左列 / 右列的 rank
    rank_left  = rank_maps.get(cur_col - 1, {})
    rank_right = rank_maps.get(cur_col + 1, {})

    # 相邻列中的邻居
    Lu = [p for p in predecessors.get(u, []) if col_of.get(p) == cur_col - 1]
    Lv = [p for p in predecessors.get(v, []) if col_of.get(p) == cur_col - 1]
    Ru = [s for s in successors.get(u, [])   if col_of.get(s) == cur_col + 1]
    Rv = [s for s in successors.get(v, [])   if col_of.get(s) == cur_col + 1]

    # 交叉数（左右两侧独立统计）
    before_left  = _count_inversions(Lu, Lv, rank_left)
    after_left   = _count_inversions(Lv, Lu, rank_left)
    before_right = _count_inversions(Ru, Rv, rank_right)
    after_right  = _count_inversions(Rv, Ru, rank_right)

    cross_before = before_left + before_right
    cross_after  = after_left  + after_right

    # 重心（把左右的中位秩做平均）
    mu_left  = _median_or_bary_rank(Lu, rank_left)
    mv_left  = _median_or_bary_rank(Lv, rank_left)
    mu_right = _median_or_bary_rank(Ru, rank_right)
    mv_right = _median_or_bary_rank(Rv, rank_right)

    def bary_cost(pos, m1, m2):
        mm = [m for m in (m1, m2) if m is not None]
        if not mm:
            return 0.0
        avg = sum(mm) / len(mm)
        return abs(pos - avg)

    median_before = bary_cost(pos_u, mu_left, mu_right) + bary_cost(pos_v, mv_left, mv_right)
    median_after  = bary_cost(pos_v, mu_left, mu_right) + bary_cost(pos_u, mv_left, mv_right)

    score_before = w_c * cross_before + w_m * median_before
    score_after  = w_c * cross_after  + w_m * median_after
    return score_after - score_before


def _apply_swap_in_column(u: str, v: str, col: int,
                          cols: Dict[int, List[str]],
                          rank_maps: Dict[int, Dict[str, int]],
                          final_positions: Dict[str, Dict[str, float]]) -> None:
    """交换同列中的相邻两点 u,v （只交换 y），维护列数组与 rank_map 一致性。"""
    arr = cols[col]
    iu, iv = rank_maps[col][u], rank_maps[col][v]
    if iu > iv:
        iu, iv = iv, iu
        u, v = v, u

    # 交换 y
    yu, yv = final_positions[u]['y'], final_positions[v]['y']
    final_positions[u]['y'], final_positions[v]['y'] = yv, yu

    # 交换顺序及 rank
    arr[iu], arr[iv] = arr[iv], arr[iu]
    rank_maps[col][arr[iu]] = iu
    rank_maps[col][arr[iv]] = iv


def _fishschool_local_swaps(predecessors: Dict[str, List[str]],
                            successors: Dict[str, List[str]],
                            undirected: Dict[str, Set[str]],
                            clusters: List[List[str]],
                            final_positions: Dict[str, Dict[str, float]],
                            max_pass: int = 3) -> Dict[str, Dict[str, float]]:
    """
    在现有坐标基础上进行“同列相邻对”的一次性交换启发式：
      - 逐 cluster / 逐列遍历；
      - 对相邻对 (u,v) 若 Δscore < 0 且此对未交换过 → 交换，加入队列的邻近对继续评估；
      - 同一对在整个阶段至多交换一次（避免抖动）。
    """
    swapped_once: Set[int] = set()  # 以 hash_pair 记录“全局只交换一次”
    def hash_pair(a: str, b: str) -> int:
        if a > b: a, b = b, a
        return (hash(a) << 1) ^ hash(b)

    for _ in range(max_pass):
        # 遍历每个 cluster
        for cluster in clusters:
            # 基于最终坐标重建该 cluster 的列与秩
            cols, col_of, rank_maps = _build_cluster_columns_for_positions(cluster, final_positions)
            if not cols:
                continue

            # 每列做“冒泡式”邻对评估
            for c, arr in cols.items():
                if len(arr) <= 1:
                    continue
                # 初始化相邻对队列
                Q = [(i, i+1) for i in range(len(arr) - 1)]
                while Q:
                    i, j = Q.pop(0)
                    u, v = arr[i], arr[j]
                    key = hash_pair(u, v)
                    if key in swapped_once:
                        continue
                    delta = _score_delta_if_swap(u, v, c, predecessors, successors, col_of, cols, rank_maps)
                    if delta < 0:  # 更优 → 交换，并标记一次性
                        _apply_swap_in_column(u, v, c, cols, rank_maps, final_positions)
                        swapped_once.add(key)
                        # 受影响的邻对入队
                        if i-1 >= 0: Q.append((i-1, i))
                        if j+1 < len(arr): Q.append((j, j+1))
    return final_positions

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
    print("   完成.")
    
    # === 新增：鱼群式局部交换阶段（在所有布局逻辑之后） ===
    print("4. 局部交换优化（鱼群式） …")
    # 为了与现有代码兼容，我们构造一些必要的参数
    # 注意：这里的 'undirected' 和 'clusters' 是简化处理的，可能与您的原始意图有细微差别
    # 如果您的布局算法中已经有这些概念，请替换成正确的版本
    undirected_graph = defaultdict(set)
    for u, vs in successors.items():
        for v in vs:
            undirected_graph[u].add(v)
            undirected_graph[v].add(u)
    
    # 简单地将所有节点视为一个大集群
    # 如果您的算法是多集群的，请使用正确的集群划分逻辑
    all_node_ids = list(final_positions.keys())
    simple_clusters = [all_node_ids] if all_node_ids else []

    final_positions = _fishschool_local_swaps(predecessors, successors, undirected_graph, simple_clusters, final_positions, max_pass=3)
    print("   局部交换优化完成。")

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

    print("5. 使用新坐标更新JSON文件...")
    if find_and_update_chip_graph(full_data, final_positions):
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=4) # 独立运行时使用 indent=4 方便查看
        print(f"\n🎉 成功！已生成终极布局文件: '{OUTPUT_FILENAME}'")
    else:
        print("❌ 致命错误: 无法在JSON文件中找到 'chip_graph' 以进行更新。")
