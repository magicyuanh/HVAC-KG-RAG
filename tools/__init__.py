# -*- coding: utf-8 -*-

"""
ArchRAG 运维工具箱 (Operations Toolkit)
=========================================
本模块包含用于系统维护、数据修复和统计分析的独立脚本。

包含工具：
1. auto_import.py           : Neo4j 图数据库自动导入工具 (CSV -> DB)
2. analyze_stats.py         : 提取质量与 Token 消耗统计分析
3. fix_data_ids.py          : 原始数据 ID 缺失修复补丁
4. clean_failed_checkpoints.py : 断点续传状态清洗工具

使用方式：
通常直接在命令行运行，例如：
> python tools/auto_import.py
"""

# 标识这是一个 Python 包
# 在此不自动导入子模块，避免在导入包时触发脚本内部的逻辑