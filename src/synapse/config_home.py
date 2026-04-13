from __future__ import annotations

from pathlib import Path


SYNAPSE_HOME_DIR = Path.home() / ".synapse"
SYNAPSE_ENV_FILE = SYNAPSE_HOME_DIR / ".env"
SYNAPSE_GATEWAY_CONFIG_FILE = SYNAPSE_HOME_DIR / "config.yaml"


def format_user_path(path: Path) -> str:
    try:
        relative = path.expanduser().resolve().relative_to(Path.home().resolve())
    except ValueError:
        return str(path)
    return f"~/{relative}" if str(relative) != "." else "~"
