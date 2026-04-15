from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class YAMLParseError(ValueError):
    pass


def load_yaml_file(path: Path) -> Any:
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return _load_simple_yaml(path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass(slots=True)
class _SimpleYAMLLine:
    indent: int
    content: str
    lineno: int


def _load_simple_yaml(path: Path) -> Any:
    lines = _tokenize_simple_yaml(path)
    if not lines:
        return {}
    value, next_index = _parse_block(lines, 0, lines[0].indent)
    if next_index != len(lines):
        raise YAMLParseError(f"{path}:{lines[next_index].lineno}: unexpected trailing YAML content")
    return value


def _tokenize_simple_yaml(path: Path) -> list[_SimpleYAMLLine]:
    parsed: list[_SimpleYAMLLine] = []
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent % 2 != 0:
            raise YAMLParseError(f"{path}:{lineno}: indentation must use multiples of 2 spaces")
        parsed.append(_SimpleYAMLLine(indent=indent, content=raw_line[indent:], lineno=lineno))
    return parsed


def _parse_block(lines: list[_SimpleYAMLLine], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        raise YAMLParseError("unexpected end of YAML input")
    if lines[index].content.startswith("- "):
        return _parse_list(lines, index, indent)
    if lines[index].content in {"{}", "[]"}:
        return _parse_scalar(lines[index].content), index + 1
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines: list[_SimpleYAMLLine], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent != indent:
            raise YAMLParseError(
                f"line {line.lineno}: unexpected indentation for mapping entry"
            )
        if line.content.startswith("- "):
            break
        if ":" not in line.content:
            raise YAMLParseError(f"line {line.lineno}: expected key: value mapping entry")
        key, remainder = line.content.split(":", 1)
        key = key.strip()
        if not key:
            raise YAMLParseError(f"line {line.lineno}: empty mapping key")
        remainder = remainder.strip()
        index += 1
        if remainder:
            result[key] = _parse_scalar(remainder)
            continue
        if index >= len(lines) or lines[index].indent <= indent:
            result[key] = None
            continue
        value, index = _parse_block(lines, index, lines[index].indent)
        result[key] = value
    return result, index


def _parse_list(lines: list[_SimpleYAMLLine], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent != indent or not line.content.startswith("- "):
            break
        item = line.content[2:].strip()
        index += 1
        if item:
            result.append(_parse_scalar(item))
            continue
        if index >= len(lines) or lines[index].indent <= indent:
            result.append(None)
            continue
        value, index = _parse_block(lines, index, lines[index].indent)
        result.append(value)
    return result, index


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"null", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1].replace('\\"', '"')
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1].replace("\\'", "'")
    if value == "{}":
        return {}
    if value == "[]":
        return []
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
