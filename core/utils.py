# -*- coding: utf-8 -*-
import json
import re
import os
from typing import Dict, Any, Set, List, Optional

# [关键引用] 相对引用
from .models import KnowledgeGraph, Entity, Relation

# ==========================================
# 0. 实体规范化处理器 (Entity Normalizer) [V3.22 最终版]
# ==========================================
class EntityNormalizer:
    """
    全局实体规范化处理器
    
    职责：
    1. [清洗]：暴力循环去括号(含方括号)、去空格、缩写强制大写。
    2. [映射]：同义词归一化 (e.g. 洁净区 -> 洁净室)。
    3. [联动]：确保实体改名后，关系中的 source/target 同步更新。
    """
    
    # 1. 预编译正则，提升性能
    # 匹配中英文括号及内容: (FP), [℃], （区）
    REGEX_BRACKET = re.compile(r'[（(\[][^）)}\]]*[）)}\]]', re.IGNORECASE)
    
    # 匹配2-6位纯字母缩写: AHU, fcu
    REGEX_ABBR = re.compile(r'^[a-zA-Z]{2,6}$')

    # 2. 暖通领域专用同义词表
    SYNONYM_MAP = {
        "洁净区": "洁净室",
        "洁净房间": "洁净室",
        "洁净室（区）": "洁净室",
        "空调机组": "空气处理机组",
        "AHU机组": "空气处理机组",
        "AHU": "空气处理机组",
        "送风机": "送风风机",
        "排风机": "排风风机",
        "回风机": "回风风机",
        "防火阀（FD）": "防火阀",
        "调节阀（FD）": "调节阀", 
        "风机盘管（FP）": "风机盘管",
        "高效过滤器": "高效空气过滤器",
        "中效过滤器": "中效空气过滤器",
        "初效过滤器": "初效空气过滤器"
    }

    @classmethod
    def normalize_graph_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        [核心接口] 全图谱联动清洗
        """
        if not data or not isinstance(data, dict):
            return data

        raw_entities = data.get("entities", [])
        raw_relations = data.get("relations", [])
        
        # --- Phase 1: 实体清洗与映射构建 ---
        clean_entities = []
        rename_map = {}  # {旧名字: 新名字}
        
        for entity in raw_entities:
            old_name = entity.get("name", "")
            if not old_name:
                continue
                
            new_name = cls._clean_single_name(old_name)
            
            # 记录映射关系
            if new_name != old_name:
                rename_map[old_name] = new_name
            
            entity["name"] = new_name
            clean_entities.append(entity)
            
        # --- Phase 2: 关系联动更新 ---
        clean_relations = []
        for rel in raw_relations:
            # 同步更新 source
            src = rel.get("source", "")
            if src in rename_map:
                rel["source"] = rename_map[src]
            else:
                # 即使不在 map 里，也执行一致的清洗
                rel["source"] = cls._clean_single_name(src)
                
            # 同步更新 target
            tgt = rel.get("target", "")
            if tgt in rename_map:
                rel["target"] = rename_map[tgt]
            else:
                rel["target"] = cls._clean_single_name(tgt)
                
            clean_relations.append(rel)
            
        data["entities"] = clean_entities
        data["relations"] = clean_relations
        return data

    @classmethod
    def _clean_single_name(cls, name: str) -> str:
        """单体名称清洗逻辑 (循环清洗，确保幂等)"""
        if not name: return ""
        name = str(name)
        
        # 1. 查表映射 (Pre-clean)
        if name in cls.SYNONYM_MAP:
            return cls.SYNONYM_MAP[name]
            
        # 2. 循环去括号 (支持嵌套括号)
        while True:
            new_name = cls.REGEX_BRACKET.sub('', name)
            if new_name == name:
                break
            name = new_name
        
        # 3. 去除首尾杂质
        name = name.strip().strip('"').strip("'").strip('`')
        
        # 4. 缩写强制大写
        if cls.REGEX_ABBR.match(name):
            name = name.upper()
            
        # 5. 二次查表 (Post-clean)
        if name in cls.SYNONYM_MAP:
            return cls.SYNONYM_MAP[name]
            
        return name

# ==========================================
# 1. 鲁棒的 JSON 解析器 & 文本清洗 (The Cleaner)
# ==========================================
class JSONParser:
    """
    数据清洗与解析器 (V3.22)
    """

    @staticmethod
    def clean_text_compliance(text: str) -> str:
        """
        强制执行 Policy 定义的格式规范
        [Fix V3.22] 
        1. 移除替换字符串中的 \b (避免插入退格符损坏数据)。
        2. 移除对 "最低/最高" 的数学符号替换，保留语义。
        """
        if not text: return ""
        text = str(text)
        
        # Unicode 单位转码 (注意：这里不要加 \b 在替换串末尾)
        text = re.sub(r'(\d+)\s*m\^?3', r'\1m³', text)
        text = re.sub(r'(\d+)\s*m\^?2', r'\1m²', text)
        text = re.sub(r'(\d+)\s*um', r'\1μm', text)
        text = re.sub(r'(\d+)\s*degC', r'\1℃', text)
        
        # 运算符标准化 (仅替换明确的数学关系词)
        # [Fix] 移除了 "最低|最高"，避免 "最低温度" 变成 ">=温度"
        text = re.sub(r'(\s|^)(>=|不小于|不低于)(\s+|$)', r'\1≥\3', text)
        text = re.sub(r'(\s|^)(<=|不大于|不高于)(\s+|$)', r'\1≤\3', text)
        # 范围连接符
        text = re.sub(r'(\d+)\s*(~|至|到)\s*(\d+)', r'\1~\3', text)
        
        return text

    @staticmethod
    def _preprocess_latex(text: str) -> str:
        """LaTeX 转义预处理"""
        pattern = r'\\(?![/u"\\bfnrt])'
        return re.sub(pattern, r'\\\\', text)

    @staticmethod
    def _triple_layer_parse(text: str) -> Dict[str, Any]:
        """三层 JSON 解析防御机制"""
        # [Task 2.3] 剥离思维链
        text = re.sub(r'<thought>[\s\S]*?</thought>', '', text)
        
        json_str = ""
        # Layer 1: Markdown
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if not match:
            match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if match:
            json_str = match.group(1)
        else:
            # Layer 2: Braces
            match = re.search(r'(\{[\s\S]*\})', text)
            if match:
                json_str = match.group(1)
            else:
                raise ValueError("未在响应中找到任何有效 JSON 结构")

        # 处理 LaTeX 符号
        json_str = JSONParser._preprocess_latex(json_str)

        # Layer 3: 修复与加载
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                from json_repair import repair_json
                repaired = repair_json(json_str)
                return json.loads(repaired) if isinstance(repaired, str) else repaired
            except Exception:
                # 最后的硬清洗策略
                json_str = re.sub(r'//.*', '', json_str)
                json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
                json_str = re.sub(r"'([^']*)'", r'"\1"', json_str)
                return json.loads(json_str)

    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        """对外接口：提取并初步清洗"""
        fallback = {"entities": [], "relations": [], "metadata": {"status": "error"}}
        try:
            data = JSONParser._triple_layer_parse(text)
            if not isinstance(data, dict): return fallback
            return JSONParser._clean_dict_compliance(data)
        except Exception as e:
            print(f"🔴 [JSON Crash Handled] Error: {str(e)[:100]}")
            return fallback

    @staticmethod
    def _clean_dict_compliance(data: Any) -> Any:
        """递归清洗数据"""
        if isinstance(data, dict):
            return {JSONParser.clean_text_compliance(str(k)): JSONParser._clean_dict_compliance(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [JSONParser._clean_dict_compliance(i) for i in data]
        elif isinstance(data, str):
            return JSONParser.clean_text_compliance(data)
        return data

    @staticmethod
    def parse_knowledge_graph(data: Dict[str, Any]) -> KnowledgeGraph:
        """工厂方法：序列化为 KnowledgeGraph 对象"""
        # [Task 5.1] 全图联动清洗
        clean_data = EntityNormalizer.normalize_graph_data(data)
        
        entities = []
        name_type_map = {}
        entity_fields = {k for k in Entity.__annotations__}
        
        for e_data in clean_data.get("entities", []):
            if isinstance(e_data, dict):
                filtered = {k: v for k, v in e_data.items() if k in entity_fields}
                try:
                    obj = Entity(**filtered)
                    entities.append(obj)
                    if obj.name: name_type_map[obj.name] = obj.type
                except: continue

        relations = []
        relation_fields = {k for k in Relation.__annotations__}
        
        for r_data in clean_data.get("relations", []):
            if isinstance(r_data, dict):
                filtered = {k: v for k, v in r_data.items() if k in relation_fields}
                # 自动补全类型
                src, tgt = filtered.get("source"), filtered.get("target")
                if not filtered.get("source_type"): filtered["source_type"] = name_type_map.get(src)
                if not filtered.get("target_type"): filtered["target_type"] = name_type_map.get(tgt)
                try:
                    relations.append(Relation(**filtered))
                except: continue
        
        return KnowledgeGraph(entities=entities, relations=relations, metadata=clean_data.get("metadata", {}))

# ==========================================
# 2. 记忆上下文管理器
# ==========================================
class ContextManager:
    """管理最近 N 个 Chunk 的关键共识"""
    def __init__(self, max_chars: int = 8000):
        self.history: List[str] = []
        self.max_chars = max_chars
        # [Fix V3.22] 性能优化：追踪当前字符数，避免 O(N) 计算
        self.current_chars = 0

    def update(self, kg: KnowledgeGraph, chunk_id: int):
        entities = [e.name for e in kg.entities if (e.confidence or 0) >= 0.8]
        summary = f"[Chunk {chunk_id}] 核心实体: {', '.join(entities[:5])}"
        
        self.history.append(summary)
        self.current_chars += len(summary)
        
        # 优化后的滑动窗口逻辑
        while self.current_chars > self.max_chars and self.history:
            removed = self.history.pop(0)
            self.current_chars -= len(removed)

    def get_prompt_context(self) -> str:
        if not self.history: return "（无起始记忆）"
        return "--- 前文关键共识 ---\n" + "\n".join(self.history[-10:])

# ==========================================
# 3. 断点续传管理器
# ==========================================
class CheckpointManager:
    """持久化处理状态"""
    def __init__(self, output_file: str):
        self.output_file = output_file
        self.processed_ids: Set[str] = set() # [Fix] 类型明确为 str
        self._load_processed_ids()
    
    def _load_processed_ids(self):
        # 使用绝对路径检查，增强跨平台兼容性
        abs_path = os.path.abspath(self.output_file)
        if not os.path.exists(os.path.dirname(abs_path)):
            return
            
        if not os.path.exists(self.output_file): return
        
        with open(self.output_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    # [Fix V3.22] 强制转 str 存储，兼容 UUID 和 Int
                    if rec.get('success'): 
                        cid = rec.get('chunk_id')
                        if cid is not None:
                            self.processed_ids.add(str(cid))
                except: continue

    def is_processed(self, chunk_id: Any) -> bool:
        return str(chunk_id) in self.processed_ids

    def save(self, result: Dict[str, Any]):
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
        # [Fix V3.22] 强制转 str
        if result.get('success'): 
            self.processed_ids.add(str(result['chunk_id']))