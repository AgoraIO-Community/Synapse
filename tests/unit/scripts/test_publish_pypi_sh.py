from __future__ import annotations

from pathlib import Path
import os
import stat
import subprocess
import textwrap
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "publish_pypi.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def project_metadata() -> tuple[str, str]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    return project["name"], project["version"]


def fake_python_script(package_name: str, package_version: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

if [[ "${{1-}}" == "-" ]]; then
  script="$(cat)"
  if [[ "$script" == *"import build"* && "$script" == *"import twine"* ]]; then
    exit 0
  fi
  if [[ "$script" == *'print(project["name"])'* && "$script" == *'print(project["version"])'* ]]; then
    printf '%s\\n%s\\n' "{package_name}" "{package_version}"
    exit 0
  fi
  echo "unexpected inline python: $script" >&2
  exit 1
fi

if [[ "${{1-}}" == "-m" && "${{2-}}" == "build" && "${{3-}}" == "--outdir" ]]; then
  dist_dir="${{4:?}}"
  mkdir -p "$dist_dir"
  touch "$dist_dir/{package_name}-{package_version}.tar.gz"
  touch "$dist_dir/{package_name}-{package_version}-py3-none-any.whl"
  exit 0
fi

if [[ "${{1-}}" == "-m" && "${{2-}}" == "twine" && "${{3-}}" == "check" ]]; then
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
"""


def test_publish_pypi_sh_reads_project_metadata_without_mapfile(tmp_path: Path):
    package_name, package_version = project_metadata()
    fake_python = tmp_path / "python3"
    dist_dir = tmp_path / "dist"
    write_executable(fake_python, fake_python_script(package_name, package_version))

    env = os.environ.copy()
    env["PYTHON"] = str(fake_python)

    completed = subprocess.run(
        ["/bin/bash", str(PUBLISH_SCRIPT), "--dry-run", "--dist-dir", str(dist_dir)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert f"[publish] package: {package_name}" in completed.stdout
    assert f"[publish] version: {package_version}" in completed.stdout
    assert "[publish] checking artifacts" in completed.stdout
    assert "[publish] dry run complete; upload skipped" in completed.stdout
    assert (dist_dir / f"{package_name}-{package_version}.tar.gz").exists()
