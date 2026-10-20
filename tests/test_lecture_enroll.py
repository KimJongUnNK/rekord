"""„Einfach reden lassen“ keeps the main voice, „Vorlesung“ separates the lecturer from the audience – without models."""
import numpy as np

from rekord import db, live, pipeline, summarize
from rekord.engines import voiceprint


def _voice(seed):
    return voiceprint.normalize(np.random.default_rng(seed).normal(size=192))


def test_free_talk_keeps_the_voice_that_talks_most():
    prof, student = _voice(1), _voice(2)
    rng = np.random.default_rng(3)
    noisy = lambda v: voiceprint.normalize(v + rng.normal(scale=0.03, size=192))  # noqa: E731
    pairs = [((i * 3.0, i * 3.0 + 3), noisy(prof)) for i in range(12)]
    pairs[4] = ((12.0, 15.0), noisy(student))  # a question from the room in between
    pairs[9] = ((27.0, 30.0), noisy(student))
    main = pipeline._main_voice(pairs)
    assert len(main) == 10
    assert all(voiceprint.cosine(v, prof) > 0.9 for _, v in main)


def test_voices_of_a_recording_and_learning_one(monkeypatch):
    rec = db.create_recording("Vorlesung Mathe", "")
    lect = db.add_speaker(rec["id"], pipeline.LECTURER, pipeline.LECTURER_COLOR, None)
    aud = db.add_speaker(rec["id"], pipeline.AUDIENCE, pipeline.UNKNOWN_COLOR, None)
    conn = db.connect()
    for i, (sid, voice, a, b, text) in enumerate([(lect, None, 0, 20, "Heute geht es um Integrale."),
                                                  (aud, 7, 20, 23, "Kommt das in der Prüfung?"),
                                                  (lect, None, 23, 50, "Ja, das kommt dran."),
                                                  (aud, 8, 50, 52, "Danke!")]):
        conn.execute("INSERT INTO segments (recording_id, speaker_id, start, end, text, voice) VALUES (?,?,?,?,?,?)",
                     (rec["id"], sid, a, b, text, voice))
    conn.commit()
    voices = pipeline.recording_voices(rec["id"])
    assert [(v["name"], v["voice"], v["seconds"]) for v in voices] == [
        (pipeline.LECTURER, None, 47.0), (pipeline.AUDIENCE, 7, 3.0), (pipeline.AUDIENCE, 8, 2.0)]
    assert voices[0]["samples"][0] == [23.0, 50.0]  # the longest piece first, to listen to
    learned = []
    monkeypatch.setattr(pipeline, "remember_speaker", lambda rid, sid, name: learned.append(("speaker", sid, name)))
    monkeypatch.setattr(pipeline, "assign_segment", lambda seg, name, remember, whole_voice: learned.append(("voice", seg, name, whole_voice)))
    monkeypatch.setattr(db, "list_profiles", lambda with_embedding=False: [{"id": 1, "name": "Prof. Huber"}, {"id": 2, "name": "Anna"}])
    assert pipeline.learn_voice(rec["id"], lect, None, "Prof. Huber")["id"] == 1
    assert pipeline.learn_voice(rec["id"], aud, 7, " Anna ")["id"] == 2
    seg7 = next(x for x in db.list_segments(rec["id"]) if x.get("voice") == 7)
    assert learned == [("speaker", lect, "Prof. Huber"), ("voice", seg7["id"], "Anna", True)]


def test_lecture_gets_the_study_sheet(monkeypatch):
    rec = db.create_recording("VO Statistik", "")
    db.update_recording(rec["id"], participants={"ids": [], "guests": 0, "meeting": "lecture"})
    used = []
    monkeypatch.setattr(summarize, "generate", lambda rid, tid, on_delta=None: used.append(tid))
    summarize.auto_summary(rec["id"])
    other = db.create_recording("Team", "")
    summarize.auto_summary(other["id"])
    assert used == ["lecture", "auto"]
    from rekord.llm import templates
    p = templates.get("lecture")["prompt"]
    assert "Prüfungsrelevant" in p and "Fragen aus dem Hörsaal" in p


class _Cluster:
    def __init__(self, clusters, profiles=()):
        self.clusters, self.profiles = clusters, list(profiles)


def _lecture_session(segments, clusters):
    s = live.LiveSession.__new__(live.LiveSession)
    s.meeting, s.participants, s.segments = "lecture", [], segments
    s.cluster = _Cluster(clusters)
    s.emitted = []
    s.emit = s.emitted.append
    return s


def test_live_lecture_names_the_main_voice_and_collects_the_rest():
    clusters = [{"key": 0, "profile": None}, {"key": 1, "profile": None}, {"key": 2, "profile": None}]
    segs = [{"key": 0, "start": 0, "end": 30, "known": False}, {"key": 1, "start": 30, "end": 33, "known": False},
            {"key": 0, "start": 33, "end": 60, "known": False}, {"key": 2, "start": 60, "end": 62, "known": False}]
    s = _lecture_session(segs, clusters)
    assert s._label({"key": 0})["name"] == pipeline.LECTURER
    assert s._label({"key": 1})["name"] == pipeline.AUDIENCE and s._label({"key": 2})["name"] == pipeline.AUDIENCE
    s._roster()
    items = s.emitted[-1]["items"]
    assert [(i["name"], i.get("voices")) for i in items] == [(pipeline.LECTURER, None), (pipeline.AUDIENCE, 2)]


def test_live_lecture_with_a_known_lecturer():
    prof = {"id": 5, "name": "Prof. Huber", "color": "#123456"}
    clusters = [{"key": 0, "profile": prof}, {"key": 1, "profile": None}]
    segs = [{"key": 0, "start": 0, "end": 50, "known": True}, {"key": 1, "start": 50, "end": 53, "known": False}]
    s = _lecture_session(segs, clusters)
    assert s._label({"key": 0})["name"] == "Prof. Huber"
    assert s._label({"key": 1})["name"] == pipeline.AUDIENCE  # the known lecturer talks most: the rest is audience
