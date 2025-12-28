"""Expose JSON-to-Java conversion as an MCP-compatible HTTP service."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from .generate_java import generate_java
except ImportError:  # pragma: no cover - allow running as a script
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from tasks.json_to_java.generate_java import generate_java

TOOL_NAME = "json_to_java"

app = FastAPI(title="JSON to Java MCP Service", version="0.1.0")

TOOL_DEFINITION = {
    "name": TOOL_NAME,
    "description": "Convert a JSON payload (file or inline) into Java POJOs with nested static classes.",
    "input_schema": {
        "type": "object",
        "properties": {
            "json_path": {
                "type": "string",
                "description": "Absolute path to a JSON file",
            },
            "json_text": {
                "type": "string",
                "description": "Inline JSON content (string)",
            },
            "root_path": {
                "type": "string",
                "description": "Dot/bracket path to select a sub-node as root (e.g., data.items[0].payload)",
            },
            "package": {
                "type": "string",
                "description": "Optional Java package name",
            },
            "class_name": {
                "type": "string",
                "description": "Root class name",
                "default": "Root",
            },
            "output_path": {
                "type": "string",
                "description": "Optional path to write generated Java code",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}


class JsonToJavaInput(BaseModel):
    json_path: Optional[str] = Field(default=None, description="Absolute path to JSON file")
    json_text: Optional[str] = Field(default=None, description="Inline JSON string")
    root_path: Optional[str] = Field(default=None, description="Dot/bracket path to sub-node root")
    package: Optional[str] = Field(default=None, description="Java package name")
    class_name: str = Field(default="Root", description="Root class name")
    output_path: Optional[str] = Field(default=None, description="Path to write generated Java code")


class InvokeRequest(BaseModel):
    input: JsonToJavaInput
    context: Optional[Dict[str, Any]] = None


def _load_json(payload: JsonToJavaInput) -> Any:
    if payload.json_text:
        try:
            return json.loads(payload.json_text)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid json_text: {exc}")

    if payload.json_path:
        path = Path(payload.json_path).expanduser().resolve()
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON file: {exc}")

    raise HTTPException(status_code=400, detail="json_text or json_path must be provided")


def _resolve_path(node: Any, path: str) -> Any:
    current = node
    for part in path.split('.'):
        if '[' in part and part.endswith(']'):
            name, idx_txt = part[:-1].split('[', 1)
            if name:
                if isinstance(current, dict):
                    current = current.get(name)
                else:
                    return None
            try:
                idx = int(idx_txt)
            except ValueError:
                return None
            if isinstance(current, list) and 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
    return current


@app.get("/healthz")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/tools")
def list_tools() -> Dict[str, Any]:
    return {"tools": [TOOL_DEFINITION]}


@app.post(f"/tools/{TOOL_NAME}")
def invoke_tool(request: InvokeRequest) -> Dict[str, Any]:
    payload = request.input
    data = _load_json(payload)

    if payload.root_path:
        data = _resolve_path(data, payload.root_path)
        if data is None:
            raise HTTPException(status_code=400, detail=f"root_path not found: {payload.root_path}")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Root JSON must be an object")

    java_code = generate_java(payload.class_name, data, payload.package)

    written_to = None
    if payload.output_path:
        out_path = Path(payload.output_path).expanduser().resolve()
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(java_code, encoding="utf-8")
            written_to = str(out_path)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to write output file: {exc}")

    return {
        "tool": TOOL_NAME,
        "data": {
            "class_name": payload.class_name,
            "package": payload.package,
            "root_path": payload.root_path,
            "java": java_code,
            "output_path": written_to,
        },
    }


if __name__ == "__main__":
    import os
    import uvicorn

    host = os.getenv("JSON_TO_JAVA_HOST", "0.0.0.0")
    port = int(os.getenv("JSON_TO_JAVA_PORT", "8030"))
    uvicorn.run("mcp_service:app", host=host, port=port, reload=False)
