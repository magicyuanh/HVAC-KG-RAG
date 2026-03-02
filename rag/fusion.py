# -*- coding: utf-8 -*-
from typing import List, Dict, Tuple
from collections import defaultdict

class FusionLayer:
    """
    融合层 (The Mixer) - V3.27 文本流专用版
    
    职责：
    利用 RRF (Reciprocal Rank Fusion) 算法，将来自同质文本源（向量、关键词）
    的有序列表合并为一个统一的、去重的候选列表。
    
    【架构变更说明 V3.27】：
    图谱检索返回的是“三元组事实” (Structured Facts)，与文档切片 (Chunks) 属于异构数据。
    因此，图谱数据不再参与此处的 RRF 融合，而是由 Retriever 在 Rerank 前进行“晚期合并”。
    本模块仅负责 Vector + BM25 的文本融合。
    """

    def __init__(self, rrf_k: int = 60):
        """
        初始化融合层
        :param rrf_k: 平滑常数，通常取 60。
                      公式: Score = 1 / (k + rank)
        """
        self.rrf_k = rrf_k

    def fuse(self, results_dict: Dict[str, List[str]], top_k: int = 50) -> List[str]:
        """
        执行 RRF 融合 (仅针对文本流)
        
        :param results_dict: 字典，Key是来源名称，Value是该来源召回的文本列表（必须是有序的！）
                             Example: {"Vector": ["doc A", "doc B"], "BM25": ["doc B", "doc C"]}
        :param top_k: 初排后保留多少个结果给 Reranker (建议 50-100)
        :return: 融合并去重后的文本列表
        """
        if not results_dict:
            return []

        # 1. 过滤空列表，仅处理有效召回
        valid_sources = {k: v for k, v in results_dict.items() if v}
        if not valid_sources:
            return []

        # print(f"   -> [FUSION] 正在融合文本流: {list(valid_sources.keys())} (RRF k={self.rrf_k})...")
        
        # 2. 初始化分数表
        # Key: 文档内容 (String), Value: RRF 分数 (Float)
        doc_scores: Dict[str, float] = defaultdict(float)
        
        # 3. 遍历每一路检索结果
        for source, docs in valid_sources.items():
            # print(f"      - {source}: 贡献了 {len(docs)} 条")
            
            for rank, doc in enumerate(docs):
                # RRF 公式: score = 1 / (k + rank + 1)
                # rank 从 0 开始，排名越靠前(rank越小)，分数越高
                # +1 是为了防止 rank=0 时分母为 k
                score = 1.0 / (self.rrf_k + rank + 1)
                
                # 累加分数 (如果一个文档在多路都被召回，它的分数会叠加，排名飙升)
                doc_scores[doc] += score
        
        # 4. 根据最终 RRF 分数倒序排列
        # sorted 返回的是 (doc, score) 的列表元组
        sorted_docs: List[Tuple[str, float]] = sorted(
            doc_scores.items(), 
            key=lambda item: item[1], 
            reverse=True
        )
        
        # print(f"      - 文本流融合去重后总数: {len(sorted_docs)} 条")
        
        # 5. 截取 Top K 并只返回文本内容
        final_candidates = [doc for doc, score in sorted_docs[:top_k]]
        
        return final_candidates

# ==========================================
# 简单的单元测试 (Unit Test)
# ==========================================
if __name__ == "__main__":
    fusion = FusionLayer()
    
    # 模拟数据：仅测试文本流融合
    mock_vector = ["文档A", "文档B", "文档C"] # Vector 认为 A 最重要
    mock_bm25 = ["文档B", "文档D", "文档A"]   # BM25 认为 B 最重要
    
    results = {
        "Vector": mock_vector,
        "BM25": mock_bm25,
        "Graph": [] # 空列表测试
    }
    
    # 执行融合
    fused = fusion.fuse(results, top_k=5)
    
    print("\n🏆 融合结果 (预期 B 排第一, A 排第二):")
    for i, doc in enumerate(fused):
        print(f"{i+1}. {doc}")
        
    # 预期分析：
    # B 在 Vector(rank 2) 和 BM25(rank 1) 都出现 -> 分数叠加 -> 第一
    # A 在 Vector(rank 1) 和 BM25(rank 3) 都出现 -> 分数叠加 -> 第二
    # C, D 只出现一次 -> 靠后