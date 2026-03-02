# HVAC-KG-RAG | HVAC Knowledge Graph RAG System

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python) ![Neo4j](https://img.shields.io/badge/Neo4j-5.x-008CC1?logo=neo4j) ![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker) ![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-green) ![License](https://img.shields.io/badge/License-MIT-yellow) ![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit)

**HVAC-KG-RAG** 是一款专为 **暖通行业**设计的工业级混合检索增强生成系统（Hybrid RAG）。

系统突破了传统 RAG 仅依赖向量检索的局限，通过融合**知识图谱（Knowledge Graph）**、**多智能体协作提取**和**多轮对话指代消解**，实现对工业复杂逻辑链的高精度检索与推理。

---

## ✨ 核心特性

- **三流并行混合检索**：向量检索（ChromaDB + BGE）、关键词检索（BM25）、图谱检索（Neo4j Cypher）三路并行，RRF 融合后经 BGE-Reranker 重排序
- **四智能体知识提取**：激进派（高召回）→ 保守派（高精度）→ 对抗派（冲突检测）→ 大法官（最终裁决），自动构建结构化知识图谱
- **多轮对话指代消解**：内置 34 项指代词审计，自动将"它的功率"还原为"AHU-01 的功率"，防止检索漂移
- **生产级鲁棒性**：图数据库离线时自动降级为纯文档模式；防长文本攻击；异步安全
- **全容器化部署**：Docker Compose 一键启动，环境完全隔离

---

## 🏗️ 系统架构

```text
┌──────────────────────────────────────────────────────────────┐
│                     用户交互层 (Streamlit UI)                   │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────┴───────────────────────────────┐
│                   应用服务层 (RAG Service)                    │
│                                                              │
│  Query Rewriter ──▶ Hybrid Retriever ──▶ Response Generator │
│  (指代消解)              │                   (DeepSeek)       │
│                  ┌───────┼───────┐                           │
│                  ▼       ▼       ▼                           │
│              Vector    BM25   Graph                          │
│              Search   Search  Search                         │
│                  └───────┼───────┘                           │
│                          ▼                                   │
│                    BGE Reranker                              │
└──────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────┴───────────────────────────────┐
│                   数据存储层 (Storage)                        │
│     ChromaDB (向量)   BM25 Index (倒排)   Neo4j (知识图谱)     │
└──────────────────────────────────────────────────────────────┘
```

**离线知识提取流程：**

```text
PDF/Word/Markdown
       │
  文档切分器 (Context-Aware Splitter)
       │
  structured_chunks.jsonl
       │
  四智能体协作提取 (激进派 → 保守派 → 对抗派 → 大法官)
       │
  graph_data_ultimate.jsonl
       │
  ┌────┴────┐
Neo4j     Vector + BM25
(图谱导入)  (索引构建)
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
| --- | --- |
| **前端** | Streamlit 1.52+ |
| **LLM** | DeepSeek-V3 (Chat) + DeepSeek-R1 (Reasoner) |
| **Embedding** | BGE-Large-zh-v1.5（768维） |
| **Reranker** | BGE-Reranker-Large（Cross-Encoder） |
| **向量数据库** | ChromaDB 1.4+ |
| **图数据库** | Neo4j 5.x |
| **稀疏检索** | Rank-BM25 + Jieba |
| **基础设施** | Docker Compose + NVIDIA GPU |

---

## 🚀 快速部署

### 1. 克隆仓库

```bash
git clone https://github.com/magicyuanh/HVAC-KG-RAG.git
cd HVAC-KG-RAG
```

### 2. 下载模型文件

将以下模型放入 `models/` 目录（不含于仓库，需手动下载）：

- `models/bge-large-zh-v1.5/`（[ModelScope](https://modelscope.cn/models/BAAI/bge-large-zh-v1.5)）
- `models/bge-reranker-large/`（[ModelScope](https://modelscope.cn/models/BAAI/bge-reranker-large)）

### 3. 配置环境变量

```bash
cp .env.example .env
```

```env
NEO4J_URI=bolt://neo4j-db:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
DEEPSEEK_API_KEY=sk-your_key
```

### 4. 启动服务

```bash
docker-compose --env-file .env up -d --build
```

### 5. 初始化知识图谱

```bash
docker exec -it archrag-core python import_graph.py
```

### 6. 访问系统

打开浏览器：[http://localhost:8501](http://localhost:8501)

---

## 📂 项目结构

```text
HVAC-KG-RAG/
├── config.py                   # 全局配置中心
├── main_pipeline.py            # 离线知识提取入口
├── main_rag.py                 # 在线 RAG 服务入口
├── import_graph.py             # 图谱数据导入脚本
├── Dockerfile / docker-compose.yml
├── requirements.txt
│
├── core/                       # 知识提取引擎
│   ├── agents.py               # 四智能体逻辑
│   ├── pipeline.py             # 流水线调度
│   ├── llm_client.py           # 异步 LLM 通信
│   └── ...
│
├── rag/                        # RAG 检索生成服务
│   ├── app.py                  # Streamlit 界面
│   ├── retriever.py            # 混合检索器
│   ├── rewriter.py             # 查询改写器
│   ├── reranker.py             # 重排序模块
│   ├── generator.py            # 答案生成器
│   └── ...
│
├── ingestion/                  # 文档处理层
│   ├── pdf_loader_api.py       # MinerU PDF 解析
│   ├── docx_loader.py          # Word 解析
│   └── ...
│
├── tools/                      # 辅助工具脚本
├── Prompt/                     # 四智能体提示词
└── models/                     # 本地模型（不含于仓库）
```

---

## ⚡ 性能指标

| 阶段 | 延迟 |
| --- | --- |
| 查询改写 | ~1-2s |
| 混合检索（三路并行） | ~300-800ms |
| BGE 重排序 | ~500ms-1s |
| 答案生成（DeepSeek） | ~3-5s |
| **端到端总延迟** | **~5-10s** |

---

## ⚠️ 常见问题

### 1. 启动报 `Connection Refused`

检查 Docker Desktop Proxies 端口是否与 VPN 一致。

### 2. 侧边栏显示"知识图谱：🔴 离线"

运行 `docker-compose ps` 检查 neo4j 容器状态，确认 `.env` 密码无特殊字符。

### 3. 多轮对话指代词未被消解

查看 `rag/rewriter.py` 日志，确认指代残留审计是否触发。

---

## 📄 License

MIT License © 2026 [magicyuanh](https://github.com/magicyuanh)
