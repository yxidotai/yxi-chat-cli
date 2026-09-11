"""Playwright-based UI testing MCP service."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from ..mcp_auth import ensure_within, make_token_dependency, write_root
except ImportError:  # pragma: no cover
    from tasks.mcp_auth import ensure_within, make_token_dependency, write_root

# v1.23.x (CLI-C1/H1): /tools/* 强制 Bearer 令牌(健康检查除外)
_token_dep = make_token_dependency("test_ui", "PLAYWRIGHT_TOKEN")

try:
    from .generate_tests import PlaywrightOptions, generate_playwright_script, load_cases_from_excel, run_cases
except ImportError:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from tasks.test_ui.generate_tests import (
        PlaywrightOptions,
        generate_playwright_script,
        load_cases_from_excel,
        run_cases,
    )

TOOL_NAME = "playwright_run"

app = FastAPI(title="Playwright UI Test MCP", version="0.1.0")


class PlaywrightOptionsModel(BaseModel):
    headless: bool = Field(default=True, description="Run browser headless")
    slow_mo: int = Field(default=0, ge=0, description="Slow motion delay in ms")
    timeout_ms: int = Field(default=10000, ge=100, description="Default timeout for actions")
    base_url: Optional[str] = Field(default=None, description="Base URL for relative paths")
    output_dir: Optional[str] = Field(default=None, description="Directory for screenshots or artifacts")
    browser: str = Field(default="chromium", description="Browser: chromium|firefox|webkit")


class PlaywrightInput(BaseModel):
    excel_path: Optional[str] = Field(default=None, description="Excel test case path, visible to the service")
    cases: Optional[List[Dict[str, Any]]] = Field(default=None, description="Parsed test cases")
    options: PlaywrightOptionsModel = Field(default_factory=PlaywrightOptionsModel)
    write_script_path: Optional[str] = Field(default=None, description="Optional path to write generated script")


class InvokeRequest(BaseModel):
    input: PlaywrightInput
    context: Optional[Dict[str, Any]] = None


TOOL_DEFINITION = {
    "name": TOOL_NAME,
    "description": "Run Playwright UI tests from Excel or generated scripts.",
    "input_schema": PlaywrightInput.schema(),
}


@app.get("/healthz")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/tools", dependencies=[Depends(_token_dep)])
def list_tools() -> Dict[str, Any]:
    return {"tools": [TOOL_DEFINITION]}


def _options_from_model(model: PlaywrightOptionsModel) -> PlaywrightOptions:
    return PlaywrightOptions(
        headless=model.headless,
        slow_mo=model.slow_mo,
        timeout_ms=model.timeout_ms,
        base_url=model.base_url,
        output_dir=model.output_dir,
        browser=model.browser,
    )


def _write_script(script_text: str, path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    # v1.23.x (CLI-H1): 写路径限制在白名单根目录内(MCP_ALLOW_WRITE_DIR,默认 ~/yxi-mcp-output)
    target = ensure_within(write_root(), path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script_text, encoding="utf-8")
    return str(target)


@app.post(f"/tools/{TOOL_NAME}", dependencies=[Depends(_token_dep)])
def invoke_tool(request: InvokeRequest) -> Dict[str, Any]:
    payload = request.input

    # v1.23.x 安全加固 (CLI-C1): 移除 script_text 直通执行 ——
    # 原「任意 Python 源码 → subprocess 执行」即零认证 RCE by design;
    # 现仅接受结构化用例(excel_path / cases),由受控模板生成脚本。
    if getattr(payload, "script_text", None):
        raise HTTPException(
            status_code=400,
            detail="script_text is no longer supported; provide excel_path or cases",
        )

    if not payload.excel_path and not payload.cases:
        raise HTTPException(status_code=400, detail="Provide excel_path or cases")

    options = _options_from_model(payload.options)
    cases = payload.cases

    if not cases and payload.excel_path:
        from tasks.mcp_auth import ensure_within as _ew, read_root as _rr
        excel = _ew(_rr(), payload.excel_path)
        cases = load_cases_from_excel(str(excel))

    script_text = generate_playwright_script(cases, options) if cases else None
    written_to = _write_script(script_text, payload.write_script_path) if script_text else None

    results = run_cases(cases or [], options)
    result_data = {
        "results": results,
        "script_written": written_to,
        "cases": cases,
    }

    return {
        "tool": TOOL_NAME,
        "data": result_data,
    }


if __name__ == "__main__":
    import uvicorn

    # 默认仅回环监听;外部暴露需显式设置环境变量并自行承担风险
    host = os.getenv("PLAYWRIGHT_HOST", "127.0.0.1")
    port = int(os.getenv("PLAYWRIGHT_PORT", "8040"))
    uvicorn.run("mcp_service:app", host=host, port=port, reload=False)
