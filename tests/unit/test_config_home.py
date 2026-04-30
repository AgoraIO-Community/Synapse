from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from newbro.config_home import ensure_newbro_home


def test_ensure_newbro_home_moves_legacy_directory(tmp_path: Path):
    legacy_home = tmp_path / ".synapse"
    new_home = tmp_path / ".newbro"
    legacy_home.mkdir()
    (legacy_home / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

    migrated = ensure_newbro_home(legacy_home=legacy_home, new_home=new_home)

    assert migrated.migrated is True
    assert migrated.warning is None
    assert not legacy_home.exists()
    assert (new_home / ".env").read_text(encoding="utf-8") == "OPENAI_API_KEY=test-key\n"


def test_ensure_newbro_home_is_noop_when_new_home_already_exists(tmp_path: Path):
    legacy_home = tmp_path / ".synapse"
    new_home = tmp_path / ".newbro"
    legacy_home.mkdir()
    new_home.mkdir()

    migrated = ensure_newbro_home(legacy_home=legacy_home, new_home=new_home)

    assert migrated.migrated is False
    assert migrated.warning is None
    assert legacy_home.exists()
    assert new_home.exists()


def test_ensure_newbro_home_falls_back_to_copytree_when_rename_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    legacy_home = tmp_path / ".synapse"
    new_home = tmp_path / ".newbro"
    legacy_home.mkdir()
    (legacy_home / "config.yaml").write_text("version: 1\n", encoding="utf-8")

    original_rename = Path.rename

    def failing_rename(self: Path, target: Path) -> Path:
        if self == legacy_home and target == new_home:
            raise OSError("cross-device link")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", failing_rename)

    migrated = ensure_newbro_home(legacy_home=legacy_home, new_home=new_home)

    assert migrated.migrated is True
    assert migrated.warning is None
    assert not legacy_home.exists()
    assert (new_home / "config.yaml").read_text(encoding="utf-8") == "version: 1\n"


def test_ensure_newbro_home_warns_when_copy_succeeds_but_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    legacy_home = tmp_path / ".synapse"
    new_home = tmp_path / ".newbro"
    legacy_home.mkdir()
    (legacy_home / "config.yaml").write_text("version: 1\n", encoding="utf-8")

    original_rename = Path.rename
    original_rmtree = shutil.rmtree

    def failing_rename(self: Path, target: Path) -> Path:
        if self == legacy_home and target == new_home:
            raise OSError("cross-device link")
        return original_rename(self, target)

    def failing_rmtree(path: Path, *args, **kwargs) -> None:
        if path == legacy_home:
            raise OSError("permission denied")
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(Path, "rename", failing_rename)
    monkeypatch.setattr("newbro.config_home.shutil.rmtree", failing_rmtree)

    migrated = ensure_newbro_home(legacy_home=legacy_home, new_home=new_home)

    assert migrated.migrated is True
    assert migrated.warning is not None
    assert "Migrated config to" in migrated.warning
    assert "could not remove" in migrated.warning
    assert new_home.exists()
    assert legacy_home.exists()
    assert (new_home / "config.yaml").read_text(encoding="utf-8") == "version: 1\n"
