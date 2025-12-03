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

### 5. 使用示例

在 Chatbot 终端输入自然语言或命令，示例：

```bash
# 添加 MCP 服务器
/mcp add LocalMCP http://localhost:8000

# 将 JSON 转成 C++ 类
将 {"name":"Alice","age":30,"address":{"city":"NY"}} 转成 class Person

# 列出已添加的 MCP
/mcp list

# 调用 MCP 工具
/mcp invoke json_to_cpp {"schema":{"name":"Demo"}}
```

## 📋 核心功能

**MCP 服务器管理**
- `/mcp add <name> <url> [token]`：添加 MCP 节点，例如 `/mcp add DevMCP http://192.168.1.100:8000`。
- `/mcp list`：列出已配置的 MCP 节点。
- `/mcp use <name>`：切换当前活跃的 MCP。
- `/mcp remove <name>`：删除指定 MCP。
- `/mcp tools [name]`：列出活跃或指定节点公开的工具。
- `/mcp invoke <tool> <json_payload>`：执行 MCP 工具，payload 必须是合法 JSON。

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

## ⚠️ 免责声明

- 本项目为实验性工具，仅供学习与内部研发使用，不保证在生产环境中的稳定性与安全性。
- 由于不当配置、第三方依赖或生成代码导致的任何数据丢失、服务中断或安全问题，作者概不负责。
- 如需在受监管或商用场景使用，请自行完成安全评估、代码审计与合规检查，并承担相应风险。

