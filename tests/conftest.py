from pathlib import Path
import os
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TEST_HOME = ROOT / ".pytest-home"
TEST_HOME.mkdir(exist_ok=True)
os.environ["HOME"] = str(TEST_HOME)
os.environ["USERPROFILE"] = str(TEST_HOME)

from newbro.runtime import config as config_module


@pytest.fixture(autouse=True)
def isolate_test_runtime_env(monkeypatch, tmp_path: Path):
    for name in list(os.environ):
        if name.startswith(("SYNAPSE_", "OPENAI_")):
            monkeypatch.delenv(name, raising=False)

    # Tests should opt into local config explicitly instead of inheriting a developer's ~/.newbro env.
    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", tmp_path / ".env")
