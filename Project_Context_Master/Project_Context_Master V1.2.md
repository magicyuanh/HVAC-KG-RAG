### 📋 文件名：Project_Context_Master V1.2.md

```markdown
## 0. 头部元数据 (Header Metadata) 
# 🛡️ SYSTEM MANIFEST: ArchRAG (暖通智脑)
# ==============================================================================
# 📅 Last Sync:       2026-01-18 01:00 (GMT+8)
# 👤 Operator:        Commander (ENTJ / Solution Architect)
# 🎯 System Phase:    Engineering Debugging (Ingestion & Extraction Layer)
# 🛠️ Tech Stack:      Python 3.10 | Neo4j 5.x | LangChain | DeepSeek-V3
# ⚠️ Core Protocol:   NO Fluff | First Principles | Strict Error Handling | SSOT
# ==============================================================================

## 1. 当前核心指令 (The Prime Directive)

### 1.1 唯一战术目标 (Unique Tactical Objective)
**主要任务：** 彻底修复 "Ingestion & Extraction" 阶段的工程鲁棒性问题，彻底修复 **Bug C: 保守派全 1.0 置信度** 。
**预期结果：** 能够让 14 个 Chunks 的暖通规范切片，在 pipeline 中连续运行，无 `JSONDecodeError`，无 `FinishReason: Length` 报错。

### 1.2 负向约束 (Scope Fencing - DO NOT TOUCH)
*   ⛔ **NO RAG Optimization:** 严禁尝试优化向量检索（Chroma）或图谱检索（Cypher）的准确率，现在不是时候。
*   ⛔ **NO UI/Frontend:** 不需要任何 Streamlit 或 Web 界面代码。
*   ⛔ **NO Architecture Refactor:** 除非现有架构导致了致命 Bug，否则不要建议重写 `agents.py` 的类结构。

### 1.3 完成标准 (Definition of Done)
1.  `utils.py` 中必须包含一个强鲁棒性的 `repair_json_with_latex` 函数。
2.  即使对抗派（Adversarial）输出了乱码，Pipeline 也不能 Crash，必须有 Fallback（降级）机制。
3.  保守派输出不能全为 1.0。必须呈现分级差异（0.6~1.0），且代码层必须包含 `_validate_confidence` 验证逻辑。
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


### 3.2 核心架构决策 (Architectural Decisions)
*   **串行优先 (Sequential over Parallel):** Pipeline 必须保持串行（Batch Size 可调整，但 Chunk 间必须有顺序）。因为我们需要在 Chunk 之间传递 `{previous_context}` 记忆对象。**严禁建议改为全异步并发。**
*   **记忆传递:** 上下文记忆机制（Context Memory）是解决跨页表格和代词指代的关键，必须保留。

### 3.3 业务逻辑宪法 (Business Logic Constraints)
*   **Schema 权威:** `Global_HVACR_Ontology_Policy.md` 定义的 13 种实体类型和 13x13 关系矩阵是绝对标准。**严禁发明新的 Node Label 或 Relationship Type。**
*   **数值降级:** 任何纯数值（如 `3000`, `50`, `0.5`）或仅包含“数值+单位”的文本，**严禁**被创建为独立节点（Node）。它们必须被处理为关系的**属性 (Property)** 或挂载在 Parameter 实体下。

# ==============================================================================

## 4. 正在解决的 P0 级 Bug (Active Battlefront)
*AI 注意：本章节包含当前阻塞系统的致命错误，请优先分析报错信息（Traceback）和复现数据。*

### 🔴 Bug C: 保守派全 1.0 置信度
*   **Location:** `core/agents.py` -> `ConservativeAgent` / `Prompt/2 保守派.txt`
*   **Symptom:** 
    *   保守派输出的 JSON 中，所有实体和关系的 `confidence` 字段均为 `1.0`。
    *   导致大法官无法通过加权平均区分“原文铁证”和“模型推测”，高质量数据被淹没。
*   **Root Cause:** 
    1.  **Prompt 缺位**: `2 保守派.txt` 中缺乏置信度分级标准，模型倾向于过度自信。
    2.  **参数噪音**: `temperature=0.1` 仍有一定随机性。
    3.  **验证缺失**: 输出后没有任何代码层去校验“给 1.0 分的理由是否充分”。
*   **Requirement:** 
    1.  **Prompt 强制分级**: 在 `2 保守派.txt` 中植入详细的置信度查表法（1.0-0.6），严禁全盘赋值 1.0。
    2.  **代码零温设置**: 将 `ConservativeAgent` 的 `temperature` 强制设为 `0.0`。
    3.  **后置验证逻辑**: 在 `agents.py` 的 `ConservativeAgent.extract()` 方法中增加 `_validate_confidence()`，检测无依据的 1.0 并自动降级。


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
**角色设定：** 你现在是 ArchRAG 项目的 **首席 Python 架构师**。
**任务目标：** 解决 Section 4 中列出的 **Bug C: 保守派全 1.0 置信度** 。

请按照以下顺序执行，**一次只解决一个问题**，待我确认后再进行下一个：

### 🏁 任务三：修复保守派置信度体系
1.  **分析**: 查看 Section 4 - Bug C。全是 1.0 是因为缺乏分级规则和验证。
2.  **执行**:
    *   **任务 3.1 (优先)**: 修改 `Prompt/2 保守派.txt`。植入“置信度分级表”（例如：强制条款 1.0，推荐 0.9，数值 0.8）。
    *   **任务 3.2 (代码)**: 修改 `core/agents.py`。修改 `ConservativeAgent` 温度，并增加 `_validate_confidence` 后处理方法。
3.  **输出**: 提供修改后的 `Prompt` 和 `agents.py` 代码片段。


# ==============================================================================

*End of State Document*
```