# -*- coding: utf-8 -*-
import json
import asyncio
from typing import Dict, Any, Union, List

# 根目录引用
from config import AgentType

# 包内模块相对引用
from .prompts import PromptManager
from .llm_client import LLMClient
from .monitoring import MonitoringManager
# [Task 5.3] 引入 EntityNormalizer
from .utils import JSONParser, EntityNormalizer
from .models import KnowledgeGraph

# ==========================================
# 1. 智能体基类 (The Strategic Base)
# ==========================================
class BaseAgent:
    """
    智能体通用基类：封装了 Prompt 渲染与异步 LLM 调用流程
    """
    def __init__(
        self, 
        agent_type: AgentType, 
        prompt_manager: PromptManager, 
        llm_client: LLMClient, 
        monitor: MonitoringManager, 
        temperature: float,
        model_name: str
    ):
        self.type = agent_type
        self.prompts = prompt_manager
        self.llm = llm_client
        self.monitor = monitor
        self.temperature = temperature
        self.model_name = model_name

    async def _process(self, **kwargs) -> str:
        """
        核心处理：渲染 Prompt -> 发起请求 -> 返回结果
        """
        prompt = self.prompts.get_prompt(self.type, **kwargs)
        
        self.monitor.log_step(self.type.value, "LLM Request Started", 
                             f"Model: {self.model_name}, Temp: {self.temperature}")
        
        response = await self.llm.call_llm(prompt, self.model_name, self.temperature)
        
        return response

# ==========================================
# 2. 激进派 (The Recall Hunter)
# ==========================================
class RadicalAgent(BaseAgent):
    """
    目标：最大化召回率。即便存在不确定性也要进行知识挖掘。
    Temperature: 0.7
    """
    def __init__(
        self, 
        prompt_manager: PromptManager, 
        llm_client: LLMClient, 
        monitor: MonitoringManager,
        model_name: str
    ):
        super().__init__(
            AgentType.RADICAL, 
            prompt_manager, 
            llm_client, 
            monitor, 
            temperature=0.7,
            model_name=model_name
        )
    
    async def extract(self, text: str, **kwargs) -> Dict[str, Any]:
        """提取知识"""
        process_kwargs = {"text": text}
        process_kwargs.update(kwargs)
        
        raw_response = await self._process(**process_kwargs)
        try:
            data = JSONParser.extract_json(raw_response)
            
            # [Task 5.3 集成] 立即规范化，确保对抗派看到的是标准名称
            # 作用：ahu -> AHU, 洁净区 -> 洁净室
            data = EntityNormalizer.normalize_graph_data(data)
            
            self.monitor.log_step(
                self.type.value, 
                "Success", 
                f"Model: {self.model_name} | Extracted {len(data.get('entities', []))} candidates"
            )
            return data
        except Exception as e:
            self.monitor.log_step(
                self.type.value, 
                "Extraction Failed", 
                f"Model: {self.model_name} | Error: {str(e)}"
            )
            return {"entities": [], "relations": []}

# ==========================================
# 3. 保守派 (The Precision Auditor)
# ==========================================
class ConservativeAgent(BaseAgent):
    """
    目标：最大化准确率。严格遵循原文，仅提取有字面铁证的关系。
    Temperature: 0.0
    """
    def __init__(
        self, 
        prompt_manager: PromptManager, 
        llm_client: LLMClient, 
        monitor: MonitoringManager,
        model_name: str
    ):
        super().__init__(
            AgentType.CONSERVATIVE, 
            prompt_manager, 
            llm_client, 
            monitor, 
            temperature=0.0,
            model_name=model_name
        )
    
    def _validate_confidence(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        置信度后置校验器
        """
        # 1. 验证实体
        valid_entities = []
        for e in data.get("entities", []):
            try:
                conf = float(e.get("confidence", 0.0))
            except (ValueError, TypeError):
                conf = 0.0
            
            # 规则 A: 严格剔除低置信度
            if conf < 0.9:
                continue
                
            # 规则 B: 证据缺失自动降级
            evidence = str(e.get("source_reference", "")).strip()
            if conf >= 0.99 and len(evidence) < 3:
                e["confidence"] = 0.9
                
            valid_entities.append(e)

        # 2. 验证关系
        valid_relations = []
        for r in data.get("relations", []):
            try:
                conf = float(r.get("confidence", 0.0))
            except (ValueError, TypeError):
                conf = 0.0
            
            if conf < 0.9:
                continue
                
            evidence = str(r.get("description", "")).strip()
            if conf >= 0.99 and len(evidence) < 3:
                r["confidence"] = 0.9
                
            valid_relations.append(r)

        data["entities"] = valid_entities
        data["relations"] = valid_relations
        return data

    async def extract(self, text: str, **kwargs) -> Dict[str, Any]:
        """提取知识并执行严格验证"""
        process_kwargs = {"text": text}
        process_kwargs.update(kwargs)
        
        raw_response = await self._process(**process_kwargs)
        try:
            data = JSONParser.extract_json(raw_response)
            
            # [Task 5.3 集成] 先规范化名称
            data = EntityNormalizer.normalize_graph_data(data)
            
            # 再执行置信度验证 (此时实体名已是对齐后的标准名)
            validated_data = self._validate_confidence(data)
            
            count_e = len(validated_data.get('entities', []))
            count_r = len(validated_data.get('relations', []))
            
            self.monitor.log_step(
                self.type.value, 
                "Success", 
                f"Model: {self.model_name} | Verified {count_e} Entities, {count_r} Relations"
            )
            return validated_data
            
        except Exception as e:
            self.monitor.log_step(
                self.type.value, 
                "Verification Failed", 
                f"Model: {self.model_name} | Error: {str(e)}"
            )
            return {"entities": [], "relations": []}

# ==========================================
# 4. 对抗派 (The Logic Critic)
# ==========================================
class AdversarialAgent(BaseAgent):
    """
    目标：质检与挑错。比对两份草案，寻找幻觉、冲突与遗漏。
    Temperature: 0.4
    """
    def __init__(
        self, 
        prompt_manager: PromptManager, 
        llm_client: LLMClient, 
        monitor: MonitoringManager,
        model_name: str
    ):
        super().__init__(
            AgentType.ADVERSARIAL, 
            prompt_manager, 
            llm_client, 
            monitor, 
            temperature=0.4,
            model_name=model_name
        )
    
    async def review(self, text: str, radical_res: Dict, conservative_res: Dict, **kwargs) -> Dict[str, Any]:
        """审查两份草案"""
        process_kwargs = {
            "text": text,
            "radical_json": json.dumps(radical_res, ensure_ascii=False),
            "conservative_json": json.dumps(conservative_res, ensure_ascii=False)
        }
        process_kwargs.update(kwargs)
        
        raw_response = await self._process(**process_kwargs)
        try:
            critique = JSONParser.extract_json(raw_response)
            
            # [Task 5.3] 即使是 Critique 里的实体名，最好也清洗一下，保持日志整洁
            # 虽然 Critique 结构可能不同，但如果它包含 entities/relations 字段，这行代码会生效
            critique = EntityNormalizer.normalize_graph_data(critique)
            
            self.monitor.log_step(
                self.type.value, 
                "Success", 
                f"Model: {self.model_name} | Critique report generated"
            )
            return critique
        except Exception as e:
            self.monitor.log_step(
                self.type.value, 
                "Critique Failed", 
                f"Model: {self.model_name} | Error: {str(e)}"
            )
            return {"has_issues": False, "critiques": []}

# ==========================================
# 5. 大法官 (The Final Adjudicator)
# ==========================================
class JudgeAgent(BaseAgent):
    """
    目标：终极裁决。综合所有派系的输入，利用 CoT 推理产出最权威图谱。
    Temperature: 0.05
    """
    def __init__(
        self, 
        prompt_manager: PromptManager, 
        llm_client: LLMClient, 
        monitor: MonitoringManager,
        model_name: str
    ):
        super().__init__(
            AgentType.JUDGE, 
            prompt_manager, 
            llm_client, 
            monitor, 
            temperature=0.05,
            model_name=model_name
        )
    
    async def adjudicate(
        self, 
        text: str, 
        radical_res: Dict, 
        conservative_res: Dict, 
        critique_res: Dict,
        **kwargs
    ) -> KnowledgeGraph:
        """综合裁决流程"""
        process_kwargs = {
            "text": text,
            "radical_json": json.dumps(radical_res, ensure_ascii=False),
            "conservative_json": json.dumps(conservative_res, ensure_ascii=False),
            "critique": json.dumps(critique_res, ensure_ascii=False)
        }
        process_kwargs.update(kwargs)
        
        raw_response = await self._process(**process_kwargs)
        
        try:
            # 1. 提取结构化判决结果
            data = JSONParser.extract_json(raw_response)
            
            # 2. 核心转化
            # 注：parse_knowledge_graph 内部已经调用了 EntityNormalizer.normalize_graph_data
            # 这是最后一道防线
            kg = JSONParser.parse_knowledge_graph(data)
            
            # 3. 证据留存
            kg.metadata.update({
                "agent": "Ultimate_Judge_V3.18",
                "model": self.model_name,
                "model_type": "reasoner" if "reasoner" in self.model_name else "chat",
                "summary": data.get("summary", {})
            })
            
            # 4. 执行最终去重与收敛
            final_kg = kg.deduplicate()
            
            self.monitor.log_step(
                self.type.value, 
                "Success", 
                f"Model: {self.model_name} | KG Finalized: {len(final_kg.entities)} Nodes, {len(final_kg.relations)} Edges"
            )
            
            return final_kg

        except Exception as e:
            # 降级策略
            self.monitor.log_step(
                self.type.value, 
                "Adjudication Critical Error", 
                f"Model: {self.model_name} | Error: {str(e)}"
            )
            try:
                # 降级时也需要经过 parse_knowledge_graph 的清洗逻辑
                fallback_kg = JSONParser.parse_knowledge_graph(conservative_res)
                fallback_kg.metadata["status"] = "fallback_conservative"
                fallback_kg.metadata["error_cause"] = str(e)
                return fallback_kg
            except:
                return KnowledgeGraph(entities=[], relations=[])