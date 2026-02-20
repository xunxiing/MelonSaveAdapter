# --- 1.1 全局声明区 (Static Scope) ---

# 定义 INPUT (输入端口) - 注意：这里不使用 :Type 语法，避免被识别为全局变量
obj = INPUT(attrs={"name": "obj", "data_type": 1})
switch_1 = INPUT(attrs={"name": "1", "data_type": 2})
angle_A = INPUT(attrs={"name": "A", "data_type": 2})
angle_B = INPUT(attrs={"name": "B", "data_type": 2})
I = INPUT(attrs={"name": "I", "data_type": 2})

# 定义 显式常量 (Constants) - 这里可以使用 :Final 语法
LAMBDA: Final[Number] = 12.0
ETA: Final[Number] = 15.0
Q_GAIN: Final[Number] = 10.0
ZERO: Final[Number] = 0.0

# --- 1.2 逻辑执行区 (Main Block) ---

if __name__ == "__main__":
    # 1. 目标角度切换逻辑
    # 注意：INPUT 模块只有一个输出，可以直接使用变量名引用
    target_angle = branch(IF=switch_1, A=angle_B, B=angle_A, attrs={"data_type": "Number"})

    # 2. 读取传感器数据
    current_angle_node = Angle(object=obj)
    current_ang_vel_node = AngularVelocity(object=obj)

    # 3. 误差计算 (DeltaAngle 处理 360 度回绕)
    # 使用端口引用方式：node["端口名"]
    error_node = DeltaAngle(**{
        "Angle (Deg) 1": target_angle, 
        "Angle (Deg) 2": current_angle_node["Angle"]
    })
    
    # 误差变化率 (目标角度 A/B 是静态的，所以 dot_e = 0 - 当前角速度)
    dot_error = SUBTRACT(A=ZERO, B=current_ang_vel_node["Angular Velocity"])

    # 4. 滑模面 s = lambda * e + dot_e
    term_s1 = MULTIPLY(A=LAMBDA, B=error_node["角度差"])
    s = ADD(A=term_s1, B=dot_error)

    # 5. 趋近律计算
    # sign(s)
    s_sign = sign(a=s)
    
    # eta * sign(s)
    reach_sign = MULTIPLY(A=ETA, B=s_sign)
    
    # q * s
    reach_linear = MULTIPLY(A=Q_GAIN, B=s)
    
    # lambda * dot_e (等效控制项)
    equiv_control = MULTIPLY(A=LAMBDA, B=dot_error)

    # 6. 合成控制指令
    sum1 = ADD(A=equiv_control, B=reach_sign)
    sum2 = ADD(A=sum1, B=reach_linear)
    
    # 最终扭矩 = I * (sum)
    final_torque = MULTIPLY(A=I, B=sum2)

    # 7. 物理输出
    ADD_ANGULAR_FORCE(OBJECT=obj, ANGULAR_FORCE=final_torque)

    # 调试输出（可选）：将误差转为字符串输出到名为 DebugError 的端口
    error_str = TO_STRING(input=error_node["角度差"])
    OUTPUT(INPUT=error_str, name="DebugError")