#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
TARGET_REPOSITORY="pypi"
TARGET_LABEL="PyPI"
DRY_RUN=0
ASSUME_YES=0
DIST_DIR=""
VERSION_OVERRIDE=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/publish_pypi.sh [--testpypi] [--dry-run] [--yes] [--dist-dir PATH] [--version VERSION]

Options:
  --testpypi        Upload to TestPyPI instead of PyPI.
  --dry-run         Build and validate artifacts but skip upload.
  --yes             Skip the interactive confirmation prompt.
  --dist-dir PATH   Write build artifacts to PATH instead of a temporary directory.
  --version VALUE   Override the package version for this build/upload. Accepts
                    either 1.2.3 or v1.2.3.
  -h, --help        Show this help message.

Environment:
  PYTHON            Python interpreter to use. Defaults to python3.
  PYPI_TOKEN        PyPI API token. If set, Twine uses __token__ automatically.
  TWINE_USERNAME    Twine username. Optional when using PYPI_TOKEN.
  TWINE_PASSWORD    Twine password or API token.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --testpypi)
      TARGET_REPOSITORY="testpypi"
      TARGET_LABEL="TestPyPI"
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    --dist-dir)
      [[ $# -ge 2 ]] || {
        echo "error: --dist-dir requires a path" >&2
        exit 1
      }
      DIST_DIR="$2"
      shift 2
      ;;
    --version)
      [[ $# -ge 2 ]] || {
        echo "error: --version requires a value" >&2
        exit 1
      }
      VERSION_OVERRIDE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

cd "$ROOT"

if [[ ! -f pyproject.toml ]]; then
  echo "error: pyproject.toml not found in $ROOT" >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: python interpreter not found: $PYTHON_BIN" >&2
  exit 1
fi

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import build  # noqa: F401
import twine  # noqa: F401
PY
then
  echo "error: missing release tooling. Run: $PYTHON_BIN -m pip install '.[release]'" >&2
  exit 1
fi

PROJECT_META=()
while IFS= read -r line; do
  PROJECT_META+=("$line")
done < <("$PYTHON_BIN" - <<'PY'
from pathlib import Path
import tomllib

pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
project = pyproject["project"]
print(project["name"])
print(project["version"])
PY
)

if [[ ${#PROJECT_META[@]} -lt 2 ]]; then
  echo "error: failed to read project metadata from pyproject.toml" >&2
  exit 1
fi

PACKAGE_NAME="${PROJECT_META[0]}"
PACKAGE_VERSION="${PROJECT_META[1]}"
PYPROJECT_VERSION="$PACKAGE_VERSION"

if [[ -n "$VERSION_OVERRIDE" ]]; then
  if [[ "$VERSION_OVERRIDE" == v* ]]; then
    VERSION_OVERRIDE="${VERSION_OVERRIDE#v}"
  fi
  if [[ -z "$VERSION_OVERRIDE" ]]; then
    echo "error: release version override cannot be empty" >&2
    exit 1
  fi
  PACKAGE_VERSION="$VERSION_OVERRIDE"
fi

if [[ -n "${PYPI_TOKEN:-}" ]]; then
  export TWINE_USERNAME="${TWINE_USERNAME:-__token__}"
  export TWINE_PASSWORD="${TWINE_PASSWORD:-$PYPI_TOKEN}"
elif [[ -n "${TWINE_PASSWORD:-}" ]]; then
  export TWINE_USERNAME="${TWINE_USERNAME:-__token__}"
fi

TEMP_DIR=""
PYPROJECT_BACKUP=""
if [[ -z "$DIST_DIR" ]]; then
  TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/newbro-publish.XXXXXX")"
  DIST_DIR="$TEMP_DIR/dist"
else
  mkdir -p "$DIST_DIR"
fi

cleanup() {
  if [[ -n "$PYPROJECT_BACKUP" && -f "$PYPROJECT_BACKUP" ]]; then
    cp "$PYPROJECT_BACKUP" "$ROOT/pyproject.toml"
    rm -f "$PYPROJECT_BACKUP"
  fi
  if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
  fi
}
trap cleanup EXIT

if [[ "$PACKAGE_VERSION" != "$PYPROJECT_VERSION" ]]; then
  PYPROJECT_BACKUP="$(mktemp "${TMPDIR:-/tmp}/pyproject.toml.backup.XXXXXX")"
  cp "$ROOT/pyproject.toml" "$PYPROJECT_BACKUP"
  "$PYTHON_BIN" - "$PACKAGE_VERSION" <<'PY'
from pathlib import Path
import re
import sys

version = sys.argv[1]
path = Path("pyproject.toml")
text = path.read_text(encoding="utf-8")
updated, count = re.subn(
    r'(?m)^version = "[^"]+"$',
    f'version = "{version}"',
    text,
    count=1,
)
if count != 1:
    raise SystemExit("error: failed to override project version in pyproject.toml")
path.write_text(updated, encoding="utf-8")
PY
fi

echo "[publish] package: $PACKAGE_NAME"
echo "[publish] version: $PACKAGE_VERSION"
if [[ "$PACKAGE_VERSION" != "$PYPROJECT_VERSION" ]]; then
  echo "[publish] pyproject version override: $PYPROJECT_VERSION -> $PACKAGE_VERSION"
fi
echo "[publish] target: $TARGET_LABEL"
echo "[publish] python: $PYTHON_BIN"
echo "[publish] dist dir: $DIST_DIR"

if [[ $ASSUME_YES -ne 1 && $DRY_RUN -ne 1 ]]; then
  read -r -p "Continue with upload to $TARGET_LABEL? [y/N] " reply
  case "${reply,,}" in
    y|yes)
      ;;
    *)
      echo "[publish] cancelled"
      exit 0
      ;;
  esac
fi

echo "[publish] building"
"$PYTHON_BIN" -m build --outdir "$DIST_DIR"

shopt -s nullglob
artifacts=("$DIST_DIR"/*)
shopt -u nullglob

if [[ ${#artifacts[@]} -eq 0 ]]; then
  echo "error: build produced no artifacts in $DIST_DIR" >&2
  exit 1
fi

echo "[publish] checking artifacts"
"$PYTHON_BIN" -m twine check "${artifacts[@]}"

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[publish] dry run complete; upload skipped"
  exit 0
fi

echo "[publish] uploading"
"$PYTHON_BIN" -m twine upload --repository "$TARGET_REPOSITORY" "${artifacts[@]}"

echo "[publish] uploaded $PACKAGE_NAME==$PACKAGE_VERSION to $TARGET_LABEL"
