#!/usr/bin/env python3
# yxi_chat.py - 终端多轮对话原型 (yxi.ai CLI)
# 保存为 yxi_chat.py 后运行: chmod +x yxi_chat.py && ./yxi_chat.py

import os
import json
import sys
from typing import Any, Dict, List

import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from mcp_client import MCPClient

# 配置 (实际产品中应从 ~/.yxi/config 读取)
API_BASE = "https://api.yxi.ai/v1"  # 替换为你的 yxi.ai 端点
API_KEY = os.getenv("YXI_API_KEY") or "YOUR_API_KEY_HERE"
MODEL = "yxi-7b-terminal"
HISTORY_FILE = os.path.expanduser("~/.yxi_chat_history.json")

console = Console()
mcp_client = MCPClient()

MODE_ONLINE = "online"
MODE_OFFLINE = "offline"

chat_state = {
    "mode": MODE_ONLINE,
    "offline_node": None,
}


def _format_json_blob(payload):
    """Return a pretty JSON dump or string fallback."""
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except TypeError:
        return str(payload)


def online_available() -> bool:
    return bool(API_KEY) and API_KEY != "YOUR_API_KEY_HERE"

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

def stream_completion(messages):
    """流式调用 yxi.ai API"""
    if not online_available():
        console.print("[bold yellow]Online mode unavailable. Set YXI_API_KEY to re-enable cloud responses.[/bold yellow]")
        return ""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
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
            timeout=30
        ) as response:
            response.raise_for_status()
            full_reply = ""
            
            # 使用 Rich 实现流式输出面板
            with Live(
                Panel(Text(""), title="🤖 yxi.ai", border_style="blue"),
                console=console,
                refresh_per_second=10
            ) as live:
                for line in response.iter_lines():
                    if line:
                        chunk = line.decode('utf-8').strip()
                        if chunk.startswith(' ') and chunk != ' [DONE]':
                            try:
                                content = json.loads(chunk[6:])["choices"][0]["delta"].get("content", "")
                                if content:
                                    full_reply += content
                                    live.update(Panel(Markdown(full_reply), title="🤖 yxi.ai", border_style="blue"))
                            except:
                                continue
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
                    title=f"MCP • {tool_name}",
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
            console.print("[red]YXI_API_KEY missing. Online completions will fail until it is set.[/red]")
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
            title=f"MCP • {tool_name} @ {node_name}",
            border_style="green",
        )
    )
    messages.append({"role": "assistant", "content": f"[MCP:{tool_name}@{node_name}]\n{formatted}"})
    console.print()
    return True

def main():
    console.print("[bold green]🚀 yxi chat (prototype) - Type /exit to quit, /clear to reset context[/bold green]\n")
    
    # 加载历史
    messages = load_history()
    
    while True:
        try:
            user_input = Prompt.ask("[bold yellow]💬 You[/bold yellow]")
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
        console.print("[bold yellow]⚠️  No usable YXI_API_KEY found. Online mode will be unavailable until you export YXI_API_KEY.[/bold yellow]")
        console.print("Example: export YXI_API_KEY='your_actual_key'")

    main()