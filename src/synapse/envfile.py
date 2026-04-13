from __future__ import annotations

import os
from pathlib import Path
import re


ENV_LINE_RE = re.compile(r"^\s*(?P<comment>#\s*)?(?P<key>[A-Z0-9_]+)=(?P<value>.*)$")


def load_env_file(path: Path, *, override: bool = False) -> dict[str, str]:
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = ENV_LINE_RE.match(raw_line)
        if not match or match.group("comment") is not None:
            continue
        key = match.group("key")
        value = match.group("value")
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded
