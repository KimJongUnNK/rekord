"""Unit tests: pure logic, storage, exports, templates, LLM plumbing. No models needed."""
import json
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from rekord import config, db, export
from rekord.engines import asr, voiceprint
from rekord.engines.diarize import clean_turns
from rekord.llm import providers, templates
from rekord import summarize


# ------------------------------------------------------------------ diarization post-processing

def test_clean_turns_merges_same_speaker_and_drops_blips():
    turns = [(0, 2, 5), (2.3, 4, 5), (4.1, 4.2, 7), (5, 8, 7)]
    out = clean_turns(turns)
    assert out == [(0, 4, 0), (5, 8, 1)]  # merged, blip removed, relabelled by first appearance


def test_clean_turns_resolves_overlap():
    out = clean_turns([(0, 5, 0), (4, 9, 1)])
    assert out[0][1] == out[1][0] == 5  # second speaker starts where the first ends
    assert [t[2] for t in out] == [0, 1]


def test_clean_turns_contained_interjection():
    out = clean_turns([(0, 10, 0), (4, 6, 1)])
    assert [t[2] for t in out] == [0, 1, 0]
    assert out[1] == (4, 6, 1)


# ------------------------------------------------------------------ ASR helpers

def test_split_long_respects_whisper_window():
    sr = 16000
    x = np.random.default_rng(0).normal(0, 0.1, sr * 70).astype(np.float32)
    x[sr * 22:sr * 23] = 0  # a pause where the cut should go
    chunks = asr.split_long(0, 70, x)
    assert all(b - a <= asr.MAX_CHUNK + 1e-6 for a, b in chunks)
    assert chunks[0][0] == 0 and chunks[-1][1] == 70
    assert 22 <= chunks[0][1] <= 23.1


def test_assign_words_to_speakers():
    words = [{"start": 0.1, "end": 0.4, "word": " Hallo"}, {"start": 0.5, "end": 0.9, "word": " zusammen"},
             {"start": 2.1, "end": 2.5, "word": " Danke"}, {"start": 2.6, "end": 2.9, "word": " dir"}]
    segs = asr.assign_words(words, [(0, 1.5, 0), (2, 3, 1)], "de")
    assert [(s["label"], s["text"]) for s in segs] == [(0, "Hallo zusammen"), (1, "Danke dir")]


def test_merge_chunks_rejoins_split_turn():
    segs = [{"start": 0, "end": 28, "label": 0, "text": "a"}, {"start": 28, "end": 40, "label": 0, "text": "b"},
            {"start": 41, "end": 45, "label": 1, "text": "c"}]
    out = asr.merge_chunks(segs)
    assert len(out) == 2 and out[0]["text"] == "a b" and out[0]["end"] == 40


@pytest.mark.parametrize("t,expected", [("Untertitel im Auftrag des ZDF, 2021", ""), ("...", ""), ("  Hallo   Welt ", "Hallo Welt")])
def test_clean_text_filters_hallucinations(t, expected):
    assert asr.clean_text(t) == expected


def test_vocabulary_whole_words_case_insensitive():
    vocab = [{"from": "beni", "to": "Beeni"}, {"from": "voltage events", "to": "Voltage Events"}]
    assert asr.apply_vocabulary("DJ beni bei voltage events, benign bleibt", vocab) == "DJ Beeni bei Voltage Events, benign bleibt"


# ------------------------------------------------------------------ voiceprints

def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_match_profiles_one_to_one():
    a, b = _unit([1, 0, 0]), _unit([0, 1, 0])
    profiles = [{"id": 1, "name": "Emil", "embedding": a}, {"id": 2, "name": "Lisa", "embedding": b}]
    spk = {0: _unit([0.9, 0.1, 0]), 1: _unit([0.8, 0.2, 0]), 2: _unit([0.1, 0.95, 0])}
    m = voiceprint.match_profiles(spk, profiles, 0.5)
    assert m[0][0]["name"] == "Emil" and m[2][0]["name"] == "Lisa" and 1 not in m  # Emil only once


def test_online_clusterer_profiles_clusters_and_closed_set():
    emil, lisa = _unit([1, 0, 0, 0]), _unit([0, 1, 0, 0])
    c = voiceprint.OnlineClusterer([{"id": 1, "name": "Emil", "color": "#f00", "embedding": emil}], 0.6, 0.6)
    r1 = c.assign(_unit([0.95, 0.05, 0, 0]))
    assert r1["name"] == "Emil" and r1["new"]
    r2 = c.assign(_unit([0, 0, 1, 0]))  # stranger → new anonymous cluster
    assert r2["name"] is None and r2["key"] == 1
    r3 = c.assign(_unit([0.05, 0, 0.97, 0]))  # same stranger again
    assert r3["key"] == 1 and not r3["new"]
    probe = c.assign(_unit([0.9, 0.1, 0, 0]), update=False)
    assert probe["name"] == "Emil"
    # closed set: a weak match still goes to the closest participant
    cs = voiceprint.OnlineClusterer([{"id": 1, "name": "Emil", "color": "#f00", "embedding": emil},
                                     {"id": 2, "name": "Lisa", "color": "#00f", "embedding": lisa}], 0.6, 0.6, closed_set=True)
    r = cs.assign(_unit([0.3, 0.6, 0.5, 0.5]))
    assert r["name"] == "Lisa"


def test_update_mean_stays_normalized():
    m = voiceprint.update_mean(_unit([1, 0]), 3, _unit([0, 1]))
    assert abs(np.linalg.norm(m) - 1) < 1e-5 and m[0] > m[1]


# ------------------------------------------------------------------ storage

@pytest.fixture()
def rec():
    r = db.create_recording("Test Meeting", "/nonexistent.wav", duration=12, highlights=[1.0])
    db.replace_transcript(r["id"], [
        {"label": 0, "name": "Emil", "color": "#FF5A1F", "embedding": _unit([1, 0, 0])},
        {"label": 1, "name": "Sprecher 1", "color": "#2D7FF9", "embedding": None},
    ], [
        {"start": 0, "end": 4, "label": 0, "text": "Wir brauchen den Rider bis Freitag.", "lang": "de"},
        {"start": 4.5, "end": 9, "label": 1, "text": "Ich schicke die Bestellung morgen.", "lang": "de"},
    ])
    yield r
    db.delete_recording(r["id"])


def test_transcript_roundtrip_and_search(rec):
    segs = db.list_segments(rec["id"])
    assert len(segs) == 2
    hits = db.search_segments("Bestellung")
    assert hits and hits[0]["speaker"] == "Sprecher 1"
    assert any(r["id"] == rec["id"] for r in db.list_recordings(q="Rider"))
    listed = next(r for r in db.list_recordings() if r["id"] == rec["id"])
    assert listed["speakers"][0] == {"name": "Emil", "color": "#FF5A1F"}


def test_find_replace_and_segment_edit(rec):
    assert db.find_replace(rec["id"], "Rider", "Technical Rider") == 1
    seg = db.list_segments(rec["id"])[1]
    db.update_segment(seg["id"], text="Ich schicke alles heute.")
    assert db.search_segments("heute")[0]["id"] == seg["id"]
    assert not db.search_segments("Bestellung")


def test_merge_speakers(rec):
    sp = db.list_speakers(rec["id"])
    db.merge_speakers(rec["id"], sp[1]["id"], sp[0]["id"])
    assert {s["speaker_id"] for s in db.list_segments(rec["id"])} == {sp[0]["id"]}
    assert len(db.list_speakers(rec["id"])) == 1


def test_profiles_crud_and_rename_propagates(rec):
    pid = db.create_profile("Lisa", _unit([0, 1, 0]))
    sp = db.list_speakers(rec["id"])[1]
    db.update_speaker(sp["id"], name="Lisa", profile_id=pid)
    db.update_profile(pid, name="Lisa M.")
    assert db.get_speaker(sp["id"])["name"] == "Lisa M."
    assert db.get_profile(pid)["recordings"] == 1
    db.delete_profile(pid)
    assert db.get_speaker(sp["id"])["profile_id"] is None


def test_participants_field(rec):
    db.update_recording(rec["id"], participants={"ids": [1, 2], "guests": 1})
    assert db.get_recording(rec["id"])["participants"] == {"ids": [1, 2], "guests": 1}


# ------------------------------------------------------------------ exports & prompts

def test_exports(rec):
    db.add_summary(rec["id"], "meeting", "Meeting-Protokoll", "# Titel\n- [ ] Rider — **Emil**")
    md = export.markdown(rec["id"])
    assert "# Test Meeting" in md and "**Emil** [00:00]" in md and "Meeting-Protokoll" in md
    srt = export.srt(rec["id"])
    assert "00:00:04,500 --> 00:00:09,000" in srt and "Sprecher 1:" in srt
    assert export.vtt(rec["id"]).startswith("WEBVTT") and "<v Emil>" in export.vtt(rec["id"])
    data = json.loads(export.as_json(rec["id"]))
    assert data["segments"][0]["speaker"] == "Emil"
    pytest.importorskip("docx")
    assert export.docx(rec["id"])[:2] == b"PK"


def test_transcript_text_marks_highlights(rec):
    t = summarize.transcript_text(rec["id"])
    assert "[00:00] Emil ★:" in t and "[00:04] Sprecher 1:" in t
    assert summarize.speaker_stats(rec["id"]) == "Sprecher 1: 53%, Emil: 47%"


def test_maybe_title_respects_lock(rec):
    summarize.maybe_title(rec["id"], "# Budget Sommerfestival\n...")
    assert db.get_recording(rec["id"])["title"] == "Budget Sommerfestival"
    db.update_recording(rec["id"], title="Mein Titel", title_locked=1)
    summarize.maybe_title(rec["id"], "# Anderer Titel")
    assert db.get_recording(rec["id"])["title"] == "Mein Titel"


def test_templates_complete_and_custom():
    ids = [t["id"] for t in templates.BUILTIN]
    assert len(ids) == len(set(ids)) >= 30 and "auto" in ids and "mindmap" in ids
    tid = db.save_template(None, "Booking DJ", "## Gage\n## Rider")
    assert templates.get(tid)["name"] == "Booking DJ"
    db.delete_template(tid)
    with pytest.raises(KeyError):
        templates.get(tid)


def test_keywords_strip_stopwords():
    assert summarize.keywords("Was hat Lisa letzte Woche zum Budget gesagt?") == "lisa woche budget"


def test_chunks_for_small_context():
    text = "\n".join(f"[00:{i:02d}] A: " + "x" * 50 for i in range(40))
    parts = summarize._chunks(text, 600)
    assert len(parts) > 3 and "\n".join(parts) == text


# ------------------------------------------------------------------ settings

def test_settings_merge_and_mask():
    s = config.save({"llm": {"anthropic": {"api_key": "sk-ant-secret-1234"}}})
    assert s["llm"]["anthropic"]["model"] == "claude-opus-5-5"  # defaults survive partial patches
    pub = config.public()
    assert pub["llm"]["anthropic"]["api_key"] == "••••1234" and pub["llm"]["anthropic"]["has_key"]
    assert config.load()["pair_token"]
    config.save({"llm": {"anthropic": {"api_key": ""}}})


# ------------------------------------------------------------------ LLM providers against a local OpenAI-compatible stub

@pytest.fixture(scope="module")
def llm_stub():
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse

    app = FastAPI()
    seen = {}

    @app.get("/v1/models")
    def models():
        return {"object": "list", "data": [{"id": "stub-1", "object": "model"}]}

    @app.post("/v1/chat/completions")
    async def chat(req: Request):
        body = await req.json()
        seen["last"] = body

        def gen():
            for piece in ["# Titel aus KI\n", "- [ ] Rider — **Emil** [00:00]"]:
                yield "data: " + json.dumps({"id": "1", "object": "chat.completion.chunk", "created": 0, "model": "stub",
                                              "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]}) + "\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=9311, log_level="error"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    config.save({"llm": {"provider": "compatible", "compatible": {"base_url": "http://127.0.0.1:9311/v1", "model": "stub-1"}}})
    yield seen
    server.should_exit = True
    config.save({"llm": {"provider": "anthropic"}})


def test_provider_stream_and_models(llm_stub):
    s = config.load()
    assert providers.list_models(s, "compatible") == ["stub-1"]
    out = providers.complete(s, "sys", [{"role": "user", "content": "hi"}])
    assert out.startswith("# Titel aus KI")
    assert llm_stub["last"]["messages"][0] == {"role": "system", "content": "sys"}


def test_generate_summary_saves_and_titles(llm_stub, rec):
    res = summarize.generate(rec["id"], "meeting")
    assert "Rider" in res["content"]
    assert db.list_summaries(rec["id"])[0]["model"] == "stub-1"
    assert db.get_recording(rec["id"])["title"] == "Titel aus KI"
    user_msg = llm_stub["last"]["messages"][1]["content"]
    assert "<transkript>" in user_msg and "Meeting-Protokoll" in user_msg


def test_provider_errors_are_friendly():
    s = config.load()
    s["llm"]["provider"] = "ollama"
    s["llm"]["ollama"]["base_url"] = "http://127.0.0.1:9"
    with pytest.raises(providers.LLMError, match="Ollama ist nicht installiert"):
        providers.complete(s, "x", [{"role": "user", "content": "x"}])
    s["llm"]["provider"] = "none"
    with pytest.raises(providers.LLMError):
        providers.complete(s, "x", [{"role": "user", "content": "x"}])


# ------------------------------------------------------------------ model registry

def test_model_registry_urls_are_sane():
    from rekord import models
    for m in models.REGISTRY.values():
        assert isinstance(m.url, str) and m.url.startswith("https://"), m.id
        assert isinstance(m.size_mb, int) and m.size_mb > 0, m.id
        assert m.files and isinstance(m.description, str), m.id
    assert set(models.ESSENTIAL) <= set(models.REGISTRY)


def test_correcting_a_misidentified_speaker_keeps_the_other_profile(rec):
    from rekord import pipeline
    lisa = db.create_profile("Lisa", _unit([0, 1, 0]))
    sp = db.list_speakers(rec["id"])[0]  # Emil's voice, wrongly matched to Lisa
    db.update_speaker(sp["id"], name="Lisa", profile_id=lisa)
    prof = pipeline.remember_speaker(rec["id"], sp["id"], "Anna")
    assert prof["name"] == "Anna" and prof["id"] != lisa
    lisa_now = db.get_profile(lisa, with_embedding=True)
    assert lisa_now["name"] == "Lisa" and lisa_now["samples"] == 1
    assert np.allclose(lisa_now["embedding"], _unit([0, 1, 0]))
    # confirming the same person again merges into that person
    again = pipeline.remember_speaker(rec["id"], sp["id"], "anna")
    assert again["id"] == prof["id"] and again["samples"] == 2
    db.delete_profile(lisa)
    db.delete_profile(prof["id"])


def test_concurrent_model_downloads_run_once(monkeypatch):
    from rekord import models
    calls = []

    def fake(mid, on_progress=None):
        calls.append(mid)
        time.sleep(0.3)
    monkeypatch.setattr(models, "_download", fake)
    ts = [threading.Thread(target=models.download, args=("silero-vad",)) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(calls) == 3  # serialized (each call re-checks installed() inside the lock)
    lock = models._dl_lock("silero-vad")
    assert not lock.locked()


def test_auto_summary_only_with_configured_ai(monkeypatch):
    from rekord import jobs
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = config.load()
    s["auto_summary"] = True
    s["llm"]["provider"], s["llm"]["anthropic"]["api_key"] = "anthropic", ""
    assert not jobs.wants_auto_summary(s)
    s["llm"]["anthropic"]["api_key"] = "sk-ant-x"
    assert jobs.wants_auto_summary(s)
    s["auto_summary"] = False
    assert not jobs.wants_auto_summary(s)


def test_strip_think_streaming():
    from rekord.llm.providers import _strip_think
    assert "".join(_strip_think(iter(["Hi ", "<thi", "nk>geheim</th", "ink>\n# Titel"]))) == "Hi # Titel"
    assert "".join(_strip_think(iter(["a < b <tag>"]))) == "a < b <tag>"


def test_merge_similar_speakers_fixes_over_split_voice():
    import numpy as np

    from rekord.pipeline import merge_similar_speakers
    rng = np.random.default_rng(1)
    a, b = rng.normal(size=192), rng.normal(size=192)
    a2 = a + rng.normal(scale=0.4, size=192)  # same person, other cluster
    turns = [(0, 5, 0), (5, 9, 1), (9, 12, 2), (12, 20, 0), (20, 22, 2)]
    out = merge_similar_speakers(turns, {0: a, 1: b, 2: a2}, 0.65)
    assert {s for _, _, s in out} == {0, 1}  # 2 → 0 (0 talks more)
    assert [s for _, _, s in out] == [0, 1, 0, 0, 0]
    assert merge_similar_speakers(turns, {0: a, 1: b}, 0.65) == turns  # different people stay apart


def test_wait_idle_gives_up_after_the_timeout(monkeypatch):
    """Tests (and quitting) wait for the background worker – but never forever."""
    import queue as q

    from rekord import jobs
    fresh: q.Queue = q.Queue()
    monkeypatch.setattr(jobs, "_q", fresh)
    assert jobs.wait_idle(0.1) is True
    fresh.put(("process", "x"))
    t = time.time()
    assert jobs.wait_idle(0.3) is False and time.time() - t < 2
    fresh.get()
    fresh.task_done()
    assert jobs.wait_idle(0.1) is True


def test_analysis_threads_leave_half_the_computer_free(monkeypatch):
    from rekord import system
    monkeypatch.setattr(system.os, "cpu_count", lambda: 10)
    assert system.processing_threads(8, gentle=True) == 5 and system.processing_threads(8, gentle=False) == 8
    assert system.processing_threads(3, gentle=True) == 3  # never more than you set
    monkeypatch.setattr(system.os, "cpu_count", lambda: 2)
    assert system.processing_threads(8, gentle=True) == 2  # but at least two


def test_mac_runs_the_analysis_with_utility_quality_of_service(monkeypatch):
    from rekord import system
    monkeypatch.setattr(system, "_taskpolicy", None)
    monkeypatch.setattr(system.sys, "platform", "darwin")
    monkeypatch.setattr(system.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
    assert system.in_background(["REKORD", "--process-job", "x"]) == ["/usr/sbin/taskpolicy", "-c", "utility", "REKORD", "--process-job", "x"]
    monkeypatch.setattr(system, "_taskpolicy", False)  # an old macOS without -c: start it plainly (nice still applies)
    assert system.in_background(["REKORD"]) == ["REKORD"]
    monkeypatch.setattr(system.sys, "platform", "linux")
    assert system.in_background(["rekord"]) == ["rekord"]


@pytest.mark.skipif(not hasattr(__import__("os"), "getpriority"), reason="POSIX priority")
def test_analysis_process_lowers_its_own_priority():
    import subprocess
    import sys
    code = "import os; from rekord import system; system.lower_priority(); print(os.getpriority(os.PRIO_PROCESS, 0))"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert int(r.stdout.strip()) >= 10, r.stderr


def test_pid_alive():
    import os
    import subprocess
    import sys

    from rekord import system
    assert system.pid_alive(os.getpid())
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert not system.pid_alive(p.pid) and not system.pid_alive(0)


def test_local_ai_context_fits_the_request():
    """Ollama reserves memory for its whole context window – only as much as the request needs."""
    from rekord.llm.providers import fit_context
    assert fit_context("Fasse zusammen.", [{"role": "user", "content": "kurz"}]) == 8192
    meeting = "x" * 26000  # ~30 min of talk
    assert fit_context("System", [{"role": "user", "content": meeting}]) == 16384
    assert fit_context("System", [{"role": "user", "content": "x" * 400000}]) == 32768  # never above the setting
    assert fit_context("System", [{"role": "user", "content": meeting}], 8192) == 8192


# ------------------------------------------------------------------ macOS: stale privacy switches after an update

def _mac(monkeypatch, frozen=True):
    import subprocess as sp
    import sys

    from rekord import system
    calls = []
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(system, "frozen", lambda: frozen)
    monkeypatch.setattr(system, "_run", lambda cmd, timeout=10: calls.append(cmd) or sp.CompletedProcess(cmd, 0, "", ""))
    return system, calls


def test_mac_reset_clears_screen_and_microphone_of_this_app_only(monkeypatch):
    system, calls = _mac(monkeypatch)
    assert system.mac_reset_permissions() is True
    assert calls == [["tccutil", "reset", "ScreenCapture", "app.rekord.desktop"],
                     ["tccutil", "reset", "Microphone", "app.rekord.desktop"],
                     ["tccutil", "reset", "SystemPolicyDownloadsFolder", "app.rekord.desktop"]]


def test_mac_new_version_resets_once(monkeypatch):
    """Every build has a new ad-hoc signature: the old build's "on" switches don't count – reset once per version."""
    from rekord import config
    system, calls = _mac(monkeypatch)
    config.save({"mac_permissions_for": "1.3.3"})
    assert system.mac_fresh_permissions("1.3.4") is True and len(calls) == 3
    assert system.mac_fresh_permissions("1.3.4") is False and len(calls) == 3  # next start: nothing
    assert config.load()["mac_permissions_for"] == "1.3.4"


def test_mac_reset_not_from_source_and_not_elsewhere(monkeypatch):
    system, calls = _mac(monkeypatch, frozen=False)
    assert system.mac_fresh_permissions("9.9.9") is False and calls == []  # running from source: Terminal's rights
    import sys
    monkeypatch.setattr(sys, "platform", "win32")
    assert system.mac_reset_permissions() is False and system.mac_open_privacy("Microphone") is False and calls == []


def test_mac_opens_the_exact_privacy_pane(monkeypatch):
    system, calls = _mac(monkeypatch)
    assert system.mac_open_privacy("ScreenCapture") and system.mac_open_privacy("Microphone")
    assert calls == [["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"],
                     ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"]]


# ------------------------------------------------------------------ add files to a recording afterwards

def _clip(path, seconds, start=0):
    from rekord import audio as a
    x = a.load(Path(__file__).parent / "fixtures" / "meeting1.wav")[int(16000 * start):int(16000 * (start + seconds))]
    a.write_wav(path, x)
    return path


def test_append_files_puts_audio_behind_the_recording(tmp_path):
    from rekord import audio as a
    from rekord import config, db, pipeline
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    first = _clip(config.AUDIO_DIR / "teil1.wav", 3)
    rec = db.create_recording("Workshop", str(first), source="import")
    db.update_recording(rec["id"], highlights=[1.5])
    added = pipeline.append_files(rec["id"], [str(_clip(tmp_path / "teil2.wav", 2, start=10)),
                                               str(_clip(tmp_path / "teil3.wav", 1, start=20))])
    r = db.get_recording(rec["id"])
    assert 2.9 < added < 3.1
    assert abs(r["duration"] - (3 + 1 + 2 + 1 + 1)) < 0.2  # 3 s + pause + 2 s + pause + 1 s
    assert r["audio_path"].endswith(".m4a") and Path(r["audio_path"]).is_file() and r["peaks"]
    assert abs(len(a.load(r["audio_path"])) / 16000 - r["duration"]) < 0.2
    assert not first.exists()  # REKORD's own old copy is replaced …
    assert (tmp_path / "teil2.wav").exists()  # … the user's files are never touched
    assert r["highlights"] == [1.5]  # earlier marks keep their times


def test_append_files_refuses_what_has_no_sound(tmp_path):
    import pytest as _pt

    from rekord import config, db, pipeline
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    rec = db.create_recording("X", str(_clip(config.AUDIO_DIR / "x.wav", 1)), source="import")
    (tmp_path / "kaputt.mp3").write_bytes(b"keine Musik")
    with _pt.raises(Exception):
        pipeline.append_files(rec["id"], [str(tmp_path / "kaputt.mp3")])
    assert db.get_recording(rec["id"])["audio_path"].endswith("x.wav")  # nothing changed
    with _pt.raises(KeyError):
        pipeline.append_files("gibtsnicht", [str(tmp_path / "kaputt.mp3")])


# ------------------------------------------------------------------ every format · stills from videos

def test_any_audio_or_video_counts_whatever_its_name(tmp_path):
    import shutil

    from rekord import audio as a
    odd = tmp_path / "aufnahme.xyz"  # an unusual ending – there's sound inside, so it's fine
    shutil.copy(Path(__file__).parent / "fixtures" / "meeting1.wav", odd)
    assert a.accepted(odd) and a.probe(odd) == {"audio": True, "video": False}
    (tmp_path / "liste.txt").write_text("kein Ton")
    assert not a.accepted(tmp_path / "liste.txt") and not a.accepted(tmp_path)
    assert a.accepted(tmp_path / "egal.mkv")  # known endings are taken without a look inside
    assert ".mkv" in a.MEDIA_EXT and ".aiff" in a.MEDIA_EXT and ".avi" in a.MEDIA_EXT and "*.wmv" in a.DIALOG_FILTER


def test_stills_at_each_new_slide_not_for_the_pointer(tmp_path):
    from media import slides_video

    from rekord import audio as a
    from rekord import frames
    vid = slides_video(tmp_path / "praesentation.mp4")
    assert a.probe(vid) == {"audio": True, "video": True}
    assert frames.extract(vid, "r1") == 3
    assert [f["t"] for f in frames.items("r1")] == [0.0, 5.0, 10.0]  # exactly the three slide changes
    assert all(Path(f["path"]).read_bytes()[:2] == b"\xff\xd8" for f in frames.items("r1"))  # real JPEGs
    assert frames.extract(vid, "r2", offset=61.0) == 3 and frames.items("r2")[0]["t"] == 61.0
    assert frames.extract(Path(__file__).parent / "fixtures" / "meeting1.wav", "r3") == 0 and not frames.has("r3")
    segs = [{"id": 7, "start": 0, "end": 4}, {"id": 8, "start": 5.5, "end": 9}, {"id": 9, "start": 10.5, "end": 14}]
    assert [(f["t"], f["seg"]) for f in frames.attach("r1", segs)] == [(0.0, 7), (5.0, 8), (10.0, 9)]
    frames.remove("r1")
    assert frames.items("r1") == []


def test_appended_video_keeps_its_stills_in_place(tmp_path):
    from media import slides_video

    from rekord import config, db, frames, pipeline
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    rec = db.create_recording("Webinar", str(_clip(config.AUDIO_DIR / "intro.wav", 4)), source="import")
    pipeline.append_files(rec["id"], [str(slides_video(tmp_path / "teil2.mp4"))])
    assert [f["t"] for f in frames.items(rec["id"])] == [5.0, 10.0, 15.0]  # 4 s intro + 1 s pause, then its slides
    assert db.get_recording(rec["id"])["audio_path"].endswith(".m4a")
