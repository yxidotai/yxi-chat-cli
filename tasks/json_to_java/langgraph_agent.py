"""LangGraph agent: docx -> tables (word_table_export) -> JSON sample -> Java code (json_to_java)."""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, TypedDict

import requests
from langgraph.graph import END, StateGraph

from tasks.word_table_export.export_tables import _build_class_defs, _sample_from_class


class AgentState(TypedDict, total=False):
    doc_path: str
    word_service_url: str
    java_service_url: str
    package: Optional[str]
    class_name: Optional[str]
    output_path: Optional[str]
    max_depth: int
    tables: List[Dict[str, Any]]
    root_class: Optional[str]
    sample: Dict[str, Any]
    java_code: str


def _call_word_tables(state: AgentState) -> AgentState:
    url = state["word_service_url"].rstrip("/") + "/tools/word_tables_to_json"
    payload = {
        "input": {
            "doc_path": state["doc_path"],
            "options": {"treat_first_row_as_header": True, "keep_empty_rows": False},
        }
    }
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    tables = data.get("data", {}).get("tables") or data.get("tables")
    if not tables:
        raise RuntimeError("No tables returned from word_table_export")
    return {"tables": tables}


def _build_sample(state: AgentState) -> AgentState:
    tables = state["tables"]
    class_defs = _build_class_defs(tables, root_name=state.get("class_name"))
    class_names = list(class_defs.keys())
    if not class_names:
        raise RuntimeError("Cannot build class definitions from tables")
    root_class = state.get("class_name") or class_names[0]
    sample = _sample_from_class(root_class, class_defs, max_depth=state.get("max_depth", 4), stack=[])
    return {"sample": sample, "root_class": root_class}


def _call_json_to_java(state: AgentState) -> AgentState:
    url = state["java_service_url"].rstrip("/") + "/tools/json_to_java"
    payload = {
        "input": {
            "json_text": json.dumps(state["sample"], ensure_ascii=False),
            "package": state.get("package"),
            "class_name": state.get("class_name") or state.get("root_class") or "Root",
            "output_path": state.get("output_path"),
        }
    }
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    java_code = data.get("java")
    output_path = data.get("output_path") or state.get("output_path")
    if not java_code and not output_path:
        raise RuntimeError("json_to_java returned no code")
    # If service wrote to disk, java_code may be None; otherwise include code.
    return {"java_code": java_code, "output_path": output_path}


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("word_tables", _call_word_tables)
    graph.add_node("build_sample", _build_sample)
    graph.add_node("json_to_java", _call_json_to_java)
    graph.set_entry_point("word_tables")
    graph.add_edge("word_tables", "build_sample")
    graph.add_edge("build_sample", "json_to_java")
    graph.add_edge("json_to_java", END)
    return graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Docx -> JSON sample -> Java via LangGraph and MCP services")
    parser.add_argument("doc_path", help="Path to the .docx file accessible by word_table_export service")
    parser.add_argument("--word-url", default="http://localhost:8000", help="word_table_export service base URL")
    parser.add_argument("--java-url", default="http://localhost:8030", help="json_to_java service base URL")
    parser.add_argument("--package", dest="package", help="Java package name", default=None)
    parser.add_argument("--class-name", dest="class_name", help="Root class name", default=None)
    parser.add_argument("--max-depth", type=int, default=4, help="Max depth when building sample JSON")
    parser.add_argument("--output-path", dest="output_path", help="Optional path to write Java code on server", default=None)
    args = parser.parse_args()

    initial: AgentState = {
        "doc_path": args.doc_path,
        "word_service_url": args.word_url,
        "java_service_url": args.java_url,
        "package": args.package,
        "class_name": args.class_name,
        "max_depth": args.max_depth,
        "output_path": args.output_path,
    }

    app = build_graph().compile()
    result = app.invoke(initial)

    java_code = result.get("java_code")
    output_path = result.get("output_path")
    if output_path:
        print(f"Java written to: {output_path}")
    if java_code:
        print(java_code)


if __name__ == "__main__":
    main()
