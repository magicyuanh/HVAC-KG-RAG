### 📋 文件名：Project_Context_Master V1.0.md

```markdown
## 0. 头部元数据 (Header Metadata) 
# 🛡️ SYSTEM MANIFEST: ArchRAG (暖通智脑)
# ==============================================================================
# 📅 Last Sync:       2026-01-16 03:00 (GMT+8)
# 👤 Operator:        Commander (ENTJ / Solution Architect)
# 🎯 System Phase:    Engineering Debugging (Ingestion & Extraction Layer)
# 🛠️ Tech Stack:      Python 3.10 | Neo4j 5.x | LangChain | DeepSeek-V3
# ⚠️ Core Protocol:   NO Fluff | First Principles | Strict Error Handling | SSOT
# ==============================================================================

## 1. 当前核心指令 (The Prime Directive)

### 1.1 唯一战术目标 (Unique Tactical Objective)
**主要任务：** 彻底修复 "Ingestion & Extraction" 阶段的工程鲁棒性问题，彻底修复 **Bug A: JSON 解析崩溃** 。
**预期结果：** 能够让 14 个 Chunks 的暖通规范切片，在 pipeline 中连续运行，无 `JSONDecodeError`，无 `FinishReason: Length` 报错。

### 1.2 负向约束 (Scope Fencing - DO NOT TOUCH)
*   ⛔ **NO RAG Optimization:** 严禁尝试优化向量检索（Chroma）或图谱检索（Cypher）的准确率，现在不是时候。
*   ⛔ **NO UI/Frontend:** 不需要任何 Streamlit 或 Web 界面代码。
*   ⛔ **NO Architecture Refactor:** 除非现有架构导致了致命 Bug，否则不要建议重写 `agents.py` 的类结构。

### 1.3 完成标准 (Definition of Done)
1.  `utils.py` 中必须包含一个强鲁棒性的 `repair_json_with_latex` 函数。
2.  即使对抗派（Adversarial）输出了乱码，Pipeline 也不能 Crash，必须有 Fallback（降级）机制。
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

### 3.2 核心架构决策 (Architectural Decisions)
*   **串行优先 (Sequential over Parallel):** Pipeline 必须保持串行（Batch Size 可调整，但 Chunk 间必须有顺序）。因为我们需要在 Chunk 之间传递 `{previous_context}` 记忆对象。**严禁建议改为全异步并发。**
*   **记忆传递:** 上下文记忆机制（Context Memory）是解决跨页表格和代词指代的关键，必须保留。

### 3.3 业务逻辑宪法 (Business Logic Constraints)
*   **Schema 权威:** `Global_HVACR_Ontology_Policy.md` 定义的 13 种实体类型和 13x13 关系矩阵是绝对标准。**严禁发明新的 Node Label 或 Relationship Type。**
*   **数值降级:** 任何纯数值（如 `3000`, `50`, `0.5`）或仅包含“数值+单位”的文本，**严禁**被创建为独立节点（Node）。它们必须被处理为关系的**属性 (Property)** 或挂载在 Parameter 实体下。

# ==============================================================================

## 4. 正在解决的 P0 级 Bug (Active Battlefront)
*AI 注意：本章节包含当前阻塞系统的致命错误，请优先分析报错信息（Traceback）和复现数据。*

### 🔴 Bug A: 致命的 JSON 解析崩溃 (Fatal JSON Crash)
*   **Location:** `core/utils.py` -> `parse_llm_json_output()`
*   **Error Log:** 
    ```text
    json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
    # 或者
    json.decoder.JSONDecodeError: Invalid control character at: line 5 column 20 (char 102)
    ```
*   **Root Cause:** 
    1.  暖通规范原文包含大量 LaTeX 符号（如 `\sim`, `\mu`, `\pm`, `\le`），LLM 输出时未正确转义（例如输出了 `\` 而不是 `\\`）。
    2.  `DeepSeek-Reasoner` 有时会在 JSON 代码块外输出大量思维链文本，导致正则表达式提取失败。
*   **Requirement:** 需要一个极强鲁棒性的 `repair_and_parse_json(text)` 函数，必须引入 `json_repair` 库或编写专门的 LaTeX 预处理正则。


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
**任务目标：** 解决 Section 4 中列出的 **Bug A (JSON Crash)** 。

请按照以下顺序执行，**一次只解决一个问题**，待我确认后再进行下一个：

### 🏁 任务一：编写强鲁棒性 JSON 修复工具 (Priority: High)
1.  **分析：** 查看 `Section 4 - Bug A` 的报错。
2.  **执行：** 编写一个新的 Python 函数 `robust_json_parse(text: str) -> dict`。
3.  **要求：**
    *   必须引入第三方库 `json_repair` (假设已安装) 或编写高级正则状态机。
    *   必须能自动处理 LaTeX 的反斜杠（如将 `\sim` 转义或保留）。
    *   必须包含 `try-except` 块，如果解析彻底失败，返回一个包含 `error` 字段的默认字典，**严禁抛出异常导致 Pipeline 崩溃**。
    *   **输出格式：** 仅提供 `core/utils.py` 的完整代码内容。


# ==============================================================================

*End of State Document*
```