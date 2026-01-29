# --- 全局声明区 (Static Scope) ---
# 1. 定义输入参数
Kp = INPUT(attrs={"name": "Kp", "data_type": 2})
Ki = INPUT(attrs={"name": "Ki", "data_type": 2})
Kd = INPUT(attrs={"name": "Kd", "data_type": 2})

TargetAngle = INPUT(attrs={"name": "TargetAngle", "data_type": 2})
TargetEntity = INPUT(attrs={"name": "Entity", "data_type": 1})

# 2. 定义全局变量 (Variables)
# 这里是关键：我们在顶部声明变量，相当于给芯片装了“内存条”
# integral_mem: 用于存储累加的误差值 (代替 Accumulator 模块)
integral_mem: Number = 0.0

# prev_error_mem: 用于存储上一帧的误差值 (代替 Delta Previous 模块)
prev_error_mem: Number = 0.0

# --- 逻辑执行区 (Main Block) ---
if __name__ == "__main__":
    # 获取时间步长
    TimeNode = TIME()
    dt = TimeNode["DELTA TIME"]
    
    # --- 1. 计算当前误差 ---
    CurrentAngle = Angle(object=TargetEntity)
    # 使用 DeltaAngle 处理 0-360 度回绕问题
    error = DeltaAngle(attrs={"Angle (Deg) 1": TargetAngle, "Angle (Deg) 2": CurrentAngle})
    
    # 调试输出
    OUTPUT(INPUT=error, attrs={"name": "ErrorDebug"})

    # --- 2. P (比例项) ---
    P_Term = error * Kp

    # --- 3. I (积分项) - 使用变量 ---
    # 读取当前存储的积分值
    current_integral = integral_mem
    # 计算新的积分值: 旧积分 + (当前误差 * 时间)
    error_step = error * dt
    new_integral = current_integral + error_step
    
    # 【关键】将新值写入变量，供下一帧使用
    # 这里的 SET 相当于修改内存
    SET(integral_mem,new_integral)
    
    # 计算最终 I 输出
