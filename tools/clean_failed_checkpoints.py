# -*- coding: utf-8 -*-
import json
import os
import sys
import shutil

# ==========================================
# 0. 路径补丁 (Path Patching)
# ==========================================
# 确保脚本能找到根目录下的 config.py
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config import SystemConfig

class CheckpointCleaner:
    """
    断点续传清洗器 (The State Scrubber)
    
    职责：
    1. 扫描输出日志 (graph_data_ultimate.jsonl)。
    2. 剔除所有标记为 "success": false 的失败记录。
    3. 保留 "success": true 的成功记录。
    4. 目的：让 Pipeline 在下次运行时重新尝试那些失败的 Chunk。
    """

    def __init__(self):
        # 加载系统配置
        self.config = SystemConfig()
        
        # 定义操作目标
        self.target_file = self.config.output_file
        self.temp_file = self.target_file + ".tmp"
        self.backup_file = self.target_file + ".bak"

    def run(self):
        print(f"🧹 [CLEANER] 启动断点清洗程序...")
        print(f"   -> 目标日志: {self.target_file}")

        if not os.path.exists(self.target_file):
            print(f"❌ 错误: 找不到日志文件，无需清洗。")
            return

        # 1. 创建安全备份
        try:
            shutil.copy(self.target_file, self.backup_file)
            print(f"   -> 已创建备份: {os.path.basename(self.backup_file)}")
        except Exception as e:
            print(f"❌ 备份失败，停止操作: {e}")
            return

        # 2. 执行清洗过滤
        success_count = 0
        fail_count = 0
        total_lines = 0
        
        try:
            with open(self.target_file, 'r', encoding='utf-8') as f_in, \
                 open(self.temp_file, 'w', encoding='utf-8') as f_out:
                
                for line in f_in:
                    line = line.strip()
                    if not line: continue
                    
                    total_lines += 1
                    try:
                        data = json.loads(line)
                        
                        # --- 核心逻辑 ---
                        # 只有 success=True 的记录才会被写回新文件
                        # success=False (如超时、报错) 的记录被丢弃 -> 意味着下次会重跑
                        if data.get("success") is True:
                            f_out.write(json.dumps(data, ensure_ascii=False) + "\n")
                            success_count += 1
                        else:
                            fail_count += 1
                        # ----------------
                        
                    except json.JSONDecodeError:
                        # 损坏的行直接丢弃
                        print(f"   ⚠️ 丢弃损坏行 (Line {total_lines})")
                        continue

            # 3. 原子替换 (Atomic Swap)
            # 删除原文件，将临时文件重命名为原文件名
            os.remove(self.target_file)
            os.rename(self.temp_file, self.target_file)
            
            print(f"\n✅ 清洗完成!")
            print(f"   -> 扫描总数: {total_lines}")
            print(f"   -> 保留记录 (Success): {success_count}")
            print(f"   -> 剔除记录 (Failed):  {fail_count}")
            
            if fail_count > 0:
                print(f"\n💡 提示: 下次运行 main_pipeline.py 时，将重新处理这 {fail_count} 个失败的任务。")
            else:
                print(f"\n✨ 提示: 文件是干净的，没有发现失败记录。")

        except Exception as e:
            print(f"\n❌ 清洗过程中发生异常: {e}")
            # 尝试回滚
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
            print("   -> 操作已取消，原文件保持不变。")

# ==========================================
# 独立运行入口
# ==========================================
if __name__ == "__main__":
    cleaner = CheckpointCleaner()
    cleaner.run()