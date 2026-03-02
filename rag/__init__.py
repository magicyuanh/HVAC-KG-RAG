# -*- coding: utf-8 -*-

# ==========================================
# RAG 核心包初始化 (Package Initializer)
# ==========================================
# 职责：
# 1. 标识 rag/ 目录为一个标准的 Python 包
# 2. 暴露核心组件类，简化外部调用路径
# 3. 隐藏内部实现细节 (如辅助函数、私有类)
# ==========================================

# --- 1. 索引构建模块 (Indexing) ---
# 用于将 JSONL 数据转化为 Chroma 向量和 BM25 索引
from .indexer import Indexer

# --- 2. 检索调度模块 (Retrieval) ---
# HybridRetriever: 三位一体总控
# GraphRetriever: Neo4j 图谱检索专用接口
from .retriever import HybridRetriever
from .graph_search import GraphRetriever

# --- 3. 排序与融合模块 (Ranking & Fusion) ---
# FusionLayer: RRF 算法实现
# RerankModel: BGE Cross-Encoder 模型封装
from .fusion import FusionLayer
from .reranker import RerankModel

# --- 4. 生成模块 (Generation) ---
# [V3.1] 已激活：负责组装 Prompt 并调用 LLM 生成回答
from .generator import ResponseGenerator

# ==========================================
# 5. 导出白名单 (__all__)
# ==========================================
# 定义当使用 `from rag import *` 时，允许外部访问的类
__all__ = [
    "Indexer",
    "HybridRetriever",
    "GraphRetriever",
    "FusionLayer",
    "RerankModel",
    "ResponseGenerator", 
]