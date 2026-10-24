"""End-to-end with the real ONNX models: diarization, person recognition across meetings, live streaming.

Run:  python scripts/make_test_audio.py && pytest -m models
(Set REKORD_TEST_MODELS=/path/to/models to reuse downloaded models.)
"""
from pathlib import Path

import numpy as np
import pytest

from rekord import config, db, models, pipeline

FIX = Path(__file__).parent / "fixtures"
pytestmark = [pytest.mark.models,
              pytest.mark.skipif(not (FIX / "meeting1.wav").exists(), reason="tests/fixtures/*.wav missing (they are in the repository)")]


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
    for i in range(0, len(pcm), 3200):  # 0.1 s chunks at ~2x real time (a real mic delivers 1x; faster, a slow CI
        s.feed_pcm16(pcm[i:i + 3200])    # runner falls behind and skips "who speaks" probes – by design)
        time.sleep(0.05)
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


def test_online_meeting_hears_the_people_in_the_call(people, pulse, tmp_path):
    """Online: the others talk only through the computer's speaker (virtual), the microphone hears nothing.
    REKORD records the call's sound, transcribes it and knows who speaks."""
    import json
    import subprocess
    import sys
    script = f"""
import json, subprocess, sys, time
sys.path.insert(0, {str(Path(__file__).resolve().parent.parent)!r})
from rekord import db, live
ev = []
s = live.LiveSession(ev.append, "Call", meeting="online", call_audio=True)
assert s.call is not None, s.notes
p = subprocess.Popen(["paplay", "--device=speakers", {str(FIX / "meeting1.wav")!r}])
last = t0 = time.time()
while time.time() - t0 < 38:  # the microphone: silence, at the real pace of a microphone
    time.sleep(0.1)
    now = time.time()
    s.feed_pcm16(bytes(int((now - last) * 16000) * 2))
    last = now
p.wait()
rid = s.stop()
print(json.dumps({{"segs": [e["name"] for e in ev if e["type"] == "segment"],
                  "text": " ".join(e.get("text", "") for e in ev if e["type"] == "segment"),
                  "participants": db.get_recording(rid)["participants"]}}))
"""
    (tmp_path / "call.py").write_text(script)
    out = subprocess.run([sys.executable, str(tmp_path / "call.py")], env=pulse, capture_output=True, text=True, timeout=240)
    assert out.returncode == 0, out.stderr[-3000:]
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert len(r["segs"]) >= 5, r
    assert {"Emil", "Lisa"} <= set(r["segs"]), r["segs"]  # known people, heard only through the call
    assert len(r["text"]) > 100
    assert r["participants"]["meeting"] == "online"


def _write_wav(path, x):
    import wave as _wave
    with _wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def test_free_talk_enrollment_ignores_a_question_in_between(people, tmp_path):
    """„Einfach reden lassen“: Emil talks, Lisa asks something in between → only Emil is learned."""
    from rekord import audio
    from rekord.engines import voiceprint
    rid = next(r["id"] for r in db.list_recordings() if r.get("audio_path", "").endswith("meeting1.wav")
               and {"Emil", "Lisa"} <= {s["name"] for s in db.list_speakers(r["id"])})
    x = audio.load(FIX / "meeting1.wav")
    segs = db.list_segments(rid)
    sp = {s["id"]: s["name"] for s in db.list_speakers(rid)}
    part = lambda who: [x[int(s["start"] * 16000):int(s["end"] * 16000)] for s in segs if sp.get(s["speaker_id"]) == who]  # noqa: E731
    emil, lisa = part("Emil"), part("Lisa")
    mixed = np.concatenate(emil[:len(emil) // 2] + lisa[:1] + emil[len(emil) // 2:])
    _write_wav(tmp_path / "free.wav", mixed)
    prof = pipeline.enroll_from_audio("Emil frei", str(tmp_path / "free.wav"), mode="free")
    assert prof["quality"]["left_out"] >= 2, prof["quality"]  # Lisa's question was left out
    learned = db.get_profile(prof["id"], with_embedding=True)["embedding"]
    ref = {p["name"]: p["embedding"] for p in db.list_profiles(with_embedding=True)}
    assert voiceprint.cosine(learned, ref["Emil"]) > voiceprint.cosine(learned, ref["Lisa"]) + 0.15
    db.delete_profile(prof["id"])


def test_lecture_separates_lecturer_and_audience(people, monkeypatch):
    """Vorlesung: nobody known → the voice that talks most is the lecturer, everyone else the audience;
    then the lecturer is learned from the recording."""
    from rekord.engines import voiceprint
    monkeypatch.setattr(voiceprint, "match_profiles", lambda embs, profiles, thr: {})  # as if nobody was enrolled
    r = db.create_recording("Vorlesung", str(FIX / "meeting1.wav"))
    db.update_recording(r["id"], participants={"ids": [], "guests": 0, "meeting": "lecture"})
    pipeline.process(r["id"])
    names = {s["name"]: s for s in db.list_speakers(r["id"])}
    assert set(names) == {pipeline.LECTURER, pipeline.AUDIENCE}, names
    assert names[pipeline.AUDIENCE]["voices"] == 2
    voices = pipeline.recording_voices(r["id"])
    lect = next(v for v in voices if v["name"] == pipeline.LECTURER)
    assert all(lect["seconds"] >= v["seconds"] for v in voices)
    assert len([v for v in voices if v["name"] == pipeline.AUDIENCE]) == 2
    monkeypatch.undo()
    prof = pipeline.learn_voice(r["id"], lect["speaker_id"], None, "Prof. Test")
    assert prof["name"] == "Prof. Test"
    assert any(s["name"] == "Prof. Test" for s in db.list_speakers(r["id"]))
    db.delete_profile(prof["id"])


def test_native_window_live_recording(people, monkeypatch):
    """The desktop window's own live path: microphone chunks at 48 kHz (a typical device rate) → bridge → engine.
    Audio that arrives while the models load is kept; names appear live; Stopp saves and hands over the recording."""
    pytest.importorskip("PySide6.QtQuick", exc_type=ImportError)
    import os
    import time

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from rekord import audio, live
    from rekord.app import bridge
    QGuiApplication.instance() or QGuiApplication(["rekord-e2e"])

    def pump(cond, timeout):
        end = time.time() + timeout
        while time.time() < end and not cond():
            QCoreApplication.processEvents()
            time.sleep(0.005)
        return cond()

    monkeypatch.setattr(bridge.Mic, "start", lambda self, device_id="": True)  # the chunks come from the file below
    monkeypatch.setattr(bridge.Mic, "stop", lambda self: None)
    x = audio.load(FIX / "meeting1.wav")
    x48 = live.resample(x, 16000, 48000)
    pcm = (np.clip(x48, -1, 1) * 32767).astype("<i2").tobytes()
    lv = bridge.Live()
    done = []
    lv.finished.connect(done.append)
    ids = {p["name"]: p["id"] for p in db.list_profiles()}
    lv.start("Native", "person", [ids["Emil"], ids["Lisa"], ids["Jake"]], 3)
    step = 9600  # 0.1 s at 48 kHz, 16 bit
    for i in range(0, len(pcm), step):
        lv._mic.chunk.emit(pcm[i:i + step], 48000)
        pump(lambda: False, 0.02)  # ~5x real time
    assert pump(lambda: lv.state == "recording", 60)
    pump(lambda: False, 3)
    lv.stop()
    assert pump(lambda: bool(done), 180)
    names = [r["name"] for r in lv.lines.items()]
    assert len(names) >= 6 and names[:2] == ["Emil", "Lisa"] and "Jake" in names
    assert {r["name"] for r in lv.roster} >= {"Emil", "Lisa", "Jake"}
    rec = db.get_recording(done[0])
    assert rec["title"] == "Native" and rec["audio_path"].endswith(".m4a")
    assert abs(rec["duration"] - len(x) / 16000) < 0.5  # nothing lost while the models loaded
    assert rec["participants"]["ids"] == [ids["Emil"], ids["Lisa"], ids["Jake"]]


def test_native_enrollment_from_the_window(hub, monkeypatch):
    """Person einsprechen in the window: native recorder (48 kHz mic) → 16 kHz sample → upload → a real voiceprint
    that recognizes the person in a meeting."""
    pytest.importorskip("PySide6.QtQuick", exc_type=ImportError)
    import json
    import os
    import time

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    from rekord import audio, live
    from rekord.app import api as api_mod
    from rekord.app import bridge
    QGuiApplication.instance() or QGuiApplication(["rekord-e2e"])
    monkeypatch.setattr(bridge.Mic, "start", lambda self, device_id="": True)
    monkeypatch.setattr(bridge.Mic, "stop", lambda self: None)

    def pump(cond, timeout):
        end = time.time() + timeout
        while time.time() < end and not cond():
            QCoreApplication.processEvents()
            time.sleep(0.01)
        return cond()

    from rekord import jobs
    assert jobs.wait_idle(300)  # the hub's worker picks up the recording of the live test before – let it finish

    # Lisa's lines from meeting 1 – what she'd say into the microphone
    x = audio.load(FIX / "meeting1.wav")
    r = db.create_recording("Probe", str(FIX / "meeting1.wav"), status="processing")
    pipeline.process(r["id"])
    first = db.list_segments(r["id"])
    lisa_voice = first[1]["voice"]
    lines = [s for s in first if s["voice"] == lisa_voice]
    sample = np.concatenate([x[int(s["start"] * 16000):int(s["end"] * 16000)] for s in lines])
    pcm = (np.clip(live.resample(sample, 16000, 48000), -1, 1) * 32767).astype("<i2").tobytes()

    v = bridge.VoiceRecorder()
    v.start(240)
    for i in range(0, len(pcm), 9600):
        v._on_chunk(pcm[i:i + 9600], 48000)
    v.stop()
    assert v.speech > 10 and v.path

    a = api_mod.Api(hub)
    got = {}
    a.reply.connect(lambda i, ok, status, data: got.__setitem__(i, (ok, data)))
    rid = a.upload("/api/profiles/enroll", v.path, json.dumps({"name": "Lisa Native", "mode": "free"}))
    assert pump(lambda: rid in got, 120)
    ok, prof = got[rid]
    assert ok, prof
    assert prof["name"] == "Lisa Native" and prof["quality"]["seconds"] > 5
    v.discard()
    assert not os.path.exists(v.path or "/nonexistent")


def test_analysis_in_its_own_low_priority_process(hub):
    """The real path after every recording: the hub's worker hands the recording to `rekord --process-job` (low
    priority, half the cores) – the transcript arrives, progress comes in few steps, the window process stays light."""
    from rekord import jobs
    assert jobs.wait_idle(300)
    events = []
    jobs.subscribe(events.append)
    try:
        r = db.create_recording("Hintergrund", str(FIX / "meeting2.wav"))
        jobs.enqueue(r["id"])
        assert jobs.wait_idle(600)
    finally:
        jobs.unsubscribe(events.append)
    rec = db.get_recording(r["id"])
    assert rec["status"] == "done", rec.get("error")
    assert len(db.list_segments(r["id"])) >= 4 and db.list_speakers(r["id"])
    mine = [e for e in events if e.get("id") == r["id"]]
    prog = [e for e in mine if e["type"] == "progress"]
    assert 3 <= len(prog) <= 40, len(prog)  # not one per half second of audio any more
    assert mine[-1]["type"] == "done"


def test_live_window_shows_who_speaks_while_the_transcript_is_busy(people, monkeypatch):
    """The bug "I talk, but REKORD shows me silent": in real time (100 ms microphone chunks at 48 kHz on the UI
    thread), while whisper works on the last sentence, the window must keep showing that someone speaks – and the
    live lines must arrive in order."""
    pytest.importorskip("PySide6.QtQuick", exc_type=ImportError)
    import time

    import sherpa_onnx
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication, QTimer
    from PySide6.QtGui import QGuiApplication

    from rekord import audio, live, models
    from rekord.app import bridge
    QGuiApplication.instance() or QGuiApplication(["rekord-e2e"])
    x = audio.load(FIX / "meeting1.wav")
    vcfg = sherpa_onnx.VadModelConfig(silero_vad=sherpa_onnx.SileroVadModelConfig(
        model=str(models.path("silero-vad")), threshold=0.5, min_silence_duration=0.35, min_speech_duration=0.25,
        max_speech_duration=30.0, window_size=live.WIN), sample_rate=16000, num_threads=1)
    vad = sherpa_onnx.VoiceActivityDetector(vcfg, buffer_size_in_seconds=120)
    for i in range(0, len(x) // live.WIN * live.WIN, live.WIN):
        vad.accept_waveform(x[i:i + live.WIN])
    vad.flush()
    truth = []
    while not vad.empty():
        truth.append((vad.front.start / 16000, (vad.front.start + len(vad.front.samples)) / 16000))
        vad.pop()

    monkeypatch.setattr(bridge.Mic, "start", lambda self, device_id="": True)
    monkeypatch.setattr(bridge.Mic, "stop", lambda self: None)
    lv = bridge.Live()
    done = []
    lv.finished.connect(done.append)
    lv.start("Echtzeit", "person", [], 3)
    end = time.time() + 120
    while lv.state != "recording" and time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    pcm = (np.clip(audio.resample(x, 16000, 48000), -1, 1) * 32767).astype("<i2").tobytes()
    step, pos, t0, shown = 9600, [0], time.monotonic(), []

    def tick():  # like a microphone: as much audio as real time allows, on the UI thread
        target = int((time.monotonic() - t0) * 10) * step
        while pos[0] < min(target, len(pcm)):
            lv._mic.chunk.emit(pcm[pos[0]:pos[0] + step], 48000)  # noqa: SLF001
            pos[0] += step
        shown.append((pos[0] / 2 / 48000, bool(lv.speaking)))
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    stop_at = time.monotonic() + len(x) / 16000 + 1
    while time.monotonic() < stop_at:
        QCoreApplication.processEvents()
        time.sleep(0.005)
    timer.stop()
    talking = [s for s in shown if any(a + 0.4 <= s[0] <= b - 0.1 for a, b in truth)]
    silent = sum(1 for s in talking if not s[1])
    assert talking and silent / len(talking) < 0.1, f"shown silent {silent / len(talking):.0%} of the talk"
    lv.stop()
    end = time.time() + 300
    while not done and time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert done and len(lv.lines.items()) >= 3
