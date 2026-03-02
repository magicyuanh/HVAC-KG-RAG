# -*- coding: utf-8 -*-
import json
import os
import sys
import glob
import numpy as np
from pathlib import Path
from typing import Set, List, Dict, Any
from tqdm import tqdm  # [新增] 进度条库

# ==========================================
# 0. 路径补丁 (Path Patching)
# ==========================================
# 确保脚本能找到根目录下的 config.py
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config import SystemConfig

class QualityAnalyzer:
    """
    质量分析器 (The Analyst) - V3.0 增强版
    
    职责：
    1. 读取 graph_data_ultimate.jsonl 分析处理耗时。
    2. 读取 monitor/ 下的 debug_*.txt 分析四方会审的纳谏率。
    3. 生成量化的性能与质量报告。
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.log_file = Path(self.config.output_file) # jsonl/graph_data_ultimate.jsonl
        self.debug_dir = Path(self.config.monitor_dir)# monitor/
        
        print(f"📊 [ANALYZER] 初始化统计分析...")
        print(f"   -> 日志路径: {self.log_file}")
        print(f"   -> 调试目录: {self.debug_dir}")

    def _extract_entities(self, filepath: Path) -> Set[str]:
        """
        辅助函数：从调试文件中解析出标准化后的实体名称集合
        """
        if not filepath.exists():
            return set()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 1. 尝试提取 JSON 部分
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                return set()
                
            json_str = content[start:end]
            data = json.loads(json_str)
            
            # 2. 兼容不同的 JSON 结构
            entities = []
            if "knowledge_graph" in data:
                entities = data["knowledge_graph"].get("entities", [])
            elif "entities" in data:
                entities = data.get("entities", [])
                
            # 3. 标准化输出
            entity_names = set()
            for e in entities:
                if isinstance(e, dict) and "name" in e:
                    name = e["name"].strip().upper()
                    if name:
                        entity_names.add(name)
                        
            return entity_names
            
        except Exception as e:
            return set()

    def run(self):
        """执行全量分析"""
        if not self.log_file.exists():
            print(f"❌ 未找到日志文件: {self.log_file}")
            print(f"   请先运行 main.py (离线提取任务)。")
            return

        # --- A. 基础性能统计 (Performance) ---
        times = []
        chunk_ids = []
        success_count = 0
        
        print(f"\n1️⃣  正在解析流水线日志...")
        try:
            # 读取所有行以显示进度条
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # [新增] 使用 tqdm 显示进度
            for line in tqdm(lines, desc="Parsing Logs", unit="line"):
                line = line.strip()
                if not line: continue
                try:
                    record = json.loads(line)
                    if record.get("success"):
                        success_count += 1
                        t = record.get("processing_time", 0.0)
                        times.append(t)
                        chunk_ids.append(record.get("chunk_id"))
                except:
                    pass
        except Exception as e:
            print(f"❌ 读取日志失败: {e}")
            return

        if not times:
            print("⚠️ 日志中没有成功的处理记录。")
            return

        avg_time = np.mean(times)
        max_time = np.max(times)
        min_time = np.min(times)
        total_time = sum(times)

        # --- B. 智能体博弈分析 (Quality) ---
        stats_data = []
        
        # 仅分析有调试记录的 Chunk
        print(f"\n2️⃣  正在分析 {len(chunk_ids)} 个任务的博弈详情...")
        
        # [新增] 使用 tqdm 显示进度
        for cid in tqdm(chunk_ids, desc="Scanning Debug Files", unit="chunk"):
            # 构造文件名
            f_rad = self.debug_dir / f"debug_Radical_Agent_chunk_{cid}.txt"
            f_con = self.debug_dir / f"debug_Conservative_Agent_chunk_{cid}.txt"
            f_jud = self.debug_dir / f"debug_Judge_Agent_chunk_{cid}.txt"

            # 检查文件完整性
            if not (f_rad.exists() and f_con.exists() and f_jud.exists()):
                continue

            # 提取实体集合
            s_rad = self._extract_entities(f_rad)
            s_con = self._extract_entities(f_con)
            s_jud = self._extract_entities(f_jud)

            if not s_jud: continue

            # 计算指标
            rad_kept = s_jud.intersection(s_rad)
            rad_recall = len(rad_kept) / len(s_rad) if len(s_rad) > 0 else 0.0

            con_kept = s_jud.intersection(s_con)
            con_precision = len(con_kept) / len(s_con) if len(s_con) > 0 else 0.0
            
            rad_unique = len(rad_kept - s_con)

            stats_data.append({
                "id": cid,
                "rad_len": len(s_rad),
                "con_len": len(s_con),
                "jud_len": len(s_jud),
                "rad_recall": rad_recall,
                "con_precision": con_precision,
                "rad_unique": rad_unique
            })

        # --- C. 输出可视化报告 ---
        print("\n" + "="*60)
        print("🚀 ArchRAG V3.0 效能分析报告")
        print("="*60)

        print(f"\n⏱️  [性能指标] (基于 {len(times)} 个 Chunk)")
        print(f"   - 总处理时长: {total_time/60:.1f} 分钟")
        print(f"   - 平均单块耗时: {avg_time:.2f} 秒")
        print(f"   - 最快 / 最慢: {min_time:.2f}s / {max_time:.2f}s")

        print(f"\n⚖️  [博弈指标] (基于 {len(stats_data)} 个含调试快照的样本)")
        
        if stats_data:
            avg_rad_rec = np.mean([d['rad_recall'] for d in stats_data])
            avg_con_pre = np.mean([d['con_precision'] for d in stats_data])
            sum_unique = sum(d['rad_unique'] for d in stats_data)

            print(f"   1. 激进派采纳率 (Recall): {avg_rad_rec*100:.1f}%")
            print(f"      (解读: 激进派有 {100-avg_rad_rec*100:.1f}% 的内容被判定为幻觉/冗余)")
            
            print(f"   2. 保守派准确率 (Precision): {avg_con_pre*100:.1f}%")
            print(f"      (解读: 保守派的内容有 {avg_con_pre*100:.1f}% 被最终认可)")
            
            print(f"   3. 激进派独家贡献: {sum_unique} 个实体")
            print(f"      (解读: 如果没有激进派，这些实体将被系统遗漏)")

            print("\n📋 [详细数据 Top 5]")
            print(f"   ID   | Rad(个) | Con(个) | Jud(个) | Rad采纳% | Con认可% | 独家贡献")
            print("   " + "-"*68)
            for d in stats_data[:5]:
                print(f"   {str(d['id']):<4} | {d['rad_len']:<7} | {d['con_len']:<7} | {d['jud_len']:<7} | {d['rad_recall']*100:6.1f}% | {d['con_precision']*100:6.1f}% | {d['rad_unique']}")
        else:
            print("   ℹ️ 暂无调试快照数据。")
            print("   (提示: 只有在 --debug 模式下运行，才能生成博弈分析)")

        print("="*60 + "\n")

# ==========================================
# 独立运行入口
# ==========================================
if __n