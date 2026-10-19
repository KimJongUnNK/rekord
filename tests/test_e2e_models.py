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
    _name_voices(r["id"], ["Emil", "Lisa", "Jake"])


def _name_voices(rid, names):
    """Like a user in "Wer ist das?": one name per unknown voice (all its lines move, the voice is learned)."""
    first = {}
    for s in db.list_segments(rid):
        if s["voice"] is not None:
            first.setdefault(s["voice"], s["id"])
    for (voice, seg_id), name in zip(sorted(first.items(), key=lambda kv: kv[1]), names):
        pipeline.assign_segment(seg_id, name, remember=True, whole_voice=True)


def _names(rid):
    sp = {s["id"]: s["name"] for s in db.list_speakers(rid)}
    return [(round(s["start"]), sp[s["speaker_id"]], s["text"]) for s in db.list_segments(rid)]


def test_meeting_diarization_transcription_and_people():
    r1 = db.create_recording("M1", str(FIX / "meeting1.wav"))
    res = pipeline.process(r1["id"])
    # nobody known yet: ONE entry "Nicht erkannte Stimme" – never "Sprecher 1, 2, 3" – but every line knows its voice
    assert res["speakers"] == 1
    (bucket,) = db.list_speakers(r1["id"])
    assert bucket["name"] == pipeline.UNKNOWN and bucket["voices"] == 3
    voices = [s["voice"] for s in db.list_segments(r1["id"])]
    # A B A B C A B  → three distinct voices in the right turn order
    assert voices[0] != voices[1] and voices[0] == voices[2] and voices[1] == voices[3]
    assert len({voices[0], voices[1], voices[4]}) == 3
    text = " ".join(t for _, _, t in _names(r1["id"])).lower()
    assert "budget" in text and "freitag" in text and "headliner" in text
    with pytest.raises(ValueError, match="mehrere Personen"):  # can't learn a voiceprint from three people at once
        pipeline.remember_speaker(r1["id"], bucket["id"], "Emil")

    # "Wer ist das?": name each voice once → all its lines move, voice profiles are created
    _name_voices(r1["id"], ["Emil", "Lisa", "Jake"])
    order = [n for _, n, _ in _names(r1["id"])]
    assert order[:5] == ["Emil", "Lisa", "Emil", "Lisa", "Jake"]
    assert {s["name"] for s in db.list_speakers(r1["id"])} == {"Emil", "Lisa", "Jake"}  # bucket is gone

    # second meeting: Emil + Lisa known, one new person → collected as "Nicht erkannte Stimme"
    r2 = db.create_recording("M2", str(FIX / "meeting2.wav"))
    pipeline.process(r2["id"])
    sp = db.list_speakers(r2["id"])
    named = {s["name"] for s in sp}
    assert {"Emil", "Lisa", pipeline.UNKNOWN} == named, named
    assert _names(r2["id"])[0][1] == "Lisa"
    unknown = next(s for s in sp if s["name"] == pipeline.UNKNOWN)
    assert unknown["voices"] == 1
    pipeline.remember_speaker(r2["id"], unknown["id"], "Dora")  # one voice in the bucket: naming it works directly
    assert "Dora" in {p["name"] for p in db.list_profiles()}


def test_headcount_without_known_people_fixes_the_number_of_voices():
    r = db.create_recording("Headcount", str(FIX / "meeting1.wav"))
    db.update_recording(r["id"], participants={"ids": [], "guests": 2})  # "Wer ist dabei?": 2 (on purpose too few)
    pipeline.process(r["id"])
    sp = db.list_speakers(r["id"])
    voices = {s["voice"] for s in db.list_segments(r["id"]) if s["voice"] is not None}
    known = [s for s in sp if s["name"] != pipeline.UNKNOWN]
    assert len(voices) + len(known) <= 2  # never more voices than people announced


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
    assert set(speaking) <= {"Emil", "Lisa", "Jake", pipeline.UNKNOWN}
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
    assert names[0] == "Lisa" and "Emil" in names and pipeline.UNKNOWN in names and "Jake" not in names
    assert not any(n.startswith("Sprecher") for n in names)


def test_enrollment_checks_that_only_one_person_speaks(tmp_path):
    import wave

    import numpy as np

    from rekord import audio
    from rekord.engines.diarize import diarize
    x = audio.load(FIX / "meeting1.wav")
    turns = diarize(x, "eres2net-base", 3, 0.6, 4)
    first = turns[0][2]
    clip = np.concatenate([x[int(a * 16000):int(b * 16000)] for a, b, s in turns if s == first])
    path = tmp_path / "one.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes((np.clip(clip, -1, 1) * 32767).astype("<i2").tobytes())
    prof = pipeline.enroll_from_audio("Solo", str(path))
    assert prof["quality"]["consistency"] >= 0.8 and prof["quality"]["seconds"] >= 8
    with pytest.raises(ValueError, match="mehreren Stimmen"):  # three people in one "sample" → refused
        pipeline.enroll_from_audio("Mix", str(FIX / "meeting1.wav"))
    with pytest.raises(ValueError, match="Zu kurz"):
        pipeline.enroll_from_audio("Kurz", str(path.parent / "short.wav") if _short(path) else "")


def _short(path):
    import wave
    out = path.parent / "short.wav"
    with wave.open(str(path)) as r, wave.open(str(out), "wb") as w:
        w.setparams(r.getparams())
        w.writeframes(r.readframes(16000 * 3))
    return True
