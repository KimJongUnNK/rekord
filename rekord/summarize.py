"""Summaries, multi-template ('multidimensional') summaries, Ask-a-recording and Ask-everything."""
from __future__ import annotations

import logging
import re
from typing import Callable, Iterator

from . import config, db, formulas
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


# ---------------------------------------------------------------- timestamps only when asked
# Einstellungen → KI → Zeitstempel: "ask" (default) = none in answers and summaries unless the question asks for them.
# Small local models ignore "leave them out", so besides the rule a filter takes them out of what is shown and saved.
TS_ANY = re.compile(r"[ \t]?\[\[[0-9a-f]+@(?:\d+:)?\d{1,2}:\d{2}\]\]|[ \t]?[\[(](?:\d+:)?\d{1,2}:\d{2}[\])]")
_ASKS_TIME = re.compile(r"zeitstempel|timestamp|time ?code|zeitpunkt|minute|sekunde|uhrzeit|an welcher stelle|welche stelle|"
                        r"wo genau|wo im|stelle im|mit zeit|mit \[|wann genau|ab wann|bei welcher zeit", re.I)


def wants_times(settings: dict, asked: str = "") -> bool:
    return settings.get("timestamps", "ask") == "always" or bool(_ASKS_TIME.search(asked or ""))


def strip_times(text: str) -> str:
    out = TS_ANY.sub("", text or "")
    # what a removed timestamp leaves ("z. B.,.") is cleaned in finish() on the whole text – never on a streamed piece,
    # where the example may still be on its way ("z. B." | " lineare Abschreibung")
    return re.sub(r"[ \t]+([.,;:!?)])", r"\1", out)


# "wurden betont, z. B. [12:34]." minus the timestamp = "z. B.,." – or a small model copied a placeholder.
# Only what is clearly a leftover goes: an example word after a comma or bracket with nothing behind it.
# Normal sentences ("we'll see.", "dauert etwa."), function calls ("print()"), paths ("../x") and code stay.
_ABBR = r"(?:z\.\s?B\.|e\.\s?g\.|bspw\.|vgl\.)"  # unambiguous: never the end of a real sentence
_WORD = r"(?:zum Beispiel|beispielsweise|etwa|siehe|for example|such as|see)"
_DANGLING = re.compile(r"(?:[ \t]*,[ \t]*\(?|[ \t]*\(|[ \t]+)" + _ABBR + r"[ \t]*\)?[ \t]*[,.;:]*[ \t]*$"
                       r"|(?:[ \t]*,[ \t]*\(?|[ \t]*\()" + _WORD + r"[ \t]*\)?[ \t]*[,.;:]*[ \t]*$", re.I | re.M)
_EMPTY_PARENS = re.compile(r"(?:(?<=\s)|^)\([ \t,.;:]*\)[ \t]*", re.M)  # "( )" left alone in text – not f()
_CODE = re.compile(r"```.*?(?:```|\Z)|`[^`\n]*`", re.S)


def fix_dangling(text: str) -> str:
    """Removes an example word with nothing after it at the end of a line ("…, z. B.,." → "….") and empty brackets;
    a real example ("z. B. lineare Abschreibung") and code stay as they are."""
    parts, last, out = [], 0, []
    for m in _CODE.finditer(text or ""):  # code spans and blocks are never touched
        parts.append((False, text[last:m.start()]))
        parts.append((True, m.group(0)))
        last = m.end()
    parts.append((False, (text or "")[last:]))
    for is_code, chunk in parts:
        if is_code:
            out.append(chunk)
            continue
        lines = []
        for line in _EMPTY_PARENS.sub("", chunk).split("\n"):
            fixed = _DANGLING.sub("", line)
            if fixed != line and fixed.strip() and not fixed.rstrip().endswith((".", "!", "?", ":", "*", ")")):
                fixed = fixed.rstrip() + "."
            if fixed != line:
                fixed = re.sub(r"[ \t]*,[ \t]*\.$", ".", fixed)
            lines.append(fixed)
        chunk = "\n".join(lines)
        out.append(re.sub(r"(?<![./\w])[ \t]*,[ \t]*\.(?=\s|$)|(?<![./])\.\.(?=[ \t]*$)", ".", chunk, flags=re.M))
    return "".join(out)


NO_PLACEHOLDER_RULE = ("- Nie Platzhalter oder angefangene Aufzählungen stehen lassen: kein „z. B.“, „etwa“, „…“ oder "
                       "„<…>“ ohne konkreten Inhalt aus dem Transkript. Gibt es kein Beispiel, lass „z. B.“ weg.")


def strip_times_stream(deltas: Iterator[str]) -> Iterator[str]:
    """The same while streaming: holds back an opened "[" or "(" until it's clear whether a timestamp follows."""
    buf = ""
    for d in deltas:
        buf += d
        cut = len(buf)
        for opener in ("[", "("):
            i = buf.rfind(opener)
            if i >= 0 and i > len(buf) - 40 and not re.search(r"[\])]", buf[i:]):
                j = i - 1 if opener == "[" and i > 0 and buf[i - 1] == "[" else i
                cut = min(cut, j)
        while cut > 0 and buf[cut - 1] in " \t":  # a space may belong to a timestamp that follows
            cut -= 1
        ready, buf = buf[:cut], buf[cut:]
        if ready:
            yield strip_times(ready)
    if buf:
        yield strip_times(buf)


def _time_rule(settings: dict, asked: str = "") -> str:
    if wants_times(settings, asked):
        return "- Belege wichtige Aussagen mit Zeitstempeln im Format [mm:ss] (klickbar in der App)."
    return ("- KEINE Zeitstempel ([mm:ss], Minuten, Zeitangaben aus dem Transkript) – auch wenn die Vorlage welche verlangt. "
            "Nur wenn der Nutzer ausdrücklich danach fragt.")


FORMULA_RULE = ("- Formeln als lesbare Formelschrift, eine pro Zeile, z. B. `Gewinn = Umsatz − Kosten`, "
                "`Rentabilität = Gewinn / Kapital × 100 %`, `x² + y²`, `√a`, `Σ`, `≤`, `≠`, `Δ` – KEIN LaTeX "
                "(kein $, kein \\frac, kein \\cdot). Gesprochene Formeln („Umsatz minus Kosten ist der Gewinn“) "
                "in diese Schreibweise bringen, Variablen erklären, wenn sie genannt wurden.")


PREFS_LENGTH = {"short": "Kurz: nur das Wichtigste, knappe Stichpunkte, etwa halb so lang wie üblich.",
                "normal": "Normale Länge: vollständig, aber ohne Wiederholungen.",
                "detailed": "Ausführlich: alle Details, Zusammenhänge und Begründungen aus dem Transkript."}
PREFS_TONE = {"direct": "Direkt und sachlich: erst die Sache, keine Einleitung, keine Floskeln, keine Rückfragen.",
              "neutral": "Neutral und sachlich, in ganzen Sätzen.",
              "friendly": "Freundlich und locker, aber auf den Punkt."}


def prefs(settings: dict) -> dict:
    p = dict(config.DEFAULTS.get("ai_prefs", {}))
    p.update(settings.get("ai_prefs") or {})
    return p


def prefs_block(settings: dict, asked: str = "") -> str:
    """Einstellungen → KI-Verhalten as ONE block of rules, the same in every AI call (summary, change, question,
    questions across all recordings). Small models follow a single clear list best – so nothing is repeated
    elsewhere, and what can be checked afterwards is checked as well (timestamps, emojis, empty "z. B.")."""
    p = prefs(settings)
    lang = LANG.get(settings.get("summary_language", "de"), settings.get("summary_language", "Deutsch"))
    rules = [f"- Sprache: {lang}.",
             "- Länge: " + PREFS_LENGTH.get(p.get("length"), PREFS_LENGTH["normal"]),
             "- Ton: " + PREFS_TONE.get(p.get("tone"), PREFS_TONE["direct"]),
             ("- Beispiele: zu jedem wichtigen Punkt ein konkretes Beispiel aus dem Transkript (Zahl, Fall, Zitat)."
              if p.get("examples", True) else "- Beispiele nur, wenn sie ausdrücklich im Transkript stehen."),
             "- Emojis: erlaubt, sparsam." if p.get("emojis") else "- Keine Emojis.",
             _time_rule(settings, asked), FORMULA_RULE, NO_PLACEHOLDER_RULE]
    own = (settings.get("ai_instructions") or "").strip()
    if own:
        rules.append("- Eigene Regeln des Nutzers (gehen bei Widerspruch vor):\n" + own[:4000])
    return ("\n\n## Verhaltensregeln des Nutzers – immer einhalten\n"
            "Lies sie einmal und halte dich in der ganzen Antwort daran. Die Überschriften einer Vorlage gehen vor, "
            "alles andere regeln diese Punkte:\n" + "\n".join(rules))


def user_rules(settings: dict) -> str:  # older name
    return prefs_block(settings)


_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2B50\u2B06\u2934\u2935\u2705\u274C\u274E\u2753-\u2755\u2757\uFE0F\u200D]")


def finish(text: str, settings: dict) -> str:
    """What every saved AI text goes through: formulas readable, no empty "z. B.", no emojis unless allowed."""
    out = fix_dangling(formulas.to_text(text or ""))
    if not prefs(settings).get("emojis"):
        out = re.sub(r"[ \t]{2,}", " ", _EMOJI.sub("", out))
    return out


def system_prompt(settings: dict, rec: dict, asked: str = "") -> str:
    return f"""Du bist REKORD, ein präziser Assistent für Gesprächsnotizen. Du bekommst das Transkript einer Aufnahme
mit Zeitstempeln [mm:ss] und Sprechernamen. Zeilen mit ★ wurden vom Nutzer während der Aufnahme als wichtig markiert –
gewichte sie stärker.

Regeln:
- Schreibe sauberes Markdown, ohne Einleitung wie "Hier ist".
- Nutze die echten Namen der Sprecher. „Nicht erkannte Stimme“ (oder ältere „Sprecher 1“ etc.) sind eine oder mehrere Personen, die REKORD nicht kennt – lass die Bezeichnung so und erfinde keine Namen.
- Erfinde nichts. Wenn etwas unklar ist oder fehlt, sag das. Transkriptionsfehler stillschweigend korrigieren, wenn eindeutig.

Was die App über diese Aufnahme weiß (Fragen nach Dateiname, Datum, Dauer usw. damit direkt beantworten):
{recording_facts(rec, settings)}
- Redeanteile: {speaker_stats(rec['id'])}""" + prefs_block(settings, asked)


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


# Status lines inside a stream ("Teil 2 von 6 wird verdichtet …"): shown while waiting, never part of the result.
STATUS, STATUS_END = "\u0001", "\u0002"
MAP_CHARS = 24_000      # a long transcript goes to a local model in pieces this big (~8k tokens: a few minutes each)
MAP_TOKENS = 1500       # and each piece comes back as at most this many tokens of notes
_MAP_CACHE: dict[tuple, str] = {}  # (piece, model) → notes: a second try or the next question doesn't start over


def status(text: str, progress: float | None = None) -> str:
    """A status line for the stream; progress 0…1 drives the bar while summarizing (None: just the text)."""
    p = "" if progress is None else f"{max(0.0, min(1.0, progress)):.3f}"
    return f"{STATUS}{p}|{text}{STATUS_END}"


def status_text(chunk: str) -> str:
    return chunk.strip(STATUS + STATUS_END).split("|", 1)[-1]


def is_status(chunk: str) -> bool:
    return chunk.startswith(STATUS)


def prepared_transcript_iter(settings: dict, rid: str, reserve: int = 0) -> Iterator[str]:
    """Fits the transcript into the model's context (minus `reserve` chars for other material, e.g. the Unterlagen).
    Long recordings on small local models are condensed piece by piece first. Yields status lines while it works;
    the last item is the transcript (or the condensed notes)."""
    import hashlib
    text = transcript_text(rid)
    limit = max(8000, providers.context_chars(settings) - reserve)
    if len(text) <= limit:
        yield text
        return
    parts = _chunks(text, min(int(limit * 0.8), MAP_CHARS))
    model = providers.model_name(settings)
    notes = []
    for i, part in enumerate(parts):
        key = (hashlib.sha1(part.encode()).hexdigest(), model, settings.get("llm", {}).get("provider"))
        if key not in _MAP_CACHE:
            stored = db.get_condensed("|".join(str(k) for k in key))  # condensed before, also before a restart
            if stored:
                _MAP_CACHE[key] = stored
        if key not in _MAP_CACHE:
            yield status(f"Lange Aufnahme – Teil {i + 1} von {len(parts)} wird verdichtet …", 0.05 + 0.65 * i / len(parts))
            _MAP_CACHE[key] = providers.complete(
                settings, "Verdichte diesen Transkript-Abschnitt zu dichten Stichpunkten: Inhalte, Begriffe, Namen, Zahlen, "
                          "Zusagen, Entscheidungen, Beispiele. Ein Stichpunkt pro Gedanke, keine Einleitung. "
                          "Behalte die [mm:ss] Zeitstempel am Ende der Stichpunkte.",
                [{"role": "user", "content": part}], MAP_TOKENS)
            _MAP_CACHE[key] = re.sub(r"<think>.*?</think>", "", _MAP_CACHE[key] or "", flags=re.S).strip()
            if _MAP_CACHE[key]:
                db.set_condensed("|".join(str(k) for k in key), _MAP_CACHE[key])
            if len(_MAP_CACHE) > 400:
                _MAP_CACHE.pop(next(iter(_MAP_CACHE)))
        notes.append(f"### Teil {i + 1}/{len(parts)}\n{_MAP_CACHE[key].strip()}")
    yield status("Alles verdichtet – jetzt wird zusammengefasst …", 0.72)
    yield "(Langes Gespräch – abschnittsweise verdichtet)\n\n" + "\n\n".join(notes)


def prepared_transcript(settings: dict, rid: str, on_status: Callable[[str], None] | None = None, reserve: int = 0) -> str:
    out = ""
    for item in prepared_transcript_iter(settings, rid, reserve):
        if is_status(item):
            if on_status:
                on_status(status_text(item))
        else:
            out = item
    return out


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
- Antworte NUR mit der vollständigen überarbeiteten Zusammenfassung, ohne Vorrede, ohne Codeblock.
"""


def edit_summary_stream(sid: int, instruction: str, settings: dict | None = None) -> Iterator[str]:
    """"Sag der KI, was sie ändern soll" for a summary, as a stream: status lines while the transcript is prepared
    (a 3-hour lecture on a local model takes minutes – no timeout, the bar shows it), then the new version as it's
    written. At the end it's saved; the old version stays for Rückgängig. Raises LLMError with a clear reason."""
    instruction = (instruction or "").strip()
    sm = db.get_summary(sid)
    if sm is None:
        raise KeyError(sid)
    if not instruction:
        raise providers.LLMError("Schreib, was die KI ändern soll.")
    settings = settings or config.load()
    yield status("Transkript wird vorbereitet …", 0.02)
    transcript = ""
    for item in prepared_transcript_iter(settings, sm["recording_id"], reserve=len(sm["content"]) + 2000):
        if is_status(item):
            yield item
        else:
            transcript = item
    user = (f"<transkript>\n{transcript}\n</transkript>\n\n<zusammenfassung>\n{sm['content']}\n</zusammenfassung>\n\n"
            f"<anweisung>\n{instruction}\n</anweisung>")
    yield status("Die KI ändert die Zusammenfassung …", 0.74 if transcript.startswith("(Langes Gespräch") else 0.1)
    out = []
    for d in providers.stream(settings, EDIT_SYSTEM + prefs_block(settings, instruction), [{"role": "user", "content": user}], 8000):
        out.append(d)
        yield d
    text = clean_answer("".join(out), settings, instruction)
    if not text:
        raise providers.LLMError("Die KI hat nichts zurückgegeben – Anweisung etwas genauer formulieren.")
    if text.strip() == sm["content"].strip():
        raise providers.LLMError("Die KI hat nichts geändert – Anweisung genauer formulieren, z. B. „kürzer, "
                                 "höchstens 10 Stichpunkte“.")
    if sm["template_id"] == "mindmap":
        text = finish_mindmap(settings, text)
    db.update_summary(sid, text, keep_prev=True)
    log.info("summary %s changed by the AI: %s", sid, instruction[:80])


def clean_answer(text: str, settings: dict, asked: str = "") -> str:
    """What a model wraps around its answer – <think>, ``` fences, LaTeX, unwanted timestamps, empty "z. B." – out."""
    out = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    out = re.sub(r"^```(?:markdown|md)?\s*\n(.*?)\n```\s*$", r"\1", out, flags=re.S).strip()
    out = formulas.to_text(out)
    if not wants_times(settings, asked):
        out = strip_times(out)
    return finish(out, settings).strip()


def edit_summary(sid: int, instruction: str, settings: dict | None = None) -> str:
    """The same without the stream (MCP, scripts): returns the new version."""
    for _ in edit_summary_stream(sid, instruction, settings):
        pass
    return db.get_summary(sid)["content"]


def generate_stream(rid: str, template_id: str) -> Iterator[str]:
    settings = config.load()
    rec = db.get_recording(rid)
    tpl = templates.get(template_id)
    docs = _docs(settings, rid)
    yield status("Transkript wird vorbereitet …", 0.02)
    transcript = ""
    for item in prepared_transcript_iter(settings, rid, reserve=len(docs)):
        if is_status(item):
            yield item  # "Teil 2 von 6 wird verdichtet …" – shown while waiting
        else:
            transcript = item
    if not transcript.strip():
        raise providers.LLMError("Transkript ist leer.")
    user = f"<transkript>\n{transcript}\n</transkript>\n\n<vorlage name=\"{tpl['name']}\">\n{tpl['prompt']}\n</vorlage>"
    if rec.get("notes"):
        user += f"\n\n<notizen_des_nutzers>\n{rec['notes']}\n</notizen_des_nutzers>"
    if docs:
        user = docs + "\n\n" + user
    system = system_prompt(settings, rec) + (DOCS_NOTE if docs else "")
    yield status("Die KI liest das Transkript …", 0.74 if transcript.startswith("(Langes Gespräch") else 0.08)
    src = providers.stream(settings, system, [{"role": "user", "content": user}])
    yield from (src if wants_times(settings) else strip_times_stream(src))


def generate(rid: str, template_id: str, on_delta: Callable[[str], None] | None = None) -> dict:
    settings = config.load()
    tpl = templates.get(template_id)
    out = []
    for d in generate_stream(rid, template_id):
        if is_status(d):
            continue
        out.append(d)
        if on_delta:
            on_delta(d)
    content = finish("".join(out).strip(), settings)
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
    transcript = ""
    for item in prepared_transcript_iter(settings, rid, reserve=len(docs)):
        if is_status(item):
            yield item
        else:
            transcript = item
    summaries = "\n\n".join(f"## {x['title']}\n{x['content']}" for x in db.list_summaries(rid)[:2])
    docs_rule = ("\nStammt eine Antwort aus den Unterlagen statt aus dem Gespräch, sag das und nenne das Dokument "
                 "(z. B. „laut Agenda.pdf“)." if docs else "")
    system = system_prompt(settings, rec, question) + f"""

Beantworte Fragen zu dieser Aufnahme, konkret und auf den Punkt.{" Belege mit [mm:ss]." if wants_times(settings, question) else ""}
Wenn die Antwort nicht im Transkript steht, sag das klar.{docs_rule}

<transkript>
{transcript}
</transkript>
<bisherige_zusammenfassungen>
{summaries}
</bisherige_zusammenfassungen>""" + ("\n" + docs if docs else "")
    msgs = history + [{"role": "user", "content": question}]
    out = []
    src = providers.stream(settings, system, msgs, 16000)
    for d in (src if wants_times(settings, question) else strip_times_stream(src)):
        out.append(d)
        yield d
    db.add_chat(rid, "user", question)
    db.add_chat(rid, "assistant", finish("".join(out), settings))


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
    times = wants_times(settings, question)
    system = f"""Du bist REKORD und kennst alle Aufnahmen des Nutzers. Beantworte die Frage konkret und auf den Punkt.
{"Belege jede Aussage mit der Quelle im Format [[aufnahme_id@mm:ss]] genau wie in den Auszügen angegeben (wird in der App klickbar)." if times else "Nenne die Quelle mit dem Titel der Aufnahme, ohne [[…]]-Links."}
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
</relevante_auszuege>""" + prefs_block(settings, question)
    history = [{"role": c["role"], "content": c["content"]} for c in db.list_chat("global")][-10:]
    out = []
    src = providers.stream(settings, system, history + [{"role": "user", "content": question}], 16000)
    for d in (src if times else strip_times_stream(src)):
        out.append(d)
        yield d
    db.add_chat("global", "user", question)
    db.add_chat("global", "assistant", finish("".join(out), settings))
