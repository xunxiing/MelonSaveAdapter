# 字符串数组
arr_str = Constant(attrs={
    "value": ["a", "b", "c"]
})

# 数字数组  
arr_num = Constant(attrs={
    "value": [1.0, 2.0, 3.0]
})

# 向量数组 - 字典
arr_vec_dict = Constant(attrs={
    "value": [
        {"x":0,"y":0,"z":0},
        {"x":1,"y":2,"z":3},
    ]
})

# 向量数组 - 列表
arr_vec_list = Constant(attrs={
    "value": [
        [0,0,0,0],
        [1,2,3,1],
    ]
})

# 普通标量
scalar_num = Constant(attrs={"value": 42.0})
scalar_str = Constant(attrs={"value": "hello"})
scalar_vec = Constant(attrs={"value": {"x":1.0,"y":2.0,"z":3.0}})
