# --- 1. 输入参数 (Inputs & Parameters) ---
# 侦测器触发信号 (1=碰撞发生, 0=未发生)
trigger_in = INPUT(attrs={"name": "InTrigger", "data_type": 2})
# 被侦测到的实体
entity_hit = INPUT(attrs={"name": "InHitEntity", "data_type": 1})

# --- 2. 逻辑处理 (Logic) ---
# 目标：当 trigger_in 为 1 时，输出 0 (禁用碰撞)
# 当 trigger_in 为 0 时，输出 1 (启用碰撞)
# 使用 NOT 模块实现逻辑反转
collision_enable_signal = NOT(A=trigger_in["OUTPUT"])
collision_enable_signal2 = NOT(A=TIME()["DELTA TIME"])
# --- 3. 实体操作 (Entity Operations) ---
# COLLISION 模块：设置被撞击实体的碰撞状态
# 将 NOT 结果连接到 ENABLE COLLISION 端口：
# - 碰撞发生 (trigger=1) -> NOT 输出 0 -> 禁用碰撞
# - 未发生碰撞 (trigger=0) -> NOT 输出 1 -> 启用碰撞 (对无效实体无影响，对脱离的实体恢复正常)
control_collision = COLLISION(OBJECT=entity_hit["OUTPUT"], **{'ENABLE COLLISION': collision_enable_signal["NOT A"]})