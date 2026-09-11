#!/usr/bin/env python3
"""
Web 会话令牌与 Origin 校验 (CLI-H4)

- 首次启动时用 secrets.token_urlsafe(32) 生成会话令牌,
  持久化到 0600 权限的 ~/.yxi_web_token(已存在则复用)
- API/WebSocket 支持 Authorization: Bearer、query ?token= 与 HttpOnly cookie
- WebSocket Origin 白名单校验(空 Origin 视为非浏览器客户端,放行)
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Optional, Set

from fastapi import HTTPException, Request, WebSocket

logger = logging.getLogger(__name__)

# 会话 cookie 名(index 路由用 ?token= 换取 HttpOnly cookie)
SESSION_COOKIE_NAME = 'yxi_session'

# Web 服务默认端口(与 server.py --port 默认一致)
DEFAULT_WEB_PORT = 8080

# WebSocket 鉴权失败关闭码
WS_CLOSE_UNAUTHORIZED = 4001
# WebSocket Origin 校验失败关闭码
WS_CLOSE_BAD_ORIGIN = 4003


def get_token_file() -> Path:
    """令牌文件路径,可用 YXI_WEB_TOKEN_FILE 覆盖(便于测试)"""
    default = Path.home() / '.yxi_web_token'
    return Path(os.getenv('YXI_WEB_TOKEN_FILE', str(default)))


def load_or_create_token(token_file: Optional[Path] = None) -> str:
    """读取会话令牌;不存在时生成新令牌并以 0600 权限写入磁盘"""
    path = Path(token_file) if token_file is not None else get_token_file()
    if path.exists():
        token = path.read_text(encoding='utf-8').strip()
        if token:
            # 复用已有令牌,并确保权限收紧为 0600
            try:
                os.chmod(path, 0o600)
            except OSError as exc:
                logger.warning('Failed to chmod token file %s: %s', path, exc)
            return token
    token = secrets.token_urlsafe(32)
    # O_CREAT 携带 0600,避免先写后改权限的竞态窗口
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        fh.write(token)
    logger.info('Generated new web session token at %s', path)
    return token


def get_web_token() -> str:
    """获取当前有效令牌(每次读盘,本地工具开销可忽略)"""
    return load_or_create_token()


def token_matches(provided: Optional[str]) -> bool:
    """常数时间比较提供的令牌与期望令牌"""
    expected = get_web_token()
    if not provided or not expected:
        return False
    return secrets.compare_digest(str(provided), expected)


def extract_token_from_headers(auth_header: Optional[str]) -> Optional[str]:
    """从 Authorization: Bearer <token> 提取令牌"""
    if not auth_header:
        return None
    scheme, _, param = auth_header.partition(' ')
    if scheme.lower() != 'bearer':
        return None
    return param.strip() or None


def extract_token_from_cookies(cookie_header: Optional[str]) -> Optional[str]:
    """从原始 Cookie 头中提取会话 cookie(WebSocket 握手时无 request.cookies)"""
    if not cookie_header:
        return None
    for part in cookie_header.split(';'):
        name, _, value = part.strip().partition('=')
        if name == SESSION_COOKIE_NAME:
            return value.strip() or None
    return None


def extract_token_from_request(request: Request) -> Optional[str]:
    """按 Authorization / query ?token= / cookie 顺序提取令牌"""
    token = extract_token_from_headers(request.headers.get('authorization'))
    if token:
        return token
    token = request.query_params.get('token')
    if token:
        return token
    return request.cookies.get(SESSION_COOKIE_NAME)


def extract_token_from_websocket(websocket: WebSocket) -> Optional[str]:
    """WebSocket 握手阶段的令牌提取(Authorization / query / cookie)"""
    token = extract_token_from_headers(websocket.headers.get('authorization'))
    if token:
        return token
    token = websocket.query_params.get('token')
    if token:
        return token
    return extract_token_from_cookies(websocket.headers.get('cookie'))


async def require_session_token(request: Request) -> None:
    """FastAPI dependency:校验会话令牌,失败返回 401"""
    provided = extract_token_from_request(request)
    if not token_matches(provided):
        raise HTTPException(
            status_code=401,
            detail='Missing or invalid session token',
        )


def get_allowed_origins(port: Optional[int] = None) -> Set[str]:
    """构造 Origin 白名单;可用 YXI_WEB_ALLOWED_ORIGINS 追加(逗号分隔)"""
    if port is None:
        port = int(os.getenv('YXI_WEB_PORT', str(DEFAULT_WEB_PORT)))
    origins = {
        f'http://localhost:{port}',
        f'http://127.0.0.1:{port}',
        f'http://[::1]:{port}',
    }
    for extra in os.getenv('YXI_WEB_ALLOWED_ORIGINS', '').split(','):
        extra = extra.strip()
        if extra:
            origins.add(extra)
    return origins


def is_origin_allowed(origin: Optional[str], port: Optional[int] = None) -> bool:
    """Origin 为空(非浏览器客户端)或在白名单中才放行"""
    if not origin:
        return True
    return origin in get_allowed_origins(port)
