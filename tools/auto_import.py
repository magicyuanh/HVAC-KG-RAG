# -*- coding: utf-8 -*-
import sys
import os
import time
import pandas as pd
from neo4j import GraphDatabase

# ==========================================
# 0. 路径补丁 (Path Patching)
# ==========================================
# 将项目根目录加入 Python 搜索路径，以便导入 config.py
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config import SystemConfig

class Neo4jImporter:
    """
    Neo4j 自动化导入引擎 (V3.0 适配版)
    职责：读取 graph/ 目录下的 CSV，将其批量注入图数据库
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        
        # 1. 获取数据库配置 (从环境变量获取)
        # 注意：Config 类初始化时已加载了 .env
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD")
        
        # [修改点]：不再硬编码，优先读取环境变量，默认值为 "dreampipeline"
        self.target_db = os.getenv("NEO4J_DB_NAME", "dreampipeline")

        # 2. 组装 CSV 文件路径 (使用 V3.0 的 graph_dir)
        self.nodes_csv = os.path.join(self.config.graph_dir, "neo4j_nodes.csv")
        self.rels_csv = os.path.join(self.config.graph_dir, "neo4j_relationships.csv")

        # 3. 初始化驱动
        if not self.password:
            raise ValueError("❌ 错误: 未在 .env 中找到 NEO4J_PASSWORD")
        
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()

    def check_connection(self):
        """测试连接是否畅通"""
        try:
            self.driver.verify_connectivity()
            print(f"✅ Neo4j 认证成功，连接正常 ({self.uri})。")
        except Exception as e:
            print(f"❌ Neo4j 连接失败: {e}")
            raise e

    def run_import(self):
        """执行导入全流程"""
        print(f"\n🚀 [IMPORTER] 开始向数据库 [{self.target_db}] 注入数据...")
        
        # 检查文件是否存在
        if not os.path.exists(self.nodes_csv) or not os.path.exists(self.rels_csv):
            print(f"❌ 找不到 CSV 文件，请检查 {self.config.graph_dir}")
            return

        start_time = time.time()

        # 1. 使用 Pandas 预读取数据并清洗
        # 确保 ID 列被视为字符串，防止数字 ID 导致匹配失败
        print(f"📖 读取 CSV 文件: {self.config.graph_dir}")
        nodes_df = pd.read_csv(self.nodes_csv, dtype={"node_id:ID": str})
        rels_df = pd.read_csv(self.rels_csv, dtype={":START_ID": str, ":END_ID": str})

        # 将 NaN 替换为空字符串，防止 Cypher 报错
        nodes_df = nodes_df.fillna("")
        rels_df = rels_df.fillna("")

        # 2. 执行数据库事务
        try:
            with self.driver.session(database=self.target_db) as session:
                
                # Step A: 创建约束 (幂等操作)
                print("🏗️  正在配置数据库索引与唯一性约束...")
                session.run("CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE")

                # Step B: 批量导入节点
                print(f"📦 正在同步 {len(nodes_df)} 个节点...")
                # node_id:ID, name, type, confidence:float, :LABEL, source_text
                node_query = """
                UNWIND $rows AS row
                MERGE (n:Entity {id: row.`node_id:ID`})
                SET n.name = row.name,
                    n.type = row.type,
                    n.confidence = toFloat(row.`confidence:float`),
                    n.source_text = row.source_text
                WITH n, row
                // 利用 APOC 动态添加具体的业务标签 (如 :Method, :Dataset)
                CALL apoc.create.addLabels(n, [row.type]) YIELD node
                RETURN count(*)
                """
                session.run(node_query, rows=nodes_df.to_dict('records'))

                # Step C: 批量导入关系
                print(f"🔗 正在编织 {len(rels_df)} 条逻辑链路...")
                # :START_ID, :END_ID, type:TYPE, description, confidence:float, bidirectional:boolean, chunk_id
                rel_query = """
                UNWIND $rows AS row
                MATCH (source:Entity {id: row.`:START_ID`})
                MATCH (target:Entity {id: row.`:END_ID`})
                // 利用 APOC 动态创建关系类型
                CALL apoc.create.relationship(source, row.`type:TYPE`, {
                    description: row.description,
                    confidence: toFloat(row.`confidence:float`),
                    chunk_id: toInteger(row.chunk_id)
                }, target) YIELD rel
                RETURN count(*)
                """
                session.run(rel_query, rows=rels_df.to_dict('records'))

            duration = time.time() - start_time
            print(f"\n✨ 任务圆满完成!")
            print(f"⏱️  导入耗时: {duration:.2f} 秒")
            print(f"📊 资产清单: {len(nodes_df)} 实体节点, {len(rels_df)} 逻辑关系。")
            print(f"📍 目标库: {self.target_db}")
            
        except Exception as e:
            print(f"❌ 数据库操作失败: {e}")
            print(f"   -> 请检查数据库 {self.target_db} 是否已创建且处于 Online 状态。")

# ==========================================
# 独立运行入口
# ==========================================
if __name__ == "__main__":
    importer = None
    try:
        # 1. 初始化配置 (自动获取路径)
        config = SystemConfig()
        
        # 2. 初始化导入器
        importer = Neo4jImporter(config)
        
        # 3. 检查连接并运行
        importer.check_connection()
        importer.run_import()
        
    except Exception as e:
        print(f"\n🚨 导入终止: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if importer:
            importer.close()