"""SQLite storage. One file, WAL mode, FTS5 index over transcript segments."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

import numpy as np

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS recordings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at REAL NOT NULL,
    duration REAL DEFAULT 0,
    audio_path TEXT,
    source TEXT DEFAULT 'import',
    status TEXT DEFAULT 'queued',
    stage TEXT DEFAULT '',
    progress REAL DEFAULT 0,
    error TEXT DEFAULT '',
    language TEXT DEFAULT '',
    folder TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    highlights TEXT DEFAULT '[]',
    notes TEXT DEFAULT '',
    peaks TEXT DEFAULT '[]',
    title_locked INTEGER DEFAULT 0,
    participants TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    embedding BLOB NOT NULL,
    samples INTEGER DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS speakers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    label INTEGER NOT NULL,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL,
    match_score REAL DEFAULT 0,
    embedding BLOB
);
CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    start REAL NOT NULL,
    end REAL NOT NULL,
    speaker_id INTEGER REFERENCES speakers(id) ON DELETE SET NULL,
    text TEXT NOT NULL,
    lang TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_segments_rec ON segments(recording_id, start);
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    template_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    provider TEXT DEFAULT '',
    model TEXT DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,              -- recording id or 'global'
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'Eigene',
    description TEXT DEFAULT '',
    prompt TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
    text, recording_id UNINDEXED, segment_id UNINDEXED, tokenize='unicode61 remove_diacritics 2'
);
"""

PALETTE = ["#FF5A1F", "#2D7FF9", "#16A34A", "#E11D74", "#A855F7", "#EAB308", "#0EA5E9", "#F97316", "#14B8A6", "#64748B"]

_local = threading.local()


def connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        config.ensure_dirs()
        conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        _migrate(conn)
        _local.conn = conn
    return conn


MIGRATIONS = {"recordings": {"title_locked": "INTEGER DEFAULT 0", "participants": "TEXT DEFAULT '{}'"},
              "speakers": {"voices": "INTEGER DEFAULT 1"},
              "segments": {"voice": "INTEGER"}}  # which unknown voice (cluster) a line in the bucket belongs to  # >1: the "Nicht erkannte Stimme" bucket holds several people


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive schema upgrades for databases created by older versions."""
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    conn.commit()


@contextmanager
def tx():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


def emb_to_blob(v: np.ndarray) -> bytes:
    return np.asarray(v, dtype=np.float32).tobytes()


def blob_to_emb(b: bytes | None) -> np.ndarray | None:
    return None if b is None else np.frombuffer(b, dtype=np.float32).copy()


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for k in ("tags", "highlights", "peaks"):
        if k in d and isinstance(d[k], str):
            d[k] = json.loads(d[k] or "[]")
    if isinstance(d.get("participants"), str):
        d["participants"] = json.loads(d["participants"] or "{}") or {}
    d.pop("embedding", None)
    return d


# ---------------------------------------------------------------- recordings

def create_recording(title: str, audio_path: str, source: str = "import", duration: float = 0,
                     highlights: list | None = None, status: str = "queued", rec_id: str | None = None) -> dict:
    rid = rec_id or uuid.uuid4().hex[:12]
    with tx() as c:
        c.execute(
            "INSERT INTO recordings(id,title,created_at,duration,audio_path,source,status,highlights) VALUES(?,?,?,?,?,?,?,?)",
            (rid, title, time.time(), duration, audio_path, source, status, json.dumps(highlights or [])),
        )
    return get_recording(rid)


def get_recording(rid: str) -> dict | None:
    return _row(connect().execute("SELECT * FROM recordings WHERE id=?", (rid,)).fetchone())


def list_recordings(q: str = "", folder: str | None = None, limit: int = 500) -> list[dict]:
    conn = connect()
    if q:
        ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT recording_id FROM segments_fts WHERE segments_fts MATCH ? LIMIT 1000", (fts_query(q),)
        )]
        like = f"%{q}%"
        marks = ",".join("?" * len(ids)) or "''"
        rows = conn.execute(
            f"SELECT * FROM recordings WHERE (title LIKE ? OR notes LIKE ? OR id IN ({marks}))"
            " ORDER BY created_at DESC LIMIT ?", (like, like, *ids, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM recordings ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = [_row(r) for r in rows]
    if folder is not None:
        out = [r for r in out if r["folder"] == folder]
    for r in out:
        r.pop("peaks", None)
        r["speakers"] = [{"name": s["name"], "color": s["color"]} for s in list_speakers(r["id"])]
    return out


ALLOWED_REC_FIELDS = {"title", "title_locked", "participants", "duration", "audio_path", "status", "stage", "progress", "error", "language",
                      "folder", "tags", "highlights", "notes", "peaks"}


def update_recording(rid: str, **fields) -> dict | None:
    fields = {k: (json.dumps(v) if k in ("tags", "highlights", "peaks", "participants") else v)
              for k, v in fields.items() if k in ALLOWED_REC_FIELDS}
    if fields:
        with tx() as c:
            c.execute(f"UPDATE recordings SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?", (*fields.values(), rid))
    return get_recording(rid)


def delete_recording(rid: str) -> None:
    with tx() as c:
        c.execute("DELETE FROM segments_fts WHERE recording_id=?", (rid,))
        c.execute("DELETE FROM chats WHERE scope=?", (rid,))
        c.execute("DELETE FROM recordings WHERE id=?", (rid,))


def folders() -> list[str]:
    return [r[0] for r in connect().execute("SELECT DISTINCT folder FROM recordings WHERE folder!='' ORDER BY folder")]


# ---------------------------------------------------------------- speakers & segments

def replace_transcript(rid: str, speakers: list[dict], segments: list[dict]) -> None:
    """speakers: [{label,name,color,profile_id,match_score,embedding}], segments: [{start,end,label,text,lang}]"""
    with tx() as c:
        c.execute("DELETE FROM segments_fts WHERE recording_id=?", (rid,))
        c.execute("DELETE FROM segments WHERE recording_id=?", (rid,))
        c.execute("DELETE FROM speakers WHERE recording_id=?", (rid,))
        label_to_id = {}
        for s in speakers:
            emb = s.get("embedding")
            cur = c.execute(
                "INSERT INTO speakers(recording_id,label,name,color,profile_id,match_score,embedding,voices) VALUES(?,?,?,?,?,?,?,?)",
                (rid, s["label"], s["name"], s["color"], s.get("profile_id"), s.get("match_score", 0),
                 emb_to_blob(emb) if emb is not None else None, int(s.get("voices", 1))))
            label_to_id[s["label"]] = cur.lastrowid
        for seg in segments:
            cur = c.execute("INSERT INTO segments(recording_id,start,end,speaker_id,text,lang,voice) VALUES(?,?,?,?,?,?,?)",
                            (rid, seg["start"], seg["end"], label_to_id.get(seg.get("label")), seg["text"], seg.get("lang", ""),
                             seg.get("voice")))
            c.execute("INSERT INTO segments_fts(text,recording_id,segment_id) VALUES(?,?,?)", (seg["text"], rid, cur.lastrowid))


def list_speakers(rid: str, with_embedding: bool = False) -> list[dict]:
    rows = connect().execute("SELECT * FROM speakers WHERE recording_id=? ORDER BY label", (rid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        emb = d.pop("embedding")
        if with_embedding:
            d["embedding"] = blob_to_emb(emb)
        out.append(d)
    return out


def get_speaker(sid: int, with_embedding: bool = False) -> dict | None:
    r = connect().execute("SELECT * FROM speakers WHERE id=?", (sid,)).fetchone()
    if r is None:
        return None
    d = dict(r)
    emb = d.pop("embedding")
    if with_embedding:
        d["embedding"] = blob_to_emb(emb)
    return d


def add_speaker(rid: str, name: str, color: str, profile_id: int | None = None) -> int:
    with tx() as c:
        label = (c.execute("SELECT COALESCE(MAX(label), -1) FROM speakers WHERE recording_id=? AND label < 900", (rid,)).fetchone()[0]) + 1
        return c.execute("INSERT INTO speakers(recording_id,label,name,color,profile_id) VALUES(?,?,?,?,?)",
                         (rid, label, name, color, profile_id)).lastrowid


def delete_speaker_if_unused(sid: int) -> None:
    with tx() as c:
        c.execute("DELETE FROM speakers WHERE id=? AND NOT EXISTS (SELECT 1 FROM segments WHERE speaker_id=?)", (sid, sid))


def update_speaker(sid: int, **fields) -> None:
    fields = {k: v for k, v in fields.items() if k in ("name", "color", "profile_id", "match_score", "embedding", "voices")}
    if "embedding" in fields:
        fields["embedding"] = emb_to_blob(fields["embedding"]) if fields["embedding"] is not None else None
    if fields:
        with tx() as c:
            c.execute(f"UPDATE speakers SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?", (*fields.values(), sid))


def merge_speakers(rid: str, source_id: int, target_id: int) -> None:
    with tx() as c:
        c.execute("UPDATE segments SET speaker_id=? WHERE recording_id=? AND speaker_id=?", (target_id, rid, source_id))
        c.execute("DELETE FROM speakers WHERE id=? AND recording_id=?", (source_id, rid))


def list_segments(rid: str) -> list[dict]:
    return [dict(r) for r in connect().execute(
        "SELECT * FROM segments WHERE recording_id=? ORDER BY start", (rid,)).fetchall()]


def update_segment(seg_id: int, text: str | None = None, speaker_id: int | None = None) -> None:
    with tx() as c:
        if text is not None:
            c.execute("UPDATE segments SET text=? WHERE id=?", (text, seg_id))
            c.execute("UPDATE segments_fts SET text=? WHERE segment_id=?", (text, seg_id))
        if speaker_id is not None:
            c.execute("UPDATE segments SET speaker_id=? WHERE id=?", (speaker_id, seg_id))


def find_replace(rid: str, find: str, replace: str) -> int:
    n = 0
    for seg in list_segments(rid):
        if find in seg["text"]:
            update_segment(seg["id"], text=seg["text"].replace(find, replace))
            n += 1
    return n


def fts_query(q: str) -> str:
    words = [w.replace('"', "") for w in q.split() if w.strip('"')]
    return " OR ".join(f'"{w}"' for w in words) or '""'


def search_segments(q: str, rid: str | None = None, limit: int = 40) -> list[dict]:
    sql = ("SELECT s.*, r.title AS recording_title, r.created_at AS recording_date, sp.name AS speaker, bm25(segments_fts) AS score "
           "FROM segments_fts f JOIN segments s ON s.id=f.segment_id JOIN recordings r ON r.id=s.recording_id "
           "LEFT JOIN speakers sp ON sp.id=s.speaker_id WHERE segments_fts MATCH ?")
    args: list = [fts_query(q)]
    if rid:
        sql += " AND f.recording_id=?"
        args.append(rid)
    sql += " ORDER BY score LIMIT ?"
    args.append(limit)
    return [dict(r) for r in connect().execute(sql, args).fetchall()]


# ---------------------------------------------------------------- profiles (voice IDs)

def list_profiles(with_embedding: bool = False) -> list[dict]:
    out = []
    for r in connect().execute("SELECT * FROM profiles ORDER BY name").fetchall():
        d = dict(r)
        emb = d.pop("embedding")
        if with_embedding:
            d["embedding"] = blob_to_emb(emb)
        d["recordings"] = connect().execute("SELECT COUNT(DISTINCT recording_id) FROM speakers WHERE profile_id=?",
                                            (d["id"],)).fetchone()[0]
        out.append(d)
    return out


def get_profile(pid: int, with_embedding: bool = False) -> dict | None:
    return next((p for p in list_profiles(with_embedding) if p["id"] == pid), None)


def create_profile(name: str, embedding: np.ndarray, samples: int = 1, color: str | None = None) -> int:
    n = connect().execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    with tx() as c:
        cur = c.execute("INSERT INTO profiles(name,color,embedding,samples,created_at) VALUES(?,?,?,?,?)",
                        (name, color or PALETTE[n % len(PALETTE)], emb_to_blob(embedding), samples, time.time()))
        return cur.lastrowid


def update_profile(pid: int, name: str | None = None, embedding: np.ndarray | None = None,
                   samples: int | None = None, color: str | None = None) -> None:
    with tx() as c:
        if name is not None:
            c.execute("UPDATE profiles SET name=? WHERE id=?", (name, pid))
            c.execute("UPDATE speakers SET name=? WHERE profile_id=?", (name, pid))
        if color is not None:
            c.execute("UPDATE profiles SET color=? WHERE id=?", (color, pid))
        if embedding is not None:
            c.execute("UPDATE profiles SET embedding=? WHERE id=?", (emb_to_blob(embedding), pid))
        if samples is not None:
            c.execute("UPDATE profiles SET samples=? WHERE id=?", (samples, pid))


def delete_profile(pid: int) -> None:
    with tx() as c:
        c.execute("DELETE FROM profiles WHERE id=?", (pid,))


# ---------------------------------------------------------------- summaries, chats, templates

def add_summary(rid: str, template_id: str, title: str, content: str, provider: str = "", model: str = "") -> int:
    with tx() as c:
        return c.execute("INSERT INTO summaries(recording_id,template_id,title,content,provider,model,created_at) VALUES(?,?,?,?,?,?,?)",
                         (rid, template_id, title, content, provider, model, time.time())).lastrowid


def list_summaries(rid: str) -> list[dict]:
    return [dict(r) for r in connect().execute(
        "SELECT * FROM summaries WHERE recording_id=? ORDER BY created_at DESC", (rid,)).fetchall()]


def update_summary(sid: int, content: str) -> None:
    with tx() as c:
        c.execute("UPDATE summaries SET content=? WHERE id=?", (content, sid))


def delete_summary(sid: int) -> None:
    with tx() as c:
        c.execute("DELETE FROM summaries WHERE id=?", (sid,))


def add_chat(scope: str, role: str, content: str) -> None:
    with tx() as c:
        c.execute("INSERT INTO chats(scope,role,content,created_at) VALUES(?,?,?,?)", (scope, role, content, time.time()))


def list_chat(scope: str) -> list[dict]:
    return [dict(r) for r in connect().execute("SELECT * FROM chats WHERE scope=? ORDER BY id", (scope,)).fetchall()]


def clear_chat(scope: str) -> None:
    with tx() as c:
        c.execute("DELETE FROM chats WHERE scope=?", (scope,))


def list_custom_templates() -> list[dict]:
    return [dict(r) | {"builtin": False} for r in connect().execute("SELECT * FROM templates ORDER BY name").fetchall()]


def save_template(tid: str | None, name: str, prompt: str, category: str = "Eigene", description: str = "") -> str:
    tid = tid or "custom-" + uuid.uuid4().hex[:8]
    with tx() as c:
        c.execute("INSERT INTO templates(id,name,category,description,prompt,created_at) VALUES(?,?,?,?,?,?) "
                  "ON CONFLICT(id) DO UPDATE SET name=excluded.name, category=excluded.category, "
                  "description=excluded.description, prompt=excluded.prompt",
                  (tid, name, category, description, prompt, time.time()))
    return tid


def delete_template(tid: str) -> None:
    with tx() as c:
        c.execute("DELETE FROM templates WHERE id=?", (tid,))
