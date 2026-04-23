from __future__ import annotations

from pathlib import Path

import pytest

from synapse.config_home import ensure_newbro_home


def test_ensure_newbro_home_moves_legacy_directory(tmp_path: Path):
    legacy_home = tmp_path / ".synapse"
    new_home = tmp_path / ".newbro"
    legacy_home.mkdir()
    (legacy_home / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

    migrated = ensure_newbro_home(legacy_home=legacy_home, new_home=new_home)

    assert migrated is True
    assert not legacy_home.exists()
    assert (new_home / ".env").read_text(encoding="utf-8") == "OPENAI_API_KEY=test-key\n"


def test_ensure_newbro_home_is_noop_when_new_home_already_exists(tmp_path: Path):
    legacy_home = tmp_path / ".synapse"
    new_home = tmp_path / ".newbro"
    legacy_home.mkdir()
    new_home.mkdir()

    migrated = ensure_newbro_home(legacy_home=legacy_home, new_home=new_home)

    assert migrated is False
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

    assert migrated is True
    assert not legacy_home.exists()
    assert (new_home / "config.yaml").read_text(encoding="utf-8") == "version: 1\n"
