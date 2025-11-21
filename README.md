# yxi-chat-cli 轻量自动化开发助手

一款基于自然语言交互的轻量级开发自动化工具，通过 **Terminal Chatbot** 接收指令，**MCP（Master Control Program）** 调度资源，**Docker Slim** 优化容器，实现 C++ JSON 序列化代码生成等开发任务的自动化执行。

## ✨ 项目亮点

- **自然语言交互**：无需记忆复杂命令，用日常语言即可触发开发任务（如“将JSON转成C++类”）。

- **轻量隔离执行**：基于 Docker Slim 优化容器，镜像体积缩减 50%-90%，启动速度快且环境隔离无污染。

- **灵活 MCP 调度**：支持动态添加/切换 MCP 服务器，实现多环境、多任务的集中化管理与资源调度。

- **开箱即用功能**：内置 C++ JSON 序列化/反序列化代码生成，自动生成 `to_json`/`from_json` 方法。

- **可扩展性强**：模块化设计，轻松扩展新任务类型（如数据处理、部署脚本生成等）。

## 🚀 快速上手

### 1. 环境准备

- 安装 [Docker](https://docs.docker.com/get-docker/)（需支持 Docker Slim）

- 安装 [Docker Slim](https://github.com/docker-slim/docker-slim)：
        `curl -sL https://raw.githubusercontent.com/docker-slim/docker-slim/master/scripts/install-dockerslim.sh | sudo -E bash -`

- 安装 Python 3.7+：`sudo apt install python3 python3-pip`（Linux/macOS）

### 2. 项目克隆与依赖安装

```bash

# 克隆项目
git clone https://github.com/your-username/terminal-chatbot-mcp.git
cd terminal-chatbot-mcp

# 安装 Chatbot 依赖
pip install requests

# 安装 MCP 依赖
cd mcp
pip install -r requirements.txt
cd ..
```

### 3. 构建优化代码生成容器

```bash

# 进入代码生成服务目录
cd app

# 构建原始镜像
docker build -t cpp-json-codegen-executor .

# 使用 Docker Slim 优化镜像（体积大幅缩减）
docker-slim build --optimize --tag cpp-json-codegen-executor:slim cpp-json-codegen-executor

cd ..
```

### 4. 启动服务

1. **启动 MCP 服务器**：
        `cd mcp
python mcp.py  # 服务默认运行在 http://localhost:8000
`

2. **启动 Terminal Chatbot**（新终端窗口）：
        `python chatbot.py
`

### 5. 开始使用

在 Chatbot 终端输入指令，示例：

```bash

# 1. 添加 MCP 服务器
> add mcp LocalMCP http://localhost:8000

# 2. 生成 C++ JSON 代码
> 将 {"name":"Alice","age":30,"address":{"city":"NY"}} 转成 class Person

# 3. 查看已添加的 MCP 服务器
> list mcps

```

## 📋 核心功能

### 1. MCP 服务器管理

|命令|说明|示例|
|---|---|---|
|add mcp <name> <url>|添加 MCP 服务器|add mcp DevMCP http://192.168.1.100:8000|
|list mcps|列出所有 MCP 服务器|list mcps|
|use mcp <name>|切换活跃 MCP 服务器|use mcp DevMCP|
|remove mcp <name>|删除 MCP 服务器|remove mcp TestMCP|
### 2. C++ JSON 代码生成

支持将 JSON 结构自动转换为 C++ `struct` 或 `class`，并生成完整的序列化/反序列化方法。

#### 输入示例

```bash

> 将 {"id":1,"name":"CppBot","features":["json","docker","mcp"]} 转成 struct CodeGen 命名为 CppBotConfig

```

#### 输出示例
> （注：文档部分内容可能由 AI 生成）