from __future__ import annotations

from pathlib import Path
import runpy
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PACKAGE_ROOT = SRC / "synapse"


def _ensure_src_on_path() -> None:
    src_str = str(SRC)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


def _load_package_shim() -> None:
    _ensure_src_on_path()
    globals()["__file__"] = str(PACKAGE_ROOT / "__init__.py")
    globals()["__package__"] = "synapse"
    globals()["__path__"] = [str(PACKAGE_ROOT)]
    init_code = (PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8")
    exec(compile(init_code, globals()["__file__"], "exec"), globals())


if __name__ == "__main__":
    _ensure_src_on_path()
    runpy.run_path(str(PACKAGE_ROOT / "__main__.py"), run_name="__main__")
else:
    _load_package_shim()
