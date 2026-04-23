from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_root_launcher_layout_has_only_newbro_bootstrap() -> None:
    assert (ROOT / "newbro").is_file()
    assert not (ROOT / "synapse.py").exists()


def test_public_package_metadata_documents_newbro_synapse_split() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    repository_url = "https://github.com/AgoraIO/Synapse"

    assert project["name"] == "newbro-cli"
    assert "Newbro CLI" in project["description"]
    assert "Synapse" in project["description"]
    assert {"newbro", "synapse"}.issubset(set(project["keywords"]))
    assert project["scripts"]["newbro"] == "synapse.cli.main:main"
    assert project["urls"]["Repository"] == repository_url
    assert project["urls"]["Documentation"] == f"{repository_url}#readme"
