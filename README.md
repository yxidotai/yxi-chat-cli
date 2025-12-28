# yxi-chat-cli — 轻量级开发自动化助手

基于自然语言交互的轻量级开发工具。通过 `yxi-chat-cli` 接收指令，使用 MCP（Master Control Program）调度任务，并可配合 Docker Slim 对执行容器进行体积与启动时间优化。

## ✨ 项目亮点

- **自然语言交互**：使用日常语言触发开发任务，降低学习成本。
- **轻量隔离执行**：结合 Docker 与 Docker Slim，可显著减小镜像体积并加快启动速度，保证环境隔离。
- **灵活的 MCP 调度**：支持动态添加/切换 MCP 节点，便于集中管理多环境与多任务。
- **开箱即用的代码生成**：内置辅助函数，可按需拓展到其他语言或代码骨架。
- **模块化与可扩展**：设计上便于扩展新任务（例如数据处理、自动化部署脚本生成等）。

## 🚀 快速上手

下面的步骤覆盖 macOS、Linux 常见场景；请根据你的系统选择合适的命令。

### 1. 环境准备

- 安装 Docker：参见 https://docs.docker.com/get-docker/ 。
- 可选：安装 Docker Slim（用于优化镜像体积）：
  - 官方仓库：https://github.com/docker-slim/docker-slim
  - 示例安装命令（Linux/macOS）：
    ```bash
    curl -sL https://raw.githubusercontent.com/docker-slim/docker-slim/master/scripts/install-dockerslim.sh | sudo -E bash -
    ```
- 安装 Python（建议 3.7+）：macOS 可用 `brew install python`，Linux 可用对应包管理器（如 `apt` / `yum`）。

### 2. 克隆项目并安装依赖

```bash
# 克隆仓库
git clone https://github.com/your-username/terminal-chatbot-mcp.git
cd terminal-chatbot-mcp

# 推荐：使用 uv 管理依赖
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync  # 根据 pyproject.toml 安装 requests、rich 等依赖

# 如需临时扩展依赖，可执行（示例）
uv add httpx

# 如果暂不使用 uv，可 fallback 到 pip
pip install -r requirements.txt
```

（如果代码中存在子模块或单独的 `mcp/requirements.txt`，请在 `mcp` 目录内运行 `pip install -r requirements.txt`。）

### 3. 构建并优化代码生成容器（可选）

```bash
# 进入代码生成服务目录（示例）
cd app

# 构建原始镜像
docker build -t codegen-executor .

# 使用 Docker Slim 优化镜像（可选）
docker-slim build --optimize --tag codegen-executor:slim codegen-executor

cd ..
```

### 4. 启动服务

1. 启动 MCP 服务器（在 `mcp` 目录）：

```bash
cd mcp
uv run python mcp.py   # 默认监听 http://localhost:8000（如需修改请查看 mcp 配置）
```

2. 启动终端 Chatbot（在项目根目录，新终端）：

```bash
uv run python chatbot.py
```

运行前可设置以下环境变量：
- `YXI_API_KEY`：云端对话所需 API 密钥。
- `YXI_API_BASE_URL`：自定义 yxi API 基础 URL（默认 `https://api.yxi.ai/v1`）。
- `YXI_MODEL`：指定调用的云端模型（默认 `yxi-7b-terminal`）。

若不便设置环境变量，也可以在 CLI 中执行 `/apikey set <值>` 临时配置；该值会以明文写入 `~/.yxi_chat_config.json`，请按需评估安全风险。

### 5. 使用示例

在 Chatbot 终端输入自然语言或命令，示例：

```bash
# 添加 MCP 服务器
/mcp add LocalMCP http://localhost:8000

# 切换到离线模式并绑定节点
/mode offline LocalMCP

# 列出现有 MCP
/mcp list

# 查看指令帮助
/help

# 将最近助理回复中的代码块复制到剪贴板（macOS）
/copy  # 或 /c

# 交互式设置 API Key
/apikey set sk-your-key

# 查看可用模型并切换
/model list
/model use yxi-7b-terminal
/model default yxi-7b-terminal

# 将 JSON 转成 C++ 类（回到在线模式）
/mode online
将 {"name":"Alice","age":30,"address":{"city":"NY"}} 转成 class Person

# 离线模式直接调用工具（node 可省略为默认离线节点）
word_tables_to_json {"doc_path":"/data/demo.docx"}

# 调用 MCP 工具
/mcp invoke json_to_cpp {"schema":{"name":"Demo"}}

# 运行 Obsidian MCP（示例）并注册
OBSIDIAN_VAULT_DIR=~/Documents/ObsidianVault OBSIDIAN_MCP_TOKEN=sk-obsidian uv run python tasks/obsidian_mcp/mcp_service.py
/mcp add obsidian http://localhost:8025 sk-obsidian
/mcp tools obsidian
/mcp invoke search_notes {"query":"roadmap","limit":5}
/mcp invoke append_note {"path":"notes/todo.md","content":"- [ ] new item"}

# 将嵌套 JSON 转成 Java 类（可指定包名）
uv run python tasks/json_to_java/generate_java.py samples/nested.json -o Output.java --package com.example.demo --class-name Root

# Docker 方式运行 Obsidian MCP（示例）
docker build -f tasks/obsidian_mcp/Dockerfile -t yxi-obsidian-mcp .
docker run --rm -p 8025:8025 \
  -v "$HOME/Documents/ObsidianVault:/vault" \
  -e OBSIDIAN_VAULT_DIR=/vault \
  -e OBSIDIAN_MCP_TOKEN=sk-obsidian \
  yxi-obsidian-mcp
```

## 📋 核心功能

**常用指令**
- `/help`：查看可用命令与模式提示。
- `/copy`（或 `/c`）：将最近一次助理回复的代码块（若存在，否则完整回复）复制到剪贴板（macOS 使用 `pbcopy`）。
- `/apikey set|clear`：配置或清除云端 API Key。

**模型管理**
- `/model list`：实时查询云端可用模型（需要有效 `YXI_API_KEY`）。
- `/model use <name>`：当前会话切换模型，立即生效。
- `/model default <name>`：设置并持久化默认模型（存储于 `~/.yxi_chat_config.json`）。
- 也可通过 `YXI_MODEL` 环境变量在启动前指定初始模型。

**MCP 服务器管理**
- `/mcp add <name> <url> [token]`：添加 MCP 节点，例如 `/mcp add DevMCP http://192.168.1.100:8000`。
- `/mcp list`：列出已配置的 MCP 节点。
- `/mcp use <name>`：切换当前活跃的 MCP。
- `/mcp remove <name>`：删除指定 MCP。
- `/mcp tools [name]`：列出活跃或指定节点公开的工具。
- `/mcp invoke <tool> <json_payload>`：执行 MCP 工具，payload 必须是合法 JSON。

**在线 / 离线模式**
- `/mode online`：回到云端模型对话，需要有效 `YXI_API_KEY`。
- `/mode offline <node>`：绑定离线模式到指定 MCP 节点（默认回落到 `/mcp use` 选中的节点）。
- 离线模式下，普通输入会被解析为 `<tool> <json_payload>` 或 `<node> <tool> <json_payload>` 并直接调用 MCP；例如 `word_tables_to_json {"doc_path":"/data/demo.docx"}`。
- 若未配置 `YXI_API_KEY`，程序会自动提醒但仍可使用离线模式。

**JSON 转 Java 类工具**
- 入口：`tasks/json_to_java/generate_java.py`
- 作用：将复杂嵌套 JSON 生成单文件 Java POJO，支持包名与根类名；嵌套对象会生成静态内部类，数组生成 `List<T>`，混合类型数组回落为 `List<Object>`。
- 示例：`uv run python tasks/json_to_java/generate_java.py samples/nested.json -o Output.java --package com.example.demo --class-name Root`
- MCP 服务：`uv run python tasks/json_to_java/mcp_service.py`（默认 0.0.0.0:8030），`/tools` 列出工具，调用示例 `/mcp invoke json_to_java {"json_text":"{...}","class_name":"Root","package":"com.example.demo"}`。
- Docker：`docker build -f tasks/json_to_java/Dockerfile -t yxi-json-to-java .`，运行示例 `docker run --rm -p 8030:8030 yxi-json-to-java`（如需访问本地文件，可通过 `-v "$PWD:/data"` 并传入绝对路径）。
- LangGraph 智能体：`uv run python tasks/json_to_java/langgraph_agent.py path/to/doc.docx --word-url http://localhost:8000 --java-url http://localhost:8030 --package com.example.demo --class-name Root --output-path /tmp/Output.java`，自动串联 `word_table_export` 与 `json_to_java` 完成 docx → 表格 → 示例 JSON → Java 生成。

**Obsidian MCP 示例**
- 服务端：`tasks/obsidian_mcp/mcp_service.py`，需要 Python 依赖 `tasks/obsidian_mcp/requirements.txt`。
- 启动示例：`OBSIDIAN_VAULT_DIR=~/Documents/ObsidianVault OBSIDIAN_MCP_TOKEN=sk-obsidian uv run python tasks/obsidian_mcp/mcp_service.py`（默认监听 0.0.0.0:8025）。
- 注册节点：`/mcp add obsidian http://localhost:8025 sk-obsidian`
- 列出工具：`/mcp tools obsidian`
- 调用搜索：`/mcp invoke search_notes {"query":"roadmap","limit":5}`
- 追加笔记：`/mcp invoke append_note {"path":"notes/todo.md","content":"- [ ] new item"}`
- Docker 运行：
  - 构建：`docker build -f tasks/obsidian_mcp/Dockerfile -t yxi-obsidian-mcp .`
  - 运行：`docker run --rm -p 8025:8025 -v "$HOME/Documents/ObsidianVault:/vault" -e OBSIDIAN_VAULT_DIR=/vault -e OBSIDIAN_MCP_TOKEN=sk-obsidian yxi-obsidian-mcp`

**代码生成**

`yxi-chat-cli` 可以根据自然语言指令或直接提供的 JSON 示例生成目标代码，当前默认输出 C++ `struct`/`class`，后续也能扩展到 Go、TypeScript 等语言的骨架。内部流程会：

1. 解析 JSON，推断字段类型、可空性与嵌套关系。
2. 根据指令选择 `struct`/`class`、是否拆分头/源文件以及命名空间。
3. 生成配套的 `to_json`/`from_json`（或等效序列化方法）以及必要的 `#include` / 宏守卫。

常见需求示例：

- “把 snake_case 字段改成驼峰命名”
- “输出为 `MyApp::Models` 命名空间下的 class”
- “把结果保存到 `generated/config.hpp` 和 `generated/config.cpp`”

示例指令：

```bash
将 {"id":1,"name":"CppBot","features":["json","docker","mcp"],"meta":{"owner":"lab","ready":true}} 转成 struct 命名为 CppBotConfig，放到命名空间 CodeGen
```

示例输出节选：

```cpp
namespace CodeGen {

struct CppBotConfig {
  int id;
  std::string name;
  std::vector<std::string> features;
  struct Meta {
    std::string owner;
    bool ready;
  } meta;
};

inline void to_json(nlohmann::json& j, const CppBotConfig& value) {
  j = { {"id", value.id}, {"name", value.name}, {"features", value.features}, {"meta", value.meta} };
}

inline void from_json(const nlohmann::json& j, CppBotConfig& value) {
  j.at("id").get_to(value.id);
  j.at("name").get_to(value.name);
  j.at("features").get_to(value.features);
  j.at("meta").get_to(value.meta);
}

} // namespace CodeGen
```

> 注：如需扩展到其他语言或模版，只需在 `tasks/` 目录中新增任务实现，并在 Chatbot 中注册相应命令。

**Word 表格转 JSON**
- 运行 `uv run python tasks/word_table_export/export_tables.py input.docx -o tables.json` 即可提取指定 Word 文档内的所有表格。
- 默认将首行视为表头，自动转换为键值结构；若需保留原始行，可添加 `--no-header`。
- 通过 `--keep-empty` 控制是否保留空行，`--indent 0` 可输出紧凑 JSON。
- 输出格式示例：

```json
{
  "source": "/path/to/input.docx",
  "table_count": 2,
  "tables": [
    {
      "index": 0,
      "headers": ["Name", "Value"],
      "rows": [
        {"Name": "Foo", "Value": "123"},
        {"Name": "Bar", "Value": "456"}
      ]
    }
  ]
}
```

**Word 表格 MCP 服务**
1. 构建镜像：`docker build -t yxi-word-mcp -f tasks/word_table_export/Dockerfile .`
2. 运行服务（映射 8000 端口，可挂载文档目录）：
   `docker run --rm -p 8010:8000 -v "$PWD/samples:/data" yxi-word-mcp`
3. 在 Chatbot 中注册节点：`/mcp add wordtables http://localhost:8010`
4. 调用工具示例：`/mcp invoke word_tables_to_json {"doc_path":"/data/demo.docx","options":{"keep_empty_rows":false}}`
5. 若需直接发送文件，可先 `base64 input.docx | tr -d "\n"`，将输出填入 `doc_base64` 字段。



# 启动两个 MCP 服务（假设 word_table_export 在 8000，json_to_java 在 8030）
# uv run python tasks/word_table_export/mcp_service.py
# uv run python tasks/json_to_java/mcp_service.py

# 运行智能体
直接使用 uv 运行
```
uv run python tasks/json_to_java/langgraph_agent.py ./samples/demo.docx \
  --word-url http://localhost:8000 \
  --java-url http://localhost:8030 \
  --package com.example.demo \
  --class-name Root \
  --output-path /tmp/Output.java
```

智能体调用文档转代码
```
/agent doc2java ./samples/demo.docx --word-url http://localhost:8000 --java-url http://localhost:8030 --package com.example.demo --class-name Root --output-path /tmp/Output.java
```


使用 docker 运行
```
docker run --rm -p 8000:8000 -v "$PWD/samples:/data" yxi-word-mcp
```

```
docker run --rm -p 8030:8030 -v "$PWD/output:/out" yxi-json-to-java
```

```
/agent doc2java /data/demo.docx --word-url http://localhost:8000 --java-url http://localhost:8030 --package com.example.demo --class-name Root --output-path /out/Output.java 
```
另外一种运行方式
```
/agent doc2java /data/demo.docx --package com.example.demo --class-name Root --output-path /out/Output.java
```
## ⚠️ 免责声明

- 本项目为实验性工具，仅供学习与内部研发使用，不保证在生产环境中的稳定性与安全性。
- 由于不当配置、第三方依赖或生成代码导致的任何数据丢失、服务中断或安全问题，作者概不负责。
- 如需在受监管或商用场景使用，请自行完成安全评估、代码审计与合规检查，并承担相应风险。

