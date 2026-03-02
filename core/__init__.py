# -*- coding: utf-8 -*-

"""
ArchRAG Core Components (V3.4 修复版)
================================
本模块包含知识提取流水线 (ETL) 的所有核心组件。

包含：
1. 数据模型 (Models & Contracts)
2. 业务流程 (Pipeline)
3. 基础设施 (Database, LLM, Monitoring)

【修复说明】：
为避免导入循环，本文件仅提供导出白名单(__all__)，
不执行具体导入操作。调用者需显式导入所需模块。
"""

# ==========================================
# 1. 导出白名单 (__all__)
# ==========================================
__all__ = [
    "Entity",
    "Relation",
    "KnowledgeGraph",
    "ProcessingResult",
    "UnifiedContext",
    "UltimateKnowledgeExtractor",
    "Neo4jExporter",
    "LLMClient",
    "MonitoringManager",
    "PromptManager",
    "JSONParser",
    "CheckpointManager"
]

# ==========================================
# 2. 元数据定义
# ==========================================
__version__ = "3.4.0"
__author__ = "ArchRAG Team"
__description__ = "知识提取流水线核心组件 (修复导入循环版)"