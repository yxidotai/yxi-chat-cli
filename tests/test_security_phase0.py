#!/usr/bin/env python3
"""
阶段0安全加固测试 (CLI-C1/C2/C3/H4/M6)

覆盖:
- 修复1: 各本地服务默认绑定 127.0.0.1(源码断言)
- 修复2: app/auth.py 会话令牌 + WebSocket Origin 校验
- 修复3: start.sh VNC 去除无密码模式、vncpasswd 不再被 git 跟踪
"""

import os
import stat
import subprocess
import sys
import types
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth import (
    SESSION_COOKIE_NAME,
    is_origin_allowed,
    load_or_create_token,
    require_session_token,
    token_matches,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# 每个需回环默认绑定的源文件
LOOPBACK_DEFAULT_FILES = [
    'tasks/test_ui/mcp_service.py',
    'tasks/json_to_java/mcp_service.py',
    'tasks/word_table_export/mcp_service.py',
    'tasks/obsidian_mcp/mcp_service.py',
    'server.py',
    'launch.py',
    'quick_test.py',
]


# ---------------------------------------------------------------------------
# 修复1: 默认 host 收敛为回环
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('relpath', LOOPBACK_DEFAULT_FILES)
def test_default_host_is_loopback(relpath):
    src = (REPO_ROOT / relpath).read_text(encoding='utf-8')
    assert '"0.0.0.0"' not in src, f'{relpath} 仍包含默认绑定 "0.0.0.0"'
    assert '127.0.0.1' in src, f'{relpath} 缺少 127.0.0.1 默认绑定'


def test_obsidian_docstring_mentions_loopback_default():
    src = (REPO_ROOT / 'tasks/obsidian_mcp/mcp_service.py').read_text(encoding='utf-8')
    assert '(default 127.0.0.1:8025)' in src


# ---------------------------------------------------------------------------
# 修复2: 会话令牌 (app/auth.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def token_file(tmp_path, monkeypatch):
    path = tmp_path / 'web_token'
    monkeypatch.setenv('YXI_WEB_TOKEN_FILE', str(path))
    return path


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_token_created_with_0600(token_file):
    assert not token_file.exists()
    token = load_or_create_token()
    assert token_file.exists()
    assert token_file.read_text(encoding='utf-8').strip() == token
    assert _mode(token_file) == 0o600
    # token_urlsafe(32) 生成的令牌足够长
    assert len(token) >= 32


def test_token_reused_when_file_exists(token_file):
    token_file.write_text('existing-token-value', encoding='utf-8')
    os.chmod(token_file, 0o644)
    token = load_or_create_token()
    assert token == 'existing-token-value'
    # 复用时权限收紧为 0600
    assert _mode(token_file) == 0o600
    assert load_or_create_token() == token


def test_blank_token_file_regenerated(token_file):
    token_file.write_text('   \n', encoding='utf-8')
    token = load_or_create_token()
    assert token and token.strip()


def test_token_matches(token_file):
    token = load_or_create_token()
    assert token_matches(token) is True
    assert token_matches('wrong-token') is False
    assert token_matches(None) is False
    assert token_matches('') is False


def _build_protected_api_app():
    app = FastAPI()

    @app.get('/api/demo')
    async def demo(_: None = Depends(require_session_token)):
        return {'ok': True}

    return app


@pytest.fixture()
def api_client(token_file):
    return TestClient(_build_protected_api_app())


def test_api_returns_401_without_token(api_client):
    resp = api_client.get('/api/demo')
    assert resp.status_code == 401


def test_api_accepts_bearer_token(api_client, token_file):
    token = load_or_create_token()
    resp = api_client.get('/api/demo', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.json() == {'ok': True}


def test_api_accepts_query_token_and_cookie(api_client, token_file):
    token = load_or_create_token()
    assert api_client.get('/api/demo', params={'token': token}).status_code == 200
    resp = api_client.get(
        '/api/demo', headers={'Cookie': f'{SESSION_COOKIE_NAME}={token}'}
    )
    assert resp.status_code == 200


def test_api_rejects_wrong_bearer_token(api_client, token_file):
    load_or_create_token()
    resp = api_client.get(
        '/api/demo', headers={'Authorization': 'Bearer not-the-token'}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 修复2: WebSocket Origin 校验
# ---------------------------------------------------------------------------

def test_origin_allowed_cases():
    assert is_origin_allowed(None) is True            # 非浏览器客户端
    assert is_origin_allowed('') is True
    assert is_origin_allowed('http://localhost:8080') is True
    assert is_origin_allowed('http://127.0.0.1:8080') is True
    assert is_origin_allowed('http://evil.example.com') is False
    assert is_origin_allowed('http://localhost:9999') is False


def test_origin_allowed_dynamic_port():
    assert is_origin_allowed('http://localhost:9999', port=9999) is True
    assert is_origin_allowed('http://127.0.0.1:9999', port=9999) is True


def test_origin_env_extra_allowlist(monkeypatch):
    monkeypatch.setenv('YXI_WEB_ALLOWED_ORIGINS', 'http://192.168.1.10:8080')
    assert is_origin_allowed('http://192.168.1.10:8080') is True
    assert is_origin_allowed('http://192.168.1.11:8080') is False


# WebSocket 端点集成测试:stub 掉重量级 chatbot_adapter,只测鉴权逻辑
class _FakeAdapter:
    def create_session(self):
        return 'sess-fake'

    def get_status(self):
        return {'status': 'ok'}

    def get_session_history(self, session_id):
        return []

    def delete_session(self, session_id):
        pass


def _install_fake_adapter():
    module = types.ModuleType('chatbot_adapter')
    module.ChatbotAdapter = _FakeAdapter
    sys.modules.setdefault('chatbot_adapter', module)


_install_fake_adapter()

from app.websocket_handler import websocket_endpoint  # noqa: E402


@pytest.fixture()
def ws_client():
    app = FastAPI()
    app.websocket('/ws/chat')(websocket_endpoint)
    return TestClient(app)


def test_ws_rejects_disallowed_origin(ws_client, token_file):
    load_or_create_token()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect(
            '/ws/chat', headers={'origin': 'http://evil.example.com'}
        ):
            pass
    assert exc_info.value.code == 4003


def test_ws_rejects_missing_token(ws_client, token_file):
    load_or_create_token()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect('/ws/chat'):
            pass
    assert exc_info.value.code == 4001


def test_ws_accepts_bearer_without_origin(ws_client, token_file):
    token = load_or_create_token()
    with ws_client.websocket_connect(
        '/ws/chat', headers={'Authorization': f'Bearer {token}'}
    ) as ws:
        status = ws.receive_json()
        assert status['type'] == 'status'
        assert status['data'] == {'status': 'ok'}


def test_ws_accepts_query_token(ws_client, token_file):
    token = load_or_create_token()
    with ws_client.websocket_connect(f'/ws/chat?token={token}') as ws:
        assert ws.receive_json()['type'] == 'status'


def test_ws_accepts_cookie_with_allowed_origin(ws_client, token_file):
    token = load_or_create_token()
    with ws_client.websocket_connect(
        '/ws/chat',
        headers={
            'origin': 'http://localhost:8080',
            'cookie': f'{SESSION_COOKIE_NAME}={token}',
        },
    ) as ws:
        assert ws.receive_json()['type'] == 'status'


def test_ws_rejects_wrong_token_with_allowed_origin(ws_client, token_file):
    load_or_create_token()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect(
            '/ws/chat', headers={'origin': 'http://localhost:8080'}
        ):
            pass
    assert exc_info.value.code == 4001


# ---------------------------------------------------------------------------
# 修复3: VNC 加固
# ---------------------------------------------------------------------------

def test_start_sh_hardening():
    src = (REPO_ROOT / 'tasks/test_ui/start.sh').read_text(encoding='utf-8')
    assert '-nopw' not in src, 'start.sh 不得再使用无密码 VNC 模式'
    assert '-passwd "$VNC_PASSWORD"' in src
    assert '-listen 127.0.0.1' in src
    assert 'VNC_PASSWORD=' in src  # 支持环境变量覆盖


def test_vncpasswd_not_tracked_by_git():
    output = subprocess.run(
        ['git', 'ls-files', '--', 'tasks/test_ui/vncpasswd'],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert output == '', f'vncpasswd 仍被 git 跟踪: {output}'


def test_vncpasswd_removed_from_worktree():
    assert not (REPO_ROOT / 'tasks/test_ui/vncpasswd').exists()


def test_vncpasswd_ignored_by_git():
    ignore_check = subprocess.run(
        ['git', 'check-ignore', '-q', 'tasks/test_ui/vncpasswd'],
        cwd=REPO_ROOT,
    )
    assert ignore_check.returncode == 0, '.gitignore 未忽略 tasks/test_ui/vncpasswd'


def test_dockerfile_documents_loopback_publish():
    src = (REPO_ROOT / 'tasks/test_ui/Dockerfile').read_text(encoding='utf-8')
    assert 'EXPOSE 5900' in src
    assert '-p 127.0.0.1:5900:5900' in src, 'Dockerfile 应注明回环发布方式'
