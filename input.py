if __name__ == "__main__":
    # 定义芯片的一个输入信号（可以接收任意数字）
    input_signal = INPUT("输入数值", "Number")
    
    # 使用 Abs（绝对值） 模块，将输入连接过去
    # 比如输入是 -10，它就会输出 10
    absolute_value = Abs(input_signal)
    
    # 将计算结果输出
    OUTPUT(absolute_value, "输出绝对值")
