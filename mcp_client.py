"""Lightweight MCP client helpers for yxi-chat-cli."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import requests

CONFIG_PATH = os.path.expanduser("~/.yxi_mcp_nodes.json")
DEFAULT_TIMEOUT = 30


@dataclass
class MCPNode:
    """Represents a registered MCP node."""

    name: str
    url: str
    token: Optional[str] = None


class MCPClient:
    """Manages MCP nodes and wraps simple HTTP interactions."""

    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self.nodes: Dict[str, MCPNode] = {}
        self.active_name: Optional[str] = None
        self._load_state()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load_state(self) -> None:
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return

        nodes_payload = payload.get("nodes", {}) if isinstance(payload, dict) else {}
        for name, meta in nodes_payload.items():
            if not isinstance(meta, dict):
                continue
            url = meta.get("url")
            if not url:
                continue
            self.nodes[name] = MCPNode(name=name, url=url, token=meta.get("token"))

        active_candidate = payload.get("active")
        if active_candidate in self.nodes:
            self.active_name = active_candidate

    def _save_state(self) -> None:
        dirname = os.path.dirname(self.config_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        payload = {
            "active": self.active_name if self.active_name in self.nodes else None,
            "nodes": {name: asdict(node) for name, node in self.nodes.items()},
        }
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------
    def list_nodes(self) -> List[MCPNode]:
        return sorted(self.nodes.values(), key=lambda node: node.name.lower())

    def add_node(self, name: str, url: str, token: Optional[str] = None) -> None:
        if not name or not url:
            raise ValueError("Both name and URL are required")
        self.nodes[name] = MCPNode(name=name, url=url.rstrip("/"), token=token)
        if not self.active_name:
            self.active_name = name
        self._save_state()

    def remove_node(self, name: str) -> None:
        if name not in self.nodes:
            raise ValueError(f"MCP node '{name}' not found")
        del self.nodes[name]
        if self.active_name == name:
            self.active_name = next(iter(self.nodes), None)
        self._save_state()

    def set_active(self, name: str) -> None:
        if name not in self.nodes:
            raise ValueError(f"MCP node '{name}' not found")
        self.active_name = name
        self._save_state()

    def get_active_node(self) -> Optional[MCPNode]:
        if self.active_name and self.active_name in self.nodes:
            return self.nodes[self.active_name]
        return None

    # ------------------------------------------------------------------
    # HTTP utilities
    # ------------------------------------------------------------------
    def _headers_for(self, node: MCPNode) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if node.token:
            headers["Authorization"] = f"Bearer {node.token}"
        return headers

    def list_tools(self, node_name: Optional[str] = None) -> List[Dict[str, Any]]:
        node = self.nodes.get(node_name) if node_name else self.get_active_node()
        if not node:
            raise ValueError("No active MCP node configured")

        response = requests.get(
            f"{node.url}/tools",
            headers=self._headers_for(node),
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "tools" in payload:
            tools = payload["tools"]
        else:
            tools = payload
        return tools if isinstance(tools, list) else []

    def invoke_tool(
        self,
        tool_name: str,
        payload: Dict[str, Any],
        *,
        node_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not tool_name:
            raise ValueError("Tool name is required")

        node = self.nodes.get(node_name) if node_name else self.get_active_node()
        if not node:
            raise ValueError("No active MCP node configured")

        body: Dict[str, Any] = {"input": payload}
        if context:
            body["context"] = context

        response = requests.post(
            f"{node.url}/tools/{tool_name}",
            headers=self._headers_for(node),
            json=body,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json() if response.content else {"ok": True}
