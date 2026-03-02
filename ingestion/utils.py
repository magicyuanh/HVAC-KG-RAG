# -*- coding: utf-8 -*-
import uuid
import re
import hashlib
from typing import List, Tuple, Dict

# ==========================================
# 0. 依赖加载
# ==========================================
# 尝试导入 markdownify，它是处理 MinerU 输出的 HTML 表格的神器
try:
    from markdownify import markdownify as md_converter
except ImportError:
    md_converter = None
    # 建议在 test 环境执行: pip install markdownify

class IngestionUtils:
    """
    上游数据清洗工具箱 (The Washer) - V3.2 增强版
    
    职责：
    1. ID生成：确保幂等性。
    2. 公式保护与恢复：防止 LaTeX 和占位符在清洗过程中被破坏。
    3. 表格结构化：HTML table -> Markdown table。
    4. 深度去噪：去除页码、水印、多余空行。
    5. OCR空格修复：修复OCR识别中的单位、数字、符号空格问题。
    """

    @staticmethod
    def generate_id(content: str) -> str:
        """根据内容生成唯一哈希 ID (确保同一段文本生成相同的 ID)"""
        if not content:
            return str(uuid.uuid4())
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_uuid() -> str:
        """生成随机 UUID"""
        return str(uuid.uuid4())

    @staticmethod
    def protect_formulas(text: str) -> Tuple[str, List[str]]:
        """
        [关键逻辑] 保护公式
        将 LaTeX 公式和 MinerU 占位符替换为无特殊含义的占位符 (FML...X)，防止被后续的正则或 Markdown 转换破坏。
        """
        # 匹配常见的 LaTeX 模式和 MinerU 占位符
        formula_patterns = [
            # MinerU 特有格式（必须优先匹配）
            r'__FORMULA_\d+__',                # 示例格式：__FORMULA_32__
            r'\\_\\_FORMULA\\_\d+\\_\\_',      # 转义版本
            r'_FORMULA_\d+_',                  # 简化版本
            
            # 标准LaTeX
            r'\$\$.*?\$\$',                    # 块级公式 $$...$$
            r'\$.*?\$',                        # 行内公式 $...$
            r'\\\(.*?\\\)',                    # 括号形式 \(...\)
            r'\\\[.*?\\\]',                    # 中括号形式 \[...\]
            
            # 技术文档特有模式
            r'C_{[^}]+}',                      # 下标表示 C_n
            r'\d+\.\d+\s*μm',                  # 单位表示 0.1μm
            r'μ\s*m',                          # 单位拆分 μ m
        ]
        
        formulas = []
        
        def replacer(match):
            formula = match.group(0)
            # 使用无下划线的纯字母数字占位符，避免被 Markdown 转义
            placeholder = f"FML{len(formulas)}X" 
            formulas.append(formula)
            return placeholder
        
        # 执行替换
        protected_text = text
        for pattern in formula_patterns:
            try:
                protected_text = re.sub(pattern, replacer, protected_text, flags=re.DOTALL)
            except Exception:
                continue
        
        return protected_text, formulas

    @staticmethod
    def restore_formulas(text: str, formulas: List[str]) -> str:
        """
        [关键逻辑] 恢复公式
        将占位符还原为原始公式，并清理公式内的多余空格。
        """
        if not formulas:
            return text
            
        for i, formula in enumerate(formulas):
            placeholder = f"FML{i}X"
            
            # 对公式进行内部清理，减少多余空格
            if formula.startswith('__FORMULA'):
                # MinerU占位符，直接替换，不需要额外空格
                text = text.replace(placeholder, formula)
            else:
                # LaTeX公式，清理内部多余空格
                # 1. 清理公式内的连续空格
                cleaned_formula = re.sub(r'\s+', ' ', formula)
                # 2. 清理公式边界多余空格
                cleaned_formula = cleaned_formula.strip()
                # 3. 替换时不需要额外添加空格
                text = text.replace(placeholder, cleaned_formula)
            
        return text

    @staticmethod
    def check_formula_problems(text: str) -> Dict:
        """
        检查文本中的公式问题，用于调试
        """
        # 查找所有可能的公式模式
        patterns = {
            "mineru_placeholder": r'__FORMULA_\d+__',
            "latex_inline": r'\$[^$]+\$',
            "latex_block": r'\$\$[^$]+\$\$',
            "units": r'\d+\s*μm',
        }
        
        results = {}
        for name, pattern in patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                results[name] = len(matches)
        
        return results

    @staticmethod
    def clean_text(text: str) -> str:
        """
        核心清洗流水线
        """
        if not text:
            return ""
    
        # --- Step 1: 公式保护 ---
        # 先把脆弱的公式藏起来
        protected_text, formulas = IngestionUtils.protect_formulas(text)
    
        # --- Step 2: 更彻底的表格转换 ---
        # 先尝试用 markdownify
        if md_converter:
            try:
                # 只使用 convert 参数，避免与 strip 冲突
                protected_text = md_converter(
                    protected_text,
                    heading_style="ATX",
                    convert=['table', 'tr', 'td', 'th', 'thead', 'tbody']
                )
            except Exception as e:
                print(f"⚠️ markdownify转换失败: {e}")
    
        # 备用方案：如果 markdownify 不可用，使用正则清理HTML标签
        if not md_converter or "<table" in protected_text:
            # 简单的HTML表格标签清理
            protected_text = re.sub(r'</?table[^>]*>', '', protected_text)
            protected_text = re.sub(r'</?tr[^>]*>', '\n', protected_text)
            protected_text = re.sub(r'</?td[^>]*>', ' | ', protected_text)
            protected_text = re.sub(r'</?th[^>]*>', ' | ', protected_text)
            protected_text = re.sub(r'\|\s+\|', '| |', protected_text)
    
        # --- Step 3: 深度正则去噪 ---
        
        # A. 清洗页码标记 (Page Markers)
        # 现象：(P53), （P4）
        protected_text = re.sub(r'[\(（]P\d+[\)）]', '', protected_text)

        # B. 清洗分隔线 (Separators)
        # 现象：OCR 识别表格线产生的 -------
        protected_text = re.sub(r'-{4,}', '---', protected_text)
        protected_text = re.sub(r'={4,}', '===', protected_text)
        
        # C. 修复换行 (Paragraphs)
        # 将 3 个以上连续换行压缩为 2 个 (保留段落结构，去除大片空白)
        protected_text = re.sub(r'\n{3,}', '\n\n', protected_text)
        
        # D. 去除不可见字符
        protected_text = protected_text.replace('\u200b', '').replace('\u3000', ' ')

        # --- Step 4: 公式恢复 ---
        # 此时文本结构已定型，把公式放回去
        cleaned_text = IngestionUtils.restore_formulas(protected_text, formulas)

        # --- Step 5: 修复 MinerU 特有的占位符 ---
        # 如果公式保护没有识别某些占位符，尝试修复
        # 查找未被保护的占位符
        leftover_formulas = re.findall(r'__FORMULA_\d+__', cleaned_text)
        for i, formula in enumerate(leftover_formulas):
            # 替换为更可读的形式
            num_match = re.search(r'\d+', formula)
            if num_match:
                num = num_match.group(0)
                cleaned_text = cleaned_text.replace(formula, f"[公式{num}]")
            else:
                cleaned_text = cleaned_text.replace(formula, "[公式]")
        
        # 修复其他可能的占位符格式
        cleaned_text = re.sub(r'_FORMULA_', '[公式]', cleaned_text)

        # --- Step 6: 增强OCR空格修复 ---
        # 修复 MinerU/OCR 常见的单位空格问题
        ocr_fixes = [
            # 单位修复 - 修复转义问题
            (r'(\d+\.?\d*)\s+μ\s*(\\mathrm\{)?m', r'\1μm'),  # 修复转义：\m → \\m
            (r'(\d+)\s+μm', r'\1μm'),
            (r'(\d+)\s+°\s*[Cc]', r'\1°C'),
            (r'(\d+)\s+×\s*10\^', r'\1×10^'),
            (r'(\d+)\s+(MPa|kPa|Pa|dB|h|m/s)', r'\1\2'),
            (r'(\d+)\s*%', r'\1%'),
            
            # LaTeX公式内空格修复
            (r'(\$[^$]+)\s+([^$]+\$)', r'\1\2'),
            (r'\\\(\s*([^)]+)\s*\\\)', r'\(\1\)'),
            (r'\\\[\s*([^]]+)\s*\\\]', r'\[\1\]'),
            
            # 下标和上标修复
            (r'C\s*_\s*{([^}]+)}', r'C_{\1}'),
            (r'10\s*^\s*{([^}]+)}', r'10^{\1}'),
            
            # 数学符号修复
            (r'\\mu\s*', 'μ'),
            (r'\\mathrm\{m\}', 'm'),
            (r'\\mathrm\{~m\}', 'm'),
            (r'\\mathbf\{m\}', 'm'),
            
            # 常见公式格式修复
            (r'(\d+)\s*\\times\s*', r'\1×'),
            (r'\\left\(([^)]+)\\right\)', r'(\1)'),
        ]
        
        for pattern, replacement in ocr_fixes:
            cleaned_text = re.sub(pattern, replacement, cleaned_text)
        
        # 额外修复：连续空格压缩为单个空格
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        # 修复LaTeX公式中常见的空格问题
        cleaned_text = cleaned_text.replace('$  ', '$').replace('  $', '$')
        cleaned_text = cleaned_text.replace('$$  ', '$$').replace('  $$', '$$')
        
        # 最终清理：去除多余的空格
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        cleaned_text = cleaned_text.strip()

        return cleaned_text

    @staticmethod
    def is_valid_chunk(content: str, min_length: int = 10) -> bool:
        """
        过滤器：丢弃过短或无意义的碎片
        """
        if not content or len(content.strip()) < min_length:
            return False
        
        # 过滤掉只包含标点符号的 Chunk
        if re.match(r'^[\W_]+$', content.strip()):
            return False
            
        return True

# ==========================================
# 单元测试 (Self-Check)
# ==========================================
if __name__ == "__main__":
    # 测试 MinerU 特有的占位符
    test_mineru_text = """
    表 3.0.1 洁净室空气洁净度整数等级
    <table><tr><td>等级</td><td>0.1μm</td></tr><tr><td>1</td><td>10</td></tr></table>
    
    计算公式：
    $C_n = 10^N \\times (0.1/D)^{2.08}$
    
    参考公式 __FORMULA_32__ 和 __FORMULA_33__。
    
    注：粒径范围应为 0.1μm 到 5μm。
    温度要求：20 °C ~ 26 °C
    压力要求：100 Pa ~ 200 Pa
    换气次数：6 m/s ~ 10 m/s
    效率要求：99.9 %
    """
    
    print("=" * 60)
    print("测试 1: MinerU占位符和LaTeX公式处理")
    print("=" * 60)
    print("--- 原始文本 ---")
    print(test_mineru_text)
    
    print("\n--- 清洗后文本 ---")
    result = IngestionUtils.clean_text(test_mineru_text)
    print(result)
    
    print("\n--- 公式问题检查 ---")
    problems = IngestionUtils.check_formula_problems(test_mineru_text)
    print(f"发现问题: {problems}")
    
    # 测试表格转换
    test_html_table = """
    这是一个HTML表格：
    <table>
    <tr><th>等级</th><th>数值</th></tr>
    <tr><td>1</td><td>10</td></tr>
    </table>
    表格结束。
    """
    
    print("\n" + "=" * 60)
    print("测试 2: HTML表格转换")
    print("=" * 60)
    print("清洗前:")
    print(test_html_table)
    print("\n清洗后:")
    print(IngestionUtils.clean_text(test_html_table))
    
    # 测试OCR空格修复
    test_ocr_text = """
    OCR常见问题：
    单位空格：0.1 μ m, 10 μ m, 20 ° C
    数字单位：100 kPa, 50 dB, 6 m/s
    公式空格：$ C_n = 10 ^ {N} \\times ( 0.1 / D ) ^ {2.08} $
    百分比：99.9 %
    科学计数法：1.5 × 10 ^ 3
    """
    
    print("\n" + "=" * 60)
    print("测试 3: OCR空格修复")
    print("=" * 60)
    print("修复前:")
    print(test_ocr_text)
    print("\n修复后:")
    print(IngestionUtils.clean_text(test_ocr_text))
    
    # 测试复杂LaTeX公式
    test_complex_formula = """
    复杂LaTeX公式测试：
    块级公式：
    $$ C_{n} = 10^{N} \\times \\left(\\frac{0.1}{D}\\right)^{2.08} $$
    
    行内公式：$ \\mu m $ 和 $ 0.1 \\mu \\mathrm{m} $
    
    括号公式：\\( C_n = 10^N \\) 和 \\[ C_n = 10^N \\]
    """
    
    print("\n" + "=" * 60)
    print("测试 4: 复杂LaTeX公式处理")
    print("=" * 60)
    print("修复前:")
    print(test_complex_formula)
    print("\n修复后:")
    print(IngestionUtils.clean_text(test_complex_formula))
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)