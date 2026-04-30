from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_root_launcher_layout_has_only_newbro_bootstrap() -> None:
    assert (ROOT / "newbro").is_file()
    assert not (ROOT / "newbro.py").exists()


def test_public_package_metadata_documents_newbro_namespace() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    repository_url = "https://github.com/AgoraIO/newbro"

    assert project["name"] == "newbro-cli"
    assert "Newbro CLI" in project["description"]
    assert "communication-brain" in project["description"]
    assert "newbro" in set(project["keywords"])
    assert project["scripts"]["newbro"] == "newbro.cli.main:main"
    assert project["urls"]["Repository"] == repository_url
    assert project["urls"]["Documentation"] == f"{repository_url}#readme"
