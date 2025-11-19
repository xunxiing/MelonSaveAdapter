# --- 1. 输入参数 ---
# 物体A
obj_a = INPUT(attrs={"name": "ObjectA", "data_type": 1})
# 物体B
obj_b = INPUT(attrs={"name": "ObjectB", "data_type": 1})
# 弹簧系数
spring_k = INPUT(attrs={"name": "SpringK", "data_type": 2})
# 阻尼系数
damper_d = INPUT(attrs={"name": "DamperD", "data_type": 2})
# 弹簧原长
rest_length = INPUT(attrs={"name": "RestLength", "data_type": 2})

# --- 2. 获取物体状态 ---
# 获取位置和速度
pos_a = Position(object=obj_a["OUTPUT"])
pos_b = Position(object=obj_b["OUTPUT"])
vel_a = Velocity(object=obj_a["OUTPUT"])
vel_b = Velocity(object=obj_b["OUTPUT"])

# --- 3. 计算弹簧力 ---
# 从A指向B的向量
vec_ab = SUBTRACT(A=pos_b["Position"], B=pos_a["Position"], attrs={"datatype": 8})
# AB距离
dist_ab = MAGNITUDE(input=vec_ab["A-B"])
# AB方向（单位向量）
dir_ab = NORMALIZE(input=vec_ab["A-B"])

# 弹簧伸长量 = 当前距离 - 原长
elongation = SUBTRACT(A=dist_ab["result"], B=rest_length["OUTPUT"])
# 弹簧力大小 = k * 伸长量
spring_force_mag = MULTIPLY(A=spring_k["OUTPUT"], B=elongation["A-B"])

# 将方向向量分解
dir_split = Split(Vector=dir_ab["result"])
# 计算作用在B上的弹簧力向量分量
spring_b_x = MULTIPLY(A=Split(Vector=dir_ab["result"])["X"], B=spring_force_mag["A*B"])
spring_b_y = MULTIPLY(A=dir_split["Y"], B=spring_force_mag["A*B"])
spring_b_z = MULTIPLY(A=dir_split["Z"], B=spring_force_mag["A*B"])
# 组合成向量
zero = Constant(attrs={"value": 0.0})
spring_force_b = Combine(X=spring_b_x["A*B"], Y=spring_b_y["A*B"], Z=spring_b_z["A*B"], W=zero["OUT"])

# 作用在A上的弹簧力 = -作用在B上的弹簧力
neg_one = Constant(attrs={"value": -1.0})
spring_a_x = MULTIPLY(A=spring_b_x["A*B"], B=neg_one["OUT"])
spring_a_y = MULTIPLY(A=spring_b_y["A*B"], B=neg_one["OUT"])
spring_a_z = MULTIPLY(A=spring_b_z["A*B"], B=neg_one["OUT"])
spring_force_a = Combine(X=spring_a_x["A*B"], Y=spring_a_y["A*B"], Z=spring_a_z["A*B"], W=zero["OUT"])

# --- 4. 计算阻尼力 ---
# 相对速度 = Vb - Va
rel_vel = SUBTRACT(A=vel_b["Velocity"], B=vel_a["Velocity"], attrs={"datatype": 8})
# 速度在弹簧方向上的投影（点积）
vel_proj = DOT_PRODUCT(A=dir_ab["result"], B=rel_vel["A-B"])
# 阻尼力大小 = d * 投影速度
damper_force_mag = MULTIPLY(A=damper_d["OUTPUT"], B=vel_proj["result"])

# 计算作用在B上的阻尼力向量分量
damper_b_x = MULTIPLY(A=dir_split["X"], B=damper_force_mag["A*B"])
damper_b_y = MULTIPLY(A=dir_split["Y"], B=damper_force_mag["A*B"])
damper_b_z = MULTIPLY(A=dir_split["Z"], B=damper_force_mag["A*B"])
damper_force_b = Combine(X=damper_b_x["A*B"], Y=damper_b_y["A*B"], Z=damper_b_z["A*B"], W=zero["OUT"])

# 作用在A上的阻尼力 = -作用在B上的阻尼力
damper_a_x = MULTIPLY(A=damper_b_x["A*B"], B=neg_one["OUT"])
damper_a_y = MULTIPLY(A=damper_b_y["A*B"], B=neg_one["OUT"])
damper_a_z = MULTIPLY(A=damper_b_z["A*B"], B=neg_one["OUT"])
damper_force_a = Combine(X=damper_a_x["A*B"], Y=damper_a_y["A*B"], Z=damper_a_z["A*B"], W=zero["OUT"])

# --- 5. 组合总力 ---
# 作用在B上的总力
total_force_b = ADD(A=spring_force_b["Vector"], B=damper_force_b["Vector"], attrs={"datatype": 8})
# 作用在A上的总力
total_force_a = ADD(A=spring_force_a["Vector"], B=damper_force_a["Vector"], attrs={"datatype": 8})

# --- 6. 施加力 ---
# 对A施加力
apply_force_a = ADD_FORCE(OBJECT=obj_a["OUTPUT"], FORCE=total_force_a["A+B"])
# 对B施加力
apply_force_b = ADD_FORCE(OBJECT=obj_b["OUTPUT"], FORCE=total_force_b["A+B"])

# --- 7. 调试输出 ---
# 当前距离
out_dist = OUTPUT(INPUT=dist_ab["result"], attrs={"name": "CurrentDistance", "data_type": 1028})
# 作用在A上的力
out_force_a = OUTPUT(INPUT=total_force_a["A+B"], attrs={"name": "ForceOnA", "data_type": 8})
# 作用在B上的力
out_force_b = OUTPUT(INPUT=total_force_b["A+B"], attrs={"name": "ForceOnB", "data_type": 8})