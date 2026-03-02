# -*- coding: utf-8 -*-
import aiohttp
import asyncio
import json
import sys
import os
import time
from typing import Optional, Dict, Any

# ==========================================
# 0. 路径补丁
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config import SystemConfig
from .monitoring import MonitoringManager

class LLMClient:
    """
    LLM 异步通讯兵 (Communications Officer) - V3.24 [最终扩容版]
    
    职责：
    1. [Fix Bug B] 动态 Token 预算：全员扩容至 8192，防止长文档截断。
    2. [生产增强] 延迟监控：记录每一跳 API 的墙上时间（Wall Time）。
    3. [生产增强] 消耗统计：提取并记录 Prompt/Completion/Total Tokens。
    4. [R1 适配] 智能处理 reasoning_content 与 content 的回退逻辑。
    """

    def __init__(self, config: SystemConfig, monitor: MonitoringManager):
        self.config = config
        self.monitor = monitor
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        if not self.config.api_key:
            raise ValueError("❌ [LLM Client] DEEPSEEK_API_KEY 未配置。")

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # 使用配置中的超时时间 (建议 600s 以适配 R1 长思考)
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def call_llm(self, prompt: str, model_name: str, temperature: float = 0.7, max_retries: int = 3) -> str:
        """
        执行 API 调用核心逻辑，集成性能监控
        """
        if not self.session:
            raise RuntimeError("Client session 尚未初始化。")

        # [Fix V3.24] 全员扩容策略
        # 金丝雀测试显示 4096 对于激进派提取长文档不够用，导致 TRUNCATED。
        # 这里统一提升至 8192 (DeepSeek 支持)，确保最大召回率。
        current_max_tokens = 8192

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "stream": False,
            "max_tokens": current_max_tokens
        }

        endpoint = f"{self.config.base_url.rstrip('/')}/chat/completions"

        for attempt in range(1, max_retries + 1):
            # --- [监控开始] 记录开始时间 ---
            start_time = time.perf_counter()
            
            try:
                async with self.session.post(endpoint, json=payload) as response:
                    
                    # --- [监控结束] 计算延迟 ---
                    latency = time.perf_counter() - start_time
                    
                    if response.status == 200:
                        data = await response.json()
                        choice = data.get('choices', [{}])[0]
                        usage = data.get('usage', {}) # 提取 Token 消耗
                        
                        finish_reason = choice.get('finish_reason')
                        message = choice.get('message', {})
                        content = message.get('content')
                        
                        # 构造性能指标字符串
                        metrics_msg = (
                            f"Model: {model_name} | Latency: {latency:.2f}s | "
                            f"Tokens: P={usage.get('prompt_tokens')} C={usage.get('completion_tokens')} T={usage.get('total_tokens')}"
                        )

                        # [Bug B 预警] 长度截断检查
                        if finish_reason == "length":
                            self.monitor.log_step("LLM_Client", "CRITICAL_WARNING", 
                                                f"TRUNCATED! {metrics_msg}")
                        else:
                            self.monitor.log_step("LLM_Client", "Success", metrics_msg)

                        # R1 模型适配：如果 content 为空，尝试获取 reasoning_content
                        # 注意：通常 content 包含最终答案，reasoning_content 包含思维链
                        if not content:
                            content = message.get('reasoning_content')
                        
                        if not content:
                            raise ValueError("API 返回内容为空 (Content is empty)")
                        
                        return content

                    elif response.status == 429:
                        # [Fix V3.24] 增强 Retry-After 解析鲁棒性
                        retry_header = response.headers.get('Retry-After', '60')
                        try:
                            retry_after = int(retry_header)
                        except ValueError:
                            # 如果不是数字（如日期格式），默认等待 60 秒兜底
                            retry_after = 60
                            
                        self.monitor.log_step("LLM_Client", "RateLimit", f"Delay: {retry_after}s")
                        
                        if attempt < max_retries:
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            raise ConnectionError(f"429 Limit Exceeded after {max_retries} attempts.")
                            
                    elif 500 <= response.status < 600:
                        # 服务器错误，指数退避
                        # [Fix V3.24] 修正语法，确保指数运算正确
                        wait_time = 2 ** attempt
                        self.monitor.log_step("LLM_Client", "ServerError", f"Status: {response.status}, Wait: {wait_time}s")
                        if attempt < max_retries:
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise ConnectionError(f"Server Error {response.status} after {max_retries} attempts.")
                    
                    else:
                        error_text = await response.text()
                        self.monitor.log_step("LLM_Client", "HTTP_Error", f"Status: {response.status}")
                        raise ValueError(f"HTTP {response.status}: {error_text[:200]}")

            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                latency = time.perf_counter() - start_time
                if attempt < max_retries:
                    # [Fix V3.24] 修正语法
                    wait_time = 2 ** attempt
                    self.monitor.log_step("LLM_Client", "NetworkRetry", f"{type(e).__name__} at {latency:.2f}s, Wait: {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    self.monitor.log_step("LLM_Client", "FinalFail", f"Network Error after {max_retries} retries.")
                    raise e

        raise Exception("LLM 调用链路异常中断")