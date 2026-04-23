from __future__ import annotations

from pathlib import Path
import shutil


NEWBRO_HOME_DIR = Path.home() / ".newbro"
LEGACY_SYNAPSE_HOME_DIR = Path.home() / ".synapse"
SYNAPSE_HOME_DIR = NEWBRO_HOME_DIR
SYNAPSE_ENV_FILE = SYNAPSE_HOME_DIR / ".env"
SYNAPSE_CONNECTOR_CONFIG_FILE = SYNAPSE_HOME_DIR / "config.yaml"


class ConfigHomeMigrationError(RuntimeError):
    pass


def ensure_newbro_home(
    *,
    legacy_home: Path | None = None,
    new_home: Path | None = None,
) -> bool:
    target_home = new_home or SYNAPSE_HOME_DIR
    source_home = legacy_home or LEGACY_SYNAPSE_HOME_DIR
    if target_home.exists():
        return False
    if not source_home.exists():
        return False
    if not source_home.is_dir():
        raise ConfigHomeMigrationError(
            f"Legacy config path is not a directory: {source_home}"
        )
    try:
        source_home.rename(target_home)
        return True
    except OSError:
        try:
            shutil.copytree(source_home, target_home)
        except Exception as exc:
            shutil.rmtree(target_home, ignore_errors=True)
            raise ConfigHomeMigrationError(
                f"Failed to migrate {format_user_path(source_home)} "
                f"to {format_user_path(target_home)}: {exc}"
            ) from exc
        try:
            shutil.rmtree(source_home)
        except Exception as exc:
            raise ConfigHomeMigrationError(
                f"Migrated config to {format_user_path(target_home)} "
                f"but could not remove {format_user_path(source_home)}: {exc}"
            ) from exc
        return True


def format_user_path(path: Path) -> str:
    try:
        relative = path.expanduser().resolve().relative_to(Path.home().resolve())
    except ValueError:
        return str(path)
    return f"~/{relative}" if str(relative) != "." else "~"
