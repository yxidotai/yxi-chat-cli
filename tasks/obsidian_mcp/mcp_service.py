"""Obsidian MCP server (sample)

Features:
- Token-protected MCP endpoints
- search_notes: keyword search within Markdown vault
- append_note: append plain text to a note (creates file if missing)

Env vars:
- OBSIDIAN_VAULT_DIR: path to your Obsidian vault (default: ./vault)
- OBSIDIAN_MCP_TOKEN: optional bearer token required in Authorization header
- HOST / PORT: optional FastAPI host/port settings (default 0.0.0.0:8025)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Obsidian MCP", version="0.1.0")

VAULT_DIR = Path(os.getenv("OBSIDIAN_VAULT_DIR", "./vault")).expanduser()
REQUIRED_TOKEN = os.getenv("OBSIDIAN_MCP_TOKEN")


# ---------- Models ----------
class ToolDescriptor(BaseModel):
    name: str
    description: str
    input_schema: dict


class SearchInput(BaseModel):
    query: str = Field(..., description="Keyword to search in file names and content")
    limit: int = Field(10, ge=1, le=100, description="Max results")


class AppendInput(BaseModel):
    path: str = Field(..., description="Relative path to note (e.g., notes/todo.md)")
    content: str = Field(..., description="Text to append")


class MCPRequest(BaseModel):
    input: dict
    context: dict | None = None


# ---------- Auth ----------

def require_token(authorization: str | None = Header(default=None)):
    if REQUIRED_TOKEN:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = authorization.split(" ", 1)[1]
        if token != REQUIRED_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid token")
    return True


# ---------- Helpers ----------

def ensure_vault():
    VAULT_DIR.mkdir(parents=True, exist_ok=True)


def iter_markdown_files() -> List[Path]:
    if not VAULT_DIR.exists():
        return []
    return [p for p in VAULT_DIR.rglob("*.md") if p.is_file()]


def search_notes(query: str, limit: int = 10):
    results = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    for path in iter_markdown_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(path.name) or pattern.search(text):
            snippet = text[:200].replace("\n", " ")
            results.append({"path": str(path.relative_to(VAULT_DIR)), "snippet": snippet})
            if len(results) >= limit:
                break
    return {"query": query, "count": len(results), "results": results}


def append_note(rel_path: str, content: str):
    ensure_vault()
    target = VAULT_DIR / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(content)
        if not content.endswith("\n"):
            f.write("\n")
    return {"path": str(target.relative_to(VAULT_DIR)), "appended": len(content)}


# ---------- Routes ----------

@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/tools", dependencies=[Depends(require_token)])
def list_tools():
    return {
        "tools": [
            {
                "name": "search_notes",
                "description": "Search markdown notes in the Obsidian vault by keyword.",
                "input_schema": SearchInput.schema(),
            },
            {
                "name": "append_note",
                "description": "Append text to a note (creates file if missing).",
                "input_schema": AppendInput.schema(),
            },
        ]
    }


@app.post("/tools/search_notes", dependencies=[Depends(require_token)])
def run_search(req: MCPRequest):
    data = SearchInput(**req.input)
    return search_notes(data.query, data.limit)


@app.post("/tools/append_note", dependencies=[Depends(require_token)])
def run_append(req: MCPRequest):
    data = AppendInput(**req.input)
    return append_note(data.path, data.content)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8025"))
    uvicorn.run("mcp_service:app", host=host, port=port, reload=False)
