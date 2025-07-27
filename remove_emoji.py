#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
remove_emoji.py

用途：递归扫描当前目录及所有子目录中指定类型的代码文件，移除文件中的 Emoji 表情符号。
支持的文件类型：.py, .js, .ts, .java, .cpp, .h, .html, .css, .json, .md, .yml, .yaml

使用方法：
  python remove_emoji.py

注意：脚本会直接覆盖原文件，建议在版本管理或备份后运行。
"""
import os
import re

# ----------------------- 配置区 -----------------------
# 扫描的文件扩展名列表（小写）
TARGET_EXTENSIONS = [
    ".py", ".js", ".ts", ".java", ".cpp", ".h",
    ".html", ".css", ".json", ".md", ".yml", ".yaml"
]

# Emoji 匹配正则：涵盖常见 Unicode Emoji 范围，无需使用 "/u" 跨面错误区间
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # 表情符号 emoticons
    "\U0001F300-\U0001F5FF"  # 符号 & 象形
    "\U0001F680-\U0001F6FF"  # 交通 & 地图
    "\U0001F1E0-\U0001F1FF"  # 国家旗帜
    "\u2600-\u26FF"        # 杂项符号
    "\u2700-\u27BF"        # 装饰符号
    "]+",
    flags=re.UNICODE
)
# -------------------------------------------------------

def remove_emojis_from_text(text: str) -> str:
    """
    移除文本中的所有 Emoji 表达式。"""
    return EMOJI_PATTERN.sub("", text)


def process_file(filepath: str) -> None:
    """
    读取文件内容，移除 Emoji，若发生变化则覆盖写回。"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        # 若 UTF-8 解码失败，则尝试 GBK 读取
        with open(filepath, "r", encoding="gbk", errors="ignore") as f:
            content = f.read()

    new_content = remove_emojis_from_text(content)
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[已处理] {filepath}")


def main():
    """
    遍历当前目录及子目录，处理所有目标文件。"""
    for dirpath, _, filenames in os.walk(os.getcwd()):
        for name in filenames:
            _, ext = os.path.splitext(name)
            if ext.lower() in TARGET_EXTENSIONS:
                process_file(os.path.join(dirpath, name))

    print("\n[完成] Emoji 清理完成！")


if __name__ == "__main__":
    main()
