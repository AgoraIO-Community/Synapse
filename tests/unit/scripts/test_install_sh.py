from __future__ import annotations

from pathlib import Path
import os
import stat
import subprocess
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def prepare_repo_root(root: Path) -> None:
    (root / "frontend").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='synapse'\n", encoding="utf-8")
    (root / "frontend" / "package.json").write_text('{"name":"synapse-frontend"}\n', encoding="utf-8")


def fake_python_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
echo "$(basename "$0") $*" >> "$FAKE_LOG"
if [[ "${1-}" == "-m" && "${2-}" == "venv" ]]; then
  target="${3:?}"
  mkdir -p "$target/bin"
  cat > "$target/bin/python" <<'INNER'
#!/usr/bin/env bash
set -euo pipefail
echo "venv-python $*" >> "$FAKE_LOG"
exit 0
INNER
  chmod +x "$target/bin/python"
fi
"""


def test_install_sh_macos_bootstraps_repo(tmp_path: Path):
    repo_root = tmp_path / "repo"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    log_file = tmp_path / "install.log"
    prepare_repo_root(repo_root)
    fake_bin.mkdir()
    home.mkdir()

    write_executable(
        fake_bin / "brew",
        """#!/usr/bin/env bash
echo "brew $*" >> "$FAKE_LOG"
""",
    )
    write_executable(fake_bin / "python3.12", fake_python_script())
    write_executable(
        fake_bin / "bun",
        """#!/usr/bin/env bash
echo "bun $*" >> "$FAKE_LOG"
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "FAKE_LOG": str(log_file),
            "HOME": str(home),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "SYNAPSE_INSTALL_ROOT": str(repo_root),
            "SYNAPSE_INSTALL_TEST_UNAME": "Darwin",
        }
    )

    completed = subprocess.run(
        ["bash", str(INSTALL_SCRIPT)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    log_text = log_file.read_text(encoding="utf-8")
    assert "brew install python@3.12 bun" in log_text
    assert f"python3.12 -m venv {repo_root / '.venv'}" in log_text
    assert "venv-python -m pip install --upgrade pip" in log_text
    assert "venv-python -m pip install -e .[dev]" in log_text
    assert "bun install" in log_text
    assert "./synapse setup" in completed.stdout


def test_install_sh_ubuntu_bootstraps_repo(tmp_path: Path):
    repo_root = tmp_path / "repo"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    log_file = tmp_path / "install.log"
    os_release = tmp_path / "os-release"
    prepare_repo_root(repo_root)
    fake_bin.mkdir()
    home.mkdir()
    os_release.write_text("ID=ubuntu\n", encoding="utf-8")

    write_executable(
        fake_bin / "id",
        """#!/usr/bin/env bash
echo "1000"
""",
    )
    write_executable(
        fake_bin / "sudo",
        """#!/usr/bin/env bash
echo "sudo $*" >> "$FAKE_LOG"
"$@"
""",
    )
    write_executable(
        fake_bin / "apt-get",
        """#!/usr/bin/env bash
echo "apt-get $*" >> "$FAKE_LOG"
""",
    )
    write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env bash
echo "curl $*" >> "$FAKE_LOG"
cat <<'INNER'
mkdir -p "$HOME/.bun/bin"
cat > "$HOME/.bun/bin/bun" <<'BUN'
#!/usr/bin/env bash
set -euo pipefail
echo "bun $*" >> "$FAKE_LOG"
BUN
chmod +x "$HOME/.bun/bin/bun"
INNER
""",
    )
    write_executable(fake_bin / "python3", fake_python_script())
    write_executable(fake_bin / "python3.12", fake_python_script())

    env = os.environ.copy()
    env.update(
        {
            "FAKE_LOG": str(log_file),
            "HOME": str(home),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "SYNAPSE_INSTALL_ROOT": str(repo_root),
            "SYNAPSE_INSTALL_TEST_UNAME": "Linux",
            "SYNAPSE_INSTALL_TEST_OS_RELEASE": str(os_release),
        }
    )

    completed = subprocess.run(
        ["bash", str(INSTALL_SCRIPT)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    log_text = log_file.read_text(encoding="utf-8")
    assert "sudo apt-get update" in log_text
    assert "apt-get install -y python3 python3-venv python3-pip curl ca-certificates" in log_text
    assert "curl -fsSL https://bun.sh/install" in log_text
    assert f"python3.12 -m venv {repo_root / '.venv'}" in log_text
    assert "venv-python -m pip install --upgrade pip" in log_text
    assert "bun install" in log_text
