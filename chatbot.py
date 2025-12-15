#!/usr/bin/env python3
# yxi_chat.py - 终端多轮对话原型 (yxi.ai CLI)
# 保存为 yxi_chat.py 后运行: chmod +x yxi_chat.py && ./yxi_chat.py

import os
import json
import re
import subprocess
import sys
from typing import Any, Dict, List

import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
import argparse

from mcp_client import MCPClient

# 配置 (实际产品中应从 ~/.yxi/config 读取)
API_BASE = os.getenv("YXI_API_BASE_URL", "https://yxi.ai/v1")  # 可使用 YXI_API_BASE_URL 覆盖
ENV_API_KEY = os.getenv("YXI_API_KEY")
API_KEY = ENV_API_KEY or "YOUR_API_KEY_HERE"
MODEL = os.getenv("YXI_MODEL", "yxi-7b-terminal")
HISTORY_FILE = os.path.expanduser("~/.yxi_chat_history.json")
CONFIG_FILE = os.path.expanduser("~/.yxi_chat_config.json")

console = Console()
mcp_client = MCPClient()

MODE_ONLINE = "online"
MODE_OFFLINE = "offline"

chat_state = {
    "mode": MODE_ONLINE,
    "offline_node": None,
    "model": MODEL,
    "api_key": API_KEY,
}


def _format_json_blob(payload):
    """Return a pretty JSON dump or string fallback."""
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except TypeError:
        return str(payload)


def current_api_key() -> str:
    key = chat_state.get("api_key") or ""
    if key == "YOUR_API_KEY_HERE":
        return ""
    return key


def online_available() -> bool:
    return bool(current_api_key())


def current_model() -> str:
    return chat_state.get("model") or MODEL


def show_help():
    """Render a quick reference of available commands."""
    lines = [
        "[bold]/help[/bold] — 显示本帮助",
        "[bold]/apikey set|clear[/bold] — 设置或清除云端 API key",
        "[bold]/model list|use|default[/bold] — 查看或切换云端模型",
        "[bold]/mode online|offline <node>[/bold] — 切换在线/离线模式",
        "[bold]/mcp ...[/bold] — 管理 MCP 节点（add/list/use/remove/tools/invoke）",
        "[bold]/copy[/bold] (/c) — 复制最近一次助理回复中的代码块（若存在）",
        "[bold]/clear[/bold] — 清空上下文（保留 system prompt）",
        "[bold]/history[/bold] — 查看最近对话摘要",
        "[bold]/exit[/bold] — 退出并保存",
        "离线模式下直接输入 `<tool> <json>` 即可调用 MCP 工具",
        "[bold]/agent doc2java <doc_path> [--word-url ... --java-url ... --package ... --class-name ... --output-path ...][/bold]",
    ]
    panel = Panel("\n".join(lines), title="指令速查", border_style="cyan")
    console.print(panel)


def fetch_model_list() -> List[Dict[str, Any]]:
    """Retrieve available models from the API."""
    if not online_available():
        console.print("[yellow]Cannot fetch models: API key missing. Use /apikey set <value> first.[/yellow]")
        return []

    headers = {"Authorization": f"Bearer {current_api_key()}"}
    try:
        response = requests.get(f"{API_BASE}/models", headers=headers, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        console.print(f"[red]Failed to fetch models:[/red] {exc}")
        return []
    except ValueError:
        console.print("[red]Model list response is not valid JSON.[/red]")
        return []

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "models", "items"):
            items = payload.get(key)
            if isinstance(items, list):
                return items
        # Some APIs return a dict keyed by id
        if all(isinstance(k, str) for k in payload.keys()):
            return [
                {"id": key, **value} if isinstance(value, dict) else {"id": key, "name": value}
                for key, value in payload.items()
            ]
    return []


def set_current_model(model_name: str, persist: bool = False):
    """Update the active model and optionally persist as default."""
    chat_state["model"] = model_name
    if persist:
        config_state["default_model"] = model_name
        save_config(config_state)


def handle_model_command(raw_command: str):
    """Manage model listing and selection."""
    command = (raw_command or "").strip()
    if not command:
        console.print(
            f"[cyan]Current model: {current_model()}[/cyan] — /model list | /model use <name> | /model default <name>"
        )
        return True

    parts = command.split(maxsplit=1)
    action = parts[0].lower()
    remainder = parts[1].strip() if len(parts) > 1 else ""

    if action in {"list", "ls"}:
        models = fetch_model_list()
        if not models:
            console.print("[yellow]No models were returned by the API.[/yellow]")
            return True
        lines = []
        current = current_model()
        for item in models:
            if isinstance(item, dict):
                identifier = item.get("id") or item.get("name") or item.get("model") or "unknown"
                desc = item.get("description") or item.get("display_name") or ""
            else:
                identifier = str(item)
                desc = ""
            prefix = "⭐" if identifier == current else " "
            line = f"{prefix} [bold]{identifier}[/bold]"
            if desc:
                line += f" — {desc}"
            lines.append(line)
        console.print(Panel("\n".join(lines), title="Available Models", border_style="cyan"))
        return True

    if action in {"use", "set"}:
        if not remainder:
            console.print("[red]Usage: /model use <model_name>[/red]")
            return True
        set_current_model(remainder, persist=False)
        console.print(f"[green]Switched to model '{remainder}'.[/green]")
        return True

    if action in {"default", "set-default"}:
        if not remainder:
            console.print("[red]Usage: /model default <model_name>[/red]")
            return True
        set_current_model(remainder, persist=True)
        console.print(f"[green]Default model set to '{remainder}'.[/green]")
        return True

    console.print(f"[red]Unknown model action: {action}[/red]")
    return True

def load_history():
    """加载历史对话"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except:
            return []
    return [{"role": "system", "content": "你是一个终端助手，用简洁专业的语言回答问题。代码用Markdown格式。"}]

def save_history(messages):
    """保存对话历史"""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(messages[-20:], f)  # 保留最近20条


def load_config() -> Dict[str, Any]:
    """Load user preferences such as default model."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            console.print(f"[yellow]Failed to read {CONFIG_FILE}: {exc}[/yellow]")
    return {}


def save_config(config: Dict[str, Any]):
    """Persist user preferences to disk."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as exc:
        console.print(f"[red]Unable to save config: {exc}[/red]")


config_state = load_config()
if config_state.get("default_model"):
    chat_state["model"] = config_state["default_model"]
stored_api_key = config_state.get("api_key")
if stored_api_key and not ENV_API_KEY:
    chat_state["api_key"] = stored_api_key

def stream_completion(messages):
    """流式调用 yxi.ai API"""
    if not online_available():
        console.print("[bold yellow]Online mode unavailable. Set YXI_API_KEY or run /apikey set <value> to re-enable cloud responses.[/bold yellow]")
        return ""

    headers = {
        "Authorization": f"Bearer {current_api_key()}",
        "Content-Type": "application/json"
    }
    data = {
        "model": current_model(),
        "messages": messages,
        "stream": True,
        "temperature": 0.3
    }
    
    try:
        with requests.post(
            f"{API_BASE}/chat/completions",
            json=data,
            headers=headers,
            stream=True,
            timeout=30,
        ) as response:
            response.raise_for_status()
            full_reply = ""

            # 使用 Rich 实现流式输出面板
            with Live(
                Panel(Text(""), title="🤖 yxi.ai • ⧉ /copy", border_style="blue"),
                console=console,
                refresh_per_second=10,
            ) as live:
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    chunk = raw_line.decode("utf-8").strip()

                    # 兼容 OpenAI 风格的 SSE："data: {...}" / "data: [DONE]"
                    if chunk.startswith("data:"):
                        payload_str = chunk[len("data:") :].strip()
                    else:
                        payload_str = chunk

                    if payload_str in {"[DONE]", "data: [DONE]"}:
                        break

                    try:
                        event = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue

                    choice = (event.get("choices") or [{}])[0]
                    delta = choice.get("delta") or choice.get("message") or {}
                    content = delta.get("content") or ""
                    if not content:
                        continue

                    full_reply += content
                    live.update(
                        Panel(
                            Markdown(full_reply),
                            title="🤖 yxi.ai • ⧉ /copy",
                            border_style="blue",
                        )
                    )

            return full_reply
    except Exception as e:
        console.print(f"[bold red]API Error:[/bold red] {str(e)}")
        return ""


def handle_mcp_command(raw_command, messages):
    """Parse and execute MCP-related slash commands."""
    command = (raw_command or "").strip()
    if not command:
        console.print("[yellow]Usage: /mcp <add|list|use|remove|tools|invoke> ...[/yellow]")
        return True

    action, *rest = command.split(maxsplit=1)
    remainder = rest[0] if rest else ""

    try:
        if action.lower() == "list":
            nodes = mcp_client.list_nodes()
            if not nodes:
                console.print("[yellow]No MCP nodes configured. Use /mcp add <name> <url>[/yellow]")
                return True
            active = mcp_client.active_name
            lines = []
            for node in nodes:
                prefix = "⭐" if node.name == active else " "
                token_hint = " (token)" if node.token else ""
                lines.append(f"{prefix} [bold]{node.name}[/bold] → {node.url}{token_hint}")
            console.print(Panel("\n".join(lines), title="MCP Nodes", border_style="cyan"))
            return True

        if action.lower() == "add":
            add_parts = remainder.split()
            if len(add_parts) < 2:
                console.print("[red]Usage: /mcp add <name> <url> [token][/red]")
                return True
            name, url, *maybe_token = add_parts
            token = maybe_token[0] if maybe_token else None
            mcp_client.add_node(name, url, token)
            console.print(f"[green]Added MCP node '{name}' → {url}[/green]")
            return True

        if action.lower() in {"use", "select"}:
            target = remainder.strip()
            if not target:
                console.print("[red]Usage: /mcp use <name>[/red]")
                return True
            mcp_client.set_active(target)
            console.print(f"[green]Active MCP set to '{target}'[/green]")
            return True

        if action.lower() == "remove":
            target = remainder.strip()
            if not target:
                console.print("[red]Usage: /mcp remove <name>[/red]")
                return True
            mcp_client.remove_node(target)
            console.print(f"[green]Removed MCP node '{target}'[/green]")
            return True

        if action.lower() == "tools":
            node_name = remainder.strip() or None
            tools = mcp_client.list_tools(node_name=node_name)
            if not tools:
                console.print("[yellow]No tools reported by the MCP node.[/yellow]")
                return True
            lines = []
            for item in tools:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("id") or "unnamed"
                    desc = item.get("description") or ""
                    lines.append(f"[bold]{name}[/bold] — {desc}")
                else:
                    lines.append(str(item))
            title = f"MCP Tools ({node_name or mcp_client.active_name})"
            console.print(Panel("\n".join(lines), title=title, border_style="magenta"))
            return True

        if action.lower() in {"invoke", "run", "call"}:
            if not remainder:
                console.print("[red]Usage: /mcp invoke <tool_name> <json_payload>[/red]")
                return True
            invoke_parts = remainder.split(maxsplit=1)
            if len(invoke_parts) < 2:
                console.print("[red]Usage: /mcp invoke <tool_name> <json_payload>[/red]")
                return True
            tool_name, payload_raw = invoke_parts
            try:
                payload_obj = json.loads(payload_raw)
            except json.JSONDecodeError as exc:
                console.print(f"[red]Invalid JSON payload: {exc}[/red]")
                return True

            context = {
                "chat_history": messages[-6:],
            }
            result = mcp_client.invoke_tool(tool_name, payload_obj, context=context)
            formatted = _format_json_blob(result)
            console.print(
                Panel(
                    Markdown(f"```json\n{formatted}\n```"),
                    title=f"MCP • {tool_name} • ⧉ /copy",
                    border_style="green",
                )
            )
            messages.append({"role": "assistant", "content": f"[MCP:{tool_name}]\n{formatted}"})
            return True

        console.print(f"[red]Unknown MCP action: {action}[/red]")
        return True

    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return True
    except requests.RequestException as exc:
        console.print(f"[red]MCP network error:[/red] {exc}")
        return True


def handle_api_key_command(raw_command: str):
    """Allow setting or clearing the API key without restarting."""
    command = (raw_command or "").strip()
    if not command:
        status = "已配置" if online_available() else "未配置"
        console.print(f"[cyan]API key 状态：{status}[/cyan]")
        console.print("[yellow]Usage: /apikey set <value> | /apikey clear[/yellow]")
        return True

    action, *rest = command.split(maxsplit=1)
    action = action.lower()

    if action == "set":
        if not rest:
            console.print("[red]Usage: /apikey set <value>[/red]")
            return True
        new_key = rest[0].strip()
        if not new_key:
            console.print("[red]API key 不能为空[/red]")
            return True
        chat_state["api_key"] = new_key
        config_state["api_key"] = new_key
        save_config(config_state)
        console.print("[green]API key 已更新（保存在 ~/.yxi_chat_config.json，纯文本存储，请注意风险）。[/green]")
        return True

    if action in {"clear", "remove"}:
        chat_state["api_key"] = "YOUR_API_KEY_HERE"
        if config_state.pop("api_key", None) is not None:
            save_config(config_state)
        console.print("[yellow]API key 已清除，在线模式将不可用，直到重新设置或导出 YXI_API_KEY。[/yellow]")
        return True

    console.print(f"[red]Unknown apikey action: {action}[/red]")
    return True


def run_doc2java_agent(args: List[str]):
    """Run the langgraph doc->java agent from terminal."""
    parser = argparse.ArgumentParser(prog="/agent doc2java", add_help=False)
    parser.add_argument("doc_path")
    parser.add_argument("--word-url", default="http://localhost:8000")
    parser.add_argument("--java-url", default="http://localhost:8030")
    parser.add_argument("--package", dest="package", default=None)
    parser.add_argument("--class-name", dest="class_name", default=None)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--output-path", dest="output_path", default=None)
    try:
        opts = parser.parse_args(args)
    except SystemExit:
        console.print("[red]用法: /agent doc2java <doc_path> [--word-url ... --java-url ... --package ... --class-name ... --output-path ...][/red]")
        return True

    from tasks.json_to_java.langgraph_agent import build_graph

    state = {
        "doc_path": opts.doc_path,
        "word_service_url": opts.word_url,
        "java_service_url": opts.java_url,
        "package": opts.package,
        "class_name": opts.class_name,
        "max_depth": opts.max_depth,
        "output_path": opts.output_path,
    }
    app = build_graph().compile()
    result = app.invoke(state)
    java_code = result.get("java_code")
    output_path = result.get("output_path")
    if output_path:
        console.print(f"[green]Java 已写入: {output_path}[/green]")
    if java_code:
        console.print(Panel(Markdown(f"```java\n{java_code}\n```"), title="Java Output", border_style="green"))
    return True


def handle_mode_command(raw_command: str):
    """Switch between online/cloud mode and offline MCP mode."""
    command = (raw_command or "").strip()
    if not command:
        offline_hint = chat_state.get("offline_node") or "(not set)"
        console.print(
            f"[cyan]Current mode: {chat_state['mode']}[/cyan] — offline node: {offline_hint}"
        )
        console.print("[yellow]Usage: /mode online | /mode offline <node_name>[/yellow]")
        return True

    parts = command.split()
    target_mode = parts[0].lower()

    if target_mode == MODE_ONLINE:
        chat_state["mode"] = MODE_ONLINE
        chat_state["offline_node"] = None
        console.print("[green]Switched to online mode.[/green]")
        if not online_available():
            console.print("[red]API key missing. Use /apikey set <value> or export YXI_API_KEY before chatting online.[/red]")
        return True

    if target_mode == MODE_OFFLINE:
        node_name = parts[1] if len(parts) > 1 else mcp_client.active_name
        if not node_name:
            console.print("[red]Specify a node: /mode offline <node_name>[/red]")
            return True
        if node_name not in mcp_client.nodes:
            console.print(f"[red]Unknown MCP node: {node_name}[/red]")
            return True
        chat_state["mode"] = MODE_OFFLINE
        chat_state["offline_node"] = node_name
        console.print(f"[green]Switched to offline mode targeting MCP '{node_name}'.[/green]")
        return True

    console.print("[red]Unknown mode. Use 'online' or 'offline'.[/red]")
    return True


def handle_offline_input(user_input: str, messages: List[Dict[str, Any]]):
    """Interpret user input as direct MCP tool invocations while offline."""
    stripped = (user_input or "").strip()
    if not stripped:
        console.print("[yellow]Offline mode expects '<tool> <json>' or '<node> <tool> <json>'.[/yellow]")
        return True

    parts = stripped.split(maxsplit=2)
    if len(parts) < 2:
        console.print("[red]Provide at least a tool name and JSON payload.[/red]")
        return True

    if len(parts) == 2:
        node_name = chat_state.get("offline_node")
        tool_name, payload_raw = parts
    else:
        node_name, tool_name, payload_raw = parts

    if not payload_raw:
        console.print("[red]Missing JSON payload.[/red]")
        return True

    if not node_name:
        console.print("[red]No offline node configured. Run /mode offline <node_name> first or prefix the command with the node name.[/red]")
        return True

    if node_name not in mcp_client.nodes:
        console.print(f"[red]Unknown MCP node: {node_name}[/red]")
        return True

    try:
        payload_obj = json.loads(payload_raw)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid JSON payload: {exc}[/red]")
        return True

    messages.append({"role": "user", "content": user_input})
    context = {"mode": MODE_OFFLINE, "chat_history": messages[-6:]}

    try:
        result = mcp_client.invoke_tool(
            tool_name,
            payload_obj,
            node_name=node_name,
            context=context,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return True
    except requests.RequestException as exc:
        console.print(f"[red]MCP network error:[/red] {exc}")
        return True

    formatted = _format_json_blob(result)
    console.print(
        Panel(
            Markdown(f"```json\n{formatted}\n```"),
            title=f"MCP • {tool_name} @ {node_name} • ⧉ /copy",
            border_style="green",
        )
    )
    messages.append({"role": "assistant", "content": f"[MCP:{tool_name}@{node_name}]\n{formatted}"})
    console.print()
    return True


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard on macOS using pbcopy."""
    try:
        proc = subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def extract_code_block(message: str) -> str:
    """Return the first fenced code block content if present."""
    match = re.search(r"```[a-zA-Z0-9_+\-]*\n(.*?)```", message, re.S)
    if match:
        return match.group(1).rstrip()
    return ""


def handle_copy_command(messages: List[Dict[str, Any]]):
    """Copy the latest assistant reply code block (or full reply) to clipboard."""
    last_assistant = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
    if not last_assistant:
        console.print("[yellow]没有可复制的助理回复。[/yellow]")
        return True

    content = last_assistant.get("content") or ""
    block = extract_code_block(content)
    payload = block if block else content
    if not payload.strip():
        console.print("[yellow]助理回复为空，无法复制。[/yellow]")
        return True

    if copy_to_clipboard(payload):
        console.print("[green]已复制到剪贴板。[/green]" + (" (复制了代码块)" if block else ""))
    else:
        console.print("[red]复制失败：未找到 pbcopy（仅支持 macOS 默认环境）。[/red]")
    return True

def main():
    console.print("[bold green]🚀 yxi chat (prototype) - Type /exit to quit, /clear to reset context[/bold green]\n")
    
    # 加载历史
    messages = load_history()
    
    while True:
        try:
            # 使用内置 input()，并避免表情等宽字符以兼容中文删除
            user_input = input("You > ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold blue]👋 Session saved. Bye![/bold blue]")
            save_history(messages)
            sys.exit(0)

        if user_input.lower().startswith('/mcp'):
            handle_mcp_command(user_input[4:], messages)
            continue

        # 处理特殊命令
        if user_input.lower().startswith('/mode'):
            handle_mode_command(user_input[5:])
            continue

        if user_input.lower().startswith('/apikey'):
            handle_api_key_command(user_input[7:])
            continue

        if user_input.lower().startswith('/model'):
            handle_model_command(user_input[6:])
            continue

        if user_input.lower().startswith('/copy') or user_input.lower().startswith('/c'):
            handle_copy_command(messages)
            continue

        if user_input.startswith('/'):
            cmd_name, *cmd_rest = user_input[1:].split(maxsplit=1)
            cmd = cmd_name.lower()
            if cmd in ('exit', 'quit'):
                save_history(messages)
                console.print("[bold blue]👋 Session saved. Bye![/bold blue]")
                sys.exit(0)
            elif cmd == 'clear':
                messages = [messages[0]]  # 保留 system prompt
                console.print("[bold yellow]🧹 Context cleared[/bold yellow]\n")
                continue
            elif cmd == 'history':
                console.print(Panel(
                    "\n".join([f"[blue]{m['role']}[/blue]: {m['content'][:50]}..." 
                              for m in messages[1:]] or ["No history"]),
                    title="📜 Chat History",
                    border_style="yellow"
                ))
                continue
            elif cmd == 'agent':
                sub = cmd_rest[0] if cmd_rest else ""
                sub_parts = sub.split()
                if not sub_parts:
                    console.print("[red]Usage: /agent doc2java <doc_path> [...options][/red]")
                    continue
                agent_name, *agent_args = sub_parts
                if agent_name == 'doc2java':
                    run_doc2java_agent(agent_args)
                    continue
                console.print(f"[red]Unknown agent: {agent_name}[/red]")
                continue
            elif cmd == 'help':
                show_help()
                continue
            else:
                console.print(f"[bold red]❓ Unknown command: /{cmd}[/bold red]")
                continue

        if chat_state.get("mode") == MODE_OFFLINE:
            handled = handle_offline_input(user_input, messages)
            if handled:
                continue

        # 添加用户消息
        messages.append({"role": "user", "content": user_input})
        
        # 获取 AI 响应
        reply = stream_completion(messages)
        
        if reply:
            messages.append({"role": "assistant", "content": reply})
            
        console.print()  # 空行分隔

if __name__ == "__main__":
    # 检查 API 密钥
    if not online_available():
        console.print("[bold yellow]⚠️  No usable API key found. Export YXI_API_KEY or run /apikey set <value> after launch.[/bold yellow]")
        console.print("Example: export YXI_API_KEY='your_actual_key'")

    main()