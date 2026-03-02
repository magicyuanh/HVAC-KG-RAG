# -*- coding: utf-8 -*-
import time
import os
import json
import statistics
from pathlib import Path
from typing import Any, Union, Dict, List, Optional
from datetime import datetime

class MonitoringManager:
    """
    监控管理器：负责系统的可观测性 (Observability)
    1. 实时日志记录 (Console + File)
    2. 中间结果留存 (Artifacts for Debugging)
    3. [增强] Agent处理时间统计与性能分析
    4. [增强] 处理进度跟踪与百分比显示
    """

    def __init__(self, monitor_dir: str):
        """
        初始化监控器
        :param monitor_dir: 日志和中间文件存放的根目录
        """
        self.monitor_dir = Path(monitor_dir)
        # 确保目录存在，如果不存在则递归创建
        self.monitor_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化当天的日志文件路径
        self.log_file = self.monitor_dir / "monitor.log"
        
        # 初始化Agent性能统计
        self.agent_stats: Dict[str, Dict[str, Any]] = {
            "radical": {"times": [], "count": 0, "total": 0.0, "avg": 0.0, "min": float('inf'), "max": 0.0},
            "conservative": {"times": [], "count": 0, "total": 0.0, "avg": 0.0, "min": float('inf'), "max": 0.0},
            "adversarial": {"times": [], "count": 0, "total": 0.0, "avg": 0.0, "min": float('inf'), "max": 0.0},
            "judge": {"times": [], "count": 0, "total": 0.0, "avg": 0.0, "min": float('inf'), "max": 0.0}
        }
        
        # 处理进度跟踪
        self.progress = {
            "total_chunks": 0,
            "processed_chunks": 0,
            "successful_chunks": 0,
            "failed_chunks": 0,
            "start_time": None,
            "current_chunk_id": None
        }
        
        # 启动时打个标记
        self.log_step("System", "Init", f"Monitoring initialized at {self.monitor_dir}")

    def log_step(self, agent: str, status: str, details: str = ""):
        """
        记录关键步骤的状态
        :param agent: 执行者名称 (e.g., "激进派", "Pipeline")
        :param status: 状态 (e.g., "Start", "Success", "Error")
        :param details: 详细信息
        """
        # 1. 获取当前时间戳
        timestamp = time.strftime("%H:%M:%S")
        
        # 2. 获取进度信息（如果可用）
        progress_info = ""
        if self.progress["total_chunks"] > 0 and self.progress["current_chunk_id"]:
            percent = (self.progress["processed_chunks"] / self.progress["total_chunks"]) * 100
            progress_info = f" [进度: {self.progress['processed_chunks']}/{self.progress['total_chunks']} ({percent:.1f}%)]"
        
        # 3. 格式化日志消息
        # 格式: [12:00:00] [激进派] Success: 提取了 5 个实体
        message = f"[{timestamp}] [{agent}] {status}{progress_info}"
        if details:
            message += f": {details}"
        
        # 4. 控制台输出 (实时反馈)
        print(message)
        
        # 5. 文件持久化 (追加模式)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception as e:
            # 即使日志写入失败，也不能让程序崩掉，打印错误即可
            print(f"⚠️ [MONITOR_ERROR] Write log failed: {e}")

    def record_agent_time(self, agent_name: str, elapsed_time: float):
        """
        记录Agent处理时间，用于性能分析
        :param agent_name: Agent名称 (radical, conservative, adversarial, judge)
        :param elapsed_time: 处理时间（秒）
        """
        if agent_name not in self.agent_stats:
            self.agent_stats[agent_name] = {"times": [], "count": 0, "total": 0.0, "avg": 0.0, "min": float('inf'), "max": 0.0}
        
        stats = self.agent_stats[agent_name]
        stats["times"].append(elapsed_time)
        stats["count"] += 1
        stats["total"] += elapsed_time
        stats["avg"] = stats["total"] / stats["count"]
        stats["min"] = min(stats["min"], elapsed_time)
        stats["max"] = max(stats["max"], elapsed_time)
        
        # 记录到日志
        self.log_step("Monitor", "AgentTime", 
                     f"{agent_name}: {elapsed_time:.2f}s (Avg: {stats['avg']:.2f}s)")

    def update_progress(self, total_chunks: Optional[int] = None, 
                       processed_chunks: Optional[int] = None,
                       successful_chunks: Optional[int] = None,
                       failed_chunks: Optional[int] = None,
                       current_chunk_id: Optional[int] = None):
        """
        更新处理进度信息
        """
        if total_chunks is not None:
            self.progress["total_chunks"] = total_chunks
        if processed_chunks is not None:
            self.progress["processed_chunks"] = processed_chunks
        if successful_chunks is not None:
            self.progress["successful_chunks"] = successful_chunks
        if failed_chunks is not None:
            self.progress["failed_chunks"] = failed_chunks
        if current_chunk_id is not None:
            self.progress["current_chunk_id"] = current_chunk_id
        
        # 如果这是第一次调用，记录开始时间
        if self.progress["start_time"] is None and total_chunks is not None:
            self.progress["start_time"] = datetime.now()

    def save_intermediate(self, filename: str, content: Any):
        """
        保存中间结果 (调试神器)
        当你开启 debug_mode 时，Pipeline 会调用此方法保存 LLM 的原始回复
        :param filename: 文件名 (e.g., "debug_radical_chunk_1.txt")
        :param content: 内容 (可以是字符串，也可以是字典/列表)
        """
        file_path = self.monitor_dir / filename
        
        try:
            # 1. 如果内容是字典或列表，自动转为格式化的 JSON 字符串
            if isinstance(content, (dict, list)):
                write_content = json.dumps(content, ensure_ascii=False, indent=2)
            else:
                write_content = str(content)
            
            # 2. 写入文件 (覆盖模式)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(write_content)
                
            # 记录保存操作
            self.log_step("Monitor", "SaveIntermediate", f"Saved {filename}")
            
        except Exception as e:
            self.log_step("Monitor", "SaveError", f"Failed to save {filename}: {e}")

    def save_agent_stats(self):
        """
        将Agent性能统计数据保存到JSON文件
        """
        stats_file = self.monitor_dir / "agent_stats.json"
        
        try:
            # 准备统计数据
            stats_data = {
                "agent_stats": self.agent_stats,
                "progress": self.progress,
                "generated_at": datetime.now().isoformat()
            }
            
            # 计算总统计
            total_calls = sum(stats["count"] for stats in self.agent_stats.values())
            total_time = sum(stats["total"] for stats in self.agent_stats.values())
            
            if total_calls > 0:
                stats_data["summary"] = {
                    "total_calls": total_calls,
                    "total_time": total_time,
                    "avg_time_per_call": total_time / total_calls if total_calls > 0 else 0
                }
            
            # 保存到文件
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            
            self.log_step("Monitor", "SaveStats", f"Agent statistics saved to {stats_file.name}")
            
        except Exception as e:
            self.log_step("Monitor", "SaveStatsError", f"Failed to save agent stats: {e}")

    def print_performance_summary(self):
        """
        打印性能统计摘要到控制台
        """
        print("\n" + "="*60)
        print("📊 AGENT PERFORMANCE SUMMARY")
        print("="*60)
        
        # 打印各Agent性能
        for agent_name, stats in self.agent_stats.items():
            if stats["count"] > 0:
                print(f"{agent_name.capitalize():12s}: {stats['count']:3d} calls | "
                      f"Total: {stats['total']:7.2f}s | "
                      f"Avg: {stats['avg']:6.2f}s | "
                      f"Min: {stats['min']:6.2f}s | "
                      f"Max: {stats['max']:6.2f}s")
        
        # 打印总体统计
        total_calls = sum(stats["count"] for stats in self.agent_stats.values())
        total_time = sum(stats["total"] for stats in self.agent_stats.values())
        
        if total_calls > 0:
            print("-"*60)
            print(f"📈 TOTAL: {total_calls} calls in {total_time:.2f}s")
            print(f"⏱️  Average time per call: {total_time/total_calls:.2f}s")
        
        # 打印进度统计
        if self.progress["total_chunks"] > 0:
            print("-"*60)
            print("📈 PROCESSING PROGRESS")
            processed = self.progress["processed_chunks"]
            total = self.progress["total_chunks"]
            success = self.progress["successful_chunks"]
            failed = self.progress["failed_chunks"]
            percent = (processed / total) * 100 if total > 0 else 0
            
            print(f"Processed: {processed}/{total} chunks ({percent:.1f}%)")
            print(f"Success: {success}, Failed: {failed}")
            
            # 计算预估剩余时间
            if self.progress["start_time"] and processed > 0:
                elapsed = (datetime.now() - self.progress["start_time"]).total_seconds()
                if processed > 0:
                    avg_time_per_chunk = elapsed / processed
                    remaining_chunks = total - processed
                    estimated_remaining = avg_time_per_chunk * remaining_chunks
                    print(f"⏳ Estimated time remaining: {estimated_remaining:.0f}s ({estimated_remaining/60:.1f} min)")
        
        print("="*60 + "\n")

    def get_log_path(self) -> str:
        """获取日志文件的绝对路径"""
        return str(self.log_file.absolute())
    
    def get_agent_stats(self, agent_name: str = None) -> Dict:
        """
        获取Agent统计信息
        :param agent_name: 指定的Agent名称，None表示获取所有
        :return: 统计信息字典
        """
        if agent_name:
            return self.agent_stats.get(agent_name, {})
        return self.agent_stats
    
    def get_progress_info(self) -> Dict:
        """获取当前进度信息"""
        return self.progress.copy()