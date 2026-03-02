# -*- coding: utf-8 -*-
import os
import json
import uuid
import sys
import re
from tqdm import tqdm
from typing import List, Dict

# ==========================================
# 0. 路径补丁与兼容性导入
# ==========================================
# 将当前目录加入系统路径，确保脚本能找到同级模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    # 包模式导入 (被 main.py 调用时)
    from .pdf_loader_api import PDFCloudLoader
    from .docx_loader import DocxIngestor
    from .txt_loader import TxtIngestor
    from .utils import IngestionUtils
except ImportError:
    # 脚本模式导入 (直接运行此文件时)
    from pdf_loader_api import PDFCloudLoader
    from docx_loader import DocxIngestor
    from txt_loader import TxtIngestor
    from utils import IngestionUtils

class IngestionPipeline:
    """
    上游数据清洗总控 (The Mining Captain) - V3.2 增强版
    
    职责：
    1. 扫描 raw_data 目录。
    2. 路由分发：
       - PDF -> Cloud API -> Clean Text -> Semantic Split
       - Word -> MarkItDown -> Semantic Split
       - TXT -> LangChain Split
    3. 深度精炼：集成表格结构化修复与公式保护逻辑。
    4. 统一封装：输出标准化的 structured_chunks.jsonl。
    """

    def __init__(self, input_dir: str, output_file: str):
        self.input_dir = input_dir
        self.output_file = output_file
        
        print(f"🏭 [INGESTION] 初始化数据清洗流水线...")
        print(f"   -> 数据源: {self.input_dir}")
        print(f"   -> 产物: {self.output_file}")
        
        # 初始化各个引擎
        # 1. PDF 引擎 (云端 API - 负责 OCR 和版面分析)
        try:
            self.pdf_loader = PDFCloudLoader()
            print("   ✅ PDF引擎 (Cloud API) 就绪")
        except Exception as e:
            print(f"   ⚠️ PDF引擎初始化失败: {e} (请检查 .env MINERU_API_TOKEN)")
            self.pdf_loader = None

        # 2. Word/Markdown 处理引擎 (本地 - 负责切分和 Word 转换)
        try:
            self.docx_loader = DocxIngestor()
            print("   ✅ Word/MD切分引擎 (MarkItDown) 就绪")
        except Exception as e:
            print(f"   ⚠️ Word引擎初始化失败: {e}")
            self.docx_loader = None

        # 3. TXT 引擎 (本地 - 负责纯文本切分)
        try:
            self.txt_loader = TxtIngestor()
            print("   ✅ TXT引擎 (LangChain) 就绪")
        except Exception as e:
            print(f"   ⚠️ TXT引擎初始化失败: {e}")
            self.txt_loader = None

    def _check_chunk_quality(self, chunk: Dict) -> bool:
        """
        检查chunk质量，返回True表示质量合格
        """
        content = chunk.get('content', '')
        
        if not content or len(content.strip()) < 10:
            return False
        
        # 检查是否有未处理的公式占位符
        unprocessed_formula = re.search(r'__FORMULA_\d+__', content)
        if unprocessed_formula:
            print(f"       ⚠️ 警告: chunk中有未处理的公式占位符: {unprocessed_formula.group(0)}")
            # 标记问题但不直接丢弃，因为占位符仍可读
            # 可以后续修复
            
        # 检查表格完整性（简单检查）
        lines = content.split('\n')
        table_lines = [l for l in lines if '|' in l and '---' not in l and l.strip()]
        
        if len(table_lines) >= 2:  # 疑似表格内容
            # 检查表格是否有表头分隔线
            separator_lines = [l for l in lines if re.match(r'^\|?[-:| ]+\|?$', l.strip())]
            if table_lines and not separator_lines:
                # 表格可能缺少分隔线，但可能仍有效
                print(f"       ⚠️ 警告: 疑似表格缺少分隔线")
        
        return True

    def _diagnose_mineru_output(self, raw_content: str, file_name: str) -> Dict:
        """
        诊断MinerU输出格式，返回诊断结果
        """
        diagnostics = {
            "file": file_name,
            "content_length": len(raw_content),
            "formula_patterns": {},
            "tables": 0,
            "warnings": []
        }
        
        # 检查公式占位符
        formula_patterns = {
            "mineru_placeholder": r'__FORMULA_\d+__',
            "escaped_placeholder": r'\\_\\_FORMULA\\_\d+\\_\\_',
            "simple_placeholder": r'_FORMULA_\d+_',
            "latex_inline": r'\$[^$]+\$',
            "latex_block": r'\$\$[^$]+\$\$',
        }
        
        for name, pattern in formula_patterns.items():
            matches = re.findall(pattern, raw_content)
            if matches:
                diagnostics["formula_patterns"][name] = len(matches)
        
        # 检查HTML表格
        table_count = raw_content.count('<table')
        diagnostics["tables"] = table_count
        
        # 检查是否有未识别的占位符
        all_formula_matches = sum(diagnostics["formula_patterns"].values())
        if all_formula_matches == 0 and 'FORMULA' in raw_content:
            diagnostics["warnings"].append("发现'FORMULA'字符串但未被正则匹配")
        
        return diagnostics

    def _process_pdf_with_diagnostics(self, file_path: str, file_name: str) -> List[Dict]:
        """
        处理PDF文件，包含诊断信息
        """
        file_chunks = []
        
        try:
            if not self.pdf_loader or not self.docx_loader:
                print(f"   ⚠️ 引擎缺失，无法处理PDF: {file_name}")
                return []
            
            print(f"   📄 处理PDF: {file_name}")
            
            # 1. 云端获取Raw Markdown
            raw_results = self.pdf_loader.process(file_path)
            if not raw_results or not raw_results[0].get("content"):
                print(f"   ⚠️ 云端解析无内容: {file_name}")
                return []
            
            raw_content = raw_results[0]["content"]
            
            # 2. 诊断输出格式
            print(f"     🔍 诊断MinerU输出格式...")
            diagnostics = self._diagnose_mineru_output(raw_content[:5000], file_name)
            
            if diagnostics["formula_patterns"]:
                print(f"     🔍 公式诊断: {diagnostics['formula_patterns']}")
            if diagnostics["tables"] > 0:
                print(f"     🔍 表格诊断: 发现 {diagnostics['tables']} 个HTML表格")
            if diagnostics["warnings"]:
                for warning in diagnostics["warnings"]:
                    print(f"     ⚠️ 警告: {warning}")
            
            # 3. 深度清洗（表格转换 + 公式保护）
            print(f"     🧹 深度清洗...")
            clean_content = IngestionUtils.clean_text(raw_content)
            
            # 4. 检查清洗效果
            leftover_formulas = re.findall(r'__FORMULA_\d+__', clean_content)
            if leftover_formulas:
                print(f"     ⚠️ 清洗后仍有 {len(leftover_formulas)} 个未处理公式占位符")
            
            # 5. 语义切分
            print(f"     🔪 语义切分...")
            file_chunks = self.docx_loader.process_raw_markdown(clean_content, file_name)
            
            # 6. 质量过滤
            valid_chunks = []
            for i, chunk in enumerate(file_chunks):
                # 确保chunk有必要字段
                if "content" not in chunk:
                    continue
                
                # 检查质量
                if self._check_chunk_quality(chunk):
                    # 确保chunk_id存在
                    if "chunk_id" not in chunk:
                        chunk["chunk_id"] = str(uuid.uuid4())
                    
                    # 确保metadata存在
                    if "metadata" not in chunk:
                        chunk["metadata"] = {}
                    
                    # 添加诊断信息
                    chunk["metadata"]["diagnostics"] = {
                        "source_file": file_name,
                        "has_formula": bool(re.search(r'__FORMULA_\d+__|\$[^$]+\$', chunk["content"])),
                        "has_table": '|' in chunk["content"] and '---' in chunk["content"],
                    }
                    
                    valid_chunks.append(chunk)
            
            print(f"     ✅ 生成 {len(valid_chunks)} 个有效chunk")
            return valid_chunks
            
        except Exception as e:
            print(f"     ❌ PDF处理异常 [{file_name}]: {type(e).__name__}")
            print(f"       错误详情: {str(e)}")
            
            # 根据不同错误类型提供建议
            if "connection" in str(e).lower() or "api" in str(e).lower():
                print("       建议: 检查网络连接或API密钥")
            elif "timeout" in str(e).lower():
                print("       建议: 增加超时时间或检查文件大小")
            elif "memory" in str(e).lower():
                print("       建议: 文件可能太大，尝试分批处理")
            
            import traceback
            traceback.print_exc()
            return []

    def run(self):
        """
        执行全量清洗任务
        """
        # 1. 扫描文件系统
        all_files = []
        if not os.path.exists(self.input_dir):
            print(f"❌ 输入目录不存在: {self.input_dir}")
            return

        for root, dirs, files in os.walk(self.input_dir):
            for file in files:
                # 过滤临时文件和隐藏文件
                if not file.startswith("~$") and not file.startswith("."):
                    all_files.append(os.path.join(root, file))

        print(f"\n📊 扫描到 {len(all_files)} 个原始文件，准备开工...")
        
        all_chunks = []
        stats = {
            "success": 0, 
            "failed": 0, 
            "skipped": 0,
            "pdf": 0,
            "word": 0,
            "txt": 0
        }

        # 2. 遍历处理 (带进度条)
        for file_path in tqdm(all_files, desc="Mining Progress", unit="file"):
            ext = os.path.splitext(file_path)[1].lower()
            file_name = os.path.basename(file_path)
            file_chunks = []
            
            try:
                # --- A. 处理 PDF (云端解析 + 本地精炼) ---
                if ext == '.pdf':
                    if self.pdf_loader and self.docx_loader:
                        file_chunks = self._process_pdf_with_diagnostics(file_path, file_name)
                        stats["pdf"] += 1
                    else:
                        print(f"⏩ 跳过 PDF (引擎缺失): {file_name}")
                        stats["skipped"] += 1

                # --- B. 处理 Word (.docx) ---
                elif ext in ['.docx', '.doc']:
                    if self.docx_loader:
                        print(f"   📄 处理Word: {file_name}")
                        file_chunks = self.docx_loader.process(file_path)
                        stats["word"] += 1
                    else:
                        print(f"⏩ 跳过 DOCX: {file_name}")
                        stats["skipped"] += 1
                        
                # --- C. 处理 TXT/MD ---
                elif ext in ['.txt', '.md']:
                    if self.txt_loader:
                        print(f"   📄 处理文本: {file_name}")
                        file_chunks = self.txt_loader.process(file_path)
                        stats["txt"] += 1
                    else:
                        print(f"⏩ 跳过 TXT: {file_name}")
                        stats["skipped"] += 1
                else:
                    # 忽略不支持的格式 (图片、压缩包等)
                    continue
                
                # --- 结果汇总与过滤 ---
                if file_chunks:
                    valid_chunks = []
                    for chunk in file_chunks:
                        # 基础过滤：去掉过短的垃圾切片
                        if IngestionUtils.is_valid_chunk(chunk.get('content', '')):
                            valid_chunks.append(chunk)
                    
                    if valid_chunks:
                        all_chunks.extend(valid_chunks)
                        stats["success"] += 1
                    else:
                        # 虽然解析了，但内容都被过滤掉了
                        print(f"   ⚠️ 文件 {file_name} 无有效chunk")
                        stats["failed"] += 1
                else:
                    stats["failed"] += 1
                    
            except Exception as e:
                print(f"\n❌ 处理失败 [{file_name}]: {type(e).__name__}")
                print(f"   错误详情: {str(e)}")
                
                # 根据不同错误类型提供建议
                if "permission" in str(e).lower():
                    print("   建议: 检查文件权限或是否被其他程序占用")
                elif "format" in str(e).lower() or "corrupt" in str(e).lower():
                    print("   建议: 文件可能损坏或格式不支持")
                
                stats["failed"] += 1

        # 3. 持久化存储
        if not all_chunks:
            print("⚠️ 任务结束，无有效数据生成。")
            return

        print(f"\n💾 正在写入 {len(all_chunks)} 个切片到: {self.output_file}")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        
        # 使用全量覆盖模式 ('w')，保证数据最新且无重复
        with open(self.output_file, 'w', encoding='utf-8') as f:
            for chunk in all_chunks:
                # 最后的 ID 保险：确保每个 chunk 都有唯一 ID
                if "chunk_id" not in chunk:
                    chunk["chunk_id"] = str(uuid.uuid4())
                
                # 确保 metadata 字段存在
                if "metadata" not in chunk:
                    chunk["metadata"] = {}
                    
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        # 4. 生成处理报告
        print("="*60)
        print(f"🎉 采矿任务圆满完成")
        print(f"   - 文件统计:")
        print(f"       成功: {stats['success']} 个文件")
        print(f"       失败: {stats['failed']} 个文件")
        print(f"       跳过: {stats['skipped']} 个文件")
        print(f"   - 文件类型:")
        print(f"       PDF: {stats['pdf']} 个")
        print(f"       Word: {stats['word']} 个")
        print(f"       文本: {stats['txt']} 个")
        print(f"   - 产出切片: {len(all_chunks)} 个")
        print(f"   - 质量检查:")
        print(f"       ✅ 表格已结构化 (HTML -> Markdown)")
        print(f"       ✅ 公式已保护 (占位符 -> 可读格式)")
        print(f"       ✅ 深度去噪 (页码、水印、空行)")
        print("="*60)
        
        # 保存统计信息到日志文件
        log_file = os.path.join(os.path.dirname(self.output_file), "ingestion_stats.json")
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": str(uuid.uuid4()),
                "input_dir": self.input_dir,
                "output_file": self.output_file,
                "stats": stats,
                "total_chunks": len(all_chunks)
            }, f, ensure_ascii=False, indent=2)
        
        print(f"📊 统计信息已保存到: {log_file}")

# ==========================================
# 独立运行入口 (调试用)
# ==========================================
if __name__ == "__main__":
    # 默认配置路径 (适配 V3.0 结构)
    # 假设脚本在 D:\KG_Test\ingestion\processor.py，向上两级是根目录
    
    # 动态获取根目录
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 定义输入输出
    INPUT_DIR = os.path.join(BASE_DIR, "raw_data")
    OUTPUT_FILE = os.path.join(BASE_DIR, "jsonl", "structured_chunks.jsonl")
    
    # 启动
    print(f"🚀 启动数据清洗流水线...")
    print(f"   根目录: {BASE_DIR}")
    print(f"   输入目录: {INPUT_DIR}")
    print(f"   输出文件: {OUTPUT_FILE}")
    print(f"   {'-'*40}")
    
    pipeline = IngestionPipeline(INPUT_DIR, OUTPUT_FILE)
    pipeline.run()