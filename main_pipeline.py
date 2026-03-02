# -*- coding: utf-8 -*-
import asyncio
import argparse
import sys
import time
from typing import List

# ==========================================
# 关键修改：适配 V3.0 模块化结构
# ==========================================
# 导入配置中枢
from config import SystemConfig

# 从 core 包中导入核心业务组件
from core.pipeline import UltimateKnowledgeExtractor
from core.database import Neo4jExporter
from core.models import ProcessingResult

# ==========================================
# 1. 异步主逻辑 (The Async Core)
# ==========================================
async def main_async(config: SystemConfig):
    """
    异步主函数：负责调度提取流水线和导出任务
    """
    # 1. 初始化提取流水线 (The Factory)
    print(f"🏭 [MAIN] 初始化知识提取流水线...")
    extractor = UltimateKnowledgeExtractor(config)
    
    # 2. 执行批量提取 (The Process)
    # 系统会根据 config.debug_mode 自动决定是串行调试还是并发生产
    print(f"🚀 [MAIN] 引擎启动，准备处理数据...")
    start_time = time.time()
    
    # 核心运行：等待所有 Agent 完成工作
    results: List[ProcessingResult] = await extractor.run()
    
    total_time = time.time() - start_time
    
    # 3. 统计结果 (The Report)
    success_count = sum(1 for r in results if r.success)
    failed_count = len(results) - success_count
    
    print("\n" + "="*60)
    print(f"🎉 任务完成 (Mission Complete)")
    print(f"⏱️  总耗时: {total_time:.2f} 秒")
    print(f"📊 成功: {success_count} | 失败: {failed_count}")
    print("="*60)
    
    # 4. 执行数据导出 (The Warehouse)
    # [V3.0 修改] 只有在成功提取数据后，才调用导出器
    if config.neo4j_export_enabled and success_count > 0:
        print(f"\n📤 [MAIN] 正在将图谱数据导出至: {config.graph_dir}")
        
        # [关键修改] 传入 config.graph_dir 目录，而不是文件路径
        # database.py 会自动在该目录下生成 neo4j_nodes.csv 和 neo4j_relationships.csv
        exporter = Neo4jExporter(config.graph_dir)
        exporter.export(results)
        
        print(f"✨ 导出完毕。请使用 auto_import.py 工具将数据导入 Neo4j。")
        
    elif success_count == 0:
        print("\n⚠️ [MAIN] 没有产生成功的提取结果，跳过导出步骤。")

# ==========================================
# 2. 程序入口 (The Entry Point)
# ==========================================
if __name__ == "__main__":
    # 1. 打印 V3.0 Banner (仪式感)
    print(r"""
    _             _      ____      _    ____  
   / \   _ __ ___| |__  |  _ \    / \  / ___| 
  / _ \ | '__/ __| '_ \ | |_) |  / _ \| |  _  
 / ___ \| | | (__| | | ||  _ <  / ___ \ |_| | 
/_/   \_\_|  \___|_| |_||_| \_\/_/   \_\____| 
                                              
    >> ArchRAG Core Pipeline V3.0 (ETL) <<
    """)

    # 2. 解析命令行参数
    parser = argparse.ArgumentParser(description="ArchRAG 知识提取引擎 (离线处理)")
    
    # 添加 --debug 参数，用于开启“伪同步”模式
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="开启调试模式 (强制串行 + 人类断点 + 中间文件保存)"
    )
    
    args = parser.parse_args()

    # 3. 初始化系统配置
    # 将命令行参数注入配置对象，config 会自动组装所有 V3.0 路径
    try:
        config = SystemConfig(debug_mode=args.debug)
    except Exception as e:
        print(f"❌ 配置初始化失败: {e}")
        sys.exit(1)

    # 4. 启动异步事件循环
    try:
        # Windows 下的 asyncio 策略调整 (防止 aiohttp 在 Windows 上报 EventLoopClosed 错误)
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        asyncio.run(main_async(config))
        
    except KeyboardInterrupt:
        print("\n\n🛑 用户强制终止任务 (User Aborted).")
    except Exception as e:
        print(f"\n\n❌ 致命错误 (Fatal Error): {e}")
        import traceback
        traceback.print_exc()