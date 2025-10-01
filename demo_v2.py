# demo_v2.py — 函数式 DSL 样例（与教程中的旧 JSON 等价）
# 时间源
t = TIME()

# 常量（字符串、向量）
greet = Constant(attrs={"value": "多端口测试"})
player_pos = Constant(attrs={"value": {"x": 1, "y": 2, "z": 3}})

# 分解向量
a = Split(Input=player_pos)

# 输出：data_type 用数字
out_dt = OUTPUT(INPUT=t["DELTA TIME"], attrs={"name": "#deltaTime", "data_type": 2})
out_px = OUTPUT(INPUT=a["X"],          attrs={"name": "#playerX",   "data_type": 2})
out_g  = OUTPUT(INPUT=greet,            attrs={"name": "#greeting",  "data_type": 4})