"""User-defined persona persistence and session loading.

Personas are stored in ~/.synapse/personas.yaml and loaded into the
blackboard at session start. Runtime state (status, current_task_id)
lives on the blackboard only.
"""

from __future__ import annotations

import re
from pathlib import Path

from synapse.config_home import SYNAPSE_HOME_DIR
from synapse.protocol import Persona

PERSONAS_FILE = SYNAPSE_HOME_DIR / "personas.yaml"
WORKSPACES_DIR = SYNAPSE_HOME_DIR / "workspaces"


def create_workspace(task_id: str) -> str:
    """Create a durable workspace id for a task.

    The detached executor node resolves this id to a local filesystem path.
    """
    return f"ws-{task_id.replace('task-', '')}"


def resolve_workspace(workspace_id: str) -> Path:
    workspace = WORKSPACES_DIR / workspace_id
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def load_personas_from_file(path: Path | None = None) -> list[Persona]:
    """Load persona definitions from YAML. Returns empty list if file missing or malformed."""
    resolved = path or PERSONAS_FILE
    if not resolved.exists():
        return []
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError:
        return []
    return _parse_personas_yaml(text)


def save_personas_to_file(personas: list[Persona], path: Path | None = None) -> None:
    """Write persona definitions to YAML."""
    resolved = path or PERSONAS_FILE
    resolved.parent.mkdir(parents=True, exist_ok=True)
    lines = ["personas:"]
    for p in personas:
        lines.append(f"  - name: {_yaml_quote(p.name)}")
        lines.append(f"    avatar: {_yaml_quote(p.avatar)}")
        lines.append(f"    base_prompt: {_yaml_quote(p.base_prompt)}")
    resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_personas_yaml(text: str) -> list[Persona]:
    """Minimal parser for the personas.yaml format we generate."""
    personas: list[Persona] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "personas:":
            continue
        # New list item: "- name: ..."
        match = re.match(r'^-\s+(\w+):\s*(.*)', stripped)
        if match:
            if current.get("name"):
                personas.append(_build_persona(current))
            current = {match.group(1): _unquote(match.group(2))}
            continue
        # Continuation field: "  key: value"
        match = re.match(r'^(\w+):\s*(.*)', stripped)
        if match:
            current[match.group(1)] = _unquote(match.group(2))
    if current.get("name"):
        personas.append(_build_persona(current))
    return personas


def _build_persona(fields: dict[str, str]) -> Persona:
    name = fields.get("name", "")
    persona_id = f"persona-{name.lower().replace(' ', '-')}"
    return Persona(
        persona_id=persona_id,
        name=name,
        avatar=fields.get("avatar", ""),
        base_prompt=fields.get("base_prompt", ""),
    )


def _unquote(value: str) -> str:
    s = value.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s


def _yaml_quote(value: str) -> str:
    if not value:
        return '""'
    if any(c in value for c in ":#{}[]&*!|>'\"%@`\n"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f'"{value}"'
