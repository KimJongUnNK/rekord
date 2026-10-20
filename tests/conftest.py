import os
import shutil
import subprocess
import sys
import tempfile
import time
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


@pytest.fixture
def pulse(tmp_path):
    """A virtual speaker (PulseAudio null sink "speakers") = the other people in an online meeting.
    Yields the environment for processes that play into it or record from it. Linux only."""
    if not (sys.platform.startswith("linux") and all(shutil.which(t) for t in ("pulseaudio", "pactl", "paplay"))):
        pytest.skip("needs PulseAudio (apt install pulseaudio pulseaudio-utils)")
    xdg = tmp_path / "xdg"
    xdg.mkdir(mode=0o700)
    env = dict(os.environ, XDG_RUNTIME_DIR=str(xdg), PULSE_RUNTIME_PATH=str(xdg / "pulse"))
    subprocess.run(["pulseaudio", "-D", "--exit-idle-time=-1", "--system=false", "-n", "--disallow-exit",
                    "--load=module-native-protocol-unix", "--load=module-null-sink sink_name=speakers",
                    "--load=module-always-sink"], env=env, check=True, capture_output=True, timeout=20)
    try:
        for _ in range(50):
            if subprocess.run(["pactl", "info"], env=env, capture_output=True).returncode == 0:
                break
            time.sleep(0.1)
        subprocess.run(["pactl", "set-default-sink", "speakers"], env=env, check=True, capture_output=True)
        yield env
    finally:
        subprocess.run(["pulseaudio", "--kill"], env=env, capture_output=True)


@pytest.fixture(scope="session")
def hub():
    """The real REKORD hub on a free port – what the native window and the iPhone app talk to."""
    import socket
    import threading

    import uvicorn

    from rekord.server import app
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app.state.port, app.state.lan, app.state.auto_download = port, False, False
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(200):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.05)
    yield port
    srv.should_exit = True
    t.join(5)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_HOME, ignore_errors=True)
