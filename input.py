# 模块功能: 自动追踪
# 输入: Tracker (Entity), Target (Entity), Force (Decimal)
# 描述: 控制 Tracker 物体向 Target 物体移动。

# --- 1. 定义输入端口 ---
# 定义追踪者实体输入
tracker_input = INPUT(attrs={"name": "Tracker", "data_type": 1})
# 定义目标实体输入
target_input = INPUT(attrs={"name": "Target", "data_type": 1})
# 定义追踪力度输入
force_input = INPUT(attrs={"name": "Force", "data_type": 2})

# --- 2. 获取实体位置 ---
# 获取追踪者的当前世界坐标
tracker_pos = Position(object=tracker_input["OUTPUT"])
# 获取目标的当前世界坐标
target_pos = Position(object=target_input["OUTPUT"])

# --- 3. 计算方向向量 ---
# 计算从追踪者指向目标的方向向量 (目标位置 - 追踪者位置)
direction_vector = SUBTRACT(A=target_pos["Position"], B=tracker_pos["Position"])

# --- 4. 标准化方向向量 ---
# 将方向向量的长度变为1，只保留方向信息
normalized_vector = NORMALIZE(input=direction_vector["A-B"])

# --- 5. 缩放向量以匹配力度 ---
# 由于不能直接将向量与单个数值相乘，我们需要先分解向量
split_vector = Split(Vector=normalized_vector["result"])

# 分别将X和Y分量乘以指定的力度
force_x = MULTIPLY(A=split_vector["X"], B=force_input["OUTPUT"])
force_y = MULTIPLY(A=split_vector["Y"], B=force_input["OUTPUT"])

# --- 6. 重新组合为最终的力向量 ---
# 创建一个值为0的常量用于Z和W分量
zero_constant = Constant(attrs={"value": 0.0})
# 将缩放后的X和Y分量重新组合成一个完整的力向量
final_force_vector = Combine(X=force_x["A*B"], Y=force_y["A*B"], Z=zero_constant["OUT"], W=zero_constant["OUT"])

# --- 7. 施加力 ---
# 将计算出的最终力向量施加到追踪者物体上
apply_force = add_FORCE(object=tracker_input["OUTPUT"], Force=final_force_vector["Vector"])