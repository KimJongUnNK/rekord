"""The role "Geräusch": lines that are only a sound (a cough, music, what Whisper "hears" in silence) – there from the
start, recognised on its own for the obvious ones, and out of transcript view, summary, questions, export and search.
Plus: deleting several recordings at once."""
import pytest
from fastapi.testclient import TestClient

from rekord import db, export, pipeline, summarize
from rekord.server import app


@pytest.fixture(scope="module")
def client():
    app.state.auto_download = False
    with TestClient(app) as c:
        yield c


def _meeting():
    rec = db.create_recording("Workshop", "", source="import")
    rid = rec["id"]
    lisa = db.add_speaker(rid, "Lisa", "#3B82F6")
    unk = db.add_speaker(rid, pipeline.UNKNOWN, pipeline.UNKNOWN_COLOR)
    c = db.connect()
    rows = [(lisa, 0, 4, "Wir starten mit dem Budget."), (unk, 4, 5, "Untertitel der Amara.org-Community"),
            (unk, 5, 6, "[Husten]"), (lisa, 6, 9, "Das Budget steht bis Freitag.")]
    for sid, a, b, t in rows:
        cur = c.execute("INSERT INTO segments (recording_id, speaker_id, start, end, text) VALUES (?,?,?,?,?)", (rid, sid, a, b, t))
        c.execute("INSERT INTO segments_fts(text,recording_id,segment_id) VALUES(?,?,?)", (t, rid, cur.lastrowid))
    c.commit()
    db.update_recording(rid, status="done", duration=9)
    return rid


@pytest.mark.parametrize("text, noise", [
    ("[Musik]", True), ("*hustet*", True), ("(Applaus)", True), ("♪ ♪", True), ("...", True), ("", True),
    ("Untertitel der Amara.org-Community", True), ("Untertitel im Auftrag des ZDF für funk, 2017", True),
    ("Vielen Dank fürs Zuschauen!", True), ("Thanks for watching!", True),
    ("Ja.", False), ("Hast du die Untertitel gemacht?", False), ("Bis zum nächsten Mal.", False),
    ("(lacht) Das stimmt", False), ("Okay, dann fangen wir an.", False),
])
def test_what_counts_as_a_sound(text, noise):
    assert pipeline.is_noise(text) is noise


def test_noise_lines_are_out_of_summary_export_and_search(client):
    rid = _meeting()
    segs = db.list_segments(rid)
    for s in segs[1:3]:  # the two phantom lines → Geräusch, like "Wer sagt das? → Ist ein Geräusch"
        r = client.post(f"/api/segments/{s['id']}/assign", json={"name": "Geräusch", "remember": True})
        assert r.status_code == 200, r.text
    assert not [p for p in db.list_profiles() if p["name"] == db.NOISE]  # a sound has no voice to learn
    noise = next(s for s in db.list_speakers(rid) if s["name"] == db.NOISE)
    assert noise["color"] == db.NOISE_COLOR and noise["profile_id"] is None
    assert [s["text"] for s in db.spoken_segments(rid)] == ["Wir starten mit dem Budget.", "Das Budget steht bis Freitag."]
    text = summarize.transcript_text(rid)
    assert "Amara" not in text and "Husten" not in text and "Budget steht" in text
    assert "Geräusch" not in summarize.speaker_stats(rid)
    md = export.markdown(rid, with_summary=False)
    assert "Amara" not in md and "Geräusch" not in md and "Lisa" in md
    assert not db.search_segments("Amara")
    assert db.search_segments("Budget")
    assert len(client.get(f"/api/recordings/{rid}").json()["segments"]) == 4  # the window still has them (to show on request)


def test_a_whole_speaker_can_be_a_sound(client):
    rid = _meeting()
    unk = next(s for s in db.list_speakers(rid) if s["name"] == pipeline.UNKNOWN)
    assert client.patch(f"/api/speakers/{unk['id']}", json={"name": "Geräusch", "remember": True}).json() == {"ok": True}
    sp = db.get_speaker(unk["id"])
    assert sp["name"] == db.NOISE and sp["profile_id"] is None
    assert len(db.spoken_segments(rid)) == 2


def test_delete_several_recordings_at_once(client):
    ids = [db.create_recording(f"Falsch {i}", "", source="import")["id"] for i in range(3)]
    keep = db.create_recording("Bleibt", "", source="import")["id"]
    r = client.post("/api/recordings/delete", json={"ids": ids + ["gibtsnicht"]}).json()
    assert r == {"ok": True, "deleted": 3}
    assert all(db.get_recording(i) is None for i in ids) and db.get_recording(keep) is not None
