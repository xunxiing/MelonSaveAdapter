# ========= 变量定义 =========



PrevError = { "Key": "PrevError", "GateDataType": "Number", "Value": 1, }
IntegralError = { "Key": "IntegralError", "GateDataType": "Number", "Value": 1, }


# --- 输入 ---
Target = INPUT(attrs={"name": "Target", "data_type": 2})
Current = INPUT(attrs={"name": "Current", "data_type": 2})
Kp = INPUT(attrs={"name": "Kp", "data_type": 2})
Ki = INPUT(attrs={"name": "Ki", "data_type": 2})
Kd = INPUT(attrs={"name": "Kd", "data_type": 2})

# --- Variable 节点 ---
Integral = VARIABLE(Value="IntegralError", Set=None)
PrevErr = VARIABLE(Value="PrevError", Set=None)

# --- 误差 error = Target - Current ---
Error = SUBTRACT(A=Target, B=Current, attrs={"data_type": 2})

# --------------------- P 项 ---------------------
P_Out = MULTIPLY(A=Error, B=Kp, attrs={"data_type": 2})

# --------------------- I 项（积分） ---------------------
# newIntegral = Integral + Error
I_Add = ADD(A=Integral, B=Error, attrs={"data_type": 2})
# 写入变量
SetIntegral = VARIABLE(Value=Integral, Set=I_Add)

# 积分输出 = newIntegral * Ki
I_Out = MULTIPLY(A=I_Add, B=Ki, attrs={"data_type": 2})

# --------------------- D 项（微分） ---------------------
# diff = Error - PrevError
Diff = SUBTRACT(A=Error, B=PrevErr, attrs={"data_type": 2})
# 写入上一误差
SetPrev = VARIABLE(Value=PrevErr, Set=Error)

# 微分输出 = diff * Kd
D_Out = MULTIPLY(A=Diff, B=Kd, attrs={"data_type": 2})

# --------------------- PID 合成 ---------------------
P_I = ADD(A=P_Out, B=I_Out, attrs={"data_type": 2})
PID = ADD(A=P_I, B=D_Out, attrs={"data_type": 2})

# --- 输出 ---
Control = OUTPUT(INPUT=PID, attrs={"name": "Control", "data_type": 2})




