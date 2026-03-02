# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import time
import re
from typing import List, Dict

# ==========================================
# 0. 路径补丁 & 异步补丁
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# [Fix 1] 解决 Streamlit 的 EventLoop 冲突
# 注意：这是保证 RAG 系统在多轮对话中“改写-检索”全链路不锁死的唯一真理
import nest_asyncio
nest_asyncio.apply()

from config import SystemConfig
from core.llm_client import LLMClient
from core.monitoring import MonitoringManager

class QueryRewriter:
    """
    问题改写器 (The Query Transformer) - V3.39 工业旗舰版
    
    职责：
    1. [身份具象化]：将模糊身份代词彻底替换为对话历史中具体的实体全名。
    2. [语义对齐]：将碎片化提问补全为具备独立检索价值的 Standalone Query。
    3. [智能审计]：程度词/方位词豁免保护 + 核心指代残留强制回退。
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.monitor = MonitoringManager(config.monitor_dir)
        
        # [Fix 2] 核心指代审计库 (精简版：仅拦截会造成检索偏移的身份代词)
        # 移除了方位词（这里/那边）和程度词（这么/那么），防止误杀高质量改写
        self.strict_pronouns = [
            "它", "其", "这", "那", "它们", "其中", "刚才说的",
            "该机", "该设备", "该装置", "该台", "该套", "前者", "后者"
        ]
        print("🔧 [REWRITER] 改写模块已就绪 (V3.39 Industrial Flagship).")

    def _clean_output(self, text: str) -> str:
        """
        [工业级清洗] 仅移除引号与废话前缀，严格保护实体内部的标识括号
        """
        if not text: return ""
        
        # 1. 移除常见前缀引导语
        prefixes = [
            r'^改写结果[:：]\s*', r'^重写句子[:：]\s*', r'^独立查询句[:：]\s*', 
            r'^输出[:：]\s*', r'^改写为[:：]\s*', r'^独立搜索短句[:：]\s*',
            r'^改写后的句子[:：]\s*', r'^重写后的句子[:：]\s*', r'^检索句[:：]\s*'
        ]
        for p in prefixes:
            text = re.sub(p, '', text, flags=re.IGNORECASE)
        
        # 2. [领域适配] 仅移除引号/书名号，严禁移除 () [] 【】
        # 因为 AHU-01 (备用) 这种括号是实体名不可分割的一部分
        symbols = ['"', '"', '"', '"', "'", "'", "‘", "’", "`", "『", "』", "「", "」", "《", "》"]
        for s in symbols:
            text = text.replace(s, '')
        
        # 3. 移除末尾多余标点
        text = text.strip().strip('。？?.!,，;；:：')
        
        # 4. 压缩冗余空格
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    def _contains_pronouns(self, text: str) -> bool:
        """[审计流] 检查改写句是否仍残留核心身份代词"""
        # 注意：这里仅检查 strict_pronouns 中的词
        return any(p in text for p in self.strict_pronouns)

    async def rewrite_async(self, query: str, history: List[Dict[str, str]]) -> str:
        """
        [异步内核] 执行语义消解与纯净度审计
        """
        if not history:
            return query

        # 1. 记忆回溯：回溯最近 10 条消息 (5轮对话) 确保长线关联
        context_str = ""
        for msg in history[-10:]:
            role = "用户" if msg["role"] == "user" else "助手"
            context_str += f"{role}: {msg['content']}\n"

        # 2. 阶梯指令宪法 (解决指令矛盾)
        system_prompt = """
你是一个工业知识库检索专家。请根据【对话历史】，将用户【当前问题】重写为一个独立的、语义完整的搜索短句。

## 执行准则：
1. **替换具体名称**：必须将代词（如“它”、“这”、“该设备”）替换为前文中明确提到的具体实体名（如：AHU-01、冷水机组）。
2. **检索导向**：只输出改写后的短句本身。严禁包含任何解释、说明或“重写如下”等前缀。
3. **补全语义**：如果当前问题不完整（如“那温度呢？”），请结合历史补全主语和动词。
4. **回退逻辑**：如果无法从历史中确定代词的具体指代，或者当前问题已经很完整，请原样输出原始问题。
        """

        user_input = f"【对话历史】：\n{context_str}\n\n【当前问题】：\n{query}\n\n【独立搜索短句】："
        
        try:
            target_model = self.config.model_name
            async with LLMClient(self.config, self.monitor) as llm:
                raw_res = await llm.call_llm(
                    prompt=f"{system_prompt}\n{user_input}", 
                    model_name=target_model, 
                    temperature=0.0 # 强制确定性
                )
                
                final_query = self._clean_output(raw_res)
                
                # [智能审计]：
                # 1. 基础校验：排除空值或无变动
                if not final_query or len(final_query) < 3 or final_query == query:
                    return query
                
                # 2. [检索纯净度审计]
                # 规则：若身份代词（如“它”、“该设备”）依然残留，说明改写失败，回退原句
                if self._contains_pronouns(final_query):
                    self.monitor.log_step("Rewriter", "Audit", "Pronoun residual found, fallback to original.")
                    return query
                
                return final_query
                
        except Exception as e:
            # 记录异常并安全回退
            self.monitor.log_step("Rewriter", "Error", f"API Error: {e}")
            return query

    def rewrite_sync(self, query: str, history: List[Dict[str, str]], timeout: int = 15) -> str:
        """
        [同步桥接器] 适配 Streamlit 同步线程环境
        """
        if not history or not query.strip():
            return query

        self.monitor.log_step("Rewriter", "Start", f"Raw Query: {query}")
        start_time = time.time()

        try:
            # 获取当前线程关联的 Loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # 执行带超时的任务
            rewritten = loop.run_until_complete(
                asyncio.wait_for(
                    self.rewrite_async(query, history), 
                    timeout=timeout
                )
            )
            
            duration = time.time() - start_time
            self.monitor.log_step("Rewriter", "Success", f"Final Query: {rewritten} ({duration:.2f}s)")
            return rewritten

        except Exception as e:
            self.monitor.log_step("Rewriter", "Fail", str(e))
            return query

# ==========================================
# 冒烟测试
# ==========================================
if __name__ == "__main__":
    cfg = SystemConfig()
    if not cfg.api_key:
        print("⚠️ 未配置 API KEY，跳过真实 API 测试。")
        sys.exit(0)
        
    rewriter = QueryRewriter(cfg)
    
    # 测试 1：方位词保护 (预期通过，保留“那里”)
    print(f"\n🧪 测试 1：方位词保护 (预期通过并保留“那里”):")
    bad_in = "输出：AHU-01 那里的过滤器状态"
    print(f"   结果: {rewriter._clean_output(bad_in)}")
    
    # 测试 2：指代彻底消解 (预期成功)
    print(f"\n🧪 测试 2：多轮指代补全:")
    h_mock = [{"role": "user", "content": "我想查冷水机组 CH-1。"}, {"role": "assistant", "content": "好的。"}]
    q_mock = "它的电流？"
    print(f"   结果: {rewriter.rewrite_sync(q_mock, h_mock)}")