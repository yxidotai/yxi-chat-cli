"""MCP HTTP 服务共享安全工具 (v1.23.x 安全加固 CLI-C1/H1/H2/H3)

提供:
  - get_service_token: 服务令牌管理(环境变量 → 0600 令牌文件 → 自动生成)
  - require_token 工厂: FastAPI 依赖,对 /tools/* 强制 Bearer 令牌校验
  - safe_resolve / ensure_within: 路径白名单限制(防路径遍历逃逸)

令牌来源优先级:
  1. 服务专属环境变量(如 PLAYWRIGHT_TOKEN / JSON_TO_JAVA_TOKEN / WORD_MCP_TOKEN)
  2. 共享环境变量 YXI_MCP_TOKEN
  3. 持久化令牌文件 ~/.yxi_mcp_tokens/<service>.token(0600;不存在则生成并落盘)
主服务(mcp_client)对本机回环节点可读取同一令牌文件完成调用。
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request

def _token_dir() -> Path:
    """令牌目录(动态读取环境变量,便于测试隔离)。"""
    return Path(os.getenv("YXI_MCP_TOKEN_DIR", "~/.yxi_mcp_tokens")).expanduser()


def get_service_token(service: str, env_var: Optional[str] = None) -> str:
    """获取服务令牌;必要时生成并持久化为 0600 文件。"""
    for var in (env_var, "YXI_MCP_TOKEN"):
        if var:
            value = os.getenv(var)
            if value:
                return value

    token_dir = _token_dir()
    token_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    token_file = token_dir / f"{service}.token"
    if token_file.exists():
        token = token_file.read_text(encoding="utf-8").strip()
        if token:
            try:
                os.chmod(token_file, 0o600)
            except OSError:
                pass
            return token

    token = secrets.token_urlsafe(32)
    # 原子写入 + 0600 权限(避免先写后 chmod 的竞态)
    fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token)
    print(f"[mcp_auth] generated token for {service}: {token_file}")
    return token


def make_token_dependency(service: str, env_var: Optional[str] = None):
    """构造 FastAPI 依赖:校验 Authorization: Bearer 或 ?token=。"""

    def dependency(request: Request) -> None:
        expected = get_service_token(service, env_var)
        header = request.headers.get("Authorization", "")
        provided = ""
        if header.startswith("Bearer "):
            provided = header[len("Bearer "):]
        else:
            provided = request.query_params.get("token", "")
        if not provided or not secrets.compare_digest(provided, expected):
            raise HTTPException(status_code=401, detail="Unauthorized")

    return dependency


def ensure_within(root: Path, user_path: str) -> Path:
    """把用户路径限制在 root 之下,防路径遍历逃逸(../、符号链接)。"""
    root_resolved = root.expanduser().resolve()
    candidate = Path(user_path).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (root_resolved / candidate).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise HTTPException(
            status_code=400,
            detail=f"path escapes allowed directory: {user_path}",
        )
    return resolved


def read_root() -> Path:
    """允许读取的根目录(默认用户家目录;env 可收紧)。"""
    return Path(os.getenv("MCP_ALLOW_READ_DIR", "~/")).expanduser()


def write_root() -> Path:
    """允许写入的根目录(默认 ~/yxi-mcp-output;env 可调整)。"""
    return Path(os.getenv("MCP_ALLOW_WRITE_DIR", "~/yxi-mcp-output")).expanduser()
