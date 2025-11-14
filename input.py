# input.py - 测试数组常量支持
# 演示三种数组类型的常量节点

# 字符串数组 (ArrayString)
arr_str = Constant(attrs={
    "value": ["a", "b", "c"]
})

# 数字数组 (ArrayNumber)  
arr_num = Constant(attrs={
    "value": [1.0, 2.0, 3.0]
})

# 向量数组 (ArrayVector) - 使用字典格式
arr_vec_dict = Constant(attrs={
    "value": [
        {"x": 0.0, "y": 0.0, "z": 0.0},
        {"x": 1.0, "y": 2.0, "z": 3.0},
    ]
})

# 向量数组 (ArrayVector) - 使用列表格式
arr_vec_list = Constant(attrs={
    "value": [
        [0.0, 0.0, 0.0],
        [1.0, 2.0, 3.0],
    ]
})

# 普通标量常量（作为对比）
scalar_num = Constant(attrs={
    "value": 42.0
})

scalar_str = Constant(attrs={
    "value": "hello"
})

scalar_vec = Constant(attrs={
    "value": {"x": 1.0, "y": 2.0, "z": 3.0}
})