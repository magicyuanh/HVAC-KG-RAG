# ArchRAG 跨机器部署迁移指南

## 📋 目录
1. [前置准备](#前置准备)
2. [方案一：Docker 部署（推荐）](#方案一docker-部署推荐)
3. [方案二：本地 Python 环境部署](#方案二本地-python-环境部署)
4. [数据迁移](#数据迁移)
5. [常见问题排查](#常见问题排查)

---

## 🎯 前置准备

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核+ |
| 内存 | 16GB | 32GB+ |
| 硬盘 | 50GB 可用空间 | 100GB+ SSD |
| GPU | 无（仅 API 模式） | NVIDIA RTX 3090+ 24GB（本地模型） |

### 软件要求

**必需软件**：
- Windows 10/11 或 Linux (Ubuntu 20.04+)
- Docker Desktop (Windows) 或 Docker Engine (Linux)
- Git (可选，用于版本控制)

**可选软件**：
- NVIDIA Container Toolkit (如果使用 GPU)
- Python 3.10+ (本地部署模式)

---

## 🐳 方案一：Docker 部署（推荐）

### 优势
✅ 环境隔离，不污染系统
✅ 一键启动，配置简单
✅ 跨平台兼容（Windows/Linux/Mac）
✅ 易于迁移和备份

### 步骤 1：准备项目文件

#### 1.1 打包源代码

在**原机器**上执行：

```bash
# 进入项目目录
cd D:\KG_Test

# 创建打包目录（排除不必要的文件）
mkdir ../ArchRAG_Package

# 复制核心代码
cp -r core rag ingestion tools Prompt ../ArchRAG_Package/
cp config.py requirements.txt docker-compose.yml Dockerfile ../ArchRAG_Package/
cp README.md ArchRAG_Architecture.md ArchRAG_File_Structure.md ../ArchRAG_Package/
cp "Global_HVACR_Ontology_Policy V1.5.0.md" ../ArchRAG_Package/
cp import_graph.py main_pipeline.py main_rag.py ../ArchRAG_Package/

# 创建必要的空目录
cd ../ArchRAG_Package
mkdir -p jsonl graph chroma_db bm25 models monitor logs neo4j_data raw_data

# 创建 .env 模板
cat > .env.template << 'EOF'
# Neo4j 配置
NEO4J_URI=bolt://neo4j-db:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=请修改为强密码
NEO4J_DATABASE=neo4j

# LLM 配置
DEEPSEEK_API_KEY=sk-请填写你的DeepSeekKey
EOF

# 压缩打包
cd ..
tar -czf ArchRAG_Package.tar.gz ArchRAG_Package/
# 或者使用 zip（Windows 友好）
# zip -r ArchRAG_Package.zip ArchRAG_Package/
```

**Windows PowerShell 版本**：
```powershell
# 创建打包目录
New-Item -ItemType Directory -Path ..\ArchRAG_Package -Force

# 复制核心文件
Copy-Item -Recurse core,rag,ingestion,tools,Prompt ..\ArchRAG_Package\
Copy-Item config.py,requirements.txt,docker-compose.yml,Dockerfile ..\ArchRAG_Package\
Copy-Item README.md,ArchRAG_Architecture.md,ArchRAG_File_Structure.md ..\ArchRAG_Package\
Copy-Item "Global_HVACR_Ontology_Policy V1.5.0.md" ..\ArchRAG_Package\
Copy-Item import_graph.py,main_pipeline.py,main_rag.py ..\ArchRAG_Package\

# 创建空目录
cd ..\ArchRAG_Package
New-Item -ItemType Directory -Path jsonl,graph,chroma_db,bm25,models,monitor,logs,neo4j_data,raw_data -Force

# 压缩（需要 7-Zip 或 WinRAR）
Compress-Archive -Path ..\ArchRAG_Package -DestinationPath ..\ArchRAG_Package.zip
```

#### 1.2 下载模型文件（重要！）

模型文件较大，需要单独下载：

```bash
# 在原机器上，复制模型文件
cd D:\KG_Test
cp -r models/bge-large-zh-v1.5 ../ArchRAG_Package/models/
cp -r models/bge-reranker-large ../ArchRAG_Package/models/
```

**模型下载地址**（如果原机器没有）：
- BGE-Large-zh-v1.5: https://huggingface.co/BAAI/bge-large-zh-v1.5
- BGE-Reranker-Large: https://huggingface.co/BAAI/bge-reranker-large

**模型目录结构**：
```
models/
├── bge-large-zh-v1.5/
│   ├── config.json
│   ├── pytorch_model.bin
│   ├── tokenizer_config.json
│   └── vocab.txt
└── bge-reranker-large/
    ├── config.json
    ├── pytorch_model.bin
    └── tokenizer_config.json
```

### 步骤 2：传输到新机器

**方法 A：网络传输**
```bash
# 使用 scp（Linux/Mac）
scp ArchRAG_Package.tar.gz user@new-machine:/path/to/destination/

# 使用 rsync（推荐，支持断点续传）
rsync -avz --progress ArchRAG_Package.tar.gz user@new-machine:/path/to/destination/
```

**方法 B：物理介质**
- U 盘、移动硬盘
- 网盘（百度网盘、阿里云盘）

**方法 C：Git 仓库**
```bash
# 在原机器上
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main

# 在新机器上
git clone <your-repo-url>
```

### 步骤 3：新机器环境配置

#### 3.1 安装 Docker

**Windows**：
1. 下载 Docker Desktop: https://www.docker.com/products/docker-desktop/
2. 安装并重启
3. 启动 Docker Desktop
4. 验证安装：
   ```powershell
   docker --version
   docker-compose --version
   ```

**Linux (Ubuntu)**：
```bash
# 更新包索引
sudo apt-get update

# 安装依赖
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 添加 Docker 官方 GPG 密钥
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 设置仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
docker --version
docker compose version
```

#### 3.2 配置 GPU 支持（可选）

如果有 NVIDIA GPU 并希望本地运行模型：

**Windows**：
- Docker Desktop 自动支持 GPU，确保安装了 NVIDIA 驱动

**Linux**：
```bash
# 安装 NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# 验证 GPU 可用
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### 步骤 4：解压并配置

```bash
# 解压项目
tar -xzf ArchRAG_Package.tar.gz
cd ArchRAG_Package

# 或者 Windows
# Expand-Archive -Path ArchRAG_Package.zip -DestinationPath .
# cd ArchRAG_Package

# 复制环境变量模板
cp .env.template .env

# 编辑 .env 文件，填入真实配置
nano .env  # Linux
# 或 notepad .env  # Windows
```

**.env 配置示例**：
```bash
# Neo4j 配置
NEO4J_URI=bolt://neo4j-db:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=YourStrongPassword123!
NEO4J_DATABASE=neo4j

# LLM 配置
DEEPSEEK_API_KEY=sk-1234567890abcdef1234567890abcdef
```

### 步骤 5：启动系统

```bash
# 构建并启动容器（首次启动）
docker-compose --env-file .env up -d --build

# 查看启动日志
docker-compose logs -f

# 等待 Neo4j 启动完成（约 30 秒）
# 看到 "Started." 表示 Neo4j 已就绪
```

**验证服务状态**：
```bash
# 查看容器状态
docker-compose ps

# 应该看到两个容器都是 "Up" 状态：
# archrag-app    Up    0.0.0.0:8501->8501/tcp
# neo4j-db       Up    0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp
```

### 步骤 6：导入数据（如果有现有数据）

#### 6.1 导入知识图谱数据

```bash
# 确保 graph/ 目录下有 CSV 文件
ls graph/
# 应该看到：neo4j_nodes.csv, neo4j_relationships.csv

# 导入到 Neo4j
docker exec -it archrag-app python import_graph.py

# 等待出现 "🎉 全部导入任务结束！"
```

#### 6.2 重建索引

```bash
# 确保 jsonl/ 目录下有数据文件
ls jsonl/
# 应该看到：structured_chunks.jsonl

# 重建向量索引和 BM25 索引
docker exec -it archrag-app python rag/indexer.py

# 等待索引构建完成
```

### 步骤 7：访问系统

打开浏览器访问：**http://localhost:8501**

如果一切正常，你应该看到 ArchRAG 的 Streamlit 界面！

---

## 🐍 方案二：本地 Python 环境部署

### 优势
✅ 更灵活的调试
✅ 直接访问文件系统
✅ 适合开发环境

### 步骤 1：安装 Python 环境

**Windows**：
1. 下载 Python 3.10+: https://www.python.org/downloads/
2. 安装时勾选 "Add Python to PATH"
3. 验证：
   ```powershell
   python --version
   pip --version
   ```

**Linux**：
```bash
sudo apt-get update
sudo apt-get install -y python3.10 python3.10-venv python3-pip
```

### 步骤 2：创建虚拟环境

```bash
# 进入项目目录
cd /path/to/ArchRAG_Package

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 升级 pip
python -m pip install --upgrade pip
```

### 步骤 3：安装依赖

```bash
# 安装所有依赖（可能需要 10-20 分钟）
pip install -r requirements.txt

# 如果遇到网络问题，使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**常见依赖问题**：

1. **PyTorch 安装**（如果需要 GPU）：
   ```bash
   # CUDA 11.8
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

   # CUDA 12.1
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

   # CPU 版本
   pip install torch torchvision torchaudio
   ```

2. **ChromaDB 安装问题**：
   ```bash
   # Windows 可能需要 Visual C++ Build Tools
   # 下载：https://visualstudio.microsoft.com/visual-cpp-build-tools/
   ```

### 步骤 4：安装 Neo4j

**方法 A：Docker 运行 Neo4j（推荐）**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  -v $(pwd)/neo4j_data:/data \
  neo4j:5.15
```

**方法 B：本地安装 Neo4j**
1. 下载 Neo4j Community: https://neo4j.com/download/
2. 解压并启动
3. 访问 http://localhost:7474 设置密码

### 步骤 5：配置环境变量

创建 `.env` 文件：
```bash
# Neo4j 配置（本地模式）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j

# LLM 配置
DEEPSEEK_API_KEY=sk-your-key
```

### 步骤 6：导入数据并启动

```bash
# 导入图谱数据
python import_graph.py

# 构建索引
python rag/indexer.py

# 启动 RAG 服务
streamlit run rag/app.py
# 或
python main_rag.py
```

---

## 📦 数据迁移

### 迁移现有数据

如果你在原机器上已经有处理好的数据，需要迁移以下内容：

#### 必需迁移的数据

1. **知识图谱数据**
   ```bash
   # 原机器导出
   cd D:\KG_Test
   cp graph/neo4j_nodes.csv /path/to/transfer/
   cp graph/neo4j_relationships.csv /path/to/transfer/

   # 新机器导入
   cp /path/to/transfer/*.csv graph/
   docker exec -it archrag-app python import_graph.py
   ```

2. **文档切片数据**
   ```bash
   # 原机器
   cp jsonl/structured_chunks.jsonl /path/to/transfer/

   # 新机器
   cp /path/to/transfer/structured_chunks.jsonl jsonl/
   docker exec -it archrag-app python rag/indexer.py
   ```

3. **模型文件**（如果本地运行）
   ```bash
   # 复制整个 models 目录
   cp -r models/ /path/to/transfer/
   ```

#### 可选迁移的数据

1. **原始文档**
   ```bash
   cp -r raw_data/ /path/to/transfer/
   ```

2. **日志文件**（用于调试）
   ```bash
   cp -r monitor/ /path/to/transfer/
   cp -r logs/ /path/to/transfer/
   ```

### 完整备份脚本

**Linux/Mac**：
```bash
#!/bin/bash
# backup.sh - 完整备份脚本

BACKUP_DIR="ArchRAG_Backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# 备份代码
cp -r core rag ingestion tools Prompt $BACKUP_DIR/
cp config.py requirements.txt docker-compose.yml Dockerfile $BACKUP_DIR/
cp *.md $BACKUP_DIR/

# 备份数据
cp -r jsonl graph models $BACKUP_DIR/

# 备份配置
cp .env $BACKUP_DIR/.env.backup

# 打包
tar -czf ${BACKUP_DIR}.tar.gz $BACKUP_DIR/
echo "备份完成: ${BACKUP_DIR}.tar.gz"
```

**Windows PowerShell**：
```powershell
# backup.ps1 - 完整备份脚本

$BackupDir = "ArchRAG_Backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force

# 备份代码
Copy-Item -Recurse core,rag,ingestion,tools,Prompt $BackupDir\
Copy-Item config.py,requirements.txt,docker-compose.yml,Dockerfile $BackupDir\
Copy-Item *.md $BackupDir\

# 备份数据
Copy-Item -Recurse jsonl,graph,models $BackupDir\

# 备份配置
Copy-Item .env "$BackupDir\.env.backup"

# 打包
Compress-Archive -Path $BackupDir -DestinationPath "$BackupDir.zip"
Write-Host "备份完成: $BackupDir.zip"
```

---

## 🔧 常见问题排查

### 问题 1：Docker 无法启动

**症状**：`docker-compose up` 报错

**解决方案**：
```bash
# 检查 Docker 服务状态
docker info

# Windows: 确保 Docker Desktop 正在运行
# Linux: 启动 Docker 服务
sudo systemctl start docker

# 检查端口占用
netstat -ano | findstr :8501  # Windows
lsof -i :8501                 # Linux

# 如果端口被占用，修改 docker-compose.yml 中的端口映射
```

### 问题 2：Neo4j 连接失败

**症状**：侧边栏显示 "知识图谱：🔴 离线"

**解决方案**：
```bash
# 检查 Neo4j 容器状态
docker-compose ps

# 查看 Neo4j 日志
docker-compose logs neo4j-db

# 检查密码是否正确
# 编辑 .env 文件，确保 NEO4J_PASSWORD 正确

# 重启容器
docker-compose restart neo4j-db

# 等待 30 秒后刷新页面
```

### 问题 3：模型加载失败

**症状**：启动时报错 "模型文件不存在"

**解决方案**：
```bash
# 检查模型文件是否存在
ls models/bge-large-zh-v1.5/
ls models/bge-reranker-large/

# 如果缺失，重新下载
# 方法 1：从 Hugging Face 下载
git lfs install
git clone https://huggingface.co/BAAI/bge-large-zh-v1.5 models/bge-large-zh-v1.5
git clone https://huggingface.co/BAAI/bge-reranker-large models/bge-reranker-large

# 方法 2：使用 modelscope（国内更快）
pip install modelscope
python -c "from modelscope import snapshot_download; snapshot_download('AI-ModelScope/bge-large-zh-v1.5', cache_dir='models')"
```

### 问题 4：API Key 无效

**症状**：查询时报错 "API 调用失败"

**解决方案**：
```bash
# 检查 .env 文件
cat .env | grep DEEPSEEK_API_KEY

# 确保 API Key 格式正确（以 sk- 开头）
# 测试 API Key 是否有效
curl https://api.deepseek.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 如果无效，重新申请：https://platform.deepseek.com/
```

### 问题 5：内存不足

**症状**：容器频繁重启或 OOM (Out of Memory)

**解决方案**：
```bash
# 检查内存使用
docker stats

# 增加 Docker 内存限制（Docker Desktop）
# Settings -> Resources -> Memory -> 调整为 8GB+

# 或修改 docker-compose.yml，限制单个容器内存
services:
  archrag-app:
    deploy:
      resources:
        limits:
          memory: 4G
```

### 问题 6：索引构建失败

**症状**：`python rag/indexer.py` 报错

**解决方案**：
```bash
# 检查数据文件是否存在
ls jsonl/structured_chunks.jsonl

# 检查文件格式是否正确（每行一个 JSON）
head -n 1 jsonl/structured_chunks.jsonl | python -m json.tool

# 清空旧索引重新构建
rm -rf chroma_db/* bm25/*
docker exec -it archrag-app python rag/indexer.py
```

### 问题 7：网络代理问题

**症状**：Docker 构建时无法下载依赖

**解决方案**：
```bash
# 配置 Docker 代理（Docker Desktop）
# Settings -> Resources -> Proxies
# 填入代理地址，如：http://127.0.0.1:7890

# 或在 docker-compose.yml 中添加代理
services:
  archrag-app:
    environment:
      - HTTP_PROXY=http://host.docker.internal:7890
      - HTTPS_PROXY=http://host.docker.internal:7890
```

---

## 📋 部署检查清单

### 部署前检查

- [ ] 硬件满足最低要求（16GB 内存，50GB 硬盘）
- [ ] Docker 已安装并正常运行
- [ ] 已获取 DeepSeek API Key
- [ ] 模型文件已下载（bge-large-zh-v1.5, bge-reranker-large）
- [ ] 项目文件已完整传输

### 部署后验证

- [ ] `docker-compose ps` 显示两个容器都是 "Up" 状态
- [ ] 访问 http://localhost:8501 能看到界面
- [ ] 侧边栏显示 "🟢 引擎状态: 在线"
- [ ] 侧边栏显示 "🕸️ 知识图谱: ✅"（如果已导入数据）
- [ ] 能够正常提问并获得回答
- [ ] 证据链能够正常展示

### 性能测试

```bash
# 测试查询响应时间
# 在界面中输入测试问题，观察响应时间
# 正常情况下应在 5-10 秒内返回结果

# 检查资源使用
docker stats

# 查看日志是否有异常
docker-compose logs -f archrag-app
```

---

## 🎓 最佳实践建议

### 1. 版本控制

```bash
# 使用 Git 管理代码
git init
git add .
git commit -m "Initial deployment"

# 创建 .gitignore
cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
test/
chroma_db/
neo4j_data/
monitor/
logs/
*.log
EOF
```

### 2. 定期备份

```bash
# 每周备份一次数据
# 使用 cron (Linux) 或 Task Scheduler (Windows)

# Linux cron 示例
0 2 * * 0 /path/to/backup.sh

# 备份到云存储
# 使用 rclone 同步到阿里云 OSS/AWS S3
```

### 3. 监控告警

```bash
# 使用 Docker 健康检查
# 在 docker-compose.yml 中添加：
services:
  archrag-app:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 4. 安全加固

```bash
# 修改默认密码
# 使用强密码（至少 16 位，包含大小写字母、数字、特殊字符）

# 限制网络访问
# 在 docker-compose.yml 中只暴露必要端口
# 使用防火墙限制访问 IP

# 定期更新依赖
pip list --outdated
pip install --upgrade <package>
```

---

## 📞 获取帮助

如果遇到无法解决的问题：

1. **查看日志**：
   ```bash
   docker-compose logs -f
   cat monitor/monitor.log
   ```

2. **检查配置**：
   ```bash
   cat .env
   cat config.py
   ```

3. **测试组件**：
   ```bash
   # 测试 Neo4j 连接
   docker exec -it neo4j-db cypher-shell -u neo4j -p your_password

   # 测试 Python 环境
   docker exec -it archrag-app python -c "import torch; print(torch.__version__)"
   ```

4. **社区支持**：
   - GitHub Issues: https://github.com/anthropics/claude-code/issues
   - DeepSeek 文档: https://platform.deepseek.com/docs

---

## 🎉 部署成功！

如果你已经完成以上步骤，恭喜你成功在新机器上部署了 ArchRAG 系统！

**下一步**：
- 导入你的领域文档数据
- 调整检索参数优化效果
- 根据实际使用情况调优系统

祝使用愉快！🚀
