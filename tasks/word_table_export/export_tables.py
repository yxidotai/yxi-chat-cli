#!/usr/bin/env python3
"""Extract all Word tables from a .docx file and emit JSON."""
from __future__ import annotations

import argparse
import json
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence

from docx import Document


def _extract_table_title(table: Any) -> str | None:
    """Heuristic: use the nearest previous paragraph as the table title."""
    element = getattr(table, "_element", None)
    prev = getattr(element, "getprevious", lambda: None)() if element is not None else None
    while prev is not None:
        tag = getattr(prev, "tag", "")
        if tag and tag.endswith("tbl"):
            # Hit another table before finding a paragraph title.
            break
        if tag and tag.endswith("p"):
            texts = [getattr(t, "text", "") for t in prev.iter() if getattr(t, "tag", "").endswith("t")]
            raw_title = "".join(texts).strip()
            title = re.sub(r"^表\s*\d+[:：]?\s*", "", raw_title)
            if title:
                return title
        prev = prev.getprevious()
    return None


def _cell_texts(cells: Sequence[Any]) -> List[str]:
    return [cell.text.strip() for cell in cells]


def _row_is_empty(values: Sequence[str]) -> bool:
    return all(value == "" for value in values)


def extract_tables_from_document(
    document: Any,
    *,
    treat_first_row_as_header: bool = True,
    keep_empty_rows: bool = False,
) -> List[Dict[str, Any]]:
    tables_payload: List[Dict[str, Any]] = []

    for index, table in enumerate(document.tables):
        title = _extract_table_title(table)
        row_cells = [_cell_texts(row.cells) for row in table.rows]
        column_count = max((len(cells) for cells in row_cells), default=0)

        headers = None
        data_rows = row_cells
        if treat_first_row_as_header and row_cells:
            headers = row_cells[0]
            data_rows = row_cells[1:]

        structured_rows: List[Any] = []
        for row_values in data_rows:
            if not keep_empty_rows and _row_is_empty(row_values):
                continue
            if headers and len(headers) == len(row_values) and any(headers):
                structured_rows.append(dict(zip(headers, row_values)))
            else:
                structured_rows.append(row_values)

        tables_payload.append(
            {
                "index": index,
                "title": title,
                "row_count": len(row_cells),
                "column_count": column_count,
                "headers": headers,
                "rows": structured_rows,
            }
        )

    return tables_payload


def extract_tables(
    doc_path: Path,
    *,
    treat_first_row_as_header: bool = True,
    keep_empty_rows: bool = False,
) -> List[Dict[str, Any]]:
    document = Document(doc_path)
    return extract_tables_from_document(
        document,
        treat_first_row_as_header=treat_first_row_as_header,
        keep_empty_rows=keep_empty_rows,
    )


def _parse_list_type(type_text: str) -> str | None:
    if type_text.startswith("List<") and type_text.endswith(">"):
        return type_text[5:-1].strip()
    return None


def _is_primitive(type_text: str) -> bool:
    primitives = {
        "string",
        "double",
        "float",
        "int",
        "integer",
        "long",
        "bool",
        "boolean",
        "number",
    }
    return type_text.lower() in primitives


def _primitive_sample(type_text: str) -> Any:
    lowered = type_text.lower()
    if lowered in {"string"}:
        return "text"
    if lowered in {"bool", "boolean"}:
        return True
    if lowered in {"int", "integer", "long"}:
        return 0
    if lowered in {"double", "float", "number"}:
        return 0.0
    return None


def _build_class_defs(tables: List[Dict[str, Any]], *, root_name: str | None = None) -> Dict[str, List[Dict[str, str]]]:
    class_defs: Dict[str, List[Dict[str, str]]] = {}
    for index, table in enumerate(tables):
        class_name = root_name if root_name and index == 0 else f"Class{index + 1}"
        headers = table.get("headers") or []
        header_index = {name: idx for idx, name in enumerate(headers)}
        rows = table.get("rows") or []
        fields: List[Dict[str, str]] = []
        for row in rows:
            if isinstance(row, dict):
                eng = str(row.get("字段英文名", "")).strip()
                ftype = str(row.get("字段类型", "")).strip()
            else:
                eng = str(row[header_index.get("字段英文名", 1)]).strip() if header_index else ""
                ftype = str(row[header_index.get("字段类型", 3)]).strip() if header_index else ""
            if not eng:
                continue
            fields.append({"name": eng, "type": ftype})
        class_defs[class_name] = fields
    return class_defs


def _sample_from_class(
    class_name: str,
    class_defs: Dict[str, List[Dict[str, str]]],
    *,
    max_depth: int,
    stack: List[str],
) -> Any:
    if max_depth <= 0:
        return None
    is_cycle = class_name in stack
    stack.append(class_name)
    result: Dict[str, Any] = {}
    fields = class_defs.get(class_name, [])
    name_lookup = {name.lower(): name for name in class_defs.keys()}
    for field in fields:
        field_name = field.get("name", "")
        raw_type = field.get("type", "").strip()
        list_inner = _parse_list_type(raw_type)
        if list_inner:
            if _is_primitive(list_inner):
                sample_value = _primitive_sample(list_inner)
            else:
                target_class = name_lookup.get(list_inner.lower())
                sample_value = (
                    _sample_from_class(target_class, class_defs, max_depth=max_depth - 1, stack=stack[:])
                    if target_class and not is_cycle
                    else {}
                )
            result[field_name] = [sample_value]
            continue

        if _is_primitive(raw_type):
            result[field_name] = _primitive_sample(raw_type)
            continue

        target_class = name_lookup.get(raw_type.lower())
        if target_class:
            result[field_name] = (
                _sample_from_class(target_class, class_defs, max_depth=max_depth - 1, stack=stack[:])
                if not is_cycle
                else {}
            )
        else:
            result[field_name] = None
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read all tables from a Word (.docx) document and output JSON."
    )
    parser.add_argument("input", help="Path to the .docx file to parse")
    parser.add_argument(
        "-o",
        "--output",
        help="Optional path to write JSON output (default: stdout)",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Treat all rows as data instead of using the first row as headers",
    )
    parser.add_argument(
        "--keep-empty",
        action="store_true",
        help="Keep empty rows instead of filtering them out",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation (set to 0 for a compact single line)",
    )
    parser.add_argument(
        "--root-index",
        type=int,
        default=0,
        help="Which table index to treat as root when generating merged sample",
    )
    parser.add_argument(
        "--root-name",
        type=str,
        help="Optional explicit root class name (default: Class1)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Maximum nesting depth when resolving class references",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    doc_path = Path(args.input).expanduser().resolve()
    if not doc_path.exists():
        print(f"[error] File not found: {doc_path}", file=sys.stderr)
        return 1
    if doc_path.suffix.lower() != ".docx":
        print(f"[warn] Expected a .docx file, got: {doc_path.suffix}", file=sys.stderr)

    tables = extract_tables(
        doc_path,
        treat_first_row_as_header=not args.no_header,
        keep_empty_rows=args.keep_empty,
    )

    class_defs = _build_class_defs(tables, root_name=args.root_name)
    class_names = list(class_defs.keys())
    root_index = max(0, min(args.root_index, len(class_names) - 1)) if class_names else 0
    root_class = class_names[root_index] if class_names else None
    merged_sample = None
    if root_class:
        merged_sample = _sample_from_class(
            root_class,
            class_defs,
            max_depth=args.max_depth,
            stack=[],
        )

    payload = {
        "source": str(doc_path),
        "table_count": len(tables),
        "tables": tables,
        "root_class": root_class,
        "sample": merged_sample,
    }

    indent_value = None if args.indent is None or args.indent <= 0 else args.indent
    json_text = json.dumps(payload, ensure_ascii=False, indent=indent_value)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_text, encoding="utf-8")
    else:
        print(json_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
