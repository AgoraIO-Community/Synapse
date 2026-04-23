from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


NEWBRO_HOME_DIR = Path.home() / ".newbro"
LEGACY_SYNAPSE_HOME_DIR = Path.home() / ".synapse"
SYNAPSE_HOME_DIR = NEWBRO_HOME_DIR
SYNAPSE_ENV_FILE = SYNAPSE_HOME_DIR / ".env"
SYNAPSE_CONNECTOR_CONFIG_FILE = SYNAPSE_HOME_DIR / "config.yaml"


class ConfigHomeMigrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ConfigHomeMigrationResult:
    migrated: bool
    warning: str | None = None


def ensure_newbro_home(
    *,
    legacy_home: Path | None = None,
    new_home: Path | None = None,
) -> ConfigHomeMigrationResult:
    target_home = new_home or SYNAPSE_HOME_DIR
    source_home = legacy_home or LEGACY_SYNAPSE_HOME_DIR
    if target_home.exists():
        return ConfigHomeMigrationResult(migrated=False)
    if not source_home.exists():
        return ConfigHomeMigrationResult(migrated=False)
    if not source_home.is_dir():
        raise ConfigHomeMigrationError(
            f"Legacy config path is not a directory: {source_home}"
        )
    try:
        source_home.rename(target_home)
        return ConfigHomeMigrationResult(migrated=True)
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
            return ConfigHomeMigrationResult(
                migrated=True,
                warning=(
                    f"Migrated config to {format_user_path(target_home)} "
                    f"but could not remove {format_user_path(source_home)}: {exc}. "
                    f"Continue using {format_user_path(target_home)} and remove "
                    f"{format_user_path(source_home)} manually if it is no longer needed."
                ),
            )
        return ConfigHomeMigrationResult(migrated=True)


def format_user_path(path: Path) -> str:
    try:
        relative = path.expanduser().resolve().relative_to(Path.home().resolve())
    except ValueError:
        return str(path)
    return f"~/{relative}" if str(relative) != "." else "~"
