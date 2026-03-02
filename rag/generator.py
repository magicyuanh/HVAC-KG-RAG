# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import time
from typing import List

# ==========================================
# 0. 路径补丁 & 异步补丁
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# [Fix 1] 解决 Streamlit 的 EventLoop 冲突
import nest_asyncio
nest_asyncio.apply()

from config import SystemConfig
# [Fix 2] 引入 Core 包组件
from core.llm_client import LLMClient
from core.monitoring import MonitoringManager
from core.models import UnifiedContext

class ResponseGenerator:
    """
    答案生成器 (The Strategic Generator) - V3.28 语义修正版
    
    职责：
    1. [Prompt工程]：将 UnifiedContext 对象列表转化为带引用的结构化 Prompt。
    2. [同步桥接]：利用 nest_asyncio 安全地在 Streamlit 线程中调用异步 LLM。
    3. [引用溯源]：强制 LLM 基于提供的上下文回答，并标注来源。
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        # 初始化监控器 (复用 monitor 目录)
        self.monitor = MonitoringManager(config.monitor_dir)
        print("🤖 [GENERATOR] 智能生成引擎已就绪 (Async patched).")

    async def generate_async(self, query: str, context_list: List[UnifiedContext]) -> str:
        """
        [异步内核]：执行真正的 Prompt 组装与 API 调用
        """
        # 1. 空值检查
        if not context_list:
            return "⚠️ [系统提示] 知识库检索结果为空，无法依据事实回答。请尝试更换提问方式或扩充知识库。"

        # 2. 精细化 Prompt 组装
        # 将 UnifiedContext 列表转化为带编号的文本块
        formatted_context = ""
        for i, ctx in enumerate(context_list):
            # 格式示例: [1] (Vector+Graph) PPO算法 --[USES]--> SFT数据...
            # 使用 ctx.source 展示来源 (e.g., "Vector", "Graph", "Vector+BM25")
            source_tag = f"({ctx.source})" 
            # 截取过长内容防止 Token 溢出 (虽然 LLMClient 会处理，这里做个兜底)
            content_safe = ctx.content[:2000] 
            formatted_context += f"[{i+1}] {source_tag} {content_safe}\n\n"

        # 3. 编写“专家宪法” (System Prompt)
        # 强约束模型必须标注 [1] [2] 引用
        system_prompt = """
你是一个精通垂直领域的专家助手。请严格基于提供的【参考上下文】回答用户的【问题】。

## 核心原则：
1. **事实优先**：回答内容必须来源于参考上下文。若信息不足，请直接承认“知识库未收录”，严禁编造。
2. **强制引用**：在陈述关键事实时，必须在句末标注来源编号，格式为 [1], [2]。
3. **逻辑整合**：不要机械罗列。如果【图谱 (Graph)】提供了逻辑关系，请优先结合【文档 (Vector/Text)】的细节进行综合阐述。
4. **结构清晰**：使用 Markdown 格式（标题、列表）组织答案，语言干练，避免废话。

## 回答格式示例：
PPO算法的核心优势在于稳定性[1]。图谱显示它与RLHF存在直接关联[2]...
        """

        # 4. 组装用户输入
        user_prompt = f"""
【参考上下文】：
{formatted_context}

【用户问题】：
{query}

【专家回答】：
"""
        
        # 5. 执行调用
        # Temperature=0.2 保证事实性问题的低幻觉
        try:
            # [Fix 3] 修正模型选择逻辑
            # 直接使用 config.py 中定义好的 model_name 属性 (指向 CONSERVATIVE 模型)
            # 避免了之前使用迭代器取第一个 key 的不确定性
            target_model = self.config.model_name
            
            async with LLMClient(self.config, self.monitor) as llm:
                response = await llm.call_llm(
                    prompt=f"{system_prompt}\n{user_prompt}", 
                    model_name=target_model, 
                    temperature=0.2 
                )
                return response
        except Exception as e:
            error_msg = f"LLM 调用失败: {str(e)}"
            self.monitor.log_step("Generator", "Error", error_msg)
            raise e

    def generate_sync(self, query: str, context_list: List[UnifiedContext], timeout: int = 60) -> str:
        """
        [同步桥接器]：Streamlit 专用的安全入口
        """
        self.monitor.log_step("Generator", "Start", f"Q: {query[:20]}...")
        start_time = time.time()

        try:
            # [Fix 4] 使用 nest_asyncio 允许的事件循环
            # 无需再手动 new_event_loop，直接获取当前 loop 即可，避免 Streamlit 线程冲突
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # 带超时的执行
            answer = loop.run_until_complete(
                asyncio.wait_for(
                    self.generate_async(query, context_list), 
                    timeout=timeout
                )
            )
            
            duration = time.time() - start_time
            self.monitor.log_step("Generator", "Success", f"Time: {duration:.2f}s")
            return answer

        except asyncio.TimeoutError:
            err = f"❌ [TIMEOUT] 生成超时 ({timeout}s)。DeepSeek 响应过慢，请重试。"
            self.monitor.log_step("Generator", "Timeout", str(timeout))
            return err
            
        except Exception as e:
            err = f"❌ [ERROR] 生成服务异常: {str(e)}"
            self.monitor.log_step("Generator", "Fail", str(e))
            return err

# ==========================================
# 单元测试
# ==========================================
if __name__ == "__main__":
    # 构造模拟数据
    cfg = SystemConfig()
    
    # 简单的冒烟测试，不依赖真实 API
    if not cfg.api_key:
        print("⚠️ 未配置 API KEY，跳过 LLM 调用测试")  # <--- 注意这里的缩进
        sys.exit(0)                                   # <--- 注意这里的缩进
        
    gen = ResponseGenerator(cfg)
    
    mock_ctx = [
        UnifiedContext(
            content="PPO算法的核心是限制策略更新幅度。", 
            source="Vector", 
            score=0.9
        ),
        UnifiedContext(
            content="【图谱事实】PPO --[REQUIRES]--> Reward Model", 
            source="Graph", 
            score=0.85
        )
    ]
    
    print("\nTesting Sync Generation...")
    # 注意：这里会真实调用 LLM，消耗 token
    res = gen.generate_sync("PPO的核心是什么？", mock_ctx)
    print(f"\n🤖 Answer:\n{res}")