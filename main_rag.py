# -*- coding: utf-8 -*-
import sys
import os
from streamlit.web import cli as stcli

# ==========================================
# ArchRAG V3.0 在线服务启动入口
# ==========================================
# 职责：
# 1. 封装 Streamlit 启动命令
# 2. 使得可以通过 python main_rag.py 直接运行
# ==========================================

def main():
    # 获取 rag/app.py 的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(current_dir, "rag", "app.py")

    print(f"🚀 [RAG] 正在启动混合检索智能终端...")
    print(f"   -> 加载界面: {app_path}")
    print(f"   -> 请在浏览器中访问显示的 URL")

    # 构造命令行参数
    # 等同于在终端执行: streamlit run rag/app.py
    sys.argv = ["streamlit", "run", app_path]
    
    # 启动 Streamlit
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()