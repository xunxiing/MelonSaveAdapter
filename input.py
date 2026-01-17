# --- 1. 输入参数定义 ---

# 核心实体
entity_body = INPUT(attrs={"name": "车身(Body)", "data_type": 1})
entity_wheel = INPUT(attrs={"name": "轮子(Wheel)", "data_type": 1})

# 悬挂参数
# LocalOffset 是轮子相对于车身中心的理想位置（向量，例如 {"x":0, "y":-2.5, "z":0, "w":0}）
target_local_offset = INPUT(attrs={"name": "理想局部偏移", "data_type": 8})

# PID 增益 (控制悬挂硬度和回弹)
kp_stiffness = INPUT(attrs={"name": "弹簧硬度(Kp)", "data_type": 2})
kd_damping = INPUT(attrs={"name": "阻尼系数(Kd)", "data_type": 2})

# --- 2. 获取当前状态 ---

# 获取车身和轮子的世界坐标
body_pos = Position(object=entity_body["OUTPUT"])
wheel_pos = Position(object=entity_wheel["OUTPUT"])

# 获取速度用于计算阻尼
body_vel = Velocity(object=entity_body["OUTPUT"])
wheel_vel = Velocity(object=entity_wheel["OUTPUT"])

# --- 3. 坐标转换与误差计算 ---

# 将车身的局部目标偏移转换成世界坐标，这样车身旋转时，轮子目标点也会跟着转
target_world_pos_node = LocalPositionToWorld(
    object=entity_body["OUTPUT"], 
    **{"Local Position": target_local_offset["OUTPUT"]}
)

# 计算位置误差 (目标位置 - 当前轮子位置)
# pos_error = target_world_pos - wheel_pos
pos_error = target_world_pos_node["world position"] - wheel_pos["Position"]

# 计算相对速度 (车身速度 - 轮子速度)
# vel_error = body_vel - wheel_vel
vel_error = body_vel["Velocity"] - wheel_vel["Velocity"]

# --- 4. 悬挂物理逻辑计算 (PD 控制) ---

# 1. 弹簧力 (P项): 误差越大，拉力越大
# spring_force = pos_error * kp
spring_force = MULTIPLY(A=pos_error, B=kp_stiffness["OUTPUT"], attrs={"datatype": 8})

# 2. 阻尼力 (D项): 抑制震荡，消耗能量
# damper_force = vel_error * kd
damper_force = MULTIPLY(A=vel_error, B=kd_damping["OUTPUT"], attrs={"datatype": 8})

# 3. 合力
# total_force = spring_force + damper_force
total_suspension_force = ADD(A=spring_force["A*B"], B=damper_force["A*B"], attrs={"datatype": 8})

# --- 5. 施加力 ---

# 对轮子施加悬挂力
apply_to_wheel = add_FORCE(
    object=entity_wheel["OUTPUT"], 
    Force=total_suspension_force["A+B"]
)

# 根据牛顿第三定律，对车身施加反作用力 (防止车身因为轮子的力而无中生有获得动量)
neg_one = Constant(attrs={"value": -1.0})
reaction_force = MULTIPLY(A=total_suspension_force["A+B"], B=neg_one["OUT"], attrs={"datatype": 8})

apply_to_body = add_FORCE(
    object=entity_body["OUTPUT"], 
    Force=reaction_force["A*B"]
)

# --- 6. 调试输出 (可选) ---
# 将偏移误差转换成字符串，方便连接到 Text Screen 观察
error_val = MAGNITUDE(pos_error)
OUTPUT(INPUT=TO_STRING(error_val["result"]), attrs={"name": "CurrentError"})