#!/usr/bin/env python3
"""Extract all Word tables from a .docx file and emit JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

from docx import Document


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
    payload = {
        "source": str(doc_path),
        "table_count": len(tables),
        "tables": tables,
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
