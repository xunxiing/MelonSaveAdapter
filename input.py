# ================= Inputs (输入参数) =================
# 控制的目标实体
TargetEntity = INPUT(attrs={"name": "Controlled Entity", "data_type": 1})

# 目标角度 (0-360)
TargetAngle = INPUT(attrs={"name": "Target Angle", "data_type": 2})

# PID 参数 (建议初始值: Kp=50, Ki=1, Kd=10，根据物体质量调整)
Kp = INPUT(attrs={"name": "Kp (Proportional)", "data_type": 2})
Ki = INPUT(attrs={"name": "Ki (Integral)", "data_type": 2})
Kd = INPUT(attrs={"name": "Kd (Derivative)", "data_type": 2})

# ================= Sensors & Time (传感器与时间) =================
# 获取全局时间数据
TimeData = TIME()

# 获取实体当前的旋转角度
CurrentAngle = Angle(object=TargetEntity["OUTPUT"])

# ================= Error Calculation (误差计算) =================
# 使用 DeltaAngle 计算最短路径误差 (处理 360 度回绕)
# 例如：目标 10度，当前 350度 -> 误差为 +20度
ErrorNode = DeltaAngle(**{
    "Angle (Deg) 1": TargetAngle["OUTPUT"],
    "Angle (Deg) 2": CurrentAngle["Angle"]
})

# ================= P-Term (比例项) =================
# P = Error * Kp
PTerm = MULTIPLY(A=ErrorNode["角度差"], B=Kp, attrs={"data_type": 2})

# ================= I-Term (积分项) =================
# 1. 计算当前帧的误差累积量: Error * dt
Error_x_DT = MULTIPLY(A=ErrorNode["角度差"], B=TimeData["DELTA TIME"], attrs={"data_type": 2})

# 2. 累加误差 (积分)
IntegralAccumulator = ACCUMULATOR(NUMBER=Error_x_DT["A*B"])

# 3. I = Integral * Ki
ITerm = MULTIPLY(A=IntegralAccumulator["RESULT"], B=Ki["OUTPUT"], attrs={"data_type": 2})

# ================= D-Term (微分项) =================
# 1. 计算误差的变化率: (Error_Current - Error_Prev)
DeltaError = DELTA_PREVIOUS(INPUT=ErrorNode["角度差"])

# 2. 计算导数: dE/dt
Derivative = divide(A=DeltaError["RESULT"], B=TimeData["DELTA TIME"], attrs={"data_type": 2})

# 3. D = Derivative * Kd
DTerm = MULTIPLY(A=Derivative["A / B"], B=Kd["OUTPUT"], attrs={"data_type": 2})

# ================= Summation (求和) =================
# Total = P + I + D
Sum_PI = ADD(A=PTerm["A*B"], B=ITerm["A*B"], attrs={"data_type": 2})
Total_PID = ADD(A=Sum_PI["A+B"], B=DTerm["A*B"], attrs={"data_type": 2})

# ================= Actuation (执行) =================
# 将计算出的 PID 总值作为角力(扭矩)施加给物体
ApplyTorque = ADD_ANGULAR_FORCE(**{
    "OBJECT": TargetEntity["OUTPUT"],
    "ANGULAR FORCE": Total_PID["A+B"]
})

# ================= Debug Output (调试输出 - 可选) =================
# 输出当前的 PID 力度，方便在属性面板查看
DebugOutput = OUTPUT(INPUT=Total_PID["A+B"], attrs={"name": "Output Torque", "data_type": 2})