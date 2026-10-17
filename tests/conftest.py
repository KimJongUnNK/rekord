import os
import shutil
import sys
import tempfile
from pathlib import Path

# isolated data dir for the whole test session – must be set before rekord is imported
_HOME = Path(tempfile.mkdtemp(prefix="rekord-test-"))
os.environ["REKORD_HOME"] = str(_HOME)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# reuse already downloaded models if available (REKORD_TEST_MODELS=/path/to/models)
_models = os.environ.get("REKORD_TEST_MODELS")
if _models and Path(_models).is_dir():
    (_HOME / "models").parent.mkdir(parents=True, exist_ok=True)
    os.symlink(_models, _HOME / "models", target_is_directory=True)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def home() -> Path:
    return _HOME


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_HOME, ignore_errors=True)
