# ==========================================
# 1. 静态声明区 (Static Scope)
# ==========================================
# 接收外部传来的 3 个核心数值
rpm_input = INPUT("RPM_Input", 2)             # 当前真实转速
up_target_input = INPUT("Up_Target", 2)       # 升档红线 (例如外部传来的 4300)
down_target_input = INPUT("Down_Target", 2)   # 降档底线 (例如外部传来的 900)

# 芯片内部维持的 2 个核心状态
current_gear: Number = 1.0                    # 当前停留在几档 (初始为1档)
shift_timer: Number = 0.6                     # 冷却计时器 (初始满值，保证起步就能换档)

# ==========================================
# 2. 主逻辑区 (Main Block)
# ==========================================
if __name__ == "__main__":
    
    # 1. 读取输入与流逝的时间
    rpm = rpm_input["OUTPUT"]
    up_target = up_target_input["OUTPUT"]
    down_target = down_target_input["OUTPUT"]
    dt = Time()["DELTA TIME"]

    # 2. 冷却时间判定 (0.6秒)
    can_shift = shift_timer >= 0.6

    # 3. 升降档意图判定 (包含撞南墙保护)
    # 突破红线 + 冷却完毕 + 小于5档 (防撞最高档南墙)
    want_up = (rpm > up_target) and can_shift and (current_gear < 5.0)
    
    # 跌破底线 + 冷却完毕 + 大于1档 (防撞最低档南墙)
    want_down = (rpm < down_target) and can_shift and (current_gear > 1.0)

    # 4. 互锁保护 (防止万一数据异常导致同时要求升降档)
    actual_up = want_up and (want_down == 0.0)
    actual_down = want_down

    # 5. 核心阶梯加减法与钳位
    # 如果 actual_up 是 1，actual_down 是 0，则 shift_val = 1 (加一档)
    # 如果 actual_up 是 0，actual_down 是 1，则 shift_val = -1 (减一档)
    shift_val = actual_up - actual_down       
    raw_gear = current_gear + shift_val
    new_gear = clamp(raw_gear, 1.0, 5.0)      # 物理极限钳位：死死锁在 1~5 之间

    # 6. 状态回写 (更新档位和计时器)
    SET(current_gear, new_gear)
    
    # 纯数学计时器刷新：只要换档了，乘数变 0，计时器瞬间清零；没换档就继续加时间
    is_shifting = actual_up or actual_down
    not_shifting = is_shifting == 0.0
    new_timer = (shift_timer + dt) * not_shifting
    SET(shift_timer, new_timer)

    # 7. 最终信号输出
    OUTPUT(current_gear, "Current_Gear")      # 输出当前数字档位 (1-5)
    
    # 顺便帮你拆解出 5 个互斥的布尔信号，你可以直接连到游戏里变速箱的 5 个齿轮离合器上
    OUTPUT(current_gear == 1.0, "Gear_1")
    OUTPUT(current_gear == 2.0, "Gear_2")
    OUTPUT(current_gear == 3.0, "Gear_3")
    OUTPUT(current_gear == 4.0, "Gear_4")
    OUTPUT(current_gear == 5.0, "Gear_5")