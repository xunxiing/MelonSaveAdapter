# --- 1. 输入参数定义 (Inputs) ---
# 潜艇预设重量
mass = INPUT(attrs={"name": "mass", "data_type": 2})
# 摇杆控制信号 (Vector)
joy_vec = INPUT(attrs={"name": "V y", "data_type": 8})
# 总开关 (0关 1开)
switch_a = INPUT(attrs={"name": "A", "data_type": 2})
# 深度传感器输入 (0为水面, 值越大越深)
depth_h = INPUT(attrs={"name": "input H", "data_type": 2})
# PI系数 (X=Kp, Y=Ki)
pk_ik = INPUT(attrs={"name": "Pk Ik", "data_type": 8})
# 摇杆放大系数 (目标速度增益)
vk_gain = INPUT(attrs={"name": "V k", "data_type": 2})
# 水面判定阈值
surface_c = INPUT(attrs={"name": "c", "data_type": 2})

# --- 2. 常量定义 (Constants) ---
const_gravity = Constant(attrs={"value": 9.8})
const_zero = Constant(attrs={"value": 0.0})
const_one = Constant(attrs={"value": 1.0})
const_neg_one = Constant(attrs={"value": -1.0})
const_time = TIME()

# --- 3. 目标速度计算 (Target Velocity Calculation) ---
# 提取摇杆Y轴
joy_split = Split(Vector=joy_vec["OUTPUT"])
# 摇杆Y通常上为正，下为负。但在深度定义中，上浮是深度减小(负速度)，下潜是深度增加(正速度)。
# 因此：摇杆上推(Y>0) -> 目标速度为负；摇杆下推(Y<0) -> 目标速度为正。
target_dir = MULTIPLY(A=joy_split["Y"], B=const_neg_one["OUT"])
# 应用增益 V k
v_target = MULTIPLY(A=target_dir["A*B"], B=vk_gain["OUTPUT"])

# --- 4. 当前速度计算 (Current Velocity Calculation) ---
# 获取上一帧的深度 [cite: 89]
h_prev = PREV_FRAME(INPUT=depth_h["OUTPUT"], attrs={"datatype": 2})
# 计算深度差 (dH) [cite: 3]
h_delta = SUBTRACT(A=depth_h["OUTPUT"], B=h_prev["RESULT"])
# 计算速度 V = dH / dt [cite: 84]
v_curr = divide(A=h_delta["A-B"], B=const_time["DELTA TIME"])

# --- 5. 误差计算 (Error Calculation) ---
# Error = Target - Current
error = SUBTRACT(A=v_target["A*B"], B=v_curr["A / B"])

# --- 6. 积分项控制逻辑 (Integral Term Logic) ---
# 分离 PID 系数
pid_coeffs = Split(Vector=pk_ik["OUTPUT"])
kp = pid_coeffs["X"]
ki = pid_coeffs["Y"]

# 条件判断：是否在水面 (深度 < c) [cite: 24]
is_surface = LESS_THAN(A=depth_h["OUTPUT"], B=surface_c["OUTPUT"])
# 条件判断：是否在尝试上浮 (摇杆Y > 0) [cite: 23]
is_pulling_up = GREATER_THAN(A=joy_split["Y"], B=const_zero["OUT"])

# 组合逻辑：(在水面 AND 尝试上浮) -> 禁止积分 [cite: 16]
surface_lock = AND(A=is_surface["A < B"], B=is_pulling_up["A > B"])
# 允许积分信号 = NOT surface_lock [cite: 19]
allow_int_logic = NOT(A=surface_lock["A AND B"])

# 总积分使能 = 开关A AND 允许积分逻辑
# 只有在开关开启且没有触发防积分饱和时，才进行累加
final_int_enable = AND(A=switch_a["OUTPUT"], B=allow_int_logic["NOT A"])

# 计算本帧积分增量：Error * dt
error_dt = MULTIPLY(A=error["A-B"], B=const_time["DELTA TIME"])
# 应用使能门控：如果 final_int_enable 为 0，则输入累加器的值为 0 (保持不变)
gated_int_input = MULTIPLY(A=error_dt["A*B"], B=final_int_enable["A AND B"])

# 积分器 [cite: 85]
integrator = ACCUMULATOR(NUMBER=gated_int_input["A*B"], RESET=const_zero["OUT"])

# --- 7. PID 输出计算 ---
# P项
p_term = MULTIPLY(A=error["A-B"], B=kp)
# I项
i_term = MULTIPLY(A=integrator["RESULT"], B=ki)
# PID 总和 (代表请求的加速度修正量)
pid_sum = ADD(A=p_term["A*B"], B=i_term["A*B"])

# --- 8. 物理力学计算 (Physics Force Calculation) ---
# 基础悬停浮力 = Mass * G (用于抵消重力)
hover_force = MULTIPLY(A=mass["OUTPUT"], B=const_gravity["OUT"])

# 控制力计算：F_buoy = Mass * (G - PID_Out)
# 如果 PID_Out > 0 (需要向下加速)，浮力应减小
# 如果 PID_Out < 0 (需要向上加速)，浮力应增大
# 这里先计算加速度差：G - PID
accel_diff = SUBTRACT(A=const_gravity["OUT"], B=pid_sum["A+B"])
# 再乘以质量得到最终浮力
raw_force = MULTIPLY(A=mass["OUTPUT"], B=accel_diff["A-B"])

# 限制浮力不能为负数 (物理限制) [cite: 3]
final_force_calc = max(A=raw_force["A*B"], B=const_zero["OUT"])

# --- 9. 输出保持逻辑 (Output Hold Logic) ---
# 需求：当 A=0 时，输出不变。
# 实现：Out = (New_Value * A) + (Prev_Out * (1-A))

# 获取上一帧的最终输出 [cite: 89]
# 注意：这里使用了前向引用，必须先定义好逻辑。
# 我们创建一个名为 final_output_signal 的变量，但它依赖于 prev_output_node
# 这种循环在 python 生成器中通常需要先声明节点。
# 既然要生成 python 代码，我们按照标准反馈环路写法：

# 1. 计算 (1 - A)
switch_a_inv = SUBTRACT(A=const_one["OUT"], B=switch_a["OUTPUT"])

# 2. 预先定义一个 PREV_FRAME 节点，它的输入将是本芯片的最终输出
# 在生成的代码中，我们需要确保变量名引用正确
# 假设最终输出变量名为 output_f_val，我们先建立这个反馈节点
prev_output_node = PREV_FRAME(INPUT=None, attrs={"datatype": 2}) # Input稍后连接

# 3. 计算保持项: Prev * (1-A)
hold_term = MULTIPLY(A=prev_output_node["RESULT"], B=switch_a_inv["A-B"])

# 4. 计算新值项: Calculated * A
active_term = MULTIPLY(A=final_force_calc["max"], B=switch_a["OUTPUT"])

# 5. 最终输出值
output_f_val = ADD(A=active_term["A*B"], B=hold_term["A*B"])

# 6. *关键步骤*：连接反馈回路
# 将计算出的 output_f_val 连接回 prev_output_node 的输入
# 注意：在生成器语法中可能需要重新赋值或使用 Set 方法，这里假设可以直接通过属性连接
# 如果是生成DSL，通常不支持直接修改INPUT，需要重新定义或确保生成器支持。
# 既然是教程格式，我们使用标准的参数传递修正 prev_output_node 的定义：
# (由于Python代码是顺序执行，无法修改已实例化的对象参数，正确做法是利用生成器的前向引用特性，
# 或者如果生成器不支持，则 A=0 时简单输出 0 或 悬停力。
# 根据题目严格要求“输出不变”，必须使用 Feedback。
# 修正写法：重新定义 prev_output_node 的输入引用)

# (修正代码逻辑：为了符合Python顺序执行，我们假定前向引用通过变量名字符串或字典处理)
# 这里使用简单的赋值逻辑修正：
prev_output_node.inputs["INPUT"] = output_f_val["A+B"] 
# (注意：上述写法取决于具体库实现，但在逻辑图描述中，就是将 output_f_val 连回 PREV_FRAME)

# --- 10. 最终输出端口 (Output Port) ---
OUTPUT(attrs={"name": "output F", "data_type": 2}, INPUT=output_f_val["A+B"])