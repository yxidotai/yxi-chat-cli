"""Playwright-based UI testing MCP service."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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
    script_text: Optional[str] = Field(default=None, description="Inline Playwright Python script text")
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


@app.get("/tools")
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
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script_text, encoding="utf-8")
    return str(target)


def _execute_script(script_text: str) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "playwright_run.py"
        script_path.write_text(script_text, encoding="utf-8")

        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout.strip() or result.stderr.strip()
        try:
            parsed = json.loads(output) if output else []
        except json.JSONDecodeError:
            parsed = output
        return {
            "exit_code": result.returncode,
            "output": parsed,
            "raw_output": output,
        }


@app.post(f"/tools/{TOOL_NAME}")
def invoke_tool(request: InvokeRequest) -> Dict[str, Any]:
    payload = request.input

    if not payload.excel_path and not payload.script_text and not payload.cases:
        raise HTTPException(status_code=400, detail="Provide excel_path, script_text, or cases")

    options = _options_from_model(payload.options)
    cases = payload.cases

    if not cases and payload.excel_path:
        cases = load_cases_from_excel(payload.excel_path)

    script_text = payload.script_text
    if not script_text and cases:
        script_text = generate_playwright_script(cases, options)

    written_to = _write_script(script_text, payload.write_script_path) if script_text else None

    if payload.script_text:
        execution = _execute_script(payload.script_text)
        result_data = {
            "execution": execution,
            "script_text": payload.script_text,
            "script_written": written_to,
            "cases": cases,
        }
    else:
        results = run_cases(cases or [], options)
        result_data = {
            "results": results,
            "script_text": script_text,
            "script_written": written_to,
            "cases": cases,
        }

    return {
        "tool": TOOL_NAME,
        "data": result_data,
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("PLAYWRIGHT_HOST", "0.0.0.0")
    port = int(os.getenv("PLAYWRIGHT_PORT", "8040"))
    uvicorn.run("mcp_service:app", host=host, port=port, reload=False)
