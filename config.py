# -*- coding: utf-8 -*-
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict
from dotenv import load_dotenv

# ==========================================
# 0. 环境初始化
# ==========================================
# 加载 .env 密钥文件
load_dotenv()

# ==========================================
# 1. 全局枚举定义
# ==========================================
class AgentType(Enum):
    """定义系统中四种智能体的唯一标识"""
    RADICAL = "激进派"       # 负责高召回率
    CONSERVATIVE = "保守派"  # 负责高准确率
    ADVERSARIAL = "对抗派"   # 负责逻辑质检
    JUDGE = "大法官"         # 负责最终裁决

# ==========================================
# 2. 系统配置中心 (V3.27 终极版)
# ==========================================
@dataclass
class SystemConfig:
    """
    配置中枢：支持不同智能体使用不同模型 + 大容量上下文
    """

    # --- A. API 访问配置 ---
    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    base_url: str = "https://api.deepseek.com"
    
    # 模型映射字典
    model_map: Dict[AgentType, str] = field(default_factory=lambda: {
        AgentType.RADICAL: "deepseek-chat",
        AgentType.CONSERVATIVE: "deepseek-chat",
        AgentType.ADVERSARIAL: "deepseek-reasoner", # R1
        AgentType.JUDGE: "deepseek-reasoner"        # R1
    })
    
    # 适应 reasoner 的更长推理时间
    timeout_seconds: int = 600

    # --- B. 物理基座路径 ---
    # 使用当前文件所在目录作为项目根目录
    base_dir: str = field(default_factory=lambda: 
        os.getenv("ARCHRAG_BASE_DIR", 
                 os.path.dirname(os.path.abspath(__file__))))
    
    # --- C. 自动生成的子路径 (由 __post_init__ 填充) ---
    prompt_dir: str = field(init=False)
    jsonl_dir: str = field(init=False)
    input_file: str = field(init=False)
    output_file: str = field(init=False)
    graph_dir: str = field(init=False)
    monitor_dir: str = field(init=False)
    chroma_db_path: str = field(init=False)
    bm25_dir: str = field(init=False)
    bm25_index_path: str = field(init=False)
    embedding_model_path: str = field(init=False)
    reranker_model_path: str = field(init=False)
    
    # 宪法路径
    policy_path: str = field(init=False)

    # --- D. 引擎参数控制 ---
    debug_mode: bool = False 
    
    # 默认串行
    max_concurrent_chunks: int = 1
    
    # 大容量上下文记忆 (8000字符)
    max_context_chars: int = 8000
    
    # --- E. 功能开关 ---
    neo4j_export_enabled: bool = True
    enable_monitoring: bool = True

    @property
    def model_name(self) -> str:
        """
        [Fix 1] 提供默认的主模型名称，防止 app.py 报错
        默认返回保守派使用的模型作为系统代表模型
        """
        return self.model_map.get(AgentType.CONSERVATIVE, "deepseek-chat")

    def __post_init__(self):
        """
        初始化后的核心逻辑：路径组装 -> 目录创建 -> 资产安检
        """
        # 1. 物理路径映射
        self.prompt_dir = os.path.join(self.base_dir, "Prompt")
        self.jsonl_dir = os.path.join(self.base_dir, "jsonl")
        
        # 输入源配置
        self.input_file = os.path.join(self.jsonl_dir, "structured_chunks.jsonl")
        self.output_file = os.path.join(self.jsonl_dir, "graph_data_ultimate.jsonl")
        
        self.graph_dir = os.path.join(self.base_dir, "graph")
        self.monitor_dir = os.path.join(self.base_dir, "monitor")
        self.chroma_db_path = os.path.join(self.base_dir, "chroma_db")
        self.bm25_dir = os.path.join(self.base_dir, "bm25")
        self.bm25_index_path = os.path.join(self.bm25_dir, "bm25.pkl")
        
        # 模型文件路径 (注意：这里指向的是包含模型文件的目录)
        self.embedding_model_path = os.path.join(self.base_dir, "models", "bge-large-zh-v1.5")
        self.reranker_model_path = os.path.join(self.base_dir, "models", "bge-reranker-large")
        
        # 宪法文件路径 (尝试自动降级查找)
        self.policy_path = os.path.join(self.base_dir, "Global_HVACR_Ontology_Policy V1.5.0.md")
        
        if not os.path.exists(self.policy_path):
            fallback_policy_path = os.path.join(self.base_dir, "Global_HVACR_Ontology_Policy.md")
            if os.path.exists(fallback_policy_path):
                self.policy_path = fallback_policy_path
                print(f"⚠️  [CONFIG] 使用备用宪法文件: {fallback_policy_path}")

        # 2. [Fix 2] 自动化基建：只创建属于输出/索引的目录
        # 严禁自动创建模型目录，否则 SentenceTransformer 会因为那是空文件夹而报错
        dirs_to_create = [
            self.jsonl_dir, 
            self.graph_dir, 
            self.monitor_dir, 
            self.bm25_dir, 
            self.chroma_db_path
        ]
        
        for folder in dirs_to_create:
            # 双重保险：如果有扩展名，视为文件，不创建目录
            if os.path.splitext(folder)[1]:
                continue
            os.makedirs(folder, exist_ok=True)

        # 3. [Fix 3] 运行模式详细提示 (恢复 V3.19 逻辑)
        if self.debug_mode:
            print(f"🔧 [MODE] 进入调试模式：Batch Size = 1 (串行) + 人类断点")
            self.max_concurrent_chunks = 1
        else:
            if self.max_concurrent_chunks > 1:
                print(f"⚠️  [WARNING] pipeline.py 目前强制串行处理，max_concurrent_chunks={self.max_concurrent_chunks} 仅作标识")
            print(f"🚀 [MODE] 进入生产模式：Batch Size = {self.max_concurrent_chunks}")
        
        # 4. [Fix 4] 显示详细配置摘要 (恢复 V3.19 逻辑)
        print(f"🤖 [MODEL] 智能体模型配置：")
        for agent_type, model_name in self.model_map.items():
            print(f"     - {agent_type.value}: {model_name}")
            
        print(f"📁 [ROOT] 项目根目录锁定在: {self.base_dir}")
        print(f"🧠 [MEMORY] 上下文记忆容量: {self.max_context_chars} 字符")
        print(f"⏱️  [TIMEOUT] API超时时间: {self.timeout_seconds} 秒")

        # 5. 执行安检 (恢复调用)
        self.validate_arsenal()

    def validate_arsenal(self):
        """
        [安检闸机]：深度检查核心资产与API密钥
        分为 Critical (阻断) 和 Warning (提示) 两个级别
        """
        missing_critical = []
        missing_warnings = []
        
        # --- A. 致命错误检查 ---
        # 检查 API 密钥
        if not self.api_key or self.api_key.strip() == "":
            missing_critical.append("🔑 DEEPSEEK_API_KEY (未在 .env 文件中配置)")

        # --- B. 警告级别检查 ---
        # 输入文件缺失仅警告 (允许启动 UI)
        if not os.path.exists(self.input_file):
            missing_warnings.append(f"ℹ️  输入文件未找到: {self.input_file} (ETL提取任务无法运行)")
        
        # Prompt 目录缺失仅警告 (Web UI 不需要)
        if not os.path.exists(self.prompt_dir):
            missing_warnings.append(f"📜 Prompt 模板目录缺失: {self.prompt_dir} (ETL提取任务无法运行)")

        # [Fix 5] 宪法文件缺失检查
        if not os.path.exists(self.policy_path):
            missing_warnings.append(f"⚖️ 宪法文件缺失: {self.policy_path} (提取质量将受影响)")

        # 检查模型目录 (不阻断，因为可能是在线下载)
        if not os.path.exists(self.embedding_model_path):
            missing_warnings.append(f"🧠 Embedding 模型路径不存在: {self.embedding_model_path}")
            
        if not os.path.exists(self.reranker_model_path):
            missing_warnings.append(f"⚖️ Reranker 模型路径不存在: {self.reranker_model_path}")

        # 检查模型名称有效性
        valid_models = ["deepseek-chat", "deepseek-reasoner"]
        for agent_type, model_name in self.model_map.items():
            if model_name not in valid_models:
                missing_warnings.append(f"🤖 {agent_type.value} 配置了未知模型: {model_name}")

        # --- C. 报告输出 ---
        if missing_warnings:
            print("\n" + "-" * 60)
            print("⚠️ [SYSTEM WARNING] 部分非核心组件缺失 (不影响 Web UI 启动)：")
            for item in missing_warnings:
                print(f"   - {item}")
            print("-" * 60 + "\n")

        if missing_critical:
            print("\n" + "!" * 60)
            print("🚫 [CRITICAL ERROR] 系统核心资产缺失，启动终止：")
            for item in missing_critical:
                print(f"   - {item}")
            print("!" * 60 + "\n")
            raise ValueError("系统关键组件缺失，初始化终止。")

    def get_neo4j_config(self):
        """快速获取 Neo4j 配置字典"""
        return {
            "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "user": os.getenv("NEO4J_USER", "neo4j"),
            "pass": os.getenv("NEO4J_PASSWORD", "")
        }
    
    def get_model_for_agent(self, agent_type: AgentType) -> str:
        """获取指定智能体的模型名称"""
        return self.model_map.get(agent_type, "deepseek-chat")