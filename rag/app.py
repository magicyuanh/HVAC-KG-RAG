# -*- coding: utf-8 -*-
import streamlit as st
import sys
import os
import time
import atexit
import re  # [Fix 5] 引入正则模块，用于清洗 Markdown 格式

# ==========================================
# 0. 路径补丁 & 环境初始化
# ==========================================
# 确保能够正确导入根目录下的 config 和 core 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# [Fix 1] 强制应用异步补丁
# 解决 Streamlit 线程内运行异步 LLM 客户端的底层冲突
import nest_asyncio
nest_asyncio.apply()

from config import SystemConfig
from rag.retriever import HybridRetriever
from rag.generator import ResponseGenerator
from rag.rewriter import QueryRewriter

# ==========================================
# 1. 页面 UI 配置 (优先加载)
# ==========================================
st.set_page_config(
    page_title="ArchRAG V3.41 | 工业级混合检索终端",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入优化后的 CSS
st.markdown("""
<style>
    .stChatInput {border-radius: 10px;}
    .stChatMessage {border-radius: 10px; margin-bottom: 12px; border: 1px solid #f0f2f6;}
    .rewritten-query-box {
        padding: 10px 15px;
        background-color: #e3f2fd;
        border-radius: 8px;
        font-size: 0.9em;
        color: #1565c0;
        border-left: 5px solid #2196f3;
        margin: 5px 0 15px 0;
    }
    .status-card {
        padding: 10px;
        border-radius: 5px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心辅助函数 (格式清洗)
# ==========================================
def format_output(text: str) -> str:
    """
    [Fix 5] 输出格式清洗器
    解决 LLM 输出格式与 Streamlit Markdown 渲染器的兼容性问题
    """
    if not text: return ""
    
    # 1. 修复波浪号导致的删除线问题 (例如 "1~3" 变成删除线)
    # 将英文 ~ 替换为中文 ～，规避 Markdown 语法冲突
    text = text.replace('~', '～')
    
    # 2. 修复 LaTeX 公式显示问题
    # 将 \[ ... \] 替换为 $$ ... $$ (块级公式)
    text = re.sub(r'\\\[', '$$', text)
    text = re.sub(r'\\\]', '$$', text)
    
    # 将 \( ... \) 替换为 $ ... $ (行内公式)
    text = re.sub(r'\\\(', '$', text)
    text = re.sub(r'\\\)', '$', text)
    
    return text

# ==========================================
# 3. 核心引擎加载 (异常不入缓存)
# ==========================================
@st.cache_resource(show_spinner=False)
def _initialize_engines_core():
    """
    内部引擎加载逻辑。此处不处理异常，确保失败时不被 Streamlit 缓存。
    """
    config = SystemConfig()
    # 按照依赖顺序初始化
    rewriter = QueryRewriter(config)
    retriever = HybridRetriever(config)
    generator = ResponseGenerator(config)
    
    # 注册资源清理
    atexit.register(retriever.close)
    
    return {
        "config": config,
        "rewriter": rewriter,
        "retriever": retriever,
        "generator": generator
    }

def load_engine_safe():
    """
    外层包装：处理加载状态与异常展示
    """
    with st.spinner("🔥 正在启动工业知识库核心引擎..."):
        try:
            return _initialize_engines_core()
        except Exception as e:
            # 展示专业的诊断仪表盘
            st.error("❌ 系统核心引擎启动失败")
            with st.expander("🛠️ 系统诊断与排查清单", expanded=True):
                st.write(f"**错误原因**: `{str(e)}`")
                st.markdown("""
                **请检查以下事项**:
                1. `.env` 文件中的 `DEEPSEEK_API_KEY` 是否正确设置。
                2. `models/` 目录下是否已下载 BGE 和 Reranker 模型。
                3. Neo4j 数据库是否已启动，且 `NEO4J_URI` 配置无误。
                4. 如果是在线运行，请检查网络是否能够访问 `api.deepseek.com`。
                """)
            return None

# 执行加载
engine_bundle = load_engine_safe()

# [Fix 2] 硬熔断逻辑
if engine_bundle is None:
    st.warning("⚠️ 引擎未就绪，请修复上述配置后刷新页面。")
    st.stop()

# 解包引擎组件
config = engine_bundle["config"]
rewriter = engine_bundle["rewriter"]
retriever = engine_bundle["retriever"]
generator = engine_bundle["generator"]

# ==========================================
# 4. 侧边栏：状态与控制面板
# ==========================================
with st.sidebar:
    st.title("🎛️ 控制中心")
    st.markdown("---")
    
    st.success("🟢 引擎状态: 在线")
    st.caption(f"驱动模型: {config.model_name}")
    
    with st.container():
        st.markdown('<div class="status-card">', unsafe_allow_html=True)
        st.write(f"🕸️ 知识图谱: {'✅' if retriever.graph_retriever.is_active else '❌'}")
        st.write(f"📄 向量数据库: {'✅' if retriever.collection else '❌'}")
        st.write(f"⚖️ 重排序裁判: ✅ Ready")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("⚙️ 检索策略")
    top_k = st.slider("检索深度 (Top K)", 1, 10, 5, help="影响模型查阅的参考证据数量。")
    
    if st.button("🗑️ 清空所有对话记忆", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 5. 主对话逻辑 (The Strategic Loop)
# ==========================================
st.title("🧠 ArchRAG Enterprise V3.41")
st.caption("🚀 混合检索生产级旗舰版 | 自动指代消解 + 语义重排序 + 知识图谱事实")

# 初始化对话历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 渲染对话历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "evidence" in msg:
            with st.expander("🔍 审阅该回答的证据链 (Evidence Chain)"):
                st.markdown(msg["evidence"])

# 处理用户实时输入
if raw_input := st.chat_input("输入工业设备指令或专业查询..."):
    # [Fix 3] 生产级输入净化与长度防御
    user_query = raw_input.strip()
    if not user_query:
        st.stop()
    if len(user_query) > 1000:
        st.error("⚠️ 输入内容过长 (限1000字符)，请精简提问。")
        st.stop()

    # 1. 展示用户提问并存入 Session
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # 2. 调度引擎生成回复
    with st.chat_message("assistant"):
        status_box = st.status("🔮 正在跨维度检索证据并思考...", expanded=True)
        
        try:
            # --- 阶段 A: 多轮对话指代消解 (Query Rewriting) ---
            status_box.write("🛰️ 正在消解上下文指代...")
            
            # [Fix 4] 历史切片精准传递
            standalone_query = rewriter.rewrite_sync(
                query=user_query, 
                history=st.session_state.messages[:-1]
            )
            
            # UI 透明化：展示系统理解后的意图
            if standalone_query != user_query:
                st.markdown(f'<div class="rewritten-query-box">💡 <b>系统理解为：</b>{standalone_query}</div>', unsafe_allow_html=True)

            # --- 阶段 B: 三路混合召回与语义精排 ---
            status_box.write("🔍 正在从向量库与知识图谱调取证据...")
            t_start = time.time()
            
            # 执行混合检索
            context_results = retriever.search(query=standalone_query, top_k=top_k)
            
            t_retrieval = time.time() - t_start
            status_box.write(f"⚖️ 执行语义重排序 (耗时: {t_retrieval:.2f}s)...")

            # --- 阶段 C: 证据链面板构建 ---
            evidence_text = f"**检索耗时**: {t_retrieval:.2f}s | **证据源**: "
            found_sources = set([ctx.source for ctx in context_results])
            evidence_text += ", ".join(found_sources) + "\n\n---\n\n"
            
            for i, ctx in enumerate(context_results):
                icon = "🕸️" if "Graph" in ctx.source else "📄"
                if "Vector" in ctx.source: icon += "⚡"
                evidence_text += f"**[{i+1}] {icon} {ctx.source}** (Score: {ctx.score:.4f})\n> {ctx.content}\n\n"

            # --- 阶段 D: 最终答案生成 ---
            status_box.write("🤖 正在组织判词并生成工业级回答...")
            
            # 调用生成器
            raw_answer = generator.generate_sync(
                query=standalone_query, 
                context_list=context_results,
                timeout=config.timeout_seconds
            )
            
            # [Fix 5 应用] 格式清洗：修复公式显示和删除线问题
            final_answer = format_output(raw_answer)
            
            status_box.update(label=f"✅ 完成 (总耗时: {time.time()-t_start:.2f}s)", state="complete", expanded=False)
            
            # 最终展示结果
            st.markdown(final_answer)
            with st.expander("🔍 审阅该回答的证据链 (Evidence Chain)"):
                st.markdown(evidence_text)

            # 3. 将结果存入持久化历史
            # 注意：存入的是清洗后的 final_answer，保证历史记录显示也正常
            st.session_state.messages.append({
                "role": "assistant",
                "content": final_answer,
                "evidence": evidence_text
            })

        except Exception as e:
            status_box.update(label="❌ 任务中断", state="error")
            st.error(f"系统运行异常: {str(e)}")
            import traceback
            st.code(traceback.format_exc())