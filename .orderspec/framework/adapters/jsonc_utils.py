"""JSONC (JSON with Comments) utilities for reading and writing kilo.jsonc files."""
import re
import json
from typing import Any, Dict

def _strip_jsonc_comments(text: str) -> str:
    """Remove // line comments and /* */ block comments from JSONC text.
    
    Simple implementation that handles comments outside of strings.
    Not perfect for all edge cases, but sufficient for kilo.jsonc files.
    """
    # Remove /* */ block comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    
    # Remove // line comments (but not inside strings)
    lines = text.split('\n')
    result = []
    for line in lines:
        in_string = False
        escape = False
        for i, c in enumerate(line):
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
            if c == '/' and i + 1 < len(line) and line[i + 1] == '/' and not in_string:
                line = line[:i]
                break
        result.append(line)
    return '\n'.join(result)


def read_jsonc(path: str) -> Dict[str, Any]:
    """Read a JSONC file and return parsed dict.
    
    Returns empty dict if file doesn't exist.
    Raises ValueError if file exists but contains invalid JSON.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return {}
    
    if not content.strip():
        return {}
    
    stripped = _strip_jsonc_comments(content)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")


def write_jsonc(path: str, data: Dict[str, Any]) -> None:
    """Write dict as JSONC file with a header comment."""
    header = "// This file is managed by OrderSpec. Manual edits may be overwritten by order.bootstrap.\n"
    with open(path, 'w', encoding='utf-8') as f:
        f.write(header)
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
