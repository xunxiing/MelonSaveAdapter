"""
名称: Universal_Gravitation_Calculator
描述: 计算两个物体之间的万有引力，并施加作用力与反作用力。
公式: F = G * (m1 * m2) / r^2
"""

# --- 1. 输入参数 (Inputs) ---
entity_a = INPUT(attrs={"name": "Object A", "data_type": 1})
entity_b = INPUT(attrs={"name": "Object B", "data_type": 1})
g_const  = INPUT(attrs={"name": "G Constant", "data_type": 2})

# --- 2. 获取物理数据 (Sensors) ---
pos_a_node  = Position(object=entity_a["OUTPUT"])
pos_b_node  = Position(object=entity_b["OUTPUT"])
mass_a_node = MASS(Entity=entity_a["OUTPUT"])
mass_b_node = MASS(Entity=entity_b["OUTPUT"])

# --- 3. 向量与距离计算 (Vector Math) ---
# 计算位移向量 delta = PosB - PosA (从A指向B)
delta_pos = SUBTRACT(
    A=pos_b_node["Position"], 
    B=pos_a_node["Position"], 
    attrs={"datatype": 8}
)

# 计算距离的平方 r^2
r_sqr = SQR_MAGNITUDE(INPUT=delta_pos["A-B"])

# 计算单位方向向量 (Normalize)
dir_vec = NORMALIZE(input=delta_pos["A-B"])

# --- 4. 引力公式计算 (Gravity Formula) ---
# 计算质量乘积: m1 * m2
mass_prod = MULTIPLY(A=mass_a_node["Mass"], B=mass_b_node["Mass"])

# 计算分子部分: G * (m1 * m2)
g_m_prod  = MULTIPLY(A=g_const["OUTPUT"], B=mass_prod["A*B"])

# 计算引力标量大小: F = (G * m1 * m2) / r^2
force_mag = divide(A=g_m_prod["A*B"], B=r_sqr["RESULT"])

# 转换为引力向量 (方向指向B): F_vec = dir * F
gravity_vec = MULTIPLY(
    A=dir_vec["result"], 
    B=force_mag["A / B"], 
    attrs={"datatype": 8}
)

# --- 5. 施加作用力与反作用力 (Apply Forces) ---
# 对物体 A 施加指向 B 的正向力
apply_a = ADD_FORCE(object=entity_a["OUTPUT"], Force=gravity_vec["A*B"])

# 对物体 B 施加指向 A 的反向力 (-1 * gravity_vec)
neg_one = Constant(attrs={"value": -1.0})
neg_gravity_vec = MULTIPLY(
    A=gravity_vec["A*B"], 
    B=neg_one["OUT"], 
    attrs={"datatype": 8}
)
apply_b = ADD_FORCE(object=entity_b["OUTPUT"], Force=neg_gravity_vec["A*B"])

# --- 6. 输出结果 (Outputs) ---
# 输出引力标量大小
OUTPUT(INPUT=force_mag["A / B"], attrs={"name": "Gravity_Force_Magnitude"})

# 输出物体 A 受到的引力向量
OUTPUT(INPUT=gravity_vec["A*B"], attrs={"name": "Gravity_Vector_A"})