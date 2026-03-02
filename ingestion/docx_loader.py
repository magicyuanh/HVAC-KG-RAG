# -*- coding: utf-8 -*-
import uuid
import os
import sys

# 尝试导入 MarkItDown
try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None

# 导入 LangChain 切分器
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

class DocxIngestor:
    """
    Word/Markdown 语义转换器 (The Semantic Crusher) - V3.2 增强版
    
    职责：
    1. 格式转换：Word -> Markdown (保留表格/标题)。
    2. 逻辑切分：基于 Markdown 标题层级进行物理分割。
    3. [V3.2] 极简上下文注入：使用紧凑格式注入父级标题，减少 Token 浪费。
    4. [V3.2] 大粒度切分：增大 Chunk Size 以保护表格完整性。
    """

    def __init__(self):
        if MarkItDown is None:
            raise ImportError("未安装 markitdown，请运行 pip install markitdown")
        
        self.mid = MarkItDown()
        
        # 1. 定义标题切分规则 (逻辑层)
        # 将文档按章节切开，Metadata 中会保留 Header_1, Header_2...
        self.headers_to_split_on = [
            ("#", "Header_1"),
            ("##", "Header_2"),
            ("###", "Header_3"),
        ]
        self.header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=self.headers_to_split_on)
        
        # 2. 定义文本切分规则 (物理层)
        # [战略调整]: chunk_size 提升至 1200，优先保全表格结构
        # 虽然 BGE-Large 最佳窗口是 512 Token，但它支持截断。
        # 宁可截断长文末尾，不可切碎表格中间。
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=150,
            separators=["\n\n", "\n", "。", "！", "；", ""]
        )

    def _inject_context(self, content: str, metadata: dict, file_name: str) -> str:
        """
        [V3.2 核心] 极简上下文注入
        将 "散文体" 改为 "代码体" (Key-Value 风格)
        """
        # 提取标题链
        headers = []
        # 按层级顺序提取
        for h_key in ["Header_1", "Header_2", "Header_3"]:
            if h_key in metadata and metadata[h_key]:
                headers.append(metadata[h_key].strip())
        
        # 拼接路径字符串 (e.g., "6 技术要求 / 6.3 气流流型")
        if headers:
            path_str = " / ".join(headers)
            # 格式: FILE: {name} | SEC: {path}
            context_header = f"FILE: {file_name} | SEC: {path_str}"
        else:
            context_header = f"FILE: {file_name}"
            
        # 焊接
        return f"{context_header}\n{content}"

    def process(self, file_path: str) -> list:
        """
        处理 .docx 文件
        """
        file_name = os.path.basename(file_path)
        print(f"📄 [DOCX] 正在精炼文档: {file_name}")
        
        if not os.path.exists(file_path):
            print("❌ 文件不存在")
            return []

        try:
            # 1. Word -> Markdown
            result = self.mid.convert(file_path)
            if not result or not result.text_content:
                return []
            raw_markdown = result.text_content

            # 2. 复用通用切分逻辑
            return self.process_raw_markdown(raw_markdown, file_name)

        except Exception as e:
            print(f"❌ [DOCX] 处理失败: {e}")
            return []

    def process_raw_markdown(self, markdown_text: str, source_name: str) -> list:
        """
        处理纯 Markdown 文本 (被 PDFLoader 复用)
        """
        # 1. 按标题切分
        header_splits = self.header_splitter.split_text(markdown_text)
        
        # 2. 按长度细分
        # 注意：这里传入的是已经按章节分开的 Document 对象列表
        final_docs = self.text_splitter.split_documents(header_splits)
        
        chunks_data = []
        
        for doc in final_docs:
            # 3. 注入极简上下文
            enriched_content = self._inject_context(doc.page_content, doc.metadata, source_name)
            
            # 4. 封装元数据
            meta = doc.metadata.copy()
            meta["source"] = source_name
            # 标记来源类型，方便后续追踪
            meta["type"] = "docx_refined" if source_name.endswith(".docx") else "pdf_md_refined"
            
            # 修复：将 chunks_data.app 改为 chunks_data.append
            chunk = {
                "content": enriched_content,
                "metadata": meta
            }
            chunks_data.append(chunk)
        
        return chunks_data