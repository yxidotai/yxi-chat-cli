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

# 安装项目依赖（示例）
pip install -r requirements.txt

# 如果只需 chat 客户端的最小依赖
pip install requests
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
python mcp.py   # 默认监听 http://localhost:8000（如需修改请查看 mcp 配置）
```

2. 启动终端 Chatbot（在项目根目录，新终端）：

```bash
python chatbot.py
```

### 5. 使用示例

在 Chatbot 终端输入自然语言或命令，示例：

```bash
# 添加 MCP 服务器
add mcp LocalMCP http://localhost:8000

# 将 JSON 转成 C++ 类
将 {"name":"Alice","age":30,"address":{"city":"NY"}} 转成 class Person

# 列出已添加的 MCP
list mcps
```

## 📋 核心功能

**MCP 服务器管理**
- `add mcp <name> <url>`：添加 MCP 节点，例如 `add mcp DevMCP http://192.168.1.100:8000`。
- `list mcps`：列出已配置的 MCP 节点。
- `use mcp <name>`：切换当前活跃的 MCP。
- `remove mcp <name>`：删除指定 MCP。

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

