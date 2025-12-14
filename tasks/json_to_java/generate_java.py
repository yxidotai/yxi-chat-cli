"""
Convert a nested JSON document into Java POJOs (single file with nested static classes).

Usage:
    uv run python tasks/json_to_java/generate_java.py input.json -o Output.java \
        --package com.example.demo --class-name Root

Features:
- Infers basic field types (String, Integer, Double, Boolean, Object)
- Supports nested objects and arrays (arrays become java.util.List<T>)
- Creates nested static classes for object fields and object arrays
- Adds Jackson annotations: @JsonIgnoreProperties(ignoreUnknown = true), @JsonProperty("<json key>")
- Generates valid Java identifiers from JSON keys

Limitations:
- Mixed-type arrays fall back to List<Object>
- Null-only fields are typed as Object
- No Lombok/getters/setters; this is a minimal DTO scaffold
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

PRIMITIVES = {str: "String", int: "Integer", float: "Double", bool: "Boolean"}


def to_identifier(name: str) -> str:
    """Convert arbitrary key to a safe Java identifier in camelCase."""
    if not name:
        return "field"
    # Replace non-alphanumeric with space, then camel-case
    name = re.sub(r"[^0-9A-Za-z]+", " ", name).strip()
    if not name:
        return "field"
    parts = name.split()
    first = parts[0].lower()
    rest = [p.capitalize() for p in parts[1:]]
    ident = first + "".join(rest)
    if ident[0].isdigit():
        ident = f"f{ident}"
    return ident


def to_pascal(name: str) -> str:
    ident = to_identifier(name)
    return ident[:1].upper() + ident[1:]


def unique_class_name(base: str, used: Dict[str, int]) -> str:
    count = used.get(base, 0)
    if count == 0:
        used[base] = 1
        return base
    used[base] = count + 1
    return f"{base}{count+1}"


def infer_list_type(field_name: str, values: List[Any], used: Dict[str, int], classes: List[str]) -> str:
    # Remove None entries for inference
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "java.util.List<Object>"

    first = non_null[0]
    # If all are dicts -> create nested class
    if all(isinstance(v, dict) for v in non_null):
        cls_base = to_pascal(f"{field_name}Item")
        cls_name = unique_class_name(cls_base, used)
        class_def = build_class(cls_name, first, used, classes)
        classes.append(class_def)
        return f"java.util.List<{cls_name}>"

    # If all same primitive type (boxed)
    if all(isinstance(v, str) for v in non_null):
        return "java.util.List<String>"
    if all(isinstance(v, bool) for v in non_null):
        return "java.util.List<Boolean>"
    # bool is subclass of int; check int after bool
    if all(isinstance(v, int) for v in non_null):
        return "java.util.List<Integer>"
    if all(isinstance(v, float) for v in non_null):
        return "java.util.List<Double>"

    # Mixed primitive types
    return "java.util.List<Object>"


def java_type_for_value(value: Any) -> str:
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, int):
        return "Integer"
    if isinstance(value, float):
        return "Double"
    if isinstance(value, str):
        return "String"
    return "Object"


def build_class(name: str, obj: Dict[str, Any], used: Dict[str, int], classes: List[str]) -> str:
    fields: List[Tuple[str, str, str]] = []

    for key, value in obj.items():
        field_name = to_identifier(key)
        json_key = key or field_name
        if isinstance(value, dict):
            cls_base = to_pascal(key or field_name)
            cls_name = unique_class_name(cls_base, used)
            nested_def = build_class(cls_name, value, used, classes)
            classes.append(nested_def)
            fields.append((cls_name, field_name, json_key))
        elif isinstance(value, list):
            list_type = infer_list_type(key or field_name, value, used, classes)
            fields.append((list_type, field_name, json_key))
        elif value is None:
            fields.append(("Object", field_name, json_key))
        else:
            fields.append((java_type_for_value(value), field_name, json_key))

    lines = ["@JsonIgnoreProperties(ignoreUnknown = true)", f"public static class {name} {{"]
    for f_type, f_name, json_key in fields:
        lines.append(f"    @JsonProperty(\"{json_key}\")")
        lines.append(f"    public {f_type} {f_name};")
    lines.append("}")
    return "\n".join(lines)


def generate_java(root_name: str, payload: Dict[str, Any], package: str | None) -> str:
    used: Dict[str, int] = {}
    classes: List[str] = []
    root_class_name = unique_class_name(root_name, used)
    root_def = build_class(root_class_name, payload, used, classes)
    classes.append(root_def)

    header = []
    if package:
        header.append(f"package {package};\n")
    header.append("import com.fasterxml.jackson.annotation.JsonIgnoreProperties;\n")
    header.append("import com.fasterxml.jackson.annotation.JsonProperty;\n")
    header.append("import java.util.*;\n")

    body = "\n\n".join(reversed(classes))  # ensure root last? we built children first then appended root
    # Actually root_def appended last; we reversed to place root first; so invert
    body = "\n\n".join(classes[::-1])
    return "\n".join(header + [body])


def main():
    parser = argparse.ArgumentParser(description="Convert JSON to Java POJOs (nested static classes)")
    parser.add_argument("input", help="Path to JSON file")
    parser.add_argument("-o", "--output", help="Output .java file (default: stdout)")
    parser.add_argument("--package", dest="package", help="Java package name", default=None)
    parser.add_argument("--class-name", dest="class_name", help="Root class name", default="Root")
    parser.add_argument(
        "--json-path",
        dest="json_path",
        help="Dot/bracket path within JSON to use as root (e.g., data.items[0].payload)",
        default=None,
    )
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))

    def resolve_path(node: Any, path: str) -> Any:
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

    if args.json_path:
        data = resolve_path(data, args.json_path)
        if data is None:
            raise SystemExit(f"json-path not found: {args.json_path}")

    if not isinstance(data, dict):
        raise SystemExit("Top-level JSON (after json-path) must be an object for class generation")

    java_code = generate_java(args.class_name, data, args.package)

    if args.output:
        Path(args.output).write_text(java_code, encoding="utf-8")
    else:
        print(java_code)


if __name__ == "__main__":
    main()
