# 使用支持 Python 3.12 的基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖 (编译某些 Python 库需要)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 注意：指定 PyTorch 的 CUDA 版本源，确保 3090 能被调用
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu121

# [关键修复] 强制卸载 uvloop，解决与 nest_asyncio 的冲突
# 即使 requirements.txt 里没有它，它也可能作为依赖被自动安装
RUN pip uninstall -y uvloop || true

# 复制项目代码
COPY . .

# 暴露 Streamlit 端口
EXPOSE 8501

# 启动命令
CMD ["streamlit", "run", "rag/app.py", "--server.port=8501", "--server.address=0.0.0.0"]