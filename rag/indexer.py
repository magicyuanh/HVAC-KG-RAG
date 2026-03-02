# -*- coding: utf-8 -*-
import json
import os
import pickle
import sys
import shutil
import time
from typing import List, Dict, Any

# ==========================================
# 0. 路径补丁 (Path Patching)
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import jieba
import torch
import chromadb
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from config import SystemConfig

class Indexer:
    """
    全能索引构建器 (The Omni-Indexer) - V3.27 生产就绪版
    
    职责：
    1. 读取清洗后的 JSONL 数据 (structured_chunks.jsonl)。
    2. 语义加工：调用本地 Embedding 模型 (BGE-Large) 生成向量 -> 存入 ChromaDB。
    3. 词汇加工：调用 Jieba 分词生成倒排索引 -> 存入 BM25 Pickle。
    4. [新] 严格的资产检查，确保构建过程不依赖外网。
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

    def build(self):
        """
        执行构建全流程
        """
        print("\n🏗️  [INDEXER] 开始构建 V3.27 混合索引...")
        print(f"   -> 运行设备: {self.device}")
        
        # 1. 前置资产检查
        if not self._validate_prerequisites():
            print("❌ [INDEXER] 前置检查未通过，任务终止。")
            return

        # 2. 加载原始数据
        chunks = self._load_chunks()
        if not chunks:
            print("❌ [INDEXER] 数据源为空，任务终止。")
            return

        # 3. 构建向量索引 (ChromaDB)
        self._build_vector_index(chunks)

        # 4. 构建关键词索引 (BM25)
        self._build_bm25_index(chunks)
        
        print("\n✅ [INDEXER] 所有索引构建完毕！RAG 系统准备就绪。")

    def _validate_prerequisites(self) -> bool:
        """检查构建所需的必要条件"""
        # 检查输入文件
        if not os.path.exists(self.config.input_file):
            print(f"❌ 输入文件不存在: {self.config.input_file}")
            print("   -> 请先运行 pipeline.py 生成数据，或检查路径配置。")
            return False

        # 检查 Embedding 模型 (严格本地模式)
        if not os.path.exists(self.config.embedding_model_path):
            print(f"❌ Embedding 模型路径不存在: {self.config.embedding_model_path}")
            print("   -> 生产环境禁止自动下载。请手动下载 'BAAI/bge-large-zh-v1.5' 并解压到该目录。")
            return False

        return True

    def _load_chunks(self) -> List[Dict]:
        """读取 JSONL 源文件"""
        print(f"\n📖 [Loader] 读取数据源: {self.config.input_file}")
        chunks = []
        
        try:
            with open(self.config.input_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        item = json.loads(line)
                        # 数据完整性检查
                        if "content" in item and "chunk_id" in item:
                            chunks.append(item)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"❌ 读取文件出错: {e}")
            return []

        print(f"   -> 成功加载 {len(chunks)} 个文本块")
        return chunks

    def _build_vector_index(self, chunks: List[Dict]):
        """构建 ChromaDB 向量索引"""
        print(f"\n⚡ [Vector] 开始构建向量索引 (ChromaDB)...")
        print(f"   -> 加载本地 Embedding 模型: {self.config.embedding_model_path}")
        
        try:
            embed_model = SentenceTransformer(self.config.embedding_model_path, device=self.device)
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            return

        print("   -> 正在生成向量 (Batch Encoding)...")
        texts = [c["content"] for c in chunks]
        
        # 批量生成向量
        # batch_size=32 是 3090/4090 的安全甜点值
        embeddings = embed_model.encode(
            texts, 
            normalize_embeddings=True, 
            show_progress_bar=True, 
            batch_size=32
        )

        print(f"   -> 正在写入 ChromaDB: {self.config.chroma_db_path}")
        
        try:
            # 初始化 Chroma 客户端 (持久化模式)
            client = chromadb.PersistentClient(path=self.config.chroma_db_path)
            
            collection_name = "knowledge_base"
            
            # 重做索引策略：如果存在旧集合，先删除
            try:
                client.delete_collection(collection_name)
                print(f"   -> 已清理旧集合: {collection_name}")
            except:
                pass
            
            # 创建新集合 (余弦相似度)
            collection = client.create_collection(
                name=collection_name, 
                metadata={"hnsw:space": "cosine"}
            )
            
            # 准备元数据
            ids = [str(c["chunk_id"]) for c in chunks]
            metadatas = []
            
            for c in chunks:
                # 基础元数据
                meta = {"chunk_id": str(c["chunk_id"]), "source": "jsonl"}
                
                # 尝试保留原始 metadata，但强制转字符串以防报错
                if "metadata" in c and isinstance(c["metadata"], dict):
                    for k, v in c["metadata"].items():
                        if v is not None:
                            meta[str(k)] = str(v)[:500] # 限制长度防止超标
                metadatas.append(meta)

            # 批量写入 (Batch Upsert)
            batch_size = 500
            total = len(chunks)
            print(f"   -> 正在存入数据库 (Total: {total})...")
            
            for i in range(0, total, batch_size):
                end = min(i + batch_size, total)
                collection.add(
                    embeddings=embeddings[i:end],
                    documents=texts[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end]
                )
                print(f"      ... Processed {end}/{total}")
                
            print("   -> 向量索引构建完成。")
            
        except Exception as e:
            print(f"❌ ChromaDB 操作失败: {e}")

    def _build_bm25_index(self, chunks: List[Dict]):
        """构建 BM25 关键词索引"""
        print(f"\n📚 [Keyword] 开始构建关键词索引 (BM25)...")
        texts = [c["content"] for c in chunks]
        
        print("   -> 执行 Jieba 分词...")
        # 对每个文档进行中文分词
        tokenized_corpus = [list(jieba.cut(text)) for text in texts]
        
        print("   -> 训练 BM25 模型...")
        bm25 = BM25Okapi(tokenized_corpus)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.config.bm25_index_path), exist_ok=True)
        
        print(f"   -> 保存索引到: {self.config.bm25_index_path}")
        try:
            with open(self.config.bm25_index_path, "wb") as f:
                pickle.dump({
                    "bm25": bm25,
                    "chunks": chunks  # 存入原始内容以便检索时回显
                }, f)
            print("   -> BM25 索引构建完成。")
        except Exception as e:
            print(f"❌ BM25 保存失败: {e}")

# ==========================================
# 独立运行入口
# ==========================================
if __name__ == "__main__":
    try:
        # 实例化配置 (会触发安检 Warning，但 Indexer 内部有更严的检查)
        cfg = SystemConfig()
        
        # 启动构建器
        indexer = Indexer(cfg)
        indexer.build()
        
    except Exception as e:
        print(f"\n❌ [FATAL ERROR] 索引构建进程崩溃: {e}")
        import traceback
        traceback.print_exc()