# -*- coding: utf-8 -*-
import csv
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set

# [关键引用] 相对引用
from .models import ProcessingResult

class Neo4jExporter:
    """
    Neo4j 数据导出器 [V3.15 悬空边拦截版]
  
    职责：
    1. [图谱坍缩]：销毁 Value 节点和数值关系，属性上浮。
    2. [悬空拦截]：物理拦截所有指向 Value 节点的关系，防止数据库导入报错。
    3. [动态 Schema]：全量扫描字段，适配不定长属性。
    """

    def __init__(self, export_dir: str):
        """
        初始化导出器
        """
        self.export_dir = Path(export_dir).resolve()
        if self.export_dir.suffix:
            self.export_dir = self.export_dir.parent
        
        self.export_dir.mkdir(parents=True, exist_ok=True)
      
        self.nodes_file = self.export_dir / "neo4j_nodes.csv"
        self.rels_file = self.export_dir / "neo4j_relationships.csv"

    def export(self, results: List[ProcessingResult]):
        """
        执行全局合并、属性上浮与导出
        """
        if not results:
            print("⚠️ [EXPORTER] 结果列表为空，取消导出。")
            return

        print(f"📦 [EXPORTER] 正在处理 {len(results)} 个任务结果 (执行数值降级与悬空拦截)...")

        # =========================================================
        # Phase 1: 节点预注册 (Node Registry)
        # =========================================================
        global_nodes: Dict[Tuple[str, str], Dict[str, Any]] = {}
        
        for res in results:
            if not res.success or not res.knowledge_graph:
                continue
            
            kg = res.knowledge_graph
            for entity in kg.entities:
                node_key = (entity.name, entity.type)
                
                # [Fix V3.14] 语法修复：else 1.0
                new_conf = entity.confidence if entity.confidence is not None else 1.0
                
                existing = global_nodes.get(node_key)
                if existing:
                    old_conf = existing.get('confidence:float', 0.0)
                    if new_conf > old_conf:
                        global_nodes[node_key] = self._format_node_row(entity)
                else:
                    global_nodes[node_key] = self._format_node_row(entity)

        # =========================================================
        # Phase 2: 关系处理与属性上浮 (Attribute Promotion)
        # =========================================================
        global_relationships: List[Dict[str, Any]] = []
        value_relations_collapsed = 0
        dangling_edges_removed = 0
        
        for res in results:
            if not res.success or not res.knowledge_graph:
                continue
            
            kg = res.knowledge_graph
            for rel in kg.relations:
                source_key = (rel.source, rel.source_type)
                target_key = (rel.target, rel.target_type)
                
                source_row = global_nodes.get(source_key)
                # 核心防御：源节点必须存在
                if not source_row:
                    continue

                # A. [Task 4.2] 标准数值降级逻辑
                # 依据 models.py 的正则判断
                if getattr(rel, '_is_value_relation', False):
                    if rel.properties:
                        for k, v in rel.properties.items():
                            if k == "value":
                                source_row["value:float"] = v
                            else:
                                source_row[k] = v
                    value_relations_collapsed += 1
                    continue

                # B. 获取目标节点
                target_row = global_nodes.get(target_key)
                if not target_row:
                    continue

                # C. [Fix V3.15] 悬空边最终拦截 (Dangling Edge Interception)
                # 既然我们在 Phase 3 会删除所有 Value 节点，
                # 那么这里必须拦截所有指向 Value 节点的关系，否则导入时会报错 "Node not found"
                if target_row.get("type") == "Value":
                    dangling_edges_removed += 1
                    continue
                
                # D. 正常关系格式化
                start_id = source_row["id:ID"]
                end_id = target_row["id:ID"]
                rel_row = self._format_rel_row(rel, res.chunk_id, start_id, end_id)
                global_relationships.append(rel_row)

        # =========================================================
        # Phase 3: 节点清洗 (Node Purging)
        # =========================================================
        final_nodes = []
        value_nodes_removed = 0
        
        for key, row in global_nodes.items():
            _, node_type = key
            # 物理删除所有 Value 节点
            if node_type == "Value":
                value_nodes_removed += 1
                continue
            final_nodes.append(row)

        # =========================================================
        # Phase 4: 动态 Schema 写入
        # =========================================================
        
        # 4.1 节点表头
        all_node_keys: Set[str] = set()
        for row in final_nodes:
            all_node_keys.update(row.keys())
        
        base_headers = ["id:ID", "name", "type", ":LABEL", "confidence:float"]
        dynamic_headers = sorted([k for k in all_node_keys if k not in base_headers])
        node_fieldnames = base_headers + dynamic_headers

        # 4.2 写入节点
        self._write_to_csv(self.nodes_file, final_nodes, fieldnames=node_fieldnames)
        
        # 4.3 写入关系 (全量扫描表头)
        if global_relationships:
            all_rel_keys: Set[str] = set()
            for row in global_relationships:
                all_rel_keys.update(row.keys())
            
            base_rel_headers = [":START_ID", ":END_ID", "type:TYPE"]
            dynamic_rel_headers = sorted([k for k in all_rel_keys if k not in base_rel_headers])
            rel_fieldnames = base_rel_headers + dynamic_rel_headers
            
            self._write_to_csv(self.rels_file, global_relationships, fieldnames=rel_fieldnames)
        else:
            with open(self.rels_file, 'w', encoding='utf-8') as f:
                f.write(":START_ID,:END_ID,type:TYPE\n")

        print(f"✅ [EXPORTER] 导出完成!")
        print(f"   -> 最终节点: {len(final_nodes)} (清洗 {value_nodes_removed} 个数值节点)")
        print(f"   -> 最终关系: {len(global_relationships)}")
        print(f"      (坍缩 {value_relations_collapsed} 条标准数值边)")
        print(f"      (拦截 {dangling_edges_removed} 条残留悬空边)")

    def _format_node_row(self, entity) -> Dict[str, Any]:
        """将 Entity 映射为 CSV 行"""
        node_id = f"{entity.name}::{entity.type}"
        row = {
            "id:ID": node_id,
            "name": entity.name,
            "type": entity.type,
            "confidence:float": entity.confidence,
            ":LABEL": f"Entity;{entity.type}",
            "source_text": entity.source_text if entity.source_text else ""
        }
        if hasattr(entity, 'properties') and entity.properties:
            row.update(entity.properties)
        return row

    def _format_rel_row(self, rel, chunk_id: int, start_id: str, end_id: str) -> Dict[str, Any]:
        """将 Relation 映射为 CSV 行"""
        row = {
            ":START_ID": start_id,
            ":END_ID": end_id,
            "type:TYPE": rel.type,
            "description": rel.description if rel.description else "",
            "confidence:float": rel.confidence,
            "bidirectional:boolean": str(rel.bidirectional).lower(),
            # [Fix V3.14] 明确 chunk_id 为字符串，防止导入类型报错
            "chunk_id:string": str(chunk_id)
        }
        if rel.properties and not getattr(rel, '_is_value_relation', False):
            row.update(rel.properties)
        return row

    def _write_to_csv(self, file_path: Path, data: List[Dict[str, Any]], fieldnames: List[str]):
        """物理写入 CSV"""
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
        except Exception as e:
            print(f"❌ [EXPORTER] 写入 CSV 失败 ({file_path.name}): {e}")