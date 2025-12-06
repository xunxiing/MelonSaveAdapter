# --- 1. 常量定义 (Constants) ---
const_0 = Constant(attrs={"value": 0.0})
const_2 = Constant(attrs={"value": 2.0})
const_4 = Constant(attrs={"value": 4.0})

# --- 2. 输入参数 (Inputs) ---
# 系数 a, b, c
val_a = INPUT(attrs={"name": "a", "data_type": 2})
val_b = INPUT(attrs={"name": "b", "data_type": 2})
val_c = INPUT(attrs={"name": "c", "data_type": 2})

# --- 3. 计算判别式 Delta = b^2 - 4ac ---
# 计算 b^2
b_squared = SQUARE(A=val_b["OUTPUT"])

# 计算 4ac
four_a = MULTIPLY(A=const_4["OUT"], B=val_a["OUTPUT"], attrs={"datatype": 2})
four_ac = MULTIPLY(A=four_a["A*B"], B=val_c["OUTPUT"], attrs={"datatype": 2})

# 计算 Delta
delta = SUBTRACT(A=b_squared["A*A"], B=four_ac["A*B"], attrs={"datatype": 2})

# --- 4. 逻辑判断 (Logic & Safety) ---
# 判断 Delta < 0 (用于报错)
is_error = LESS_THAN(A=delta["A-B"], B=const_0["OUT"])

# 判断 Delta >= 0 (用于正常计算的条件)
is_valid = GREATER_OR_EQUAL(A=delta["A-B"], B=const_0["OUT"])

# --- 5. 安全开根号 (Safe SQRT) ---
# 如果 Delta < 0，传入 0 给 SQRT 模块，防止报错；否则传入 Delta
safe_delta = branch(IF=is_valid["A >= B"], A=delta["A-B"], B=const_0["OUT"], attrs={"datatype": 2})

# 计算 sqrt(Delta)
sqrt_delta = SQRT(A=safe_delta)

# --- 6. 计算分子与分母 ---
# 计算 -b (0 - b)
neg_b = SUBTRACT(A=const_0["OUT"], B=val_b["OUTPUT"], attrs={"datatype": 2})

# 分子 1: -b + sqrt(Delta)
num_1 = ADD(A=neg_b["A-B"], B=sqrt_delta["sqrt(A)"], attrs={"datatype": 2})

# 分子 2: -b - sqrt(Delta)
num_2 = SUBTRACT(A=neg_b["A-B"], B=sqrt_delta["sqrt(A)"], attrs={"datatype": 2})

# 分母: 2a
denom = MULTIPLY(A=const_2["OUT"], B=val_a["OUTPUT"], attrs={"datatype": 2})

# --- 7. 初步求值 (Raw Calculation) ---
# 注意：这里假设 a 不为 0。如果 a 为 0，divide 模块可能会输出无穷大或特定值
raw_root_1 = divide(A=num_1["A+B"], B=denom["A*B"], attrs={"datatype": 2})
raw_root_2 = divide(A=num_2["A-B"], B=denom["A*B"], attrs={"datatype": 2})

# --- 8. 最终输出过滤 (Final Output Filtering) ---
# 如果 Delta < 0，强制输出 0；否则输出计算结果
final_root_1 = branch(IF=is_valid["A >= B"], A=raw_root_1["A / B"], B=const_0["OUT"], attrs={"datatype": 2})
final_root_2 = branch(IF=is_valid["A >= B"], A=raw_root_2["A / B"], B=const_0["OUT"], attrs={"datatype": 2})

# --- 9. 输出端口 (Outputs) ---
# 输出根1
OUTPUT(INPUT=final_root_1, attrs={"name": "Root 1", "data_type": 2})
# 输出根2
OUTPUT(INPUT=final_root_2, attrs={"name": "Root 2", "data_type": 2})
# 输出错误信号 (1代表无实根/Delta<0)
OUTPUT(INPUT=is_error["A < B"], attrs={"name": "Error", "data_type": 2})