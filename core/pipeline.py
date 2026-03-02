# -*- coding: utf-8 -*-
import asyncio
import json
import os
import sys
import time
from typing import List, Dict, Any, Optional, Tuple

# ==========================================
# 0. 引用修正
# ==========================================
# 根目录配置
from config import SystemConfig, AgentType

# 包内模块相对引用
from .monitoring import MonitoringManager
from .prompts import PromptManager
from .llm_client import LLMClient
from .utils import CheckpointManager, ContextManager  # [V3.3] 上下文管理器将自动使用8000字符配置
from .agents import RadicalAgent, ConservativeAgent, AdversarialAgent, JudgeAgent
from .models import ProcessingResult

class UltimateKnowledgeExtractor:
    """
    终极知识提取流水线 (The Orchestrator) - V3.3 多模型支持版
    
    职责：
    1. [调度]：管理四方会审流程，支持不同智能体使用不同模型。
    2. [记忆]：利用 ContextManager 在批次间传递 {previous_context} (8000字符容量)。
    3. [断点]：管理任务的跳过与保存。
    4. [模型路由]：从 config.model_map 获取各智能体的专属模型。
    5. [增强监控]：添加进度百分比显示和Agent耗时统计。
    """

    def __init__(self, config: SystemConfig):
        """
        初始化流水线 (V3.3 多模型支持)
        """
        self.config = config
        
        # 初始化各个子系统
        self.monitor = MonitoringManager(config.monitor_dir)
        
        # [V3.3] PromptManager 会自动加载 Policy 宪法
        self.prompts = PromptManager(config.prompt_dir, config.policy_path, self.monitor)
        
        self.checkpoint_mgr = CheckpointManager(config.output_file)
        
        # [V3.3] 初始化记忆海马体 (自动使用 config.max_context_chars = 8000)
        self.context_mgr = ContextManager(max_chars=config.max_context_chars)
        
        # [V3.3] 模型配置映射表
        self.model_map = config.model_map
        
        # 增强监控：Agent耗时统计
        self.agent_times = {
            "radical": {"total": 0.0, "count": 0, "avg": 0.0},
            "conservative": {"total": 0.0, "count": 0, "avg": 0.0},
            "adversarial": {"total": 0.0, "count": 0, "avg": 0.0},
            "judge": {"total": 0.0, "count": 0, "avg": 0.0}
        }
        
        self.monitor.log_step("Pipeline", "Init", 
                            f"V3.3 Multi-Model Pipeline Ready. Memory: {config.max_context_chars} chars")

    def _debug_pause(self, chunk_id: int, stage_name: str, intermediate_data: Any = None):
        """
        [伪同步核心] 人类断点机制
        """
        if not self.config.debug_mode:
            return

        # 1. 自动保存中间结果
        if intermediate_data:
            filename = f"debug_{stage_name}_chunk_{chunk_id}.txt"
            self.monitor.save_intermediate(filename, intermediate_data)
            print(f"   💾 中间结果已保存: {filename}")

        # 2. 阻塞等待用户指令
        print(f"\n⏸️ [DEBUG PAUSE] Chunk {chunk_id} - {stage_name} 阶段完成。")
        print(f"   👉 按 <Enter> 继续下一步...")
        print(f"   👉 输入 'q' 并回车以终止程序...")
        
        user_input = input("   Your command: ").strip().lower()
        
        if user_input == 'q':
            print("🛑 用户手动终止调试。Exiting...")
            sys.exit(0)
        
        print("▶️ Resuming...\n")

    def _update_agent_time(self, agent_name: str, elapsed_time: float):
        """
        更新Agent耗时统计
        """
        if agent_name not in self.agent_times:
            self.agent_times[agent_name] = {"total": 0.0, "count": 0, "avg": 0.0}
        
        self.agent_times[agent_name]["total"] += elapsed_time
        self.agent_times[agent_name]["count"] += 1
        self.agent_times[agent_name]["avg"] = self.agent_times[agent_name]["total"] / self.agent_times[agent_name]["count"]
        
        # 记录到监控
        self.monitor.log_step("Pipeline", "AgentTime", 
                             f"{agent_name}: {elapsed_time:.2f}s (Avg: {self.agent_times[agent_name]['avg']:.2f}s)")

    async def process_chunk(
        self, 
        chunk: Dict[str, Any], 
        llm_client: LLMClient, 
        current_context: str
    ) -> Optional[ProcessingResult]:
        """
        处理单个文本块的完整生命周期 (V3.3 多模型支持)
        [V3.3 升级]：为每个智能体配置专属模型
        """
        chunk_id = chunk.get("chunk_id")
        content = chunk.get("content", "")
        
        if not content or chunk_id is None:
            self.monitor.log_step("Pipeline", "Skip", f"Invalid chunk: {chunk_id}")
            return None

        # 开始计时
        chunk_start_time = asyncio.get_event_loop().time()
        
        try:
            # 0. 初始化特工组 (V3.3: 每个智能体使用专属模型)
            # 从配置中获取各智能体对应的模型名称
            radical_model = self.model_map.get(AgentType.RADICAL, "deepseek-chat")
            conservative_model = self.model_map.get(AgentType.CONSERVATIVE, "deepseek-chat")
            adversarial_model = self.model_map.get(AgentType.ADVERSARIAL, "deepseek-chat")
            judge_model = self.model_map.get(AgentType.JUDGE, "deepseek-reasoner")
            
            # 每次实例化以确保状态隔离，但共享 PromptManager (含 Policy) 和 Monitor
            # V3.3: 传递模型名称给智能体构造函数
            rad_agent = RadicalAgent(
                self.prompts, 
                llm_client, 
                self.monitor,
                model_name=radical_model
            )
            con_agent = ConservativeAgent(
                self.prompts, 
                llm_client, 
                self.monitor,
                model_name=conservative_model
            )
            adv_agent = AdversarialAgent(
                self.prompts, 
                llm_client, 
                self.monitor,
                model_name=adversarial_model
            )
            jud_agent = JudgeAgent(
                self.prompts, 
                llm_client, 
                self.monitor,
                model_name=judge_model
            )

            # 准备上下文参数 (所有 Agent 共享同一个前文记忆)
            ctx_kwargs = {"previous_context": current_context}

            # --- 阶段 1: 激进派 (高召回) ---
            # 激进派利用前文记忆，可能会推断出代词指代的对象
            rad_start = asyncio.get_event_loop().time()
            self.monitor.log_step("Pipeline", "Stage", f"Chunk {chunk_id}: Radical Agent (Model: {radical_model})")
            rad_result = await rad_agent.extract(content, **ctx_kwargs)
            rad_time = asyncio.get_event_loop().time() - rad_start
            self._update_agent_time("radical", rad_time)
            self._debug_pause(chunk_id, "Radical_Agent", rad_result)

            # --- 阶段 2: 保守派 (高准确) ---
            # 保守派利用前文记忆（如表头定义），解析当前孤立的表格行
            con_start = asyncio.get_event_loop().time()
            self.monitor.log_step("Pipeline", "Stage", f"Chunk {chunk_id}: Conservative Agent (Model: {conservative_model})")
            con_result = await con_agent.extract(content, **ctx_kwargs)
            con_time = asyncio.get_event_loop().time() - con_start
            self._update_agent_time("conservative", con_time)
            self._debug_pause(chunk_id, "Conservative_Agent", con_result)

            # --- 阶段 3: 对抗派 (逻辑找茬) ---
            adv_start = asyncio.get_event_loop().time()
            self.monitor.log_step("Pipeline", "Stage", f"Chunk {chunk_id}: Adversarial Agent (Model: {adversarial_model})")
            critique_result = await adv_agent.review(content, rad_result, con_result, **ctx_kwargs)
            adv_time = asyncio.get_event_loop().time() - adv_start
            self._update_agent_time("adversarial", adv_time)
            self._debug_pause(chunk_id, "Adversarial_Agent", critique_result)

            # --- 阶段 4: 大法官 (最终裁决) ---
            jud_start = asyncio.get_event_loop().time()
            self.monitor.log_step("Pipeline", "Stage", f"Chunk {chunk_id}: Judge Agent (Model: {judge_model})")
            final_kg = await jud_agent.adjudicate(content, rad_result, con_result, critique_result, **ctx_kwargs)
            jud_time = asyncio.get_event_loop().time() - jud_start
            self._update_agent_time("judge", jud_time)
            self._debug_pause(chunk_id, "Judge_Agent", final_kg.to_dict())

            # 计算总耗时
            chunk_end_time = asyncio.get_event_loop().time()
            chunk_duration = chunk_end_time - chunk_start_time

            # 封装结果
            return ProcessingResult(
                chunk_id=chunk_id,
                success=True,
                knowledge_graph=final_kg,
                processing_time=chunk_duration,
                agent_results={
                    "radical_model": radical_model,
                    "conservative_model": conservative_model,
                    "adversarial_model": adversarial_model,
                    "judge_model": judge_model,
                    "agent_times": {
                        "radical": rad_time,
                        "conservative": con_time,
                        "adversarial": adv_time,
                        "judge": jud_time
                    }
                }
            )

        except Exception as e:
            chunk_end_time = asyncio.get_event_loop().time()
            error_msg = f"Pipeline Error: {str(e)}"
            self.monitor.log_step("Pipeline", "Fail", f"Chunk {chunk_id}: {error_msg}")
            
            return ProcessingResult(
                chunk_id=chunk_id,
                success=False,
                error_message=error_msg,
                processing_time=chunk_end_time - chunk_start_time
            )

    async def run(self) -> List[ProcessingResult]:
        """
        启动批量处理任务 (V3.3 串行模式 + 多模型支持)
        """
        # 1. 加载输入数据
        if not os.path.exists(self.config.input_file):
            self.monitor.log_step("Pipeline", "Critical", f"Input file not found: {self.config.input_file}")
            return []

        print(f"📖 Loading chunks from {self.config.input_file}...")
        chunks = []
        with open(self.config.input_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        chunks.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        total_chunks = len(chunks)
        if total_chunks == 0:
            print("❌ 输入文件中没有有效的数据块")
            return []
        
        print(f"📊 Total chunks loaded: {total_chunks}")
        
        # 显示模型配置信息
        print(f"🤖 Active Models:")
        for agent_type, model_name in self.model_map.items():
            print(f"   {agent_type.value}: {model_name}")
        
        # 2. 建立 LLM 连接池
        async with LLMClient(self.config, self.monitor) as llm_client:
            
            all_results = []
            
            # [V3.3 修复] 核心循环：串行处理，确保每个chunk都能基于最新的记忆
            for i, chunk_data in enumerate(chunks, 1):
                cid = chunk_data.get("chunk_id")
                
                # Checkpoint 检查
                if self.checkpoint_mgr.is_processed(cid):
                    print(f"⏭️ Skipping Chunk {cid} (Already processed)")
                    continue
                
                # 显示处理进度
                progress_percent = (i / total_chunks) * 100
                print(f"\n🚀 [{i}/{total_chunks}] ({progress_percent:.1f}%) Processing Chunk {cid}...")
                
                # A. 获取当前时刻的记忆快照 (Snapshot)
                # 由于串行处理，每个chunk都能获取到前一个chunk处理后的最新记忆
                memory_snapshot = self.context_mgr.get_prompt_context()
                print(f"   🧠 Memory snapshot: {len(memory_snapshot)} chars")
                
                # B. 串行处理当前chunk
                res = await self.process_chunk(chunk_data, llm_client, memory_snapshot)
                
                # C. 后处理：保存结果并更新记忆
                if res:
                    # 1. 持久化保存
                    self.checkpoint_mgr.save(res.to_dict())
                    
                    if res.success:
                        print(f"   ✅ Chunk {res.chunk_id} Done ({res.processing_time:.2f}s) "
                              f"[Judge Model: {res.agent_results.get('judge_model', 'N/A')}]")
                        all_results.append(res)
                        
                        # 2. [关键] 立即更新记忆海马体
                        # 将提取到的新知识注入 ContextManager，供下一个chunk使用
                        if res.knowledge_graph:
                            self.context_mgr.update(res.knowledge_graph, res.chunk_id)
                    else:
                        print(f"   ❌ Chunk {res.chunk_id} Failed: {res.error_message}")
                        all_results.append(res)
            
            # 3. 打印Agent平均处理时间统计
            self._print_agent_time_summary()
            
            print(f"\n🎉 Pipeline finished. Processed {len(all_results)} new chunks.")
            return all_results
    
    def _print_agent_time_summary(self):
        """
        打印各Agent平均处理时间统计
        """
        print("\n" + "="*60)
        print("📊 Agent Processing Time Summary")
        print("="*60)
        
        total_processed = 0
        for agent_name, stats in self.agent_times.items():
            if stats["count"] > 0:
                total_processed += stats["count"]
                print(f"{agent_name.capitalize():12s}: {stats['count']:3d} calls | "
                      f"Total: {stats['total']:7.2f}s | Avg: {stats['avg']:6.2f}s")
        
        if total_processed > 0:
            print(f"\n📈 Total processed chunks: {total_processed}")
            # 计算平均每chunk总耗时
            total_time = sum(stats["total"] for stats in self.agent_times.values())
            avg_chunk_time = total_time / total_processed if total_processed > 0 else 0
            print(f"⏱️  Avg time per chunk: {avg_chunk_time:.2f}s")
        else:
            print("\nℹ️ No chunks were processed, no time statistics available.")
        print("="*60)