#!/usr/bin/env bash
set -euo pipefail

ROOT="${SYNAPSE_INSTALL_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
FRONTEND_DIR="$ROOT/src/synapse/ui"

log() {
  printf '[install] %s\n' "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

detect_uname() {
  if [[ -n "${SYNAPSE_INSTALL_TEST_UNAME:-}" ]]; then
    printf '%s\n' "$SYNAPSE_INSTALL_TEST_UNAME"
    return
  fi
  uname -s
}

os_release_path() {
  if [[ -n "${SYNAPSE_INSTALL_TEST_OS_RELEASE:-}" ]]; then
    printf '%s\n' "$SYNAPSE_INSTALL_TEST_OS_RELEASE"
    return
  fi
  printf '/etc/os-release\n'
}

run_as_root() {
  if [[ "$(id -u)" == "0" ]]; then
    "$@"
    return
  fi
  if have_cmd sudo; then
    sudo "$@"
    return
  fi
  die "sudo is required for system package installation."
}

install_macos_dependencies() {
  if ! have_cmd brew; then
    die "Homebrew is required on macOS. Install Homebrew first, then rerun ./install.sh."
  fi

  log "Installing macOS dependencies with Homebrew"
  brew install python@3.12 bun
}

install_linux_dependencies() {
  if ! have_cmd apt-get; then
    die "Only Ubuntu/Debian apt-get environments are supported by install.sh right now."
  fi

  log "Installing Ubuntu/Debian dependencies with apt-get"
  run_as_root apt-get update
  run_as_root apt-get install -y python3 python3-venv python3-pip curl ca-certificates

  if ! have_cmd bun; then
    if ! have_cmd curl; then
      die "curl is required to install Bun."
    fi
    log "Installing Bun"
    curl -fsSL https://bun.sh/install | bash
    export PATH="$HOME/.bun/bin:$PATH"
  fi
}

ensure_supported_linux() {
  local os_release
  os_release="$(os_release_path)"
  [[ -f "$os_release" ]] || die "Cannot detect Linux distribution: missing $os_release"

  # shellcheck disable=SC1090
  source "$os_release"
  case "${ID:-}" in
    ubuntu|debian)
      ;;
    *)
      die "install.sh supports Ubuntu and Debian on Linux right now."
      ;;
  esac
}

choose_python() {
  if have_cmd python3.12; then
    command -v python3.12
    return
  fi
  if have_cmd python3; then
    command -v python3
    return
  fi
  die "A Python 3 interpreter is required but was not found after dependency installation."
}

bootstrap_repo_dependencies() {
  local python_bin="$1"
  local venv_python
  venv_python="$ROOT/.venv/bin/python"

  [[ -d "$FRONTEND_DIR" ]] || die "Expected frontend directory at $FRONTEND_DIR"

  log "Creating repo virtualenv"
  "$python_bin" -m venv "$ROOT/.venv"
  [[ -x "$venv_python" ]] || die "Virtualenv bootstrap did not create $venv_python"

  log "Installing editable Python dependencies"
  "$venv_python" -m pip install --upgrade pip
  "$venv_python" -m pip install -e '.[dev]'

  if have_cmd bun; then
    log "Installing frontend dependencies with Bun"
    (
      cd "$FRONTEND_DIR"
      bun install
    )
    return
  fi

  if have_cmd npm; then
    log "Installing frontend dependencies with npm"
    (
      cd "$FRONTEND_DIR"
      npm install
    )
    return
  fi

  die "Need Bun or npm to install frontend dependencies."
}

bootstrap_config_files() {
  local venv_python="$ROOT/.venv/bin/python"

  [[ -x "$venv_python" ]] || die "Expected virtualenv python at $venv_python"

  log "Creating starter Synapse config files"
  "$venv_python" -m synapse setup --bootstrap-defaults
}

main() {
  local uname_out
  local python_bin

  uname_out="$(detect_uname)"
  case "$uname_out" in
    Darwin)
      install_macos_dependencies
      ;;
    Linux)
      ensure_supported_linux
      install_linux_dependencies
      ;;
    *)
      die "install.sh supports macOS and Ubuntu/Debian right now."
      ;;
  esac

  python_bin="$(choose_python)"
  bootstrap_repo_dependencies "$python_bin"
  bootstrap_config_files

  printf '\nNext:\n'
  printf '  ./synapse setup\n'
  printf '  ./synapse doctor\n'
  printf '  ./synapse dev\n'
}

main "$@"
