# ArchRAG Enterprise V3.40 文件架构详解

## 📁 项目根目录结构

```
D:\KG_Test\
├── 📄 配置与文档
│   ├── .env                                    # 环境变量配置（API Key、数据库密码）
│   ├── .dockerignore                           # Docker 构建忽略文件
│   ├── config.py                    (9.5K)    # 全局配置中心（SystemConfig 类）
│   ├── requirements.txt             (6.6K)    # Python 依赖清单（172个包）
│   ├── docker-compose.yml           (1.7K)    # 容器编排配置
│   ├── Dockerfile                   (909B)    # 应用镜像构建文件
│   ├── README.md                    (15K)     # 项目说明文档
│   ├── ArchRAG_Architecture.md      (28K)     # 系统架构图文档
│   ├── Global_HVACR_Ontology_Policy V1.5.0.md (8.8K)  # 领域本体定义（最高宪法）
│   └── 操作指令.txt                  (1.2K)    # 常用命令速查表
│
├── 🧠 核心业务层 (core/)
│   ├── __init__.py                  (1.2K)    # 模块导出接口
│   ├── agents.py                    (12K)     # 四大智能体实现
│   │                                           # - BaseAgent（基类）
│   │                                           # - RadicalAgent（激进派 - 高召回）
│   │                                           # - ConservativeAgent（保守派 - 高精度）
│   │                                           # - AdversarialAgent（对抗派 - 冲突检测）
│   │                                           # - JudgeAgent（大法官 - 最终裁决）
│   ├── models.py                    (9.4K)    # Pydantic 数据模型定义
│   │                                           # - Entity（实体）
│   │                                           # - Relation（关系）
│   │                                           # - UnifiedContext（统一上下文）
│   ├── pipeline.py                  (15K)     # 知识提取流水线主控
│   │                                           # - UltimateKnowledgeExtractor 类
│   ├── llm_client.py                (7.5K)    # LLM API 异步客户端
│   │                                           # - 支持 DeepSeek-V3 / DeepSeek-R1
│   │                                           # - 动态 Token 策略
│   ├── prompts.py                   (6.2K)    # Prompt 加载与防爆机制
│   ├── utils.py                     (13K)     # JSON 修复与数据清洗工具
│   │                                           # - repair_json_with_latex()
│   │                                           # - extract_code_block()
│   ├── database.py                  (8.8K)    # 图谱数据导出与全局去重
│   └── monitoring.py                (11K)     # 系统监控与日志管理
│
├── 🔍 RAG 应用服务层 (rag/)
│   ├── __init__.py                  (1.5K)    # 暴露核心类
│   ├── app.py                       (11K)     # Streamlit 前端界面（主入口）
│   │                                           # - 对话历史管理
│   │                                           # - 实时状态监控
│   │                                           # - 证据链展示
│   ├── retriever.py                 (8.7K)    # 混合检索器（三位一体）
│   │                                           # - HybridRetriever 类
│   │                                           # - 向量 + BM25 + 图谱并行检索
│   ├── rewriter.py                  (8.1K)    # 多轮对话查询改写器
│   │                                           # - QueryRewriter 类
│   │                                           # - 34 项指代词审计
│   ├── generator.py                 (6.9K)    # 答案生成器
│   │                                           # - ResponseGenerator 类
│   │                                           # - Prompt 工程 + 引用溯源
│   ├── graph_search.py              (6.6K)    # Neo4j 图谱检索接口
│   │                                           # - GraphRetriever 类
│   │                                           # - Cypher 查询生成
│   ├── reranker.py                  (6.2K)    # BGE 重排序模型接口
│   │                                           # - Reranker 类
│   │                                           # - Cross-Encoder 打分
│   ├── fusion.py                    (4.2K)    # RRF 融合算法
│   │                                           # - reciprocal_rank_fusion()
│   └── indexer.py                   (8.3K)    # 索引构建器
│                                               # - 向量索引（ChromaDB）
│                                               # - BM25 索引（Pickle）
│
├── 📥 文档处理层 (ingestion/)
│   ├── __init__.py                  (0B)      # 空文件（标识为包）
│   ├── processor.py                 (17K)     # 文档处理总调度
│   │                                           # - DocumentProcessor 类
│   │                                           # - 路由分发（PDF/Word/Markdown）
│   ├── pdf_loader_api.py            (6.3K)    # PDF 解析器（MinerU API）
│   │                                           # - PDFIngestor 类
│   ├── docx_loader.py               (4.7K)    # Word 文档解析器（MarkItDown）
│   │                                           # - DocxIngestor 类
│   ├── txt_loader.py                (1.8K)    # 文本切分器
│   │                                           # - TextSplitter 类
│   └── utils.py                     (13K)     # 切分工具与表格保护
│
├── 🛠️ 工具脚本层 (tools/)
│   ├── __init__.py                  (723B)    # 工具函数导出
│   ├── analyze_stats.py             (7.9K)    # 分析 graph_data_ultimate.jsonl 统计
│   ├── auto_import.py               (6.3K)    # 批量导入到 Neo4j
│   ├── clean_failed_checkpoints.py  (4.3K)    # 清理失败的检查点
│   └── fix_data_ids.py              (4.1K)    # 自动补全 chunk_id
│
├── 🎯 提示词库 (Prompt/)
│   ├── 1 激进派 ok.txt                         # 激进派智能体提示词
│   ├── 2 保守派 ok.txt                         # 保守派智能体提示词
│   ├── 3 对抗派 ok.txt                         # 对抗派智能体提示词
│   └── 4 大法官 ok.txt                         # 大法官智能体提示词
│
├── 📊 数据存储层
│   ├── jsonl/                                  # 中间数据存储
│   │   ├── structured_chunks.jsonl             # 文档切片数据（原始）
│   │   ├── structured_chunks.txt               # 文档切片文本版
│   │   └── ingestion_stats.json                # 导入统计信息
│   │
│   ├── graph/                                  # 图谱数据（CSV 格式）
│   │   ├── neo4j_nodes.csv                     # 实体节点表
│   │   └── neo4j_relationships.csv             # 关系边表
│   │
│   ├── chroma_db/                              # 向量数据库存储
│   │   ├── chroma.sqlite3                      # SQLite 数据库文件
│   │   └── [UUID 文件夹]/                      # 向量索引数据
│   │
│   ├── bm25/                                   # BM25 索引存储
│   │   └── bm25.pkl                            # 序列化的倒排索引
│   │
│   ├── models/                                 # 本地模型权重
│   │   ├── bge-large-zh-v1.5/                  # 嵌入模型（768维）
│   │   ├── bge-reranker-large/                 # 重排序模型
│   │   └── MinerU_Models/                      # MinerU 相关模型
│   │
│   ├── neo4j_data/                             # Neo4j 数据持久化
│   │   ├── databases/                          # 图数据库文件
│   │   ├── transactions/                       # 事务日志
│   │   └── logs/                               # Neo4j 日志
│   │
│   └── raw_data/                               # 原始文档存储
│       ├── auto_mineru/                        # MinerU 自动处理
│       ├── auto_vlm/                           # VLM 自动处理
│       └── manual_word/                        # 手动 Word 文档
│
├── 📝 日志与监控
│   ├── monitor/                                # 系统监控日志
│   │   ├── monitor.log                         # 主日志文件
│   │   ├── debug_*.txt                         # 调试模式输出
│   │   └── agent_stats.json                    # 智能体性能统计
│   │
│   └── logs/                                   # 应用日志
│       └── [各类运行日志]
│
├── 🧪 测试与微调数据
│   ├── fine_tuning_data/                       # 微调数据集
│   │   ├── final_clean_sft_v2.jsonl            # 清洗后的 SFT 数据
│   │   └── sft_train_data.jsonl                # 训练数据
│   │
│   ├── table_full_coverage.jsonl               # 表格覆盖测试数据
│   └── ArchRAG_Test_Report_V3.40.xlsx          # 测试报告
│
├── 📚 项目文档 (Project_Context_Master/)
│   ├── Project_Context_Master V1.0.md          # 项目上下文 V1.0
│   ├── Project_Context_Master V1.1.md          # 项目上下文 V1.1
│   ├── Project_Context_Master V1.2.md          # 项目上下文 V1.2
│   ├── Project_Context_Master V1.3.md          # 项目上下文 V1.3
│   ├── Project_Context_Master V1.4.md          # 项目上下文 V1.4
│   └── Project_Context_Master V1.5.md          # 项目上下文 V1.5（最新）
│
├── 🚀 主程序入口
│   ├── main_pipeline.py             (4.3K)    # 离线知识提取入口
│   ├── main_rag.py                  (959B)    # 在线 RAG 服务入口
│   ├── import_graph.py              (11K)     # 图谱数据导入脚本
│   ├── batch_test.py                (8.9K)    # 批量测试脚本
│   ├── data_refine.py               (8.6K)    # 数据精炼工具
│   ├── clean_jsonl.py               (1.5K)    # JSONL 清理工具
│   └── table_booster.py             (4.6K)    # 表格数据增强
│
└── 🐍 Python 虚拟环境
    └── test/                                   # 虚拟环境目录
        ├── Scripts/                            # 可执行文件
        ├── Lib/                                # 依赖库
        └── pyvenv.cfg                          # 环境配置
```

---

## 📊 文件统计信息

### 代码规模统计

| 模块 | 文件数 | 总代码量 | 平均文件大小 |
|------|--------|----------|-------------|
| core/ | 9 | ~83KB | ~9.2KB |
| rag/ | 9 | ~62KB | ~6.9KB |
| ingestion/ | 6 | ~43KB | ~7.2KB |
| tools/ | 5 | ~23KB | ~4.6KB |
| 根目录脚本 | 8 | ~50KB | ~6.3KB |
| **总计** | **37** | **~261KB** | **~7.1KB** |

### 数据文件统计

| 类型 | 位置 | 说明 |
|------|------|------|
| 文档切片 | jsonl/structured_chunks.jsonl | 原始文档切分结果 |
| 知识提取 | jsonl/graph_data_ultimate.jsonl | 四智能体提取结果 |
| 图谱节点 | graph/neo4j_nodes.csv | 实体节点表 |
| 图谱关系 | graph/neo4j_relationships.csv | 关系边表 |
| 向量索引 | chroma_db/ | ChromaDB 数据库 |
| BM25 索引 | bm25/bm25.pkl | 倒排索引文件 |

---

## 🔑 核心文件详解

### 1. 配置文件

#### config.py (9.5K)
```python
class SystemConfig:
    """全局配置中心"""
    - base_dir: 项目根目录
    - api_key: DeepSeek API Key
    - model_name: 默认模型名称
    - neo4j_uri/user/password: 图数据库连接
    - embedding_model_path: 嵌入模型路径
    - reranker_model_path: 重排序模型路径
    - chunk_size/overlap: 文档切分参数
    - top_k: 检索数量
    - timeout_seconds: 超时设置
```

#### .env
```bash
# Neo4j 配置
NEO4J_URI=bolt://neo4j-db:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j

# LLM 配置
DEEPSEEK_API_KEY=sk-your-key
```

### 2. 核心业务模块

#### core/agents.py (12K)
四大智能体实现：
- **RadicalAgent**: 高召回率，提取尽可能多的知识
- **ConservativeAgent**: 高精度，过滤低置信度结果
- **AdversarialAgent**: 冲突检测，发现矛盾和不一致
- **JudgeAgent**: 最终裁决，融合多方意见

#### core/pipeline.py (15K)
知识提取流水线：
```python
class UltimateKnowledgeExtractor:
    def process_chunk(chunk) -> dict:
        """单个切片的四智能体协作提取"""
        1. 激进派提取
        2. 保守派过滤
        3. 对抗派审计
        4. 大法官裁决
        5. 返回最终结果
```

#### core/models.py (9.4K)
数据模型定义：
```python
class Entity(BaseModel):
    """实体模型"""
    name: str
    type: str
    properties: Dict

class Relation(BaseModel):
    """关系模型"""
    source: str
    target: str
    relation_type: str
    properties: Dict

class UnifiedContext(BaseModel):
    """统一上下文模型"""
    content: str
    source: str
    score: float
```

### 3. RAG 服务模块

#### rag/app.py (11K)
Streamlit 前端主程序：
- 对话历史管理
- 实时状态监控
- 证据链展示
- 用户交互界面

#### rag/retriever.py (8.7K)
混合检索器：
```python
class HybridRetriever:
    def search(query, top_k) -> List[UnifiedContext]:
        """三路并行检索 + RRF 融合 + 重排序"""
        1. 向量检索（ChromaDB）
        2. BM25 检索（关键词）
        3. 图谱检索（Neo4j）
        4. RRF 融合
        5. BGE 重排序
        6. 返回 Top-K
```

#### rag/rewriter.py (8.1K)
查询改写器：
```python
class QueryRewriter:
    def rewrite_sync(query, history) -> str:
        """多轮对话指代消解"""
        1. 回溯历史上下文
        2. LLM 改写
        3. 34 项指代词审计
        4. 智能回退
```

### 4. 文档处理模块

#### ingestion/processor.py (17K)
文档处理总调度：
```python
class DocumentProcessor:
    def process_document(file_path) -> List[dict]:
        """路由分发 + 上下文感知切分"""
        1. 识别文件类型（PDF/Word/Markdown）
        2. 调用对应 Loader
        3. 上下文感知切分
        4. 生成 structured_chunks.jsonl
```

---

## 🔄 数据流转路径

### 离线流程
```
raw_data/
  ↓ (ingestion/processor.py)
jsonl/structured_chunks.jsonl
  ↓ (core/pipeline.py)
jsonl/graph_data_ultimate.jsonl
  ↓ (core/database.py)
graph/neo4j_nodes.csv + neo4j_relationships.csv
  ↓ (import_graph.py)
neo4j_data/ (Neo4j Database)

jsonl/structured_chunks.jsonl
  ↓ (rag/indexer.py)
chroma_db/ + bm25/bm25.pkl
```

### 在线流程
```
用户提问 (rag/app.py)
  ↓
查询改写 (rag/rewriter.py)
  ↓
混合检索 (rag/retriever.py)
  ├─ chroma_db/ (向量检索)
  ├─ bm25/bm25.pkl (BM25 检索)
  └─ neo4j_data/ (图谱检索)
  ↓
重排序 (rag/reranker.py)
  ↓
答案生成 (rag/generator.py)
  ↓
返回用户 (rag/app.py)
```

---

## 🎯 关键路径说明

### 启动路径

1. **离线知识提取**
   ```bash
   python main_pipeline.py
   ```
   执行流程：
   - 加载 config.py 配置
   - 调用 ingestion/processor.py 处理文档
   - 调用 core/pipeline.py 提取知识
   - 调用 core/database.py 导出 CSV
   - 生成 graph/neo4j_nodes.csv 和 neo4j_relationships.csv

2. **图谱数据导入**
   ```bash
   python import_graph.py
   ```
   或 Docker 模式：
   ```bash
   docker exec -it archrag-core python import_graph.py
   ```

3. **索引构建**
   ```bash
   python rag/indexer.py
   ```
   生成：
   - chroma_db/ (向量索引)
   - bm25/bm25.pkl (BM25 索引)

4. **启动 RAG 服务**
   ```bash
   streamlit run rag/app.py
   ```
   或：
   ```bash
   python main_rag.py
   ```

### 依赖关系

```
config.py (全局配置)
    ↓
core/ (核心引擎)
    ↓
ingestion/ (文档处理) → jsonl/
    ↓
core/pipeline.py (知识提取) → jsonl/
    ↓
core/database.py (导出) → graph/
    ↓
import_graph.py (导入) → neo4j_data/
    ↓
rag/indexer.py (索引) → chroma_db/ + bm25/
    ↓
rag/ (RAG 服务)
    ↓
rag/app.py (前端界面)
```

---

## 📦 Docker 部署结构

```
docker-compose.yml
├── archrag-app (应用容器)
│   ├── Dockerfile
│   ├── 挂载: ./rag → /app/rag
│   ├── 挂载: ./core → /app/core
│   ├── 挂载: ./models → /app/models
│   ├── 挂载: ./chroma_db → /app/chroma_db
│   └── 端口: 8501
│
└── neo4j-db (数据库容器)
    ├── 镜像: neo4j:5.x
    ├── 挂载: ./neo4j_data → /data
    ├── 挂载: ./graph → /import
    └── 端口: 7687 (Bolt), 7474 (HTTP)
```

---

## 💡 文件命名规范

### Python 模块
- **小写 + 下划线**: `llm_client.py`, `graph_search.py`
- **类名大驼峰**: `QueryRewriter`, `HybridRetriever`
- **函数名小写**: `rewrite_sync()`, `search()`

### 数据文件
- **JSONL 格式**: `structured_chunks.jsonl`, `graph_data_ultimate.jsonl`
- **CSV 格式**: `neo4j_nodes.csv`, `neo4j_relationships.csv`
- **序列化文件**: `bm25.pkl`

### 配置文件
- **环境变量**: `.env`
- **Docker**: `docker-compose.yml`, `Dockerfile`
- **Python 配置**: `config.py`

---

## 🔍 快速定位指南

| 需求 | 文件位置 |
|------|---------|
| 修改 API Key | `.env` 或 `config.py` |
| 调整检索参数 | `config.py` (top_k, chunk_size) |
| 修改提示词 | `Prompt/` 目录下的 txt 文件 |
| 查看日志 | `monitor/monitor.log` |
| 修改前端界面 | `rag/app.py` |
| 调整检索策略 | `rag/retriever.py` |
| 修改智能体逻辑 | `core/agents.py` |
| 调整文档切分 | `ingestion/processor.py` |
| 查看测试报告 | `ArchRAG_Test_Report_V3.40.xlsx` |

---

## 📈 代码质量指标

- **模块化程度**: ⭐⭐⭐⭐⭐ (高度模块化，职责清晰)
- **可维护性**: ⭐⭐⭐⭐⭐ (良好的注释和文档)
- **可扩展性**: ⭐⭐⭐⭐⭐ (插件化设计，易于扩展)
- **代码规范**: ⭐⭐⭐⭐☆ (遵循 PEP 8，部分中文注释)
- **测试覆盖**: ⭐⭐⭐☆☆ (有测试脚本，但覆盖不全)

---

## 🎓 学习路径建议

1. **入门**: 阅读 `README.md` 和 `ArchRAG_Architecture.md`
2. **配置**: 理解 `config.py` 和 `.env`
3. **数据流**: 跟踪 `main_pipeline.py` → `core/pipeline.py` → `core/database.py`
4. **检索流**: 跟踪 `rag/app.py` → `rag/retriever.py` → `rag/generator.py`
5. **深入**: 研究 `core/agents.py` 的四智能体协作机制
6. **优化**: 调整 `Prompt/` 目录下的提示词
