# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys

# ==========================================
# 0. 路径补丁 (Path Patching)
# ==========================================
# 将项目根目录加入 Python 搜索路径，以便导入 config.py
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config import SystemConfig

class DataFixer:
    """
    数据身份证修复器 (The ID Patcher)
    
    职责：
    1. 扫描 structured_chunks.jsonl
    2. 检测缺失 'chunk_id' 的记录
    3. 自动补全 ID (使用行号序列)
    4. 安全备份原文件
    """

    def __init__(self):
        # 加载系统配置
        self.config = SystemConfig()
        
        # 定义目标文件
        self.target_file = self.config.input_file
        # 定义备份文件 (e.g., structured_chunks.jsonl.bak)
        self.backup_file = self.target_file + ".bak"
        # 定义临时文件
        self.temp_file = self.target_file + ".tmp"

    def run(self):
        print(f"🔧 [FIXER] 启动数据 ID 修复程序...")
        print(f"   -> 目标文件: {self.target_file}")

        if not os.path.exists(self.target_file):
            print(f"❌ 错误: 找不到输入文件，无需修复。")
            return

        # 1. 创建备份 (安全第一)
        try:
            shutil.copy(self.target_file, self.backup_file)
            print(f"   -> 已创建备份: {os.path.basename(self.backup_file)}")
        except Exception as e:
            print(f"❌ 备份失败: {e}")
            return

        # 2. 执行修复
        fixed_count = 0
        total_count = 0
        
        try:
            with open(self.target_file, 'r', encoding='utf-8') as f_in, \
                 open(self.temp_file, 'w', encoding='utf-8') as f_out:
                
                for index, line in enumerate(f_in):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        total_count += 1
                        
                        # --- 核心修复逻辑 ---
                        # 如果没有 chunk_id，或者 chunk_id 为 null
                        if 'chunk_id' not in data or data['chunk_id'] is None:
                            # 自动分配 ID (行号从 1 开始)
                            # 注意：如果后续需要 UUID，可改为 uuid.uuid4().hex
                            data['chunk_id'] = index + 1
                            fixed_count += 1
                        # --------------------
                        
                        f_out.write(json.dumps(data, ensure_ascii=False) + "\n")
                        
                    except json.JSONDecodeError:
                        print(f"   ⚠️ 跳过损坏的 JSON 行: 第 {index+1} 行")
                        continue

            # 3. 替换文件
            # 只有在处理过程无致命错误时才执行替换
            # 先关闭文件句柄 (with块已自动处理)，再操作文件系统
            os.remove(self.target_file)
            os.rename(self.temp_file, self.target_file)
            
            print(f"\n✅ 修复完成!")
            print(f"   -> 扫描总数: {total_count}")
            print(f"   -> 修复数量: {fixed_count}")
            print(f"   -> 现在可以安全运行 main_pipeline.py 了。")

        except Exception as e:
            print(f"\n❌ 修复过程中发生异常: {e}")
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
            print("   -> 原文件保持不变 (已回滚)。")

# ==========================================
# 独立运行入口
# ==========================================
if __name__ == "__main__":
    fixer = DataFixer()
    fixer.run()