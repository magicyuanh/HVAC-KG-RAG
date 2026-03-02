### 📋 文件名：Project_Context_Master V1.4.md

```markdown
## 0. 头部元数据 (Header Metadata) 
# 🛡️ SYSTEM MANIFEST: ArchRAG (暖通智脑)
# ==============================================================================
# 📅 Last Sync:       2026-01-20 01:00 (GMT+8)
# 👤 Operator:        Commander (ENTJ / Solution Architect)
# 🎯 System Phase:    Engineering Debugging (Ingestion & Extraction Layer)
# 🛠️ Tech Stack:      Python 3.10 | Neo4j 5.x | LangChain | DeepSeek-V3
# ⚠️ Core Protocol:   NO Fluff | First Principles | Strict Error Handling | SSOT
# ==============================================================================

## 1. 当前核心指令 (The Prime Directive)

### 1.1 唯一战术目标 (Unique Tactical Objective)
**主要任务：** P0 级工程鲁棒性修复**全部完成**。
**预期结果：** Pipeline 已通过冒烟测试，具备生产环境运行能力。

### 1.2 负向约束 (Scope Fencing - DO NOT TOUCH)
*   ⛔ **NO RAG Optimization:** 严禁尝试优化向量检索（Chroma）或图谱检索（Cypher）的准确率，现在不是时候。
*   ⛔ **NO UI/Frontend:** 不需要任何 Streamlit 或 Web 界面代码。
*   ⛔ **NO Architecture Refactor:** 除非现有架构导致了致命 Bug，否则不要建议重写 `agents.py` 的类结构。

### 1.3 完成标准
1.  **鲁棒性**: `utils.py` 必须包含三层防御机制 (`extract_json`)，即使在输入包含 LaTeX 符号或 Markdown 混杂时，Pipeline 也不会因 `JSONDecodeError` 崩溃。
2.  **完整性**: `llm_client.py` 必须对 `DeepSeek-Reasoner` 设置 `max_tokens=8192`；`4 大法官.txt` 必须强制使用 `<thought>` 标签外置思维链，确保 JSON 输出不被截断。
3.  **准确性**: `agents.py` 中 `ConservativeAgent` 必须设置 `temperature=0.0`，并实现 `_validate_confidence()` 后置验证，严禁输出全 1.0 的无效置信度。
4.  **性能**: `database.py` 导出的 `neo4j_nodes.csv` 中严禁包含 `Value` 类型的孤立节点；数值数据必须被转换为关系的属性 (`value:float`, `unit:string`)，杜绝图爆炸。
5.  **一致性**: `utils.py` 必须包含 `EntityNormalizer` 类，所有 Prompt 必须包含命名规范（禁括号、强制大写缩写），确保 `AHU` 和 `ahu` 被正确归并为同一实体。

# ==============================================================================

## 2. 系统架构快照 (Architecture Snapshot)

### 2.1 核心技术栈 (Tech Stack)
- **Language:** Python 3.10 (Strict Type Hinting)
- **LLM Engine:** 
  - *Logic:* DeepSeek-V3 (Chat) for extraction.
  - *Reasoning:* DeepSeek-R1 (Reasoner) for auditing & judging.
- **Database:** 
  - *Graph:* Neo4j Community 5.x (Cypher)
  - *Vector:* ChromaDB (Local persistence)
- **Key Libs:** LangChain, Pydantic v2, Neo4j Driver, Pandas.

### 2.2 数据流水线 (The Pipeline)
`[Source: PDF/Docx]` --> `[Ingestion: MinerU/MarkItDown]` --> `[Artifact: Markdown]` 
--> `[Chunking: Context-Aware Splitter]` 
--> `[Extraction: 4-Agent Multi-Turn Loop]` 
    ├── 1. Radical (Recall++)
    ├── 2. Conservative (Precision++)
    ├── 3. Adversarial (Audit & Conflict Detect)
    └── 4. Judge (Final Fusion & Schema Check)
--> `[Storage: Neo4j Graph DB]`

### 2.3 关键文件目录 (File Directory)
```text
D:\KG_Test\
├── core\                      # 核心业务逻辑
│   ├── pipeline.py            # 主控流程 (Sequential Processing)
│   ├── agents.py              # 四大智能体实现类
│   ├── utils.py               # 清洗与JSON修复工具 (★重点调试区)
│   ├── models.py              # Pydantic数据模型定义 (Schema)
│   ├── config.py              # 路径与环境配置
│   └── llm_client.py          # LLM API 封装
├── Prompt\                    # 提示词仓库 (txt格式)
│   ├── 1 激进派.txt
│   ├── 2 保守派.txt
│   ├── 3 对抗派.txt
│   └── 4 大法官.txt
├── jsonl\                     # 中间数据存储
│   └── structured_chunks.jsonl
└── Global_HVACR_Ontology_Policy.md  # SSOT (最高宪法/本体定义)
```
# ==============================================================================

## 3. 已确定的事实 (Immutable Truths)
*AI 注意：以下内容代表项目中的“已解决状态”或“最高准则”，在生成代码时必须无条件遵守，严禁尝试修改或回滚。*

### 3.1 已修复的代码 (Stable Codebase)
*   **Ingestion 路由:** `processor.py` 已重构完成。`.md` 文件现在复用 `DocxIngestor` 的切分逻辑（防止表格被切碎），此逻辑已验证通过，**不许修改**。
*   **路径配置:** `config.py` 中的 `base_dir` 已修正为 `os.path.dirname` 动态获取，路径问题已解决。
*   **PDF/Word 引擎:** `pdf_loader_api.py` (MinerU) 和 `docx_loader.py` (MarkItDown) 接口已统一，运行稳定。
*   **JSON 解析器:** 已修复。引入 `json_repair`，实现了“提取-修复-兜底”三层机制。针对 LaTeX 符号和 Markdown 混杂导致的解析崩溃问题已彻底消除 (P0 #1 完成)。

*   **大法官输出截断:** 已修复 (P0 #2 完成)。
    *   通过 `<thought>` 标签外置思维链，实现了推理与数据的物理隔离。
    *   `llm_client.py` 实现了动态 Token 策略 (reasoner=8192, chat=4096)。
    *   配合 `utils.py` 的代码块提取机制，彻底解决了 DeepSeek-R1 的截断问题。

*   **保守派置信度体系:** 已修复 (P0 #3 完成)。
    *   在 `2 保守派.txt` 中植入了置信度分级标准（强制/推荐/数值/推断）。
    *   `agents.py` 中 `ConservativeAgent` 实现了温度强制 0.0 和 `_validate_confidence()` 后置验证逻辑。
    *   即使 LLM 试图全盘输出 1.0，代码层也会强制纠错至 0.9 或更低。

*   **数值节点图爆炸:** 已修复 (P0 #4 完成)。
    *   `models.py` 中 `Relation` 实现了数值属性化逻辑（`properties` 字段 + 自引用转换）。
    *   `database.py` 实现了 Value 节点拦截机制，将数值数据压平为关系属性。
    *   彻底消除了 Value 节点导致的图谱膨胀和语义混乱问题。

*   **实体命名规范:** 已修复 (P0 #5 完成)。
    *   引入 `EntityNormalizer` 类，实现去括号、缩写大写和同义词映射逻辑。
    *   所有 Agent Prompt 已植入命名约束（禁括号、强一致）。
    *   彻底解决了“洁净室（区）”和“ahu/AHU”导致的实体碎片化问题。

### 3.2 核心架构决策 (Architectural Decisions)
*   **串行优先 (Sequential over Parallel):** Pipeline 必须保持串行（Batch Size 可调整，但 Chunk 间必须有顺序）。因为我们需要在 Chunk 之间传递 `{previous_context}` 记忆对象。**严禁建议改为全异步并发。**
*   **记忆传递:** 上下文记忆机制（Context Memory）是解决跨页表格和代词指代的关键，必须保留。

### 3.3 业务逻辑宪法 (Business Logic Constraints)
*   **Schema 权威:** `Global_HVACR_Ontology_Policy.md` 定义的 13 种实体类型和 13x13 关系矩阵是绝对标准。**严禁发明新的 Node Label 或 Relationship Type。**
*   **数值降级:** 任何纯数值（如 `3000`, `50`, `0.5`）或仅包含“数值+单位”的文本，**严禁**被创建为独立节点（Node）。它们必须被处理为关系的**属性 (Property)** 或挂载在 Parameter 实体下。

# ==============================================================================

## 4. 正在解决的 P0 级 Bug (Active Battlefront)
*AI 注意：本章节包含当前阻塞系统的致命错误，请优先分析报错信息（Traceback）和复现数据。*


# ==============================================================================

## 5. 失败尝试记录 (Memory Bank of Failed Attempts)
*AI 注意：以下方案已被验证无效，为了节省 Token 和时间，严禁再次建议使用这些方法。请寻找 Plan B/C。*

### 5.1 关于 JSON 修复 (JSON Repair)
- ❌ **尝试 1:** 仅在 Prompt 中添加 "You must return valid JSON" 指令。
  - **结果:** 失败。DeepSeek-Reasoning 在处理复杂 LaTeX 公式（如 `\mu`, `\sim`）时，依然会输出未转义的字符，导致解析崩溃。Prompt 约束力不足。
- ❌ **尝试 2:** 使用 Python 原生 `re` 模块提取 `{...}`。
  - **结果:** 失败。当 JSON 内部嵌套花括号（如 `{ "key": "{ value }" }`）或包含多行文本时，简单的正则表达式无法正确匹配闭合括号。
- ❌ **尝试 3:** 使用 `json.loads(text, strict=False)`。
  - **结果:** 失败。Python 的标准 JSON 库对格式容忍度极低，无法处理 LLM 常见的 "Trailing Commas"（尾部逗号）或单引号问题。

### 5.2 关于 Agent 流程 (Agent Workflow)
- ❌ **尝试 4:** 让大法官（Judge）一次性接收激进派（Radical）的所有提取结果。
  - **结果:** 失败。上下文（Context）过长，导致大法官出现“注意力丢失”，忽略了表格中的关键数据，且更容易触发 Token 截断。
  - **结论:** 必须采用“冲突集（Conflict Set）”输入模式，只让大法官裁决有争议的部分。

### 5.3 关于 Neo4j 写入
- ❌ **尝试 5:** 让 LLM 直接生成 Cypher 语句 (CREATE ...)。
  - **结果:** 失败。LLM 生成的 Cypher 经常包含语法错误或特殊字符转义错误，导致数据库写入中断。
  - **结论:** 必须让 LLM 输出结构化数据 (JSON/CSV)，然后由 Python 代码（Driver）负责生成和执行 Cypher。

# ==============================================================================

## 6. 下一步战术指令 (Next Tactical Orders)
**角色设定：** 你现在是 ArchRAG 项目的 **最终验收官**。
**阶段状态：** P0 级工程鲁棒性修复阶段 **全数完成**。
**目标：** 执行全量 Dataset 测试，验证 V1.5 代码库的生产就绪状态。

### 🏁 任务五：全量实战验收测试
1.  **分析**: 当前已无 Active Bug (Section 4 为空)。所有核心防御机制（JSON 修复、Token 策略、置信度验证、属性化图谱、实体清洗）已就位。
2.  **执行**:
    *   **任务 5.1 (全量运行)**: 在项目根目录运行 `main_pipeline.py`（或 `python main.py`）。使用完整的 14 个暖通规范 Chunks 进行提取。
    *   **任务 5.2 (产出检查)**: 检查 `core/graph/` 目录下的 CSV 文件。
        *   确认 `neo4j_nodes.csv` 中没有 `Value` 节点。
        *   确认 `neo4j_relationships.csv` 中包含 `value:float` 列。
        *   确认实体名称列中没有括号（如 `洁净室（区）`）或大小写混杂（如 `ahu`）。
    *   **任务 5.3 (数据导入)**: 使用 `neo4j-admin` 或 Cypher Shell 导入 CSV，验证无语法错误。
3.  **输出**: 
    *   如果运行成功，请回复：**"Mission Accomplished. ArchRAG Kernel V3.18 Ready for Deployment."**
    *   如果运行中出现任何异常，请提供 Traceback。

# ==============================================================================

*End of State Document*
```