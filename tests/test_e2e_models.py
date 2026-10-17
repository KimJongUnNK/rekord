"""End-to-end with the real ONNX models: diarization, person recognition across meetings, live streaming.

Run:  python scripts/make_test_audio.py && pytest -m models
(Set REKORD_TEST_MODELS=/path/to/models to reuse downloaded models.)
"""
from pathlib import Path

import pytest

from rekord import config, db, models, pipeline

FIX = Path(__file__).parent / "fixtures"
pytestmark = [pytest.mark.models,
              pytest.mark.skipif(not (FIX / "meeting1.wav").exists(), reason="run scripts/make_test_audio.py first")]


@pytest.fixture(scope="module", autouse=True)
def ready():
    config.save({"asr_model": "whisper-base", "language": ""})
    models.ensure(models.ESSENTIAL + ["whisper-base"])


@pytest.fixture(scope="module")
def people():
    """Emil, Lisa, Jake enrolled from meeting 1 (by naming the diarized speakers, like a user would)."""
    if {"Emil", "Lisa", "Jake"} <= {p["name"] for p in db.list_profiles()}:
        return
    r = db.create_recording("Enroll", str(FIX / "meeting1.wav"))
    pipeline.process(r["id"])
    first = {}
    for s in db.list_segments(r["id"]):
        first.setdefault(s["speaker_id"], s["start"])
    for sid, name in zip(sorted(first, key=first.get), ["Emil", "Lisa", "Jake"]):
        pipeline.remember_speaker(r["id"], sid, name)


def _names(rid):
    sp = {s["id"]: s["name"] for s in db.list_speakers(rid)}
    return [(round(s["start"]), sp[s["speaker_id"]], s["text"]) for s in db.list_segments(rid)]


def test_meeting_diarization_transcription_and_people():
    r1 = db.create_recording("M1", str(FIX / "meeting1.wav"))
    res = pipeline.process(r1["id"])
    assert res["speakers"] == 3
    segs = _names(r1["id"])
    order = [n for _, n, _ in segs]
    # A B A B C A B  → three distinct people in the right turn order
    assert order[0] != order[1] and order[0] == order[2] and order[1] == order[3]
    assert len({order[0], order[1], order[4]}) == 3
    text = " ".join(t for _, _, t in segs).lower()
    assert "budget" in text and "freitag" in text and "headliner" in text

    # name them → voice profiles
    by_first = {}
    for s in db.list_segments(r1["id"]):
        by_first.setdefault(s["speaker_id"], s["start"])
    ids = sorted(by_first, key=by_first.get)
    for sid, name in zip(ids, ["Emil", "Lisa", "Jake"]):
        pipeline.remember_speaker(r1["id"], sid, name)

    # second meeting: Emil + Lisa known, one new person
    r2 = db.create_recording("M2", str(FIX / "meeting2.wav"))
    pipeline.process(r2["id"])
    sp = db.list_speakers(r2["id"])
    named = {s["name"] for s in sp}
    assert {"Emil", "Lisa"} <= named, named
    assert any(n.startswith("Sprecher") for n in named)
    assert "Jake" not in named
    first = _names(r2["id"])[0]
    assert first[1] == "Lisa"


def test_live_session_recognizes_people_in_realtime(people):
    from rekord import audio, live
    x = audio.load(FIX / "meeting1.wav")
    ev = []
    s = live.LiveSession(ev.append, "Live", sample_rate=16000)
    pcm = (x * 32767).astype("<i2").tobytes()
    import time
    for i in range(0, len(pcm), 3200):  # 0.1 s chunks at ~4x real time (a real mic delivers 1x)
        s.feed_pcm16(pcm[i:i + 3200])
        time.sleep(0.025)
    rid = s.stop()
    segs = [e for e in ev if e["type"] == "segment"]
    speaking = [e["name"] for e in ev if e["type"] == "speaking"]
    assert len(segs) >= 6
    assert [e["name"] for e in segs[:2]] == ["Emil", "Lisa"]
    assert "Jake" in [e["name"] for e in segs]
    assert speaking.count("Emil") >= 3 and speaking.count("Lisa") >= 3 and "Jake" in speaking
    assert set(speaking) <= {"Emil", "Lisa", "Jake", "Neue Stimme"}
    rec = db.get_recording(rid)
    assert rec["audio_path"].endswith(".m4a") and abs(rec["duration"] - len(x) / 16000) < 0.5 and rec["peaks"]


def test_participants_restrict_matching(people):
    from rekord import audio, live
    ids = {p["name"]: p["id"] for p in db.list_profiles()}
    x = audio.load(FIX / "meeting2.wav")
    ev = []
    s = live.LiveSession(ev.append, "P", participants=[ids["Emil"], ids["Lisa"]], guests=1)
    pcm = (x * 32767).astype("<i2").tobytes()
    for i in range(0, len(pcm), 3200):
        s.feed_pcm16(pcm[i:i + 3200])
    s.stop()
    names = [e["name"] for e in ev if e["type"] == "segment"]
    assert names[0] == "Lisa" and "Emil" in names and any(n.startswith("Sprecher") for n in names) and "Jake" not in names
