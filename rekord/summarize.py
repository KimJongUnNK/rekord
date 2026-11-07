"""Summaries, multi-template ('multidimensional') summaries, Ask-a-recording and Ask-everything."""
from __future__ import annotations

import logging
import re
from typing import Callable, Iterator

from . import config, db
from .llm import providers, templates

log = logging.getLogger("rekord.summarize")

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
    for seg in db.spoken_segments(rid):
        star = " ★" if any(seg["start"] - 3 <= h <= seg["end"] + 3 for h in hl) else ""
        lines.append(f"[{fmt_time(seg['start'])}] {sp.get(seg['speaker_id'], 'Unbekannt')}{star}: {seg['text']}")
    return "\n".join(lines)


def speaker_stats(rid: str) -> str:
    sp = {s["id"]: s["name"] for s in db.list_speakers(rid)}
    talk: dict[str, float] = {}
    for seg in db.spoken_segments(rid):
        n = sp.get(seg["speaker_id"], "Unbekannt")
        talk[n] = talk.get(n, 0) + seg["end"] - seg["start"]
    total = sum(talk.values()) or 1
    return ", ".join(f"{n}: {v / total:.0%}" for n, v in sorted(talk.items(), key=lambda x: -x[1]))


SOURCE = {"import": "importierte Datei", "inbox": "aus dem Eingangsordner", "live": "live aufgenommen",
          "mic": "live aufgenommen", "call": "Call/Meeting mitgeschnitten"}


def recording_facts(rec: dict, settings: dict | None = None) -> str:
    """What the app shows about a recording – so the AI can answer "wie heißt die Datei?", "welche Unterlagen?"."""
    import datetime as dt
    from . import context
    lines = [f"- Titel: {rec['title']}", f"- ID: {rec['id']}"]
    if rec.get("created_at"):
        lines.append(f"- Datum: {dt.datetime.fromtimestamp(rec['created_at']):%d.%m.%Y %H:%M}")
    lines.append(f"- Dauer: {fmt_time(rec.get('duration') or 0)}")
    lines.append(f"- Herkunft: {SOURCE.get(rec.get('source') or '', rec.get('source') or '?')}")
    files = rec.get("files") or []
    if files:
        lines.append(("- Audio-/Videodatei: " if len(files) == 1 else f"- Audio-/Videodateien ({len(files)}, in dieser Reihenfolge): ")
                     + ", ".join(files))
    if rec.get("folder"):
        lines.append(f"- Ordner: {rec['folder']}")
    people = rec.get("participants") or []
    if isinstance(people, list) and people:
        lines.append("- Teilnehmer: " + ", ".join(str(x) for x in people))
    docs = context.items(rec["id"]) if context.ai_allowed(settings or config.load())[0] else []  # cloud: only if allowed
    if docs:
        lines.append("- Unterlagen: " + ", ".join(
            d["name"] + (f" ({d['pages']} S.)" if d.get("pages") else "") for d in docs))
    return "\n".join(lines)


def user_rules(settings: dict) -> str:
    """Einstellungen → KI → Anweisungen an die KI: the user's own rules for tone and form, in every answer."""
    t = (settings.get("ai_instructions") or "").strip()
    return f"\n\nAnweisungen des Nutzers – halte dich in jeder Antwort daran (Aufbau einer Vorlage geht vor):\n{t[:4000]}" if t else ""


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

Was die App über diese Aufnahme weiß (Fragen nach Dateiname, Datum, Dauer usw. damit direkt beantworten):
{recording_facts(rec, settings)}
- Redeanteile: {speaker_stats(rec['id'])}""" + user_rules(settings)


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


def prepared_transcript(settings: dict, rid: str, on_status: Callable[[str], None] | None = None, reserve: int = 0) -> str:
    """Fits the transcript into the model's context (minus `reserve` chars for other material, e.g. the Unterlagen).
    Long recordings on small local models get map-reduced."""
    text = transcript_text(rid)
    limit = max(8000, providers.context_chars(settings) - reserve)
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


DOCS_NOTE = """

Zur Aufnahme gibt es Unterlagen (<unterlagen>: Agenda, Folien, Dokumente, Fotos). Sie sind Hintergrund:
- Nutze sie für die richtige Schreibweise von Namen, Begriffen und Zahlen und um Bezüge zu verstehen („Folie 3“, „Punkt 2 der Agenda“).
- Fasse das GESPRÄCH zusammen, nicht die Unterlagen. Was nur in den Unterlagen steht und im Gespräch nicht vorkam, gehört nicht
  als Gesprächsinhalt hinein – höchstens als Hinweis (z. B. „Agenda-Punkt X wurde nicht besprochen“).
- Widerspricht das Gespräch den Unterlagen (andere Zahl, anderer Termin), gilt das Gesagte – weise auf den Unterschied hin."""


def docs_budget(settings: dict) -> int:
    """How much of the Unterlagen goes into a prompt: plenty for long-context AIs, a share for small local models."""
    limit = providers.context_chars(settings)
    return min(80_000, max(3000, int(limit * 0.2)))


def _docs(settings: dict, rid: str) -> str:
    """The Unterlagen for the prompt – only for an AI on this computer (or a cloud AI you allowed for Unterlagen)."""
    from . import context
    if not context.has(rid) or not context.ai_allowed(settings)[0]:
        return ""
    return context.prompt_block(rid, docs_budget(settings))


MINDMAP_FIX = """Du ordnest eine Mind Map neu. Sie ist zu flach: Fasse die Einträge zu 4-6 Oberthemen (Ästen) zusammen, jeder mit
2-5 Unterpunkten. Nichts weglassen, nichts erfinden, kurze Einträge (höchstens 6 Wörter).
Antworte NUR mit der verschachtelten Markdown-Liste, 2 Leerzeichen Einrückung pro Ebene:
- Hauptthema
  - Ast
    - Punkt"""


def finish_mindmap(settings: dict, content: str) -> str:
    """Small local models often ignore the nesting and write one long flat list – a "mind map" without branches or
    lines. Then the AI sorts it into branches once more (with the flat list as input). Clean-up either way."""
    from .app import md
    if not md.is_flat(content):
        return content
    try:
        fixed = providers.complete(settings, MINDMAP_FIX, [{"role": "user", "content": content}], 4000)
    except providers.LLMError as e:
        log.warning("mind map stays flat: %s", e)
        return content
    if fixed.strip() and not md.is_flat(fixed):
        log.info("mind map was flat – sorted into branches")
        return fixed.strip()
    return content


EDIT_SYSTEM = """Du überarbeitest eine Zusammenfassung (Markdown) nach der Anweisung des Nutzers.
Regeln:
- Setze die Anweisung genau um – auch Format-Wünsche: welche Zeichen (z. B. „keine Sternchen“, „Spiegelstriche statt Punkte“,
  „Emojis weg“, „nummeriert“), Länge, Ton, Sprache, Reihenfolge, Überschriften.
- Alles, was die Anweisung nicht betrifft, bleibt wie es ist – auch Zeitstempel [mm:ss] und Namen.
- Neue Inhalte nur aus dem Transkript (falls mitgegeben) – nichts erfinden.
- Antworte NUR mit der vollständigen überarbeiteten Zusammenfassung, ohne Vorrede, ohne Codeblock."""


def edit_summary(sid: int, instruction: str, settings: dict | None = None) -> str:
    """"Sag der KI, was sie ändern soll" for a summary – the old version stays for Rückgängig."""
    instruction = (instruction or "").strip()
    sm = db.get_summary(sid)
    if sm is None:
        raise KeyError(sid)
    if not instruction:
        raise providers.LLMError("Schreib, was die KI ändern soll.")
    settings = settings or config.load()
    transcript = prepared_transcript(settings, sm["recording_id"], reserve=len(sm["content"]) + 2000)
    user = (f"<transkript>\n{transcript}\n</transkript>\n\n<zusammenfassung>\n{sm['content']}\n</zusammenfassung>\n\n"
            f"<anweisung>\n{instruction}\n</anweisung>")
    out = providers.complete(settings, EDIT_SYSTEM + user_rules(settings), [{"role": "user", "content": user}], 8000)
    out = re.sub(r"<think>.*?</think>", "", out or "", flags=re.S).strip()
    out = re.sub(r"^```(?:markdown|md)?\s*\n(.*?)\n```\s*$", r"\1", out, flags=re.S).strip()
    if not out:
        raise providers.LLMError("Die KI hat nichts zurückgegeben – Anweisung etwas genauer formulieren.")
    if sm["template_id"] == "mindmap":
        out = finish_mindmap(settings, out)
    db.update_summary(sid, out, keep_prev=True)
    log.info("summary %s changed by the AI: %s", sid, instruction[:80])
    return out


def generate_stream(rid: str, template_id: str) -> Iterator[str]:
    settings = config.load()
    rec = db.get_recording(rid)
    tpl = templates.get(template_id)
    docs = _docs(settings, rid)
    transcript = prepared_transcript(settings, rid, reserve=len(docs))
    if not transcript.strip():
        raise providers.LLMError("Transkript ist leer.")
    user = f"<transkript>\n{transcript}\n</transkript>\n\n<vorlage name=\"{tpl['name']}\">\n{tpl['prompt']}\n</vorlage>"
    if rec.get("notes"):
        user += f"\n\n<notizen_des_nutzers>\n{rec['notes']}\n</notizen_des_nutzers>"
    if docs:
        user = docs + "\n\n" + user
    system = system_prompt(settings, rec) + (DOCS_NOTE if docs else "")
    yield from providers.stream(settings, system, [{"role": "user", "content": user}])


def generate(rid: str, template_id: str, on_delta: Callable[[str], None] | None = None) -> dict:
    settings = config.load()
    tpl = templates.get(template_id)
    out = []
    for d in generate_stream(rid, template_id):
        out.append(d)
        if on_delta:
            on_delta(d)
    content = "".join(out).strip()
    if template_id == "mindmap":
        content = finish_mindmap(settings, content)
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
    rec = db.get_recording(rid) or {}
    if tid == "auto" and (rec.get("participants") or {}).get("meeting") == "lecture":
        tid = "lecture"  # recorded as „Vorlesung“: a study sheet, not a meeting protocol
    generate(rid, tid)


# ------------------------------------------------------------------ Ask

def ask_recording_stream(rid: str, question: str) -> Iterator[str]:
    settings = config.load()
    rec = db.get_recording(rid)
    history = [{"role": c["role"], "content": c["content"]} for c in db.list_chat(rid)][-12:]
    docs = _docs(settings, rid)
    transcript = prepared_transcript(settings, rid, reserve=len(docs))
    summaries = "\n\n".join(f"## {x['title']}\n{x['content']}" for x in db.list_summaries(rid)[:2])
    docs_rule = ("\nStammt eine Antwort aus den Unterlagen statt aus dem Gespräch, sag das und nenne das Dokument "
                 "(z. B. „laut Agenda.pdf“)." if docs else "")
    system = system_prompt(settings, rec) + f"""

Beantworte Fragen zu dieser Aufnahme. Antworte knapp und konkret und belege mit [mm:ss].
Wenn die Antwort nicht im Transkript steht, sag das klar.{docs_rule}

<transkript>
{transcript}
</transkript>
<bisherige_zusammenfassungen>
{summaries}
</bisherige_zusammenfassungen>""" + ("\n" + docs if docs else "")
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
        segs = db.spoken_segments(h["recording_id"])
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
    from . import context as _ctx
    docs_ok = _ctx.ai_allowed(settings)[0]  # names of Unterlagen go to a cloud AI only if allowed, like their content

    def files_of(r):
        from . import context
        f = r.get("files") or []
        d = [x["name"] for x in context.items(r["id"])] if docs_ok else []
        return (f"; Datei: {', '.join(f)}" if f else "") + (f"; Unterlagen: {', '.join(d)}" if d else "")
    rec_list = "\n".join(f"- {r['title']} [[{r['id']}@00:00]] ({dt.datetime.fromtimestamp(r['created_at']):%d.%m.%Y}, "
                         f"{fmt_time(r.get('duration') or 0)}, {', '.join(x['name'] for x in r['speakers'])}{files_of(r)})"
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
Fragen nach Dateinamen, Datum oder Dauer beantwortest du direkt aus <letzte_aufnahmen>.

<letzte_aufnahmen>
{rec_list}
</letzte_aufnahmen>
<zusammenfassungen>
{chr(10).join(summaries)}
</zusammenfassungen>
<relevante_auszuege>
{chr(10).join(lines) or '(keine Treffer in der Volltextsuche)'}
</relevante_auszuege>""" + user_rules(settings)
    history = [{"role": c["role"], "content": c["content"]} for c in db.list_chat("global")][-10:]
    out = []
    for d in providers.stream(settings, system, history + [{"role": "user", "content": question}], 16000):
        out.append(d)
        yield d
    db.add_chat("global", "user", question)
    db.add_chat("global", "assistant", "".join(out))
