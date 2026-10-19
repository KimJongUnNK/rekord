"""Summaries, multi-template ('multidimensional') summaries, Ask-a-recording and Ask-everything."""
from __future__ import annotations

import re
from typing import Callable, Iterator

from . import config, db
from .llm import providers, templates

LANG = {"de": "Deutsch", "en": "Englisch", "auto": "der Sprache des Gesprächs"}

STOP = set("""der die das und oder aber ein eine einer eines einem einen ist sind war waren wird werden hat haben
hatte ich du er sie es wir ihr mich mir dich dir uns euch was wer wie wo wann warum wieso welche welcher welches
im in am an auf aus bei mit nach von vor zu zum zur über unter für gegen ohne um nicht noch nur auch schon sehr
denn dass da dann so als wenn ob mal eigentlich gesagt sagen sagte meeting gespräch letzte letzten
the a an and or but is are was were be been have has had i you he she it we they what who how where when why
which in on at of to for with about from did do does said say meeting call last""".split())


def fmt_time(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def transcript_text(rid: str) -> str:
    rec = db.get_recording(rid)
    sp = {s["id"]: s["name"] for s in db.list_speakers(rid)}
    hl = rec.get("highlights") or []
    lines = []
    for seg in db.list_segments(rid):
        star = " ★" if any(seg["start"] - 3 <= h <= seg["end"] + 3 for h in hl) else ""
        lines.append(f"[{fmt_time(seg['start'])}] {sp.get(seg['speaker_id'], 'Unbekannt')}{star}: {seg['text']}")
    return "\n".join(lines)


def speaker_stats(rid: str) -> str:
    sp = {s["id"]: s["name"] for s in db.list_speakers(rid)}
    talk: dict[str, float] = {}
    for seg in db.list_segments(rid):
        n = sp.get(seg["speaker_id"], "Unbekannt")
        talk[n] = talk.get(n, 0) + seg["end"] - seg["start"]
    total = sum(talk.values()) or 1
    return ", ".join(f"{n}: {v / total:.0%}" for n, v in sorted(talk.items(), key=lambda x: -x[1]))


def system_prompt(settings: dict, rec: dict) -> str:
    lang = LANG.get(settings.get("summary_language", "de"), settings.get("summary_language", "Deutsch"))
    return f"""Du bist REKORD, ein präziser Assistent für Gesprächsnotizen. Du bekommst das Transkript einer Aufnahme
mit Zeitstempeln [mm:ss] und Sprechernamen. Zeilen mit ★ wurden vom Nutzer während der Aufnahme als wichtig markiert –
gewichte sie stärker.

Regeln:
- Schreibe auf {lang}, als sauberes Markdown. Kurze, klare Sätze. Kein Gelaber, keine Einleitung wie "Hier ist".
- Nutze die echten Namen der Sprecher. „Nicht erkannte Stimme“ (oder ältere „Sprecher 1“ etc.) sind eine oder mehrere Personen, die REKORD nicht kennt – lass die Bezeichnung so und erfinde keine Namen.
- Belege wichtige Aussagen mit Zeitstempeln im Format [mm:ss] (klickbar in der App).
- Erfinde nichts. Wenn etwas unklar ist oder fehlt, sag das. Transkriptionsfehler stillschweigend korrigieren, wenn eindeutig.

Aufnahme: "{rec['title']}" · Dauer {fmt_time(rec.get('duration') or 0)} · Redeanteile: {speaker_stats(rec['id'])}"""


def _chunks(text: str, size: int) -> list[str]:
    lines, out, cur, n = text.split("\n"), [], [], 0
    for ln in lines:
        if n + len(ln) > size and cur:
            out.append("\n".join(cur))
            cur, n = [], 0
        cur.append(ln)
        n += len(ln) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def prepared_transcript(settings: dict, rid: str, on_status: Callable[[str], None] | None = None) -> str:
    """Fits the transcript into the model's context. Long recordings on small local models get map-reduced."""
    text = transcript_text(rid)
    limit = providers.context_chars(settings)
    if len(text) <= limit:
        return text
    parts = _chunks(text, int(limit * 0.8))
    notes = []
    for i, part in enumerate(parts):
        if on_status:
            on_status(f"Teil {i + 1}/{len(parts)} verdichten …")
        notes.append(providers.complete(settings, "Verdichte diesen Transkript-Abschnitt zu detaillierten Stichpunkten. "
                                        "Behalte Namen, Zahlen, Zusagen, Entscheidungen und [mm:ss] Zeitstempel.",
                                        [{"role": "user", "content": part}], 8000))
    return "(Langes Gespräch – abschnittsweise verdichtet)\n\n" + "\n\n".join(notes)


def generate_stream(rid: str, template_id: str) -> Iterator[str]:
    settings = config.load()
    rec = db.get_recording(rid)
    tpl = templates.get(template_id)
    transcript = prepared_transcript(settings, rid)
    if not transcript.strip():
        raise providers.LLMError("Transkript ist leer.")
    user = f"<transkript>\n{transcript}\n</transkript>\n\n<vorlage name=\"{tpl['name']}\">\n{tpl['prompt']}\n</vorlage>"
    if rec.get("notes"):
        user += f"\n\n<notizen_des_nutzers>\n{rec['notes']}\n</notizen_des_nutzers>"
    yield from providers.stream(settings, system_prompt(settings, rec), [{"role": "user", "content": user}])


def generate(rid: str, template_id: str, on_delta: Callable[[str], None] | None = None) -> dict:
    settings = config.load()
    tpl = templates.get(template_id)
    out = []
    for d in generate_stream(rid, template_id):
        out.append(d)
        if on_delta:
            on_delta(d)
    content = "".join(out).strip()
    sid = db.add_summary(rid, template_id, tpl["name"], content, settings["llm"]["provider"], providers.model_name(settings))
    maybe_title(rid, content)
    return {"id": sid, "content": content, "title": tpl["name"]}


def maybe_title(rid: str, content: str) -> None:
    rec = db.get_recording(rid)
    m = re.match(r"\s*#\s+(.+)", content)
    if rec and m and not rec.get("title_locked"):
        title = m.group(1).strip().strip("*")[:90]
        if title and not title.lower().startswith(("to-dos", "highlights", "faq", "entscheidungen")):
            db.update_recording(rid, title=title)


def auto_summary(rid: str) -> None:
    s = config.load()
    tid = s.get("default_template") or "auto"
    generate(rid, tid)


# ------------------------------------------------------------------ Ask

def ask_recording_stream(rid: str, question: str) -> Iterator[str]:
    settings = config.load()
    rec = db.get_recording(rid)
    history = [{"role": c["role"], "content": c["content"]} for c in db.list_chat(rid)][-12:]
    transcript = prepared_transcript(settings, rid)
    summaries = "\n\n".join(f"## {x['title']}\n{x['content']}" for x in db.list_summaries(rid)[:2])
    system = system_prompt(settings, rec) + f"""

Beantworte Fragen zu dieser Aufnahme. Antworte knapp und konkret und belege mit [mm:ss].
Wenn die Antwort nicht im Transkript steht, sag das klar.

<transkript>
{transcript}
</transkript>
<bisherige_zusammenfassungen>
{summaries}
</bisherige_zusammenfassungen>"""
    msgs = history + [{"role": "user", "content": question}]
    out = []
    for d in providers.stream(settings, system, msgs, 16000):
        out.append(d)
        yield d
    db.add_chat(rid, "user", question)
    db.add_chat(rid, "assistant", "".join(out))


def keywords(q: str) -> str:
    words = re.findall(r"[\wäöüÄÖÜß\-]{2,}", q.lower())
    kept = [w for w in words if w not in STOP]
    return " ".join(kept or words)


def retrieve(question: str, limit: int = 40) -> list[dict]:
    hits = db.search_segments(keywords(question), limit=limit)
    # add neighbours for context
    out, seen = [], set()
    for h in hits:
        segs = db.list_segments(h["recording_id"])
        idx = next((i for i, s in enumerate(segs) if s["id"] == h["id"]), None)
        if idx is None:
            continue
        sp = {s["id"]: s["name"] for s in db.list_speakers(h["recording_id"])}
        for s in segs[max(0, idx - 1): idx + 2]:
            if s["id"] in seen:
                continue
            seen.add(s["id"])
            out.append({**s, "speaker": sp.get(s["speaker_id"], "?"), "recording_title": h["recording_title"],
                        "recording_date": h["recording_date"]})
    out.sort(key=lambda s: (s["recording_date"], s["start"]))
    return out


def ask_all_stream(question: str) -> Iterator[str]:
    import datetime as dt
    settings = config.load()
    ctx = retrieve(question)
    recent = db.list_recordings()[:30]
    lines = [f"[[{s['recording_id']}@{fmt_time(s['start'])}]] ({s['recording_title']}, "
             f"{dt.datetime.fromtimestamp(s['recording_date']):%d.%m.%Y}) {s['speaker']}: {s['text']}" for s in ctx]
    rec_list = "\n".join(f"- {r['title']} ({dt.datetime.fromtimestamp(r['created_at']):%d.%m.%Y}, {', '.join(x['name'] for x in r['speakers'])})"
                         for r in recent)
    summaries = []
    for r in recent[:8]:
        sm = db.list_summaries(r["id"])
        if sm:
            summaries.append(f"### {r['title']} [[{r['id']}@00:00]]\n{sm[0]['content'][:1500]}")
    lang = LANG.get(settings.get("summary_language", "de"), "Deutsch")
    system = f"""Du bist REKORD und kennst alle Aufnahmen des Nutzers. Beantworte die Frage auf {lang}, knapp und konkret.
Belege jede Aussage mit der Quelle im Format [[aufnahme_id@mm:ss]] genau wie in den Auszügen angegeben (wird in der App klickbar).
Wenn die Auszüge die Antwort nicht enthalten, sag das ehrlich und schlage vor, wonach gesucht werden könnte.

<letzte_aufnahmen>
{rec_list}
</letzte_aufnahmen>
<zusammenfassungen>
{chr(10).join(summaries)}
</zusammenfassungen>
<relevante_auszuege>
{chr(10).join(lines) or '(keine Treffer in der Volltextsuche)'}
</relevante_auszuege>"""
    history = [{"role": c["role"], "content": c["content"]} for c in db.list_chat("global")][-10:]
    out = []
    for d in providers.stream(settings, system, history + [{"role": "user", "content": question}], 16000):
        out.append(d)
        yield d
    db.add_chat("global", "user", question)
    db.add_chat("global", "assistant", "".join(out))
