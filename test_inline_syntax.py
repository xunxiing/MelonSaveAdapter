# 测试内联语法
dir_ab = NORMALIZE(input=some_vector["A-B"])
spring_force_mag = MULTIPLY(A=spring_k["OUTPUT"], B=elongation["A-B"])

# 目标语法：支持在传入参数里面写内联函数调用+端口访问
spring_b_x = MULTIPLY(A=Split(Vector=dir_ab["result"])["X"], B=spring_force_mag["A*B"])

# 也应该支持其他复杂内联
result = ADD(A=Combine(X=val1["OUT"], Y=val2["OUT"])["Vector"], B=Constant(attrs={"value": 5})["OUT"])