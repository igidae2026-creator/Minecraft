from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
from typing import Any


_REAL_YAML = None
_REAL_YAML_PATH = Path("/usr/lib/python3/dist-packages/yaml/__init__.py")
if _REAL_YAML_PATH.is_file():
    spec = importlib.util.spec_from_file_location(
        "_pyyaml_real",
        _REAL_YAML_PATH,
        submodule_search_locations=[str(_REAL_YAML_PATH.parent)],
    )
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _REAL_YAML = module


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line


def _scalar(raw: str) -> Any:
    s = raw.strip()
    if s == "":
        return ""
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "none", "~"}:
        return None
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    try:
        if any(c in s for c in (".", "e", "E")):
            return float(s)
        return int(s)
    except ValueError:
        pass
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
        try:
            return ast.literal_eval(s)
        except Exception:
            return s
    return s


def safe_load(text):
    if _REAL_YAML is not None:
        if hasattr(text, "read"):
            return _REAL_YAML.safe_load(text)  # type: ignore[union-attr]
        return _REAL_YAML.safe_load(text)  # type: ignore[union-attr]
    if hasattr(text, "read"):
        text = text.read()
    if text is None:
        return None
    lines = []
    for raw in text.splitlines():
        clean = _strip_comment(raw).rstrip("\n\r")
        if clean.strip() == "":
            continue
        indent = len(clean) - len(clean.lstrip(" "))
        lines.append((indent, clean.strip()))

    idx = 0

    def parse_block(base_indent: int):
        nonlocal idx
        # decide container type by first line at this level
        if idx >= len(lines):
            return {}
        is_list = lines[idx][1] == "-" or lines[idx][1].startswith("- ")
        container = [] if is_list else {}

        while idx < len(lines):
            indent, content = lines[idx]
            if indent < base_indent:
                break
            if indent > base_indent:
                raise ValueError(f"Invalid indentation near: {content}")

            if isinstance(container, list):
                if content != "-" and not content.startswith("- "):
                    break
                item = "" if content == "-" else content[2:].strip()
                idx += 1
                if item == "":
                    if idx < len(lines) and lines[idx][0] > indent:
                        container.append(parse_block(lines[idx][0]))
                    else:
                        container.append(None)
                elif ":" in item and not item.startswith(('"', "'")):
                    key, value = item.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    obj = {}
                    if value == "":
                        if idx < len(lines) and lines[idx][0] > indent:
                            obj[key] = parse_block(lines[idx][0])
                        else:
                            obj[key] = {}
                    else:
                        obj[key] = _scalar(value)
                        if idx < len(lines) and lines[idx][0] > indent:
                            nested = parse_block(lines[idx][0])
                            if isinstance(nested, dict):
                                obj.update(nested)
                    container.append(obj)
                else:
                    container.append(_scalar(item))
                continue

            # mapping
            if content.startswith("- "):
                break
            if ":" not in content:
                raise ValueError(f"Invalid mapping line: {content}")
            key, value = content.split(":", 1)
            key = key.strip()
            value = value.strip()
            idx += 1
            if value == "":
                if idx < len(lines) and (lines[idx][0] > indent or (lines[idx][0] == indent and lines[idx][1].startswith("- "))):
                    container[key] = parse_block(lines[idx][0])
                else:
                    container[key] = {}
            else:
                container[key] = _scalar(value)
        return container

    if not lines:
        return None
    result = parse_block(lines[0][0])
    return result


def safe_dump(payload, stream, sort_keys=False, allow_unicode=True):  # noqa: ARG001
    if _REAL_YAML is not None:
        return _REAL_YAML.safe_dump(payload, stream, sort_keys=sort_keys, allow_unicode=allow_unicode)  # type: ignore[union-attr]

    def fmt(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v)
        if not s or any(ch in s for ch in (":", "#", "\n")) or s.strip() != s:
            return repr(s)
        return s

    def emit(obj, ind=0):
        pad = " " * ind
        if isinstance(obj, dict):
            items = obj.items()
            if sort_keys:
                items = sorted(items, key=lambda kv: kv[0])
            parts = []
            for k, v in items:
                if isinstance(v, (dict, list)):
                    parts.append(f"{pad}{k}:")
                    parts.append(emit(v, ind + 2))
                else:
                    parts.append(f"{pad}{k}: {fmt(v)}")
            return "\n".join(parts)
        if isinstance(obj, list):
            parts = []
            for v in obj:
                if isinstance(v, (dict, list)):
                    parts.append(f"{pad}-")
                    parts.append(emit(v, ind + 2))
                else:
                    parts.append(f"{pad}- {fmt(v)}")
            return "\n".join(parts)
        return f"{pad}{fmt(obj)}"

    stream.write(emit(payload) + "\n")
