#!/usr/bin/env python3
"""Expose Word table extraction as an MCP-compatible HTTP service."""
from __future__ import annotations

import base64
import binascii
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from docx import Document
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
try:
    from .export_tables import extract_tables_from_document
except ImportError:  # pragma: no cover - fallback for direct script execution
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from tasks.word_table_export.export_tables import extract_tables_from_document

TOOL_NAME = "word_tables_to_json"

app = FastAPI(title="Word Table MCP Service", version="0.1.0")

TOOL_DEFINITION = {
    "name": TOOL_NAME,
    "description": "Convert all tables in a Word (.docx) document into JSON.",
    "input_schema": {
        "type": "object",
        "properties": {
            "doc_path": {
                "type": "string",
                "description": "Absolute path to a .docx file accessible to the service",
            },
            "doc_base64": {
                "type": "string",
                "description": "Base64-encoded binary of a .docx file",
            },
            "options": {
                "type": "object",
                "properties": {
                    "treat_first_row_as_header": {"type": "boolean", "default": True},
                    "keep_empty_rows": {"type": "boolean", "default": False},
                },
                "additionalProperties": False,
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}


class WordTableOptions(BaseModel):
    treat_first_row_as_header: bool = True
    keep_empty_rows: bool = False


class WordTableInput(BaseModel):
    doc_path: Optional[str] = Field(
        default=None, description="Absolute path to the target .docx file"
    )
    doc_base64: Optional[str] = Field(
        default=None, description="Base64-encoded .docx contents"
    )
    options: WordTableOptions = Field(default_factory=WordTableOptions)


class InvokeRequest(BaseModel):
    input: WordTableInput
    context: Optional[Dict[str, Any]] = None


def _load_document_from_input(payload: WordTableInput) -> Document:
    if payload.doc_base64:
        try:
            binary = base64.b64decode(payload.doc_base64)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {exc}")
        return Document(BytesIO(binary))

    if payload.doc_path:
        path = Path(payload.doc_path).expanduser().resolve()
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        if path.suffix.lower() != ".docx":
            raise HTTPException(status_code=400, detail="Only .docx files are supported")
        return Document(path)

    raise HTTPException(status_code=400, detail="doc_path or doc_base64 must be provided")


@app.get("/healthz")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/tools")
def list_tools() -> Dict[str, Any]:
    return {"tools": [TOOL_DEFINITION]}


@app.post(f"/tools/{TOOL_NAME}")
def invoke_tool(request: InvokeRequest) -> Dict[str, Any]:
    document = _load_document_from_input(request.input)
    options = request.input.options
    tables = extract_tables_from_document(
        document,
        treat_first_row_as_header=options.treat_first_row_as_header,
        keep_empty_rows=options.keep_empty_rows,
    )

    response = {
        "tool": TOOL_NAME,
        "data": {
            "source": request.input.doc_path or "inline",
            "table_count": len(tables),
            "tables": tables,
        },
    }
    if request.context:
        response["context_echo"] = request.context
    return response


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("WORD_MCP_HOST", "0.0.0.0")
    port = int(os.getenv("WORD_MCP_PORT", "8000"))
    uvicorn.run("mcp_service:app", host=host, port=port, reload=False)
