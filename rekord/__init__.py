"""REKORD - local AI note taker. Record, transcribe, know who speaks, summarize."""
import os as _os

# REKORD_TEST_VERSION: the update tests pretend to be an older version
__version__ = _os.environ.get("REKORD_TEST_VERSION") or "1.3.3"
