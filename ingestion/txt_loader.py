# -*- coding: utf-8 -*-
import uuid
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter

class TxtIngestor:
    """
    纯文本解析器 (LangChain 版)
    职责：简单高效地切分 TXT/MD 文件
    """

    def __init__(self):
        # 初始化切分器
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""]
        )

    def process(self, file_path: str) -> list:
        print(f"📄 [TXT] 解析中: {os.path.basename(file_path)}")
        
        try:
            # 1. 读取全文 (尝试 UTF-8 和 GBK)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    full_text = f.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='gbk') as f:
                    full_text = f.read()

            if not full_text.strip():
                return []

            # 2. 智能切分
            docs = self.splitter.create_documents([full_text])
            
            # 3. 封装数据
            chunks_data = []
            file_name = os.path.basename(file_path)
            
            for i, doc in enumerate(docs):
                chunks_data.append({
                    "chunk_id": str(uuid.uuid4()),
                    "content": doc.page_content,
                    "metadata": {
                        "source": file_name,
                        "chunk_index": i,
                        "type": "txt"
                    }
                })
                
            return chunks_data

        except Exception as e:
            print(f"❌ TXT 解析失败: {e}")
            return []