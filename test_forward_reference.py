# 测试前向引用功能
out_dt = OUTPUT(INPUT=t["DELTA TIME"], attrs={"name":"#dt","data_type":2})  # 先用
t = TIME()                                                                  # 后定义

# 常量
greet = Constant(attrs={"value": "hello"})

# 前向引用常量
out_g = OUTPUT(INPUT=greet["OUT"], attrs={"name":"#g","data_type":4})      # 先用
greet = Constant(attrs={"value": "world"})                                 # 后定义（首次定义为准）

# 多重前向引用
out_x = OUTPUT(INPUT=xyz["X"], attrs={"name":"#x","data_type":2})          # 先用
xyz = Split(Vector=player_pos["OUT"])                                       # 中间定义
player_pos = Constant(attrs={"value": {"x": 1, "y": 2, "z": 3}})          # 最后定义