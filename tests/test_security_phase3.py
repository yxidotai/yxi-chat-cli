"""阶段 3a 安全加固测试 (v1.23.x CLI-C1/H1/H2/H3/H5/H6/L3)

覆盖:
  - mcp_auth: 令牌生成/0600/复用、依赖鉴权、路径白名单
  - test_ui: script_text 直通执行已移除;端点强制 Bearer
  - json_to_java / word_table_export: 路径逃逸被拒、未授权 401
  - obsidian_mcp: append_note 路径遍历被拒、令牌必选
  - chatbot OAuth 回调: state 校验(错/缺 → 403)、token 文件 0600
"""

import os
import stat
import threading
import urllib.request
import urllib.error
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("YXI_MCP_TOKEN_DIR", "/tmp/yxi-test-tokens-phase3")

from tasks.mcp_auth import (  # noqa: E402
    ensure_within,
    get_service_token,
    make_token_dependency,
)
from tasks.obsidian_mcp import mcp_service as obsidian  # noqa: E402
from tasks.json_to_java import mcp_service as j2j  # noqa: E402
from tasks.word_table_export import mcp_service as word  # noqa: E402
from tasks.test_ui import mcp_service as pw  # noqa: E402


@pytest.fixture()
def isolated_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("YXI_MCP_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.delenv("YXI_MCP_TOKEN", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_TOKEN", raising=False)
    monkeypatch.delenv("JSON_TO_JAVA_TOKEN", raising=False)
    monkeypatch.delenv("WORD_MCP_TOKEN", raising=False)
    monkeypatch.delenv("OBSIDIAN_MCP_TOKEN", raising=False)
    # 各服务模块在 import 时已捕获 REQUIRED_TOKEN 的服务需要重载;
    # obsidian 改为在调用时读取,这里直接重置其模块级变量
    import importlib
    import tasks.obsidian_mcp.mcp_service as om
    importlib.reload(om)
    yield tmp_path


# ---------------------------------------------------------------------------
# mcp_auth 单元
# ---------------------------------------------------------------------------

def test_token_generated_with_0600_and_reused(isolated_tokens, monkeypatch):
    monkeypatch.setenv("YXI_MCP_TOKEN_DIR", str(isolated_tokens / "tokens"))
    token1 = get_service_token("unit_service")
    token_file = isolated_tokens / "tokens" / "unit_service.token"
    assert token_file.exists()
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    token2 = get_service_token("unit_service")
    assert token1 == token2  # 复用,不重新生成


def test_env_token_takes_precedence(isolated_tokens, monkeypatch):
    monkeypatch.setenv("YXI_MCP_TOKEN_DIR", str(isolated_tokens / "tokens"))
    monkeypatch.setenv("MYPW_TOKEN", "from-env")
    assert get_service_token("unit2", "MYPW_TOKEN") == "from-env"


def test_ensure_within_blocks_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    ok = ensure_within(root, "sub/file.txt")
    assert str(ok).startswith(str(root.resolve()))
    with pytest.raises(Exception, match="escapes"):
        ensure_within(root, "../../etc/passwd")


def test_dependency_rejects_bad_token(isolated_tokens, monkeypatch):
    monkeypatch.setenv("YXI_MCP_TOKEN_DIR", str(isolated_tokens / "tokens"))
    app = FastAPI()
    dep = make_token_dependency("dep_service")
    app.get("/x")(FastAPI.route if False else lambda request: None)  # placeholder no-op
    from fastapi import Depends

    @app.get("/secure", dependencies=[Depends(dep)])
    def secure():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/secure").status_code == 401
    assert client.get("/secure?token=wrong").status_code == 401
    good = get_service_token("dep_service")
    assert client.get("/secure", headers={"Authorization": f"Bearer {good}"}).status_code == 200


# ---------------------------------------------------------------------------
# 各 MCP 服务
# ---------------------------------------------------------------------------

def _auth_header(isolated_tokens, service, env_var, monkeypatch):
    monkeypatch.setenv("YXI_MCP_TOKEN_DIR", str(isolated_tokens / "tokens"))
    token = get_service_token(service, env_var)
    return {"Authorization": f"Bearer {token}"}


def test_playwright_script_text_removed(isolated_tokens, monkeypatch):
    headers = _auth_header(isolated_tokens, "test_ui", "PLAYWRIGHT_TOKEN", monkeypatch)
    client = TestClient(pw.app)
    # 无令牌 → 401
    assert client.post("/tools/playwright_run", json={"input": {"cases": []}}).status_code == 401
    # 有令牌 + script_text → 400(直通执行已移除)
    r = client.post(
        "/tools/playwright_run",
        json={"input": {"script_text": "import os; os.system('id')"}},
        headers=headers,
    )
    assert r.status_code == 400
    # script_text 字段已从模型移除(pydantic 忽略未知字段)→ 落到参数缺失 400
    assert "excel_path or cases" in r.json()["detail"]
    # 有令牌 + 合法 cases → 不再 404/405(结构化路径可用)
    r2 = client.post("/tools/playwright_run", json={"input": {"cases": []}}, headers=headers)
    assert r2.status_code != 401


def test_json_to_java_path_escape_and_auth(isolated_tokens, monkeypatch, tmp_path):
    headers = _auth_header(isolated_tokens, "json_to_java", "JSON_TO_JAVA_TOKEN", monkeypatch)
    client = TestClient(j2j.app)
    assert client.post("/tools/json_to_java", json={"input": {"json_text": "{}"}}).status_code == 401
    r = client.post(
        "/tools/json_to_java",
        json={"input": {"json_path": "/etc/passwd"}},
        headers=headers,
    )
    assert r.status_code == 400
    assert "escapes" in r.json()["detail"]
    r2 = client.post(
        "/tools/json_to_java",
        json={"input": {"output_path": "/tmp/evil/Out.java", "json_text": '{"a":1}'}},
        headers=headers,
    )
    assert r2.status_code == 400


def test_word_doc_path_escape(isolated_tokens, monkeypatch):
    headers = _auth_header(isolated_tokens, "word_table_export", "WORD_MCP_TOKEN", monkeypatch)
    client = TestClient(word.app)
    assert client.post("/tools/word_tables_to_json", json={"input": {}}).status_code == 401
    r = client.post(
        "/tools/word_tables_to_json",
        json={"input": {"doc_path": "/etc/hostname.docx"}},
        headers=headers,
    )
    assert r.status_code == 400
    assert "escapes" in r.json()["detail"]


def test_obsidian_append_note_escape_and_token_required(isolated_tokens):
    client = TestClient(obsidian.app)
    # 令牌必选(fail-closed)
    r0 = client.post(
        "/tools/append_note",
        json={"input": {"path": "a.md", "content": "x"}},
    )
    assert r0.status_code in (401, 403)
    token = obsidian.REQUIRED_TOKEN
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/tools/append_note",
        json={"input": {"path": "../../tmp/evil.md", "content": "x"}},
        headers=headers,
    )
    assert r.status_code == 400
    assert "escapes" in r.json()["detail"]


# ---------------------------------------------------------------------------
# chatbot OAuth 回调 (CLI-H5)
# ---------------------------------------------------------------------------

def test_oauth_callback_state_validation(tmp_path, monkeypatch):
    # 延迟导入:chatbot 导入链较重
    import chatbot

    port = 18765
    server = chatbot.start_callback_server(port)
    try:
        base = f"http://localhost:{port}/callback"
        # 期望 state 未设置 → 任何回调 403
        chatbot.CallbackHandler.expected_state = None
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"{base}?state=x&apiKey=abc")
        assert exc.value.code == 403

        # 错误 state → 403
        chatbot.CallbackHandler.expected_state = "right-state"
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"{base}?state=wrong&apiKey=abc")
        assert exc.value.code == 403

        # 正确 state + apiKey → 200,token 落盘 0600,state 消费一次
        monkeypatch.setattr(chatbot, "TOKEN_FILE", str(tmp_path / "tok"))
        chatbot.CallbackHandler.expected_state = "right-state"
        with urllib.request.urlopen(f"{base}?state=right-state&apiKey=abc") as resp:
            assert resp.status == 200
        tok = Path(tmp_path / "tok")
        assert tok.read_text() == "abc"
        assert stat.S_IMODE(tok.stat().st_mode) == 0o600

        # 同一 state 重放 → 403
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"{base}?state=right-state&apiKey=abc")
        assert exc.value.code == 403
    finally:
        server.shutdown()
