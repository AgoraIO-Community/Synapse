"""User-defined persona persistence and session loading.

Personas are stored in ~/.synapse/personas.yaml and loaded into the
blackboard at session start. The same file also persists the optional
communication-brain persona prompt. Runtime state (status,
current_task_id) lives on the blackboard only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from synapse.config_home import SYNAPSE_HOME_DIR
from synapse.protocol import Persona

PERSONAS_FILE = SYNAPSE_HOME_DIR / "personas.yaml"
WORKSPACES_DIR = SYNAPSE_HOME_DIR / "workspaces"


@dataclass(slots=True)
class PersonaStore:
    personas: list[Persona] = field(default_factory=list)
    communication_persona_prompt: str = ""


def create_workspace(task_id: str) -> str:
    """Create a durable workspace id for a task."""
    return f"ws-{task_id.replace('task-', '')}"


def resolve_workspace(workspace_id: str) -> Path:
    """Resolve a durable workspace id into a local workspace path."""
    resolved_id = (
        f"ws-{workspace_id.replace('task-', '')}"
        if workspace_id.startswith("task-")
        else workspace_id
    )
    candidates = [
        WORKSPACES_DIR / resolved_id,
        Path.cwd() / ".synapse" / "workspaces" / resolved_id,
    ]
    last_error: OSError | None = None
    for workspace in candidates:
        try:
            workspace.mkdir(parents=True, exist_ok=True)
            return workspace
        except OSError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError("Failed to create a workspace directory.")


def load_personas_from_file(path: Path | None = None) -> list[Persona]:
    """Load persona definitions from YAML. Returns empty list if file missing or malformed."""
    resolved = path or PERSONAS_FILE
    if not resolved.exists():
        return []
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError:
        return []
    return _parse_persona_store_yaml(text).personas


def load_communication_persona_prompt_from_file(path: Path | None = None) -> str:
    """Load the persisted communication-brain persona prompt from YAML."""
    resolved = path or PERSONAS_FILE
    if not resolved.exists():
        return ""
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError:
        return ""
    return _parse_persona_store_yaml(text).communication_persona_prompt


def save_personas_to_file(personas: list[Persona], path: Path | None = None) -> None:
    """Write persona definitions to YAML."""
    resolved = path or PERSONAS_FILE
    communication_persona_prompt = load_communication_persona_prompt_from_file(resolved)
    _write_persona_store(
        PersonaStore(
            personas=personas,
            communication_persona_prompt=communication_persona_prompt,
        ),
        resolved,
    )


def save_communication_persona_prompt_to_file(prompt: str, path: Path | None = None) -> None:
    """Write the communication-brain persona prompt while preserving worker personas."""
    resolved = path or PERSONAS_FILE
    personas = load_personas_from_file(resolved)
    _write_persona_store(
        PersonaStore(
            personas=personas,
            communication_persona_prompt=prompt,
        ),
        resolved,
    )


def _parse_personas_yaml(text: str) -> list[Persona]:
    """Minimal parser for the personas.yaml format we generate."""
    return _parse_persona_store_yaml(text).personas


def _parse_persona_store_yaml(text: str) -> PersonaStore:
    """Minimal parser for the personas.yaml format we generate."""
    store = PersonaStore()
    personas: list[Persona] = []
    current: dict[str, str] = {}
    in_personas_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "personas:":
            in_personas_block = True
            continue
        if stripped.startswith("communication_persona_prompt:"):
            _, value = stripped.split(":", 1)
            store.communication_persona_prompt = _unquote(value)
            continue
        if not in_personas_block:
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
    store.personas = personas
    return store


def _write_persona_store(store: PersonaStore, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"communication_persona_prompt: {_yaml_quote(store.communication_persona_prompt)}",
        "personas:",
    ]
    for persona in store.personas:
        lines.append(f"  - name: {_yaml_quote(persona.name)}")
        lines.append(f"    avatar: {_yaml_quote(persona.avatar)}")
        lines.append(f"    base_prompt: {_yaml_quote(persona.base_prompt)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
        return (
            s[1:-1]
            .replace("\\n", "\n")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s


def _yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
    return f'"{escaped}"'
