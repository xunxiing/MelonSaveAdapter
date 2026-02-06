#### 1. 全局变量声明
# === 字符串数组 ===
# 用于测试 data_type = 4 的推断
arr_strings: ArrayString = ["Hello", "World", "Melon"]

# === 向量数组 ===
# 用于测试 data_type = 8 的推断 (这是最容易炸的，因为字典结构复杂)
arr_vectors: ArrayVector = [
    {"x": 1, "y": 0, "z": 0}, 
    {"x": 0, "y": 1, "z": 0}
]

if __name__ == "__main__":
    # === 逻辑执行区 ===
    
    # --- 测试 A: 字符串数组读取 ---
    # 从数组取出一个字符串
    str_val = ArraysGet(Array=arr_strings, Index=0)[0]
    
    # 1. 让编译器猜 (自动推断)
    OUTPUT(INPUT=str_val, name="Out_Str_Auto")
    
    # 2. 帮编译器一把 (手动指定 data_type=4)
    OUTPUT(INPUT=str_val, name="Out_Str_Manual", attrs={"data_type": 4})


    # --- 测试 B: 向量数组读取 ---
    # 从数组取出一个向量
    vec_val = ArraysGet(Array=arr_vectors, Index=0)[0]
    
    # 3. 让编译器猜 (自动推断)
    # 很多编译器会在这里把 Vector 误判为 Entity 或 Number
    OUTPUT(INPUT=vec_val, name="Out_Vec_Auto")
    
    # 4. 帮编译器一把 (手动指定 data_type=8)
    OUTPUT(INPUT=vec_val, name="Out_Vec_Manual", attrs={"data_type": 8})