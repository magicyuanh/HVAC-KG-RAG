# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import datetime
import re

# ==========================================
# 1. 原子数据层 (Atomic Layer) - 执法单元
# ==========================================

@dataclass
class Entity:
    """
    实体对象：知识图谱中的逻辑锚点
    
    [V3.9 属性上浮]: 
    新增 properties 字段，用于在图谱坍缩阶段承载从 Relation 上浮的数值属性。
    例如：(Parameter {value: 20, unit: "℃"})
    """
    name: str
    type: str
    confidence: Optional[float] = 1.0
    source_text: Optional[str] = None
    # [Task 4.1] 新增属性容器
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """
        [自洁钩子]：对象实例化时的自动化规整
        """
        # 1. 物理清洗
        if self.name:
            self.name = self.name.strip().strip('"').strip("'").replace('`', '')
            self.name = self.name.replace('\u200b', '')
        
        # 2. 缩写强规整
        if self.name and re.match(r'^[a-zA-Z]{2,6}$', self.name):
            self.name = self.name.upper()
        
        # 3. 类型标准化
        if self.type:
            self.type = self.type.strip().capitalize()

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        result = {"name": self.name, "type": self.type}
        if self.confidence is not None: 
            result["confidence"] = self.confidence
        if self.source_text: 
            result["source_text"] = self.source_text
        if self.properties:
            result["properties"] = self.properties
        return result

@dataclass
class Relation:
    """
    关系对象：实体间的逻辑链路
    
    [Task 4.1 数值降级]: 
    实现数值属性化解析。当 type="HAS_VALUE" 且 target 为数值时，
    将数值解析存入 properties，并标记 _is_value_relation=True。
    """
    source: str
    target: str
    type: str
    # 源实体和目标实体的类型
    source_type: Optional[str] = None
    target_type: Optional[str] = None
    
    description: Optional[str] = None
    confidence: Optional[float] = 1.0
    bidirectional: bool = False
    
    # [Task 4.1] 数值属性容器与标记位
    properties: Dict[str, Any] = field(default_factory=dict)
    _is_value_relation: bool = field(default=False, init=False)
    
    def __post_init__(self):
        """
        [自洁钩子]：关系类型的强约束与数值解析
        """
        # 1. 实体名修剪
        if self.source: 
            self.source = self.source.strip().strip('"').strip("'").replace('`', '').replace('\u200b', '')
        if self.target: 
            self.target = self.target.strip().strip('"').strip("'").replace('`', '').replace('\u200b', '')
        
        # 2. 谓语标准化
        if self.type:
            self.type = self.type.strip().upper().replace(" ", "_").replace("-", "_")
        
        # 3. 实体类型标准化
        if self.source_type: self.source_type = self.source_type.strip().capitalize()
        if self.target_type: self.target_type = self.target_type.strip().capitalize()
        
        # 4. [核心逻辑] 数值解析拦截器
        # 触发条件：关系类型为 HAS_VALUE，且 Target 符合数值特征
        if self.type == "HAS_VALUE" and self._looks_like_value(self.target):
            parsed = self._parse_numerical_value(self.target)
            if parsed:
                # 存入属性 (键名已统一)
                self.properties.update(parsed)
                # 标记为数值关系 (将在导出层被拦截)
                self._is_value_relation = True
                # [Fix] 清空 target_type，因为目标已降级为属性，不再是实体
                self.target_type = None
        
        # 5. 自环降级 (仅非数值关系)
        if self.source == self.target and not self._is_value_relation:
            self.confidence = 0.1 

    def _looks_like_value(self, text: str) -> bool:
        """
        [严格正则] 判断字符串是否为数值表达式
        [Fix V3.12] 移除了对连续字母的排除，防止误杀 '10Pa', '20kW' 等合法单位。
        """
        if not text: 
            return False
        
        # 必须以 [数字] 或 [运算符+数字] 开头
        # 这已经足够排除 AHU-1 (以字母开头)
        return bool(re.match(r'^[≥≤><=~±]?\s*\d', text.strip()))

    def _parse_numerical_value(self, text: str) -> Optional[Dict[str, Any]]:
        """
        [数值解析引擎]
        将 "≥50Pa" 解析为 {operator: "≥", value: 50.0, unit: "Pa"}
        """
        if not text:
            return None

        # 正则分解：(运算符)? (数值) (单位)?
        pattern = r'^([≥≤><=~±]?)\s*([-+]?\d*\.?\d+)\s*(.*)$'
        match = re.match(pattern, text.strip())
        
        if match:
            op, num_str, unit = match.groups()
            try:
                val = float(num_str)
                # [Fix] 统一键名，适配 database.py
                return {
                    "operator": op if op else "=",
                    "value": val,
                    "unit": unit.strip() if unit else "", # 保证非 None
                    "value_raw": text  # 保留原始文本
                }
            except ValueError:
                return None
        return None

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        result = {
            "source": self.source, 
            "target": self.target, 
            "type": self.type
        }
        if self.source_type: result["source_type"] = self.source_type
        if self.target_type: result["target_type"] = self.target_type
        if self.description: result["description"] = self.description
        if self.confidence is not None: result["confidence"] = self.confidence
        if self.bidirectional: result["bidirectional"] = self.bidirectional
        # 序列化属性
        if self.properties: result["properties"] = self.properties
        return result

# ==========================================
# 2. 领域对象层 (Domain Layer)
# ==========================================

@dataclass
class KnowledgeGraph:
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "metadata": self.metadata
        }
    
    def deduplicate(self) -> "KnowledgeGraph":
        """
        [高级自洁]：基于置信度优先原则的去重逻辑
        """
        # 1. 实体去重
        entity_map: Dict[tuple, Entity] = {}
        for e in self.entities:
            if not e.name or not e.type: continue
            key = (e.name, e.type)
            if key not in entity_map or (e.confidence or 0) > (entity_map[key].confidence or 0):
                entity_map[key] = e
        
        # 2. 关系去重
        rel_map: Dict[tuple, Relation] = {}
        for r in self.relations:
            if not r.type: continue
            key = (r.source, r.source_type, r.target, r.target_type, r.type)
            if key not in rel_map or (r.confidence or 0) > (rel_map[key].confidence or 0):
                rel_map[key] = r
                
        return KnowledgeGraph(
            entities=list(entity_map.values()), 
            relations=list(rel_map.values()), 
            metadata=self.metadata
        )

# ==========================================
# 3. 结果传输层 (Transfer Layer)
# ==========================================

@dataclass
class ProcessingResult:
    chunk_id: int
    success: bool
    knowledge_graph: Optional[KnowledgeGraph] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0
    agent_results: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        res = {
            "chunk_id": self.chunk_id,
            "success": self.success,
            "processing_time": self.processing_time,
            "timestamp": datetime.datetime.now().isoformat()
        }
        if self.success and self.knowledge_graph:
            res["knowledge_graph"] = self.knowledge_graph.to_dict()
        if self.error_message:
            res["error_message"] = self.error_message
        return res

# ==========================================
# 4. 检索上下文层 (Retrieval Context)
# ==========================================

@dataclass
class UnifiedContext:
    content: str
    source: str
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.content or not str(self.content).strip():
            self.content = "[Empty Context]"
        if self.score is None:
            self.score = 0.0
        else:
            try:
                self.score = float(self.score)
            except (ValueError, TypeError):
                self.score = 0.0

    def __str__(self):
        return f"[{self.source}] {self.content[:50]}... (Score: {self.score:.4f})"