# -*- coding: utf-8 -*-
import os
import csv
import time
from typing import Dict, List, Any, Tuple
from dotenv import load_dotenv
from neo4j import GraphDatabase

# ==========================================
# 配置部分
# ==========================================
# 加载 .env 环境变量
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
TARGET_DB = "neo4j"  # Docker版默认数据库名为 neo4j

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NODES_FILE = os.path.join(BASE_DIR, "graph", "neo4j_nodes.csv")
RELS_FILE = os.path.join(BASE_DIR, "graph", "neo4j_relationships.csv")

BATCH_SIZE = 1000  # 每次提交的批次大小

class Neo4jImporter:
    def __init__(self, uri, user, password, database):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self):
        self.driver.close()

    def create_constraints(self):
        """创建唯一性约束，加速导入"""
        print("⚡ 正在创建索引和约束...")
        query = "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE"
        with self.driver.session(database=self.database) as session:
            session.run(query)
        print("✅ 约束创建完成: Entity(id)")

    def _parse_header(self, header_row: List[str]) -> Dict[str, str]:
        """
        解析表头，返回 字段名 -> 类型 的映射
        例如: 'confidence:float' -> ('confidence', 'float')
        """
        mapping = {}
        for col in header_row:
            if ":" in col:
                # 处理 id:ID, :LABEL, confidence:float 等
                parts = col.split(":")
                name = parts[0]
                type_hint = parts[-1] # 取最后一个作为类型 (处理 id:ID)
                
                # 特殊字段处理
                if type_hint == "ID": 
                    mapping[col] = ("id", "string")
                elif type_hint == "LABEL":
                    mapping[col] = ("_labels", "label_list")
                elif type_hint == "START_ID":
                    mapping[col] = ("_start", "string")
                elif type_hint == "END_ID":
                    mapping[col] = ("_end", "string")
                elif type_hint == "TYPE":
                    mapping[col] = ("_type", "type_str")
                else:
                    mapping[col] = (name, type_hint)
            else:
                # 无后缀默认为 string
                mapping[col] = (col, "string")
        return mapping

    def _convert_value(self, value: str, type_hint: str) -> Any:
        """根据类型后缀转换数据"""
        if value is None or value == "":
            return None
        
        try:
            if type_hint == "float":
                return float(value)
            elif type_hint == "int" or type_hint == "long":
                return int(value)
            elif type_hint == "boolean":
                return value.lower() == "true"
            elif type_hint == "label_list":
                # Entity;Standard -> ['Entity', 'Standard']
                return value.split(";")
            else:
                return value
        except ValueError:
            return value # 转换失败保留原值

    def import_nodes(self):
        if not os.path.exists(NODES_FILE):
            print(f"❌ 未找到节点文件: {NODES_FILE}")
            return

        print(f"📥 开始导入节点: {NODES_FILE}")
        
        with open(NODES_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # 解析表头映射
            header_map = self._parse_header(reader.fieldnames)
            
            # 按 Label 组合进行分组缓冲
            # key: tuple(labels), value: list of node_dicts
            batches = {} 
            count = 0

            for row in reader:
                node_data = {}
                labels = ["Entity"] # 默认标签
                
                for csv_col, val in row.items():
                    prop_name, prop_type = header_map.get(csv_col, (csv_col, "string"))
                    converted_val = self._convert_value(val, prop_type)
                    
                    if prop_type == "label_list" and converted_val:
                        labels = converted_val # 覆盖默认标签，使用CSV中的 Entity;Standard
                    elif converted_val is not None:
                        node_data[prop_name] = converted_val
                
                # 使用标签元组作为分组键
                label_key = tuple(sorted(labels))
                if label_key not in batches:
                    batches[label_key] = []
                
                batches[label_key].append(node_data)
                count += 1

                # 检查是否需要提交
                if len(batches[label_key]) >= BATCH_SIZE:
                    self._flush_nodes(label_key, batches[label_key])
                    batches[label_key] = []

            # 提交剩余数据
            for label_key, data in batches.items():
                if data:
                    self._flush_nodes(label_key, data)
            
            print(f"✅ 节点导入完成，共处理 {count} 个节点")

    def _flush_nodes(self, labels: Tuple[str], data: List[Dict]):
        """执行节点批量插入"""
        label_str = "".join([f":`{l}`" for l in labels])
        # Cypher: UNWIND $batch as row MERGE (n:Label1:Label2 {id: row.id}) SET n += row
        # 注意：我们要把 id 从属性中分离出来做 MERGE 键，其他做 SET
        
        query = f"""
        UNWIND $batch AS row
        MERGE (n{label_str} {{id: row.id}})
        SET n += row
        """
        try:
            with self.driver.session(database=self.database) as session:
                session.run(query, batch=data)
            print(f"   -> 写入 {len(data)} 个节点 (Labels: {labels})")
        except Exception as e:
            print(f"❌ 节点写入失败: {e}")

    def import_relationships(self):
        if not os.path.exists(RELS_FILE):
            print(f"❌ 未找到关系文件: {RELS_FILE}")
            return

        print(f"📥 开始导入关系: {RELS_FILE}")
        
        with open(RELS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header_map = self._parse_header(reader.fieldnames)
            
            # 按关系类型分组缓冲
            batches = {}
            count = 0

            for row in reader:
                rel_data = {}
                start_id = None
                end_id = None
                rel_type = "RELATED_TO" # 默认

                for csv_col, val in row.items():
                    prop_name, prop_type = header_map.get(csv_col, (csv_col, "string"))
                    converted_val = self._convert_value(val, prop_type)

                    if prop_name == "_start":
                        start_id = converted_val
                    elif prop_name == "_end":
                        end_id = converted_val
                    elif prop_name == "_type":
                        rel_type = converted_val
                    elif converted_val is not None:
                        rel_data[prop_name] = converted_val
                
                if not start_id or not end_id:
                    continue

                # 构造符合 Cypher 传入的数据结构
                item = {
                    "start": start_id,
                    "end": end_id,
                    "props": rel_data
                }

                if rel_type not in batches:
                    batches[rel_type] = []
                
                batches[rel_type].append(item)
                count += 1

                if len(batches[rel_type]) >= BATCH_SIZE:
                    self._flush_relationships(rel_type, batches[rel_type])
                    batches[rel_type] = []

            # 提交剩余数据
            for r_type, data in batches.items():
                if data:
                    self._flush_relationships(r_type, data)
            
            print(f"✅ 关系导入完成，共处理 {count} 条关系")

    def _flush_relationships(self, rel_type: str, data: List[Dict]):
        """执行关系批量插入"""
        # 注意：这里我们假设节点已经存在，使用 MATCH 查找
        # 关系类型在 Cypher 中不能参数化，必须拼接到字符串中 (注意防注入，但这里来源是受控的)
        
        query = f"""
        UNWIND $batch AS row
        MATCH (source:Entity {{id: row.start}})
        MATCH (target:Entity {{id: row.end}})
        MERGE (source)-[r:`{rel_type}`]->(target)
        SET r += row.props
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                session.run(query, batch=data)
            print(f"   -> 写入 {len(data)} 条关系 (Type: {rel_type})")
        except Exception as e:
            print(f"❌ 关系写入失败: {e}")

if __name__ == "__main__":
    if not NEO4J_URI or not NEO4J_USER:
        print("❌ 请在 .env 文件中配置 NEO4J_URI, NEO4J_USER 和 NEO4J_PASSWORD")
        exit(1)

    importer = Neo4jImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, TARGET_DB)
    
    try:
        # 1. 建立约束 (重要：大幅提升关系导入速度)
        importer.create_constraints()
        
        # 2. 导入节点
        importer.import_nodes()
        
        # 3. 导入关系
        importer.import_relationships()
        
        print("\n🎉 全部导入任务结束！")
        print(f"🎯 目标数据库: {TARGET_DB}")
        
    except Exception as e:
        print(f"\n❌ 发生未捕获异常: {e}")
        if "Database does not exist" in str(e):
            print("💡 提示: 请检查 Neo4j Desktop 中是否存在名为 'gb500732013' 的数据库。")
            print("   如果是社区版 Neo4j，默认数据库通常是 'neo4j'，请修改脚本中的 TARGET_DB 变量。")
    finally:
        importer.close()