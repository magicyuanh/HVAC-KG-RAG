# -*- coding: utf-8 -*-
import os
import sys
from typing import List, Dict, Any
from neo4j import GraphDatabase
from dotenv import load_dotenv

# ==========================================
# 0. 路径补丁 & 依赖加载
# ==========================================
# 确保能引用到 core 包
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# [Fix 1] 引入标准数据模型，适配融合层
from core.models import UnifiedContext

# 加载环境变量
load_dotenv()

class GraphRetriever:
    """
    图谱检索器 (The Resilience Scout) - V3.27 修复版
    
    职责：
    1. 实体链接：在用户提问中发现图谱节点。
    2. 逻辑召回：提取一跳邻居关系，补充向量检索丢失的因果链。
    3. [数据契约]：返回 UnifiedContext 对象列表，适配混合检索融合层。
    """

    def __init__(self):
        # 1. 基础连接配置
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "")
        
        # [Fix 2] 数据库名不再硬编码，默认回退到 neo4j
        self.db_name = os.getenv("NEO4J_DATABASE", "neo4j")
        
        self.driver = None
        self.is_active = False

        # 2. 凭证自检
        # 允许密码为空字符串（开发环境），但如果连 uri 都没有则跳过
        if not self.uri:
            print("⚠️  [GRAPH] 警告: NEO4J_URI 未配置。图谱模块已挂起。")
            return

        # 3. 建立连接 (带防火墙逻辑)
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # 握手验证
            self.driver.verify_connectivity()
            self.is_active = True
            # print(f"🕸️  [GRAPH] Neo4j 连接成功: {self.uri} (DB: {self.db_name})")
        except Exception as e:
            self.driver = None
            self.is_active = False
            print(f"⚠️  [GRAPH] 数据库连接失败: {e}。系统将降级为纯向量模式。")

    def query_graph(self, query_text: str, limit: int = 20) -> List[UnifiedContext]:
        """
        执行图谱召回
        
        [Fix V3.27]：
        返回 UnifiedContext 对象列表，而非字符串列表。
        这允许 Reranker 基于 content 打分，同时保留 source="Graph" 的元数据。
        """
        if not self.is_active or not self.driver:
            return []

        # Cypher 逻辑：执行大小写不敏感的实体匹配
        # [Performance Note]: 生产环境建议为 Entity(name) 建立 Fulltext Index
        # 并使用 db.index.fulltext.queryNodes 以提升性能。
        # 当前 CONTAINS 写法兼容性最好，但数据量超 10w 时会变慢。
        cypher = """
        MATCH (n:Entity)
        WHERE toLower($q) CONTAINS toLower(n.name)
        MATCH (n)-[r]-(m)
        RETURN DISTINCT n.name AS source_name, 
                        type(r) AS rel_type, 
                        m.name AS target_name, 
                        r.description AS desc, 
                        r.confidence AS confidence
        ORDER BY confidence DESC
        LIMIT $limit
        """
        
        graph_contexts: List[UnifiedContext] = []
        
        try:
            with self.driver.session(database=self.db_name) as session:
                # 使用 q=query_text 传递参数，防止注入
                result = session.run(cypher, q=query_text, limit=limit)
                
                for record in result:
                    # [Fix 3] 使用别名安全获取字段
                    n_name = record["source_name"]
                    r_type = record["rel_type"]
                    m_name = record["target_name"]
                    desc = record["desc"]
                    confidence = record["confidence"]
                    
                    # 1. 构造自然语言描述 (供 LLM 阅读)
                    # 格式: 【图谱事实】实体A --[关系]--> 实体B (描述)
                    fact_str = f"【图谱事实】{n_name} --[{r_type}]--> {m_name}"
                    if desc:
                        fact_str += f" (描述: {desc})"
                    
                    # 2. 归一化置信度 (处理 None)
                    score = float(confidence) if confidence is not None else 0.8
                    
                    # 3. 封装为标准对象
                    ctx = UnifiedContext(
                        content=fact_str,
                        source="Graph",
                        score=score,
                        metadata={
                            "source_entity": n_name,
                            "target_entity": m_name,
                            "relation": r_type
                        }
                    )
                    
                    graph_contexts.append(ctx)
                    
        except Exception as e:
            # 捕获 DatabaseNotFound 等特定错误并提示
            if "Database does not exist" in str(e):
                print(f"❌ [GRAPH] 数据库 '{self.db_name}' 不存在。请在 .env 中设置正确的 NEO4J_DATABASE (默认: neo4j)")
            else:
                print(f"⚠️  [GRAPH] 检索过程异常: {e}")
            return []
            
        return graph_contexts

    def close(self):
        """释放连接池资源"""
        if self.driver:
            try:
                self.driver.close()
            except:
                pass

    def __del__(self):
        """确保对象销毁时关闭驱动"""
        self.close()

# ==========================================
# 测试桩
# ==========================================
if __name__ == "__main__":
    # 简单的冒烟测试
    retriever = GraphRetriever()
    test_q = "洁净室" # 也可以换成 "洁净室" 或其他领域词
    
    if retriever.is_active:
        print(f"\n🔍 正在执行回归测试: Query='{test_q}' (DB: {retriever.db_name})")
        results = retriever.query_graph(test_q)
        
        if results:
            print(f"✅ 召回了 {len(results)} 条图谱知识:")
            for i, ctx in enumerate(results[:3]):
                print(f"   [{i+1}] {ctx}")
        else:
            print("\nℹ️ 未发现关联知识 (空库或无匹配是正常的)。")
    else:
        print("\n🚫 跳过测试 (无数据库连接)。")
    
    retriever.close()