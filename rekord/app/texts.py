"""Texts shared with the previous interface: the ⓘ help (rekord/web/help.js stays the one place they're written)
and the reading texts for "Person einsprechen" (every person gets their own, ~45 s)."""
from __future__ import annotations

import functools
import random
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


@functools.lru_cache(maxsize=1)
def tips() -> dict[str, str]:
    src = (WEB / "help.js").read_text("utf-8")
    body = src[src.index("const TIPS = {"):]
    body = body[: body.index("\n};")]
    out = {}
    for m in re.finditer(r'^\s*"?([\w.]+)"?:\s*"((?:[^"\\]|\\.)*)",?\s*$', body, re.M):
        out[m[1]] = m[2].replace('\\"', '"').replace("\\'", "'")
    return out


@functools.lru_cache(maxsize=1)
def _pools() -> dict[str, list[str]]:
    src = (WEB / "app.js").read_text("utf-8")
    out = {}
    for key, name in (("de", "READ_POOL"), ("en", "READ_POOL_EN")):
        block = src[src.index(f"const {name} = ["):]
        block = block[: block.index("];")]
        out[key] = re.findall(r'^\s*"((?:[^"\\]|\\.)*)",?\s*$', block, re.M)
    return out


def reading_text(name: str, variant: int = 0, lang: str = "de") -> str:
    """The same text for the same name (another one with variant+1): 7 varied sentences between intro and counting."""
    lang = "en" if lang == "en" else "de"
    who = (name or "").strip() or "…"
    h = 2166136261
    for ch in (name or "").strip().lower() + "#" + str(variant):
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    pool = [t for _, t in sorted((((h ^ ((i + 1) * 2654435761 & 0xFFFFFFFF)) & 0xFFFFFFFF) % 100003, t)
                                 for i, t in enumerate(_pools()[lang]))]
    if lang == "en":
        first = f"Hi, my name is {who}. I am reading this text in my normal voice so that REKORD can recognise me in meetings."
        last = "Finally I count slowly to ten: one, two, three, four, five, six, seven, eight, nine, ten."
    else:
        first = f"Hallo, ich heiße {who}. Ich lese diesen Text jetzt in meiner normalen Stimme vor, damit REKORD mich in Meetings erkennt."
        last = "Zum Schluss zähle ich langsam bis zehn: eins, zwei, drei, vier, fünf, sechs, sieben, acht, neun, zehn."
    return " ".join([first, *pool[:7], last])


TALK_IDEAS = {
    "de": ["Erzähl, was du heute schon gemacht hast.", "Was ist dein Lieblingsessen – und wie kocht man es?",
           "Beschreib den Weg von dir zuhause zur Arbeit oder Uni.", "Was war dein letzter Urlaub – wo, mit wem, was war das Beste?",
           "Woran arbeitest du gerade, und was ist dabei schwierig?", "Erklär einem Kind, was du beruflich machst oder studierst.",
           "Welches Buch, welche Serie oder welcher Film hat dich zuletzt beeindruckt?", "Was würdest du mit einem freien Tag machen?",
           "Erzähl von einem Konzert oder Event, das du nie vergisst."],
    "en": ["Tell what you have done today so far.", "What is your favourite food – and how do you cook it?",
           "Describe your way from home to work or university.", "Where did you go on your last holiday, and what was the best part?",
           "What are you working on right now, and what is hard about it?", "Explain to a child what you do or study.",
           "Which book, series or film impressed you lately?", "What would you do with a free day?",
           "Tell about a concert or event you will never forget."],
}


def talk_idea(lang: str = "de", previous: str = "") -> str:
    pool = [t for t in TALK_IDEAS["en" if lang == "en" else "de"] if t != previous]
    return random.choice(pool)
