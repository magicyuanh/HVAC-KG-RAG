# -*- coding: utf-8 -*-
import os
import sys
import pickle
import jieba
import torch
import time
import chromadb
from typing import List, Dict, Any, Set

# ==========================================
# 0. 路径补丁
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from sentence_transformers import SentenceTransformer
from config import SystemConfig
# [Fix 1] 引入核心数据契约
from core.models import UnifiedContext
# 引入组件
from rag.graph_search import GraphRetriever
from rag.fusion import FusionLayer
from rag.reranker import RerankModel

class HybridRetriever:
    """
    混合检索指挥部 (The Operation Command) - V3.27 双流架构版
    
    职责：
    1. [调度]：并行调度 Vector, BM25, Graph 三路侦察兵。
    2. [分流]：
       - 流 A (文本): Vector + BM25 -> RRF 融合
       - 流 B (知识): Graph -> 独立保留
    3. [归一]：将文本流和知识流统一封装为 UnifiedContext 对象。
    4. [精排]：指挥 Reranker 对异构结果进行统分。
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        print(f"\n⚙️  [RETRIEVER] 初始化作战指挥部 (Device: {self.device})...")

        # 1. 文本流资源 (Vector)
        try:
            self.chroma_client = chromadb.PersistentClient(path=self.config.chroma_db_path)
            self.collection = self.chroma_client.get_collection("knowledge_base")
            # 注意：此处加载 Embedding 模型用于 Query 编码
            self.embed_model = SentenceTransformer(self.config.embedding_model_path, device=self.device)
            print("   ✅ Vector: ChromaDB & Embedding Ready.")
        except Exception as e:
            print(f"   ⚠️ Vector: 初始化失败 ({e})")
            self.collection = None
            self.embed_model = None

        # 2. 文本流资源 (Keyword)
        try:
            if os.path.exists(self.config.bm25_index_path):
                with open(self.config.bm25_index_path, "rb") as f:
                    bm25_data = pickle.load(f)
                    self.bm25 = bm25_data["bm25"]
                    self.bm25_chunks = bm25_data["chunks"]
                print("   ✅ Keyword: BM25 Index Ready.")
            else:
                print("   ⚠️ Keyword: BM25 文件缺失 (跳过)")
                self.bm25 = None
        except Exception as e:
            print(f"   ⚠️ Keyword: 初始化失败 ({e})")
            self.bm25 = None

        # 3. 知识流资源 (Graph)
        # GraphRetriever 内部有完善的容错机制
        self.graph_retriever = GraphRetriever()
        if self.graph_retriever.is_active:
            print("   ✅ Graph: Neo4j Connector Ready.")
        else:
            print("   ⚠️ Graph: Neo4j 未连接 (将降级运行)")

        # 4. 后处理组件
        self.fusion_layer = FusionLayer(rrf_k=60)
        self.rerank_engine = RerankModel(self.config)
        
        print("🚀 [RETRIEVER] 系统就绪，等待指令。")

    def search(self, query: str, top_k: int = 5) -> List[UnifiedContext]:
        """
        执行混合检索任务 (双流并行 + 晚期合并)
        :param query: 用户问题
        :param top_k: 最终返回给 LLM 的参考条数
        :return: 排序后的 UnifiedContext 对象列表
        """
        # print(f"\n🔍 [SEARCH] Query: '{query}'")
        start_total = time.time()
        
        # 宽召回策略：每路召回 top_k * 5 条，保证 Reranker 有足够的候选集
        recall_n = top_k * 5
        
        # === 阶段 1: 多路并行召回 ===
        
        # --- A. 向量路 (Text Stream) ---
        vector_texts: List[str] = []
        t0 = time.time()
        if self.collection and self.embed_model:
            try:
                q_vec = self.embed_model.encode(query, normalize_embeddings=True).tolist()
                res = self.collection.query(query_embeddings=[q_vec], n_results=recall_n)
                if res['documents']:
                    vector_texts = res['documents'][0]
            except Exception as e:
                print(f"   ⚠️ Vector Search Error: {e}")
        t_vec = time.time() - t0

        # --- B. 关键词路 (Text Stream) ---
        bm25_texts: List[str] = []
        t0 = time.time()
        if self.bm25:
            try:
                tokens = list(jieba.cut(query))
                bm25_texts = self.bm25.get_top_n(tokens, [c['content'] for c in self.bm25_chunks], n=recall_n)
            except Exception as e:
                print(f"   ⚠️ BM25 Search Error: {e}")
        t_bm25 = time.time() - t0

        # --- C. 图谱路 (Knowledge Stream) ---
        graph_contexts: List[UnifiedContext] = []
        t0 = time.time()
        try:
            # GraphRetriever 现在直接返回 UnifiedContext 对象列表
            graph_contexts = self.graph_retriever.query_graph(query, limit=recall_n)
        except Exception as e:
            print(f"   ⚠️ Graph Search Error: {e}")
        t_graph = time.time() - t0

        # 性能日志
        # print(f"   ⏱️  Recall Time: Vec={t_vec:.3f}s | BM25={t_bm25:.3f}s | Graph={t_graph:.3f}s")
        # print(f"   📊 Recall Count: V={len(vector_texts)} | B={len(bm25_texts)} | G={len(graph_contexts)}")

        # === 阶段 2: 文本流 RRF 融合 ===
        
        # 仅对同质的文本数据进行融合
        text_stream_results = {
            "Vector": vector_texts,
            "BM25": bm25_texts
        }
        
        # 获取融合排序后的纯文本列表
        fused_texts = self.fusion_layer.fuse(text_stream_results, top_k=recall_n) # 保持宽口径给 Reranker
        
        # === 阶段 3: 归一化与晚期合并 (Late Fusion) ===
        
        candidates: List[UnifiedContext] = []
        
        # 3.1 处理文本流结果
        # 为了标记来源 (Vector/BM25)，我们建立查找集
        set_vec = set(vector_texts)
        set_bm25 = set(bm25_texts)
        
        for text in fused_texts:
            sources = []
            if text in set_vec: sources.append("Vector")
            if text in set_bm25: sources.append("BM25")
            source_tag = "+".join(sources) if sources else "Text"
            
            # 封装为标准对象
            ctx = UnifiedContext(
                content=text,
                source=source_tag,
                score=0.0 # 初始分置0，完全依赖 Reranker 打分
            )
            candidates.append(ctx)
            
        # 3.2 合并知识流结果
        # 图谱结果已经是 UnifiedContext 对象，直接加入
        # 注意：这里我们不做去重，因为图谱事实(Structured)和文档(Unstructured)本质不同
        candidates.extend(graph_contexts)
        
        if not candidates:
            print("   ⚠️ 无任何候选结果。")
            return []

        # === 阶段 4: 统一重排序 (Rerank) ===
        
        # RerankModel 能够处理 mixed candidates (文本 + 事实)
        final_results = self.rerank_engine.rank(
            query=query,
            candidates=candidates,
            top_k=top_k
        )
        
        total_time = time.time() - start_total
        print(f"✅ [SEARCH] 检索完成，总耗时 {total_time:.3f}s (Candidates: {len(candidates)} -> Final: {len(final_results)})")
        
        return final_results

    def close(self):
        """清理资源"""
        if hasattr(self, 'graph_retriever'):
            self.graph_retriever.close()

    def __del__(self):
        self.close()

# ==========================================
# 调试入口
# ==========================================
if __name__ == "__main__":
    try:
        cfg = SystemConfig()
        # 确保安检通过
        cfg.validate_arsenal()
        
        retriever = HybridRetriever(cfg)
        
        query = "洁净室" # 测试词
        print(f"\n🧪 Testing Query: {query}")
        
        results = retriever.search(query, top_k=5)
        
        print(f"\n🏆 Top {len(results)} Results:")
        for i, item in enumerate(results):
            # 打印简略信息
            content_preview = item.content.replace('\n', ' ')[:60]
            print(f"[{i+1}] Score: {item.score:.4f} | Src: {item.source} | {content_preview}...")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()