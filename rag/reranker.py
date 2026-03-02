# -*- coding: utf-8 -*-
import os
import sys
import torch
from typing import List

# ==========================================
# 0. 路径补丁
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from sentence_transformers import CrossEncoder
from config import SystemConfig
# [Fix 1] 引入核心数据契约
from core.models import UnifiedContext

class RerankModel:
    """
    重排序裁判 (The Standardized Referee) - V3.28 生产健壮版
    
    职责：
    1. 接收 UnifiedContext 对象列表（包含文本切片和图谱事实）。
    2. 提取 content 与 query 组成对。
    3. 利用 BGE-Reranker 计算语义相关性 Logits。
    4. 原地更新对象的 score 属性，实现跨模态内容的统一排序。
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        print(f"\n🔥 [RERANKER] 初始化重排序引擎...")
        print(f"   -> 运行设备: {self.device}")
        
        # [Fix 2] 严格的本地路径检查
        # 生产环境严禁自动联网下载大文件，必须手动部署模型
        if not os.path.exists(self.config.reranker_model_path):
            error_msg = (
                f"❌ [CRITICAL] Reranker 模型路径不存在: {self.config.reranker_model_path}\n"
                f"   请手动下载 'BAAI/bge-reranker-large' 并解压到该目录。\n"
                f"   系统禁止自动从 HuggingFace 下载模型。"
            )
            print(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            print(f"   -> 加载本地模型: {self.config.reranker_model_path}")
            # 加载 Cross-Encoder
            # max_length=512 是 BGE 的模型限制，保持硬编码以匹配模型特性
            self.model = CrossEncoder(
                self.config.reranker_model_path, 
                max_length=512, 
                device=self.device
            )
            print("   ✅ [RERANKER] 裁判就位 (BGE-Reranker-Large).")
        except Exception as e:
            print(f"❌ [RERANKER] 模型加载失败: {e}")
            raise e

    def rank(self, query: str, candidates: List[UnifiedContext], top_k: int = 5) -> List[UnifiedContext]:
        """
        执行对象级精排 (异构数据统分)
        
        :param query: 用户问题
        :param candidates: 统一上下文对象列表 (包含 content 和 source)
        :param top_k: 最终保留多少条
        :return: 排序后的对象列表 (score 已更新)
        """
        if not candidates:
            return []

        # 1. 构造输入对：提取 UnifiedContext 中的文本
        # 格式: [[query, doc.content], ...]
        # 这一步实现了"晚期融合"：不论是 Vector 召回的文档，还是 Graph 召回的事实，
        # 在 Reranker 眼里都是等待与 Query 比对的文本。
        pairs = [[query, doc.content] for doc in candidates]

        # 2. 推理打分 (No Grad 模式节省显存)
        try:
            with torch.no_grad():
                # BGE Reranker 输出的是 logits (无界的实数)，越大越相关
                # [Fix 3] 增加 batch_size 防止 OOM，虽然通常 candidates 不多，但这是安全措施
                scores = self.model.predict(
                    pairs, 
                    batch_size=32, 
                    show_progress_bar=False
                )
        except Exception as e:
            # [Fix 4] 优雅降级 (Graceful Degradation)
            # 如果 Reranker 挂了（如显存溢出、特殊字符报错），不要丢弃召回结果！
            # 而是返回原始的候选集（按召回阶段的粗排顺序），保证系统至少有输出。
            print(f"   ⚠️ [RERANKER] 推理异常 (自动降级为原始排序): {e}")
            return candidates[:top_k]

        # 3. 原地更新对象属性 (In-place Update)
        # 保持对象的 source 和 metadata 不变，仅注入分数
        for doc, score in zip(candidates, scores):
            doc.score = float(score)

        # 4. 依据分数倒序排列
        ranked_results = sorted(candidates, key=lambda x: x.score, reverse=True)

        # 5. 截取 Top K
        return ranked_results[:top_k]

# ==========================================
# 单元测试
# ==========================================
if __name__ == "__main__":
    try:
        # 模拟配置
        cfg = SystemConfig()
        
        # 预检查路径，防止测试脚本直接崩溃
        if not os.path.exists(cfg.reranker_model_path):
             print(f"⚠️ [TEST SKIP] 本地无模型 ({cfg.reranker_model_path})，跳过测试。")
             sys.exit(0)

        engine = RerankModel(cfg)
        
        # 构造 V3.28 标准测试数据 (包含文本流和知识流)
        q = "PPO算法的优势"
        
        mock_candidates = [
            UnifiedContext(
                content="PPO算法通过截断策略更新幅度，保证了训练的稳定性。", 
                source="Vector", 
                score=0.0
            ),
            UnifiedContext(
                content="今天天气不错，适合出去游玩。", # 干扰项
                source="BM25", 
                score=0.0
            ),
            UnifiedContext(
                content="【图谱事实】PPO --[HAS_ADVANTAGE]--> 训练稳定性", # 知识流
                source="Graph", 
                score=0.0
            )
        ]
        
        print(f"\n🧪 测试 Query: {q}")
        results = engine.rank(q, mock_candidates, top_k=3)
        
        print("\n🏆 最终排序 (预期: Vector/Graph 前两名, BM25 最后):")
        for i, res in enumerate(results):
            # 打印 score 和 source 验证融合效果
            print(f"[{i+1}] Score: {res.score:.4f} | Src: {res.source} | {res.content[:30]}...")
            
    except Exception as e:
        print(f"❌ Error: {e}")