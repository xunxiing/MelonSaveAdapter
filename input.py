# ========= 变量定义 =========



PrevError = { "Key": "PrevError", "GateDataType": "Number", "Value": 1, }
IntegralError = { "Key": "IntegralError", "GateDataType": "Number", "Value": 1, }


# --- 输入 ---
Target = INPUT(attrs={"name": "Target", "data_type": 2})
Current = INPUT(attrs={"name": "Current", "data_type": 2})
Kp = INPUT(attrs={"name": "Kp", "data_type": 2})
Ki = INPUT(attrs={"name": "Ki", "data_type": 2})
Kd = INPUT(attrs={"name": "Kd", "data_type": 2})


# 写入变量
PrevError = VARIABLE(Value=Kp, Set=1)






