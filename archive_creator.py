#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
archive_creator.py
==================
新阶段：将 ungraph.json、MetaData 和 Icon 文件压缩并重命名为 .melsave 后缀
"""

import zipfile
import os
import random
import string
from pathlib import Path
from typing import List

def generate_random_filename(length: int = 8) -> str:
    """
    生成随机文件名
    
    Args:
        length: 文件名长度
        
    Returns:
        str: 随机文件名
    """
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for _ in range(length))

def create_melsave_archive(ungraph_path: Path, metadata_path: Path, icon_path: Path, output_path: Path) -> bool:
    """
    将 ungraph.json 重命名为 Data，并与 MetaData 和 Icon 一起压缩成 .melsave 文件
    
    Args:
        ungraph_path: ungraph.json 文件路径
        metadata_path: MetaData 文件路径  
        icon_path: Icon 文件路径
        output_path: 输出的 .melsave 文件路径
        
    Returns:
        bool: 是否成功创建压缩文件
    """
    # 检查所有必需文件是否存在
    required_files = [
        (ungraph_path, "ungraph.json"),
        (metadata_path, "MetaData"),
        (icon_path, "Icon")
    ]
    
    for file_path, name in required_files:
        if not file_path.exists():
            print(f"❌ 错误：未找到必需文件 '{name}' 在路径 '{file_path}'")
            return False
    
    try:
        # 创建压缩文件
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加 ungraph.json 并重命名为 Data
            print(f"📦 添加 '{ungraph_path}' 为 'Data'")
            zipf.write(ungraph_path, 'Data')
            
            # 添加 MetaData 文件
            print(f"📦 添加 '{metadata_path}' 为 'MetaData'")
            zipf.write(metadata_path, 'MetaData')
            
            # 添加 Icon 文件
            print(f"📦 添加 '{icon_path}' 为 'Icon'")
            zipf.write(icon_path, 'Icon')
        
        print(f"✅ 成功创建压缩文件: '{output_path}'")
        return True
        
    except Exception as e:
        print(f"❌ 创建压缩文件时发生错误: {e}")
        return False

def run_archive_creation_stage() -> bool:
    """
    执行归档创建阶段
    
    Returns:
        bool: 是否成功完成
    """
    print("\n--- 阶段 7: 创建 .melsave 归档文件 ---")
    
    # 定义文件路径
    ungraph_path = Path("ungraph.json")
    metadata_path = Path("MetaData")
    icon_path = Path("Icon")
    
    # 生成随机文件名
    random_name = generate_random_filename()
    output_path = Path(f"{random_name}.melsave")
    
    print(f"📁 生成随机文件名: {random_name}.melsave")
    
    # 创建归档
    success = create_melsave_archive(ungraph_path, metadata_path, icon_path, output_path)
    
    if success:
        print("✅ 归档创建阶段完成！")
    else:
        print("❌ 归档创建阶段失败！")
    
    return success

if __name__ == "__main__":
    run_archive_creation_stage()
