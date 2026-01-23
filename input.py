
obj = INPUT(name="Object", data_type="Entity")

# 内部变量：用于积分项的累加
IntegralSum: Number = 0.0

if __name__ == "__main__":
    # 1. 获取输入
    # 获取需要控制的物体

    
    # 2. 获取当前状态
    # 获取物体的当前世界角度
    current_angle = Angle(object=obj)
    OUTPUT(INPUT=current_angle, name="Result", data_type="Number")
    IntegralSum=current_angle

    # 获取当前帧的时间间隔
    