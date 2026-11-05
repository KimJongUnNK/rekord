"""Unterlagen: documents that belong to a recording – the agenda, the slides, a handout, a contract, a photo of the
whiteboard. Speech recognition only hears sounds: a name like "Boenke" or a term like "Kubernetes" it has never seen
comes out as "Bönke" or "Kubernetis". The documents know how they are written.

Everything happens on this computer. REKORD reads the documents (PDF, Word, PowerPoint, Excel, OpenDocument, text,
Markdown, HTML, RTF, EPUB) and uses them three ways:

1. **Correct the transcript.** The rare words of the documents (names, technical terms, product names, acronyms – words
   that aren't in the built-in word list) are compared with the transcript, by spelling and by sound (Kölner Phonetik):
   "Kubernetis" becomes "Kubernetes", "Sapir" becomes "Zapier". Real words ("Vortrag") are never touched. A local AI
   (Ollama, LM Studio) looks over it too – it may only correct *to* words that are in the documents, never rephrase.
   Every correction is listed and can be switched off again.
2. **Hint the recognizer** where the engine takes hints (faster-whisper: the terms as hotwords).
3. **Background for summaries and questions** – with a local AI.

Photos and scanned PDFs: macOS' own text recognition reads them (offline), elsewhere a local AI that can see.
Unterlagen never go to a cloud AI (Claude, ChatGPT) – unless you switch that on yourself
(Einstellungen → Transkription → „Unterlagen auch an Cloud-KI“)."""
from __future__ import annotations

import gzip
import html
import json
import logging
import math
import re
import shutil
import tempfile
import time
import unicodedata
import zipfile
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

from . import config, db

log = logging.getLogger("rekord.context")

DOC_EXT = {".pdf", ".docx", ".docm", ".dotx", ".pptx", ".pptm", ".ppsx", ".xlsx", ".xlsm", ".odt", ".odp", ".ods",
           ".txt", ".md", ".markdown", ".csv", ".tsv", ".rtf", ".html", ".htm", ".xhtml", ".epub", ".json", ".xml",
           ".srt", ".vtt", ".tex", ".log", ".yaml", ".yml"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".avif"}
OLD_OFFICE = {".doc", ".ppt", ".xls", ".pages", ".key", ".numbers"}  # binary formats: ask for PDF/DOCX instead
EXT = DOC_EXT | IMAGE_EXT
DIALOG_FILTER = "Unterlagen (" + " ".join(f"*{e}" for e in sorted(EXT)) + ")"

MAX_BYTES = 200 * 1024 * 1024   # per file
MAX_CHARS = 400_000             # text kept per document (a 300-page book is ~600k – the beginning is plenty for terms)
MAX_SCAN_PAGES = 12             # pages of a scanned PDF an AI reads
AI_IMAGE_WIDTH = 1568           # what vision models look at anyway
TERMS = 80                      # terms used for correcting
PROMPT_TERMS = 40               # terms handed to the recognizer as hint
_HIDDEN = ".text"               # extracted text and notes, next to the files


class Unsupported(ValueError):
    """Not a document REKORD can read (or an old binary Office format)."""


def is_doc(path: str | Path) -> bool:
    return Path(path).suffix.lower() in EXT | OLD_OFFICE


def folder(rid: str) -> Path:
    return config.HOME / "context" / rid


def _meta_dir(rid: str) -> Path:
    return folder(rid) / _HIDDEN


def _safe(name: str) -> str:
    name = Path(name).name.replace("\x00", "").strip() or "Dokument"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name[:150]


# ------------------------------------------------------------------ files

def add(rid: str, src: str | Path, name: str | None = None) -> dict:
    """Copy a document into the recording's folder and read its text. Returns its entry (see items()).
    Unsupported: not a document; OSError: unreadable source."""
    src = Path(src)
    ext = src.suffix.lower() if not name else Path(name).suffix.lower()
    if ext in OLD_OFFICE:
        raise Unsupported(f"{(name or src.name)}: altes Format – bitte als PDF oder {_modern(ext)} speichern und nochmal hinzufügen.")
    if ext not in EXT:
        raise Unsupported(f"{(name or src.name)}: kein Dokument (geht: PDF, Word, PowerPoint, Excel, Text, Bilder …)")
    if src.stat().st_size > MAX_BYTES:
        raise Unsupported(f"{(name or src.name)}: größer als {MAX_BYTES // 1024 // 1024} MB")
    out = folder(rid)
    _meta_dir(rid).mkdir(parents=True, exist_ok=True)
    base = _safe(name or src.name)
    dest, i = out / base, 2
    while dest.exists():
        dest = out / f"{Path(base).stem} ({i}){Path(base).suffix}"
        i += 1
    shutil.copyfile(src, dest)
    try:
        info = _read(dest)
    except Exception as e:  # noqa: BLE001 - a broken file: keep it, say so
        log.warning("context %s: %s", dest.name, e)
        info = {"text": "", "kind": _kind(ext), "note": f"Nicht lesbar: {e}"}
    _store(rid, dest.name, info)
    log.info("context %s: %s (%s, %d chars)", rid, dest.name, info.get("kind"), len(info.get("text", "")))
    return _entry(rid, dest)


def _modern(ext: str) -> str:
    return {".doc": "DOCX", ".pages": "DOCX", ".ppt": "PPTX", ".key": "PPTX", ".xls": "XLSX", ".numbers": "XLSX"}.get(ext, "PDF")


def _store(rid: str, name: str, info: dict) -> None:
    d = _meta_dir(rid)
    d.mkdir(parents=True, exist_ok=True)
    text = info.pop("text", "") or ""
    (d / f"{name}.txt").write_text(text[:MAX_CHARS], "utf-8")
    info["chars"] = len(text)
    info["words"] = len(text.split())
    (d / f"{name}.json").write_text(json.dumps(info, ensure_ascii=False), "utf-8")


def _info(rid: str, name: str) -> dict:
    try:
        return json.loads((_meta_dir(rid) / f"{name}.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _entry(rid: str, p: Path) -> dict:
    info = _info(rid, p.name)
    return {"name": p.name, "kind": info.get("kind") or _kind(p.suffix.lower()), "size": p.stat().st_size,
            "pages": info.get("pages", 0), "chars": info.get("chars", 0), "words": info.get("words", 0),
            "note": info.get("note", ""), "via": info.get("via", ""), "needs_ai": bool(info.get("needs_ai")),
            "path": str(p)}


def items(rid: str) -> list[dict]:
    d = folder(rid)
    if not d.is_dir():
        return []
    return [_entry(rid, p) for p in sorted(d.iterdir(), key=lambda p: p.stat().st_mtime)
            if p.is_file() and not p.name.startswith(".")]


def has(rid: str) -> bool:
    d = folder(rid)
    return d.is_dir() and any(p.is_file() and not p.name.startswith(".") for p in d.iterdir())


def path(rid: str, name: str) -> Path | None:
    p = folder(rid) / _safe(name)
    return p if p.is_file() and p.parent == folder(rid) and not p.name.startswith(".") else None


def remove(rid: str, name: str) -> bool:
    p = path(rid, name)
    if p is None:
        return False
    p.unlink(missing_ok=True)
    for suffix in (".txt", ".json"):
        (_meta_dir(rid) / f"{p.name}{suffix}").unlink(missing_ok=True)
    return True


def remove_all(rid: str) -> None:
    shutil.rmtree(folder(rid), ignore_errors=True)


def text_of(rid: str, name: str) -> str:
    try:
        return (_meta_dir(rid) / f"{name}.txt").read_text("utf-8")
    except OSError:
        return ""


def all_text(rid: str) -> str:
    return "\n\n".join(t for t in (text_of(rid, d["name"]) for d in items(rid)) if t.strip())


def prompt_block(rid: str, budget: int) -> str:
    """The documents for an AI prompt: <unterlagen> with one section per file, each shortened to its share of `budget`."""
    docs = [(d["name"], text_of(rid, d["name"]).strip()) for d in items(rid)]
    docs = [(n, t) for n, t in docs if t]
    if not docs or budget <= 0:
        return ""
    share = max(1500, budget // len(docs))
    parts = []
    for n, t in docs:
        cut = t if len(t) <= share else t[:share].rsplit(" ", 1)[0] + " […gekürzt]"
        parts.append(f'<dokument name="{html.escape(n, quote=True)}">\n{cut}\n</dokument>')
    return "<unterlagen>\n" + "\n".join(parts) + "\n</unterlagen>"


def _kind(ext: str) -> str:
    if ext in IMAGE_EXT:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in (".docx", ".docm", ".dotx", ".odt", ".rtf"):
        return "text-doc"
    if ext in (".pptx", ".pptm", ".ppsx", ".odp"):
        return "slides"
    if ext in (".xlsx", ".xlsm", ".ods", ".csv", ".tsv"):
        return "sheet"
    return "text"


# ------------------------------------------------------------------ reading

def _read(p: Path) -> dict:
    ext = p.suffix.lower()
    kind = _kind(ext)
    if ext in IMAGE_EXT:
        return {"kind": kind, "text": "", "needs_ai": True}
    if ext == ".pdf":
        return _pdf(p)
    if ext in (".docx", ".docm", ".dotx"):
        return {"kind": kind, "text": _docx(p)}
    if ext in (".pptx", ".pptm", ".ppsx"):
        text, n = _pptx(p)
        return {"kind": kind, "text": text, "pages": n}
    if ext in (".xlsx", ".xlsm"):
        return {"kind": kind, "text": _xlsx(p)}
    if ext in (".odt", ".odp", ".ods"):
        return {"kind": kind, "text": _odf(p)}
    if ext == ".epub":
        return {"kind": kind, "text": _epub(p)}
    raw = _decode(p.read_bytes()[:MAX_CHARS * 4])
    if ext in (".html", ".htm", ".xhtml"):
        raw = _html_text(raw)
    elif ext == ".rtf":
        raw = _rtf_text(raw)
    elif ext in (".srt", ".vtt"):
        raw = "\n".join(ln for ln in raw.splitlines() if ln.strip() and "-->" not in ln and not ln.strip().isdigit()
                        and ln.strip() != "WEBVTT")
    return {"kind": kind, "text": raw}


def _decode(b: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16") if b[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig",):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("cp1252", errors="replace")


def _pdf(p: Path) -> dict:
    from pypdf import PdfReader
    r = PdfReader(str(p))
    if r.is_encrypted:  # often only "no printing/copying" with an empty password – that opens
        try:
            opened = bool(r.decrypt(""))
        except Exception as e:  # noqa: BLE001 - e.g. AES without the crypto library
            log.debug("pdf decrypt: %s", e)
            opened = False
        if not opened:
            return {"kind": "pdf", "text": "", "note": "Verschlüsselt – ohne Passwort/Schutz als PDF speichern und nochmal hinzufügen."}
    pages, total = [], 0
    for page in r.pages:
        try:
            t = page.extract_text() or ""
        except Exception as e:  # noqa: BLE001 - one broken page
            log.debug("pdf page: %s", e)
            t = ""
        pages.append(t)
        total += len(t)
        if total > MAX_CHARS:
            break
    n = len(r.pages)
    text = "\n\n".join(pages)
    if n and len(text.strip()) < 25 * min(n, 20):  # (almost) no text layer: a scan or photographed pages
        return {"kind": "pdf", "text": text, "pages": n, "needs_ai": True, "scan": True}
    return {"kind": "pdf", "text": text, "pages": n}


def _xml_paragraphs(data: bytes, para: str, run: str, extra: dict[str, str] | None = None) -> list[str]:
    """Paragraph texts of an Office XML part: `para` and `run` are local tag names (e.g. p / t)."""
    out: list[str] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return out
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] != para:
            continue
        buf = []
        for sub in el.iter():
            tag = sub.tag.rsplit("}", 1)[-1]
            if tag == run and sub.text:
                buf.append(sub.text)
            elif extra and tag in extra:
                buf.append(extra[tag])
        line = "".join(buf).strip()
        if line:
            out.append(line)
    return out


def _docx(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        parts = ["word/document.xml"] + sorted(n for n in names if re.match(r"word/(header|footer|footnotes|endnotes|comments)\d*\.xml$", n))
        lines = []
        for n in parts:
            if n in names:
                lines += _xml_paragraphs(z.read(n), "p", "t", {"tab": "\t", "br": "\n"})
    return "\n".join(lines)


def _pptx(p: Path) -> tuple[str, int]:
    def num(n: str) -> int:
        m = re.search(r"(\d+)\.xml$", n)
        return int(m.group(1)) if m else 0
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        slides = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=num)
        notes = {num(n): n for n in names if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)}
        out = []
        for s in slides:
            body = _xml_paragraphs(z.read(s), "p", "t")
            note = _xml_paragraphs(z.read(notes[num(s)]), "p", "t") if num(s) in notes else []
            note = [ln for ln in note if not ln.isdigit()]  # the slide number placeholder
            block = [f"Folie {num(s)}"] + body + ([f"Notizen: {' '.join(note)}"] if note else [])
            out.append("\n".join(block))
    return "\n\n".join(out), len(slides)


def _xlsx(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        lines = []
        if "xl/sharedStrings.xml" in names:
            lines += _xml_paragraphs(z.read("xl/sharedStrings.xml"), "si", "t")
        for n in sorted(n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)):
            lines += _xml_paragraphs(z.read(n), "is", "t")  # inline strings
    return "\n".join(lines)


def _odf(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        try:
            root = ET.fromstring(z.read("content.xml"))
        except (KeyError, ET.ParseError):
            return ""
    out = []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] in ("p", "h"):
            t = "".join(el.itertext()).strip()
            if t:
                out.append(t)
    return "\n".join(out)


def _epub(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        parts = sorted(n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm")))
        out, total = [], 0
        for n in parts:
            t = _html_text(_decode(z.read(n)))
            out.append(t)
            total += len(t)
            if total > MAX_CHARS:
                break
    return "\n\n".join(out)


def _html_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return "\n".join(" ".join(ln.split()) for ln in s.splitlines() if ln.strip())


def _rtf_text(s: str) -> str:
    s = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), s)
    s = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), s)
    s = re.sub(r"{\\\*[^{}]*}", "", s)
    s = re.sub(r"\\(par|line)\b ?", "\n", s)
    s = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", s)
    s = s.replace("{", "").replace("}", "")
    return "\n".join(" ".join(ln.split()) for ln in s.splitlines() if ln.strip())


# ------------------------------------------------------------------ pictures and scans (read on this computer)

def ai_allowed(settings: dict) -> tuple[bool, str]:
    """May an AI see the Unterlagen? Only one that runs on this computer or in your own network (Ollama, LM Studio …) –
    a cloud AI (Claude, ChatGPT) only if you switch that on (Einstellungen → Transkription). → (ok, reason)"""
    from .llm import providers
    ok, why = providers.configured(settings)
    if not ok:
        return False, "none"
    if providers.is_local(settings) or settings.get("context_cloud"):
        return True, ""
    return False, "cloud"


def _pictures(d: dict) -> list[bytes]:
    """JPEGs of a document that has no text layer: the picture itself, or the page images of a scanned PDF."""
    p = Path(d["path"])
    if d["kind"] == "image":
        jpg = _to_jpeg(p)
        return [jpg] if jpg else []
    if d["kind"] != "pdf":
        return []
    out = []
    for data, ext in _pdf_page_images(p):
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(data)
        try:
            jpg = _to_jpeg(Path(f.name))
        finally:
            Path(f.name).unlink(missing_ok=True)
        if jpg:
            out.append(jpg)
    return out


def _pdf_page_images(p: Path):
    """The biggest picture of each page of a scanned PDF, as the encoded bytes (JPEG / JPEG 2000) – no image library."""
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject
    for page in PdfReader(str(p)).pages[:MAX_SCAN_PAGES]:
        best = None
        try:
            res = page.get("/Resources")
            xobjs = res.get_object().get("/XObject") if res else None
            for ref in (xobjs.get_object().values() if xobjs else []):
                o = ref.get_object()
                if o.get("/Subtype") != "/Image":
                    continue
                flt = o.get("/Filter")
                if isinstance(flt, ArrayObject):
                    flt = flt[0] if len(flt) == 1 else None
                if flt in ("/DCTDecode", "/JPXDecode"):
                    data = o._data  # the stream as stored: a complete JPEG / JPEG 2000 file
                    if best is None or len(data) > len(best[0]):
                        best = (bytes(data), ".jpg" if flt == "/DCTDecode" else ".jp2")
        except Exception as e:  # noqa: BLE001 - an odd page
            log.debug("pdf page images: %s", e)
        if best:
            yield best


def _to_jpeg(p: Path) -> bytes | None:
    """Any picture FFmpeg can decode → a JPEG at most AI_IMAGE_WIDTH wide."""
    import av
    from . import frames
    try:
        with av.open(str(p)) as c:
            vs = next((s for s in c.streams if s.type == "video"), None)
            if vs is None:
                return None
            for frame in c.decode(vs):
                return frames._jpeg(frame, width=AI_IMAGE_WIDTH, quality="3")
    except Exception as e:  # noqa: BLE001 - a format this FFmpeg can't decode (e.g. some HEIC)
        log.warning("image %s: %s", p.name, e)
    return None


def mac_ocr(image: Path) -> str:
    """macOS' own text recognition (Vision – the one behind „Live Text“): on this computer, offline, German and English.
    Lines top to bottom. RuntimeError when it isn't available (not a Mac, older macOS)."""
    import sys
    if sys.platform != "darwin":
        raise RuntimeError("nur am Mac")
    try:
        import Vision
        from Foundation import NSURL
    except ImportError as e:
        raise RuntimeError("Texterkennung von macOS nicht verfügbar") from e
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(True)
    try:
        req.setRecognitionLanguages_(["de-DE", "en-US"])
    except Exception as e:  # noqa: BLE001 - very old macOS: its default languages
        log.debug("ocr languages: %s", e)
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(str(image)), {})
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"macOS-Texterkennung: {err}")
    found = []
    for obs in req.results() or []:
        cand = obs.topCandidates_(1)
        if not cand:
            continue
        box = obs.boundingBox()
        found.append((box.origin.y + box.size.height, box.origin.x, str(cand[0].string())))
    found.sort(key=lambda f: (-round(f[0], 2), f[1]))  # Vision's origin is bottom left: top line first
    return "\n".join(t for _, _, t in found)


def _ocr_bytes(jpg: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(jpg)
    try:
        return mac_ocr(Path(f.name))
    finally:
        Path(f.name).unlink(missing_ok=True)


READ_PROMPT = ("Schreib den gesamten Text auf diesem Bild ab – Folien, Whiteboard, Dokumente, Beschriftungen, Namen –, "
               "Zeile für Zeile, ohne Kommentar und ohne Einleitung. Steht kein Text darauf, beschreib in einem Satz, was "
               "zu sehen ist, beginnend mit „Bild:“.")


def _read_pictures(rid: str, settings: dict) -> None:
    """Photos and scanned PDFs: their text, read on this computer – macOS' own text recognition, otherwise a local AI
    that can see (Ollama with a vision model). A cloud AI only if you allowed it for Unterlagen. Once per document."""
    import sys
    from .llm import providers
    pending = [d for d in items(rid) if d["needs_ai"]]
    if not pending:
        return
    allowed, why = ai_allowed(settings)
    for d in pending:
        info = _info(rid, d["name"])
        info["text"] = text_of(rid, d["name"])
        try:
            pics = _pictures(d)
        except Exception as e:  # noqa: BLE001
            log.warning("pictures %s: %s", d["name"], e)
            pics = []
        if not pics:
            info["note"] = ("Bild nicht lesbar – als JPG oder PNG speichern und nochmal hinzufügen." if d["kind"] == "image"
                            else "Gescannt, ohne Text – die Seiten ließen sich nicht als Bild lesen.")
            _store(rid, d["name"], info)
            continue
        texts, via, problem = [], "", ""
        if sys.platform == "darwin":
            try:
                texts = [_ocr_bytes(j) for j in pics]
                via = "macOS"
            except Exception as e:  # noqa: BLE001
                log.warning("mac ocr %s: %s", d["name"], e)
                problem = str(e)
        if not any(t.strip() for t in texts) and allowed:
            try:
                texts = [providers.read_image(settings, j, "image/jpeg", READ_PROMPT).strip() for j in pics]
                via = "lokale KI" if providers.is_local(settings) else "KI"
            except Exception as e:  # noqa: BLE001 - no vision in this model, Ollama not running …
                log.warning("ai read %s: %s", d["name"], e)
                problem = str(e)
        if any(t.strip() for t in texts):
            info["text"] = "\n\n".join(t if len(texts) == 1 else f"Seite {i + 1}\n{t}" for i, t in enumerate(texts) if t.strip())
            info.update(needs_ai=False, via=via, note="")
            if d["kind"] == "pdf":
                info["pages"] = info.get("pages") or len(pics)
        elif problem:
            info["note"] = f"Konnte nicht gelesen werden: {problem}"
        elif why == "cloud":
            info["note"] = ("Kein Text gefunden. Bilder liest REKORD mit einer lokalen KI, die sehen kann (Ollama, z. B. "
                            "qwen2.5vl) – deine KI läuft in der Cloud, Unterlagen bleiben auf dem Rechner.")
        elif sys.platform == "darwin":
            info["note"] = "Kein Text auf dem Bild gefunden."
        else:
            info["note"] = ("Bild – den Text liest eine lokale KI, die sehen kann: Ollama mit z. B. qwen2.5vl oder gemma3 "
                            "(Einstellungen → KI → Lokal).")
        _store(rid, d["name"], info)


# ------------------------------------------------------------------ terms

_WORD = re.compile(r"[^\W\d_](?:[\w’'&+\-.]*\w)?")
_SENT_END = re.compile(r"[.!?:;•\n]\s*$")
# words that are capitalized anyway (German nouns at a sentence start, articles …): never "terms"
_STOP = set("""der die das den dem des ein eine einer eines einem einen und oder aber doch sondern denn weil wenn als
ob dass daß wie wo was wer wann warum ich du er sie es wir ihr mein dein sein unser euer ihre ihren seine seinen im in
am an auf aus bei mit nach von vor zu zum zur über unter für gegen ohne um bis durch ist sind war waren wird werden
hat haben hatte hatten kann können muss müssen soll sollen will wollen darf dürfen nicht kein keine auch noch nur schon
sehr mehr hier dort heute morgen gestern jetzt dann also so ja nein bitte danke herr frau dr prof seite folie kapitel
abbildung tabelle anhang inhalt einleitung fazit agenda protokoll datum uhr ort thema januar februar märz april mai
juni juli august september oktober november dezember montag dienstag mittwoch donnerstag freitag samstag sonntag
the a an and or but if when as of to in on at by for with from into about this that these those it its is are was
were be been have has had do does did not no yes we you they he she i my our your their page slide chapter figure table
mr mrs ms dear thanks thank hello hi best regards""".split())


@lru_cache(maxsize=1)
def _ranks() -> dict[str, int]:
    """The 50 000 most frequent German and English words each, by frequency (rekord/data/words.txt.gz, in the app –
    never loaded from the internet). Not in it: names, jargon, product names – what speech recognition gets wrong."""
    try:
        words = gzip.decompress((Path(__file__).parent / "data" / "words.txt.gz").read_bytes()).decode("utf-8").split("\n")
    except OSError:
        log.warning("word list missing")
        return {}
    return {w: i for i, w in enumerate(words)}


COMMON_RANK = 30_000  # among the 30 000 most frequent words: a real word, never "corrected"


def rank(word: str) -> int:
    return _ranks().get(word.lower(), 10 ** 9)


def is_word(word: str) -> bool:
    """A word of the language (in the word list) – not a name or a term."""
    return word.lower() in _ranks()


def norm(s: str) -> str:
    """Lowercase, no accents/umlaut dots, letters and digits only: "Bönke" → "bonke", "sherpa-onnx" → "sherpaonnx"."""
    s = unicodedata.normalize("NFKD", s.replace("ß", "ss").lower())
    return "".join(c for c in s if c.isalnum() and not unicodedata.combining(c))


def phonetic(word: str) -> str:
    """Kölner Phonetik: words that sound alike get the same code (Meier/Maier/Mayer → 67; Zapier/Sapir → 817)."""
    w = norm(word)
    w = re.sub(r"\d", "", w)
    codes = []
    for i, c in enumerate(w):
        prev = w[i - 1] if i else ""
        nxt = w[i + 1] if i + 1 < len(w) else ""
        if c in "aeijouy":
            code = "0"
        elif c == "h":
            code = ""
        elif c == "b":
            code = "1"
        elif c == "p":
            code = "3" if nxt == "h" else "1"
        elif c in "dt":
            code = "8" if nxt in "csz" else "2"
        elif c in "fvw":
            code = "3"
        elif c in "gkq":
            code = "4"
        elif c == "c":
            if i == 0:
                code = "4" if nxt in "ahkloqrux" else "8"
            else:
                code = "8" if prev in "sz" or nxt not in "ahkoqux" else "4"
        elif c == "x":
            code = "8" if prev in "ckq" else "48"
        elif c == "l":
            code = "5"
        elif c in "mn":
            code = "6"
        elif c == "r":
            code = "7"
        elif c in "sz":
            code = "8"
        else:
            code = ""
        codes.append(code)
    out = ""
    for code in "".join(codes):
        if not out or out[-1] != code:
            out += code
    return out[:1] + out[1:].replace("0", "") if out else ""


def _shape(w: str) -> str:
    letters = [c for c in w if c.isalpha()]
    if any(c.isdigit() for c in w) and letters:
        return "digit"
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        return "acronym"
    if any(c.isupper() for c in w[1:]) and any(c.islower() for c in w):
        return "mixed"
    if w[:1].isupper():
        return "cap"
    return "lower"


def terms(text: str, limit: int = TERMS) -> list[str]:
    """The words of a document that speech recognition is likely to get wrong: names, technical terms, product names,
    acronyms – words that aren't in the language's word list, weighed by how often and how they are written.
    Most important first."""
    seen: dict[str, dict] = {}
    pairs: dict[str, int] = {}
    prev_word, prev_end = None, 0

    def note(w: str, start_of_sentence: bool) -> None:
        low = w.lower()
        shape = _shape(w)
        rare = not is_word(low)
        keep = low not in _STOP and (
            shape in ("acronym", "mixed", "digit")
            or (shape == "cap" and rare and len(w) >= 4)
            or (shape == "lower" and rare and len(w) >= 6))
        if keep:
            e = seen.setdefault(low, {"forms": {}, "n": 0, "mid": 0, "shape": shape, "rare": rare})
            e["forms"][w] = e["forms"].get(w, 0) + 1
            e["n"] += 1
            e["mid"] += 0 if start_of_sentence else 1

    for m in _WORD.finditer(text[:MAX_CHARS]):
        w = m.group(0).strip("'’.-")
        if len(w) < 2:
            prev_word = None
            continue
        start_of_sentence = m.start() == 0 or bool(_SENT_END.search(text[max(0, m.start() - 4):m.start()]))
        note(w, start_of_sentence)
        if "-" in w:  # "Kubernetes-Cluster": "Kubernetes" is the term to listen for
            for part in w.split("-"):
                if len(part) >= 4:
                    note(part, start_of_sentence)
        shape = _shape(w)
        # "Firstname Lastname", "Coffee Club": two capitalized words in a row
        if prev_word and shape in ("cap", "mixed") and text[prev_end:m.start()] == " " \
                and w.lower() not in _STOP and prev_word.lower() not in _STOP:
            pair = f"{prev_word} {w}"
            pairs[pair] = pairs.get(pair, 0) + 1
        prev_word = w if shape in ("cap", "mixed") else None
        prev_end = m.end()
    scored = []
    for low, e in seen.items():
        if e["shape"] == "cap" and e["mid"] == 0 and e["n"] < 2:
            continue  # only ever at a sentence start: just a capitalized word
        if e["shape"] == "lower" and e["n"] < 2:
            continue
        base = {"mixed": 4, "acronym": 3, "digit": 3, "cap": 2, "lower": 1}[e["shape"]]
        score = base + (1.5 if e["rare"] else 0) + min(2.5, math.log2(e["n"] + 1)) + (0.5 if len(low) >= 9 else 0)
        form = max(e["forms"].items(), key=lambda kv: kv[1])[0]
        scored.append((score, form))
    for pair, n in pairs.items():
        a, b = pair.split(" ", 1)
        rare = not is_word(a) or not is_word(b)
        if (n >= 2 and rare) or (a.lower() in seen and b.lower() in seen):
            scored.append((2 + min(2.5, math.log2(n + 1)) + (1.5 if rare else 0), pair))
    scored.sort(key=lambda x: (-x[0], x[1].lower()))
    out, have = [], set()
    for _, t in scored:
        if t.lower() not in have:
            have.add(t.lower())
            out.append(t)
        if len(out) >= limit:
            break
    return out


def doc_words(text: str) -> set[str]:
    return {norm(m.group(0)) for m in _WORD.finditer(text[:MAX_CHARS])}


def hint(rid: str, settings: dict | None = None) -> str:
    """The terms as a hint for engines that take one (faster-whisper's hotwords)."""
    if not has(rid):
        return ""
    t = terms(all_text(rid), PROMPT_TERMS)
    return ", ".join(t)[:800]


# ------------------------------------------------------------------ correcting the transcript

class _Term:
    __slots__ = ("text", "n", "ph", "first")

    def __init__(self, text: str):
        self.text = text
        self.n = norm(text)
        self.ph = phonetic(text)
        self.first = self.ph[:1]


def _correctable(term_list: list[str]) -> list[_Term]:
    out = []
    for t in term_list:
        x = _Term(t)
        if len(x.n) >= 5 and len(x.ph) >= 2:
            out.append(x)
    return out


_TOKEN = re.compile(r"[^\W_][\w’'\-]*", re.UNICODE)


def _windows(text: str, size: int = 3):
    """(start, end, surface) of 1–3 neighbouring words separated by one space or hyphen."""
    toks = [(m.start(), m.end()) for m in _TOKEN.finditer(text)]
    for i in range(len(toks)):
        for k in range(1, size + 1):
            j = i + k - 1
            if j >= len(toks):
                break
            if k > 1 and text[toks[j - 1][1]:toks[j][0]] not in (" ", "-"):
                break
            yield toks[i][0], toks[j][1], text[toks[i][0]:toks[j][1]], k


def _same_sound(a: str, b: str) -> bool:
    """Kölner Phonetik, plus: a final "-er" sounds like "-a" (Dinzler / Dinzla)."""
    return a == b or (a.rstrip("7") == b.rstrip("7") and len(a.rstrip("7")) >= 2)


def _match(surface: str, words: int, term: _Term, vocab: set[str]) -> float:
    """How surely `surface` (from the transcript) is a misheard `term` – 0 = not at all."""
    n = norm(surface)
    if not n or surface == term.text:
        return 0.0
    if n == term.n:  # only spacing or case differs: "Order Bird" → "Orderbird", "sumup" → "SumUp"
        return 0.95 if words > 1 or _shape(term.text) in ("mixed", "acronym", "digit") else 0.0
    if abs(len(n) - len(term.n)) > max(2, len(term.n) * 0.3):
        return 0.0
    if n in vocab:  # the documents use that word themselves: it's a real word
        return 0.0
    if words == 1 and rank(surface) < COMMON_RANK:  # a word of the language ("Vortrag" is not a misheard "Vertrag")
        return 0.0
    if n.startswith(term.n) or term.n.startswith(n):  # "Strategiepapiere" ↔ "Strategiepapier": an ending, not a mistake
        if abs(len(n) - len(term.n)) <= 3:
            return 0.0
    ph = phonetic(surface)
    if ph[:1] != term.first and n[:1] != term.n[:1]:
        return 0.0
    sm = SequenceMatcher(None, n, term.n)
    if sm.real_quick_ratio() < 0.7 or sm.quick_ratio() < 0.7:
        return 0.0
    r = sm.ratio()
    if words > 1:
        return r if r >= 0.9 or (r >= 0.75 and _same_sound(ph, term.ph)) else 0.0
    if r >= 0.86:
        return r
    if r >= 0.72 and _same_sound(ph, term.ph) and len(term.n) >= 6:
        return r
    return 0.0


def find_local(texts: list[str], term_list: list[str], vocab: set[str]) -> list[dict]:
    """[{from, to}] – words in the transcript that are a misheard document term (by spelling and by sound)."""
    tl = _correctable(term_list)
    if not tl:
        return []
    found: dict[tuple[str, str], int] = {}
    for text in texts:
        taken: list[tuple[int, int]] = []
        cands = []
        for a, b, surface, k in _windows(text):
            best, best_t = 0.0, None
            for t in tl:
                r = _match(surface, k, t, vocab)
                if r > best:
                    best, best_t = r, t
            if best_t:
                cands.append((best, k, a, b, surface, best_t.text))
        for _r, _k, a, b, surface, to in sorted(cands, key=lambda c: (-c[0], -c[1])):
            if any(a < y and x < b for x, y in taken):
                continue
            taken.append((a, b))
            found[(surface, to)] = found.get((surface, to), 0) + 1
    return [{"from": f, "to": t} for (f, t) in found]


def _pattern(src: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(src)}(?!\w)")


def apply_fixes(text: str, fixes: list[dict], counts: dict | None = None) -> str:
    """The switched-on fixes, longest first (word boundaries, exact spelling of the misheard word)."""
    for f in sorted((f for f in fixes if not f.get("off")), key=lambda f: -len(f["from"])):
        text, n = _pattern(f["from"]).subn(f["to"].replace("\\", "\\\\"), text)
        if counts is not None and n:
            counts[(f["from"], f["to"])] = counts.get((f["from"], f["to"]), 0) + n
    return text


# ------------------------------------------------------------------ … with an AI

AI_SYSTEM = """Du korrigierst Fehler einer Spracherkennung anhand von Unterlagen zum Gespräch.
Die Spracherkennung schreibt seltene Namen und Fachbegriffe oft falsch, aber ähnlich klingend
(z. B. „Kubernetis“ statt „Kubernetes“, „Frau Bönke“ statt „Frau Boenke“, „Sapir“ statt „Zapier“).

Finde solche Stellen im Transkript. Regeln:
- „richtig“ MUSS genau so in den Begriffen oder Unterlagen vorkommen. Nichts anderes korrigieren.
- „falsch“ ist exakt die Zeichenfolge aus dem Transkript (Groß-/Kleinschreibung wie dort), ein bis drei Wörter.
- Nur sichere Fälle, bei denen klar ist, dass derselbe Begriff gemeint war. Keine Grammatik, keine Umformulierung,
  keine Synonyme, keine Übersetzung. Im Zweifel weglassen.
- Antworte ausschließlich mit JSON: {"korrekturen": [{"falsch": "…", "richtig": "…"}]} – leer, wenn nichts zu tun ist."""


def find_with_ai(settings: dict, texts: list[str], term_list: list[str], doc_text: str) -> list[dict]:
    from .llm import providers
    joined = "\n".join(texts)
    if not joined.strip():
        return []
    limit = providers.context_chars(settings)
    chunk = max(6000, min(120_000, int(limit * 0.55)))
    excerpt_len = max(2000, min(30_000, int(limit * 0.2)))
    excerpt = doc_text[:excerpt_len]
    head = f"<begriffe>\n{chr(10).join(term_list)}\n</begriffe>\n<unterlagen_auszug>\n{excerpt}\n</unterlagen_auszug>\n"
    doc_low = doc_text.lower()
    vocab_terms = {t.lower() for t in term_list}
    out: dict[tuple[str, str], None] = {}
    lines, cur, size = joined.split("\n"), [], 0
    chunks = []
    for ln in lines:
        if size + len(ln) > chunk and cur:
            chunks.append("\n".join(cur))
            cur, size = [], 0
        cur.append(ln)
        size += len(ln) + 1
    if cur:
        chunks.append("\n".join(cur))
    for part in chunks:
        raw = providers.complete(settings, AI_SYSTEM, [{"role": "user", "content": head + f"<transkript>\n{part}\n</transkript>"}], 4000)
        for f in _parse_fixes(raw):
            src, dst = f["from"], f["to"]
            if not (0 < len(src) <= 60 and 0 < len(dst) <= 80) or src.lower() == dst.lower() and src == dst:
                continue
            if len(src.split()) > 3 or not _pattern(src).search(part):
                continue  # not in the transcript as written
            if dst.lower() not in doc_low and dst.lower() not in vocab_terms:
                continue  # an AI's own idea, not a word from the documents
            if re.search(rf"(?<!\w){re.escape(src.lower())}(?!\w)", doc_low):
                continue  # the documents use the "wrong" word too: it's a real word
            out[(src, dst)] = None
    return [{"from": a, "to": b} for a, b in out]


def _parse_fixes(raw: str) -> list[dict]:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    out = []
    for f in data.get("korrekturen") or data.get("corrections") or []:
        if isinstance(f, dict):
            src = str(f.get("falsch") or f.get("from") or "").strip()
            dst = str(f.get("richtig") or f.get("to") or "").strip()
            if src and dst:
                out.append({"from": src, "to": dst})
    return out


# ------------------------------------------------------------------ the whole step

def state(rid: str) -> dict:
    try:
        return json.loads((_meta_dir(rid) / "_state.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _set_state(rid: str, **kw) -> None:
    d = _meta_dir(rid)
    if not d.parent.is_dir():
        return
    d.mkdir(parents=True, exist_ok=True)
    s = state(rid)
    s.update(kw)
    (d / "_state.json").write_text(json.dumps(s, ensure_ascii=False), "utf-8")


def run(rid: str, settings: dict | None = None, use_ai: bool | None = None) -> dict:
    """Read what still needs reading (photos, scans), then correct the transcript with the documents' terms: on this
    computer, and with an AI if one is allowed to see the Unterlagen (a local one; a cloud AI only if you switched that
    on) and „Mit KI abgleichen“ is on. Starts from the transcript as the recognizer wrote it, so running again (more
    documents, one removed) never stacks corrections. Fixes you switched off stay off.
    Returns {"fixes": n, "changed": lines, "note": …}."""
    s = settings or config.load()
    rec = db.get_recording(rid)
    if rec is None:
        return {"fixes": 0, "changed": 0, "note": ""}
    _read_pictures(rid, s)
    segs = db.list_segments(rid)
    base = [(seg["id"], seg["orig"] if seg.get("orig") is not None else seg["text"]) for seg in segs]
    text = all_text(rid)
    note = ""
    found: list[dict] = []
    if text.strip() and base:
        tl = terms(text, TERMS)
        found = [{**f, "by": "lokal"} for f in find_local([b for _, b in base], tl, doc_words(text))]
        ai_on = s.get("context_ai", True) if use_ai is None else use_ai
        allowed, why = ai_allowed(s)
        if ai_on and allowed:
            try:
                have = {(f["from"], f["to"]) for f in found}
                taken = {f["from"] for f in found}
                for f in find_with_ai(s, [b for _, b in base], tl, text):
                    if (f["from"], f["to"]) not in have and f["from"] not in taken:
                        found.append({**f, "by": "KI"})
            except Exception as e:  # noqa: BLE001 - Ollama not running … the local fixes still count
                log.warning("context ai %s: %s", rid, e)
                note = f"KI-Abgleich ging nicht: {e}"
        elif ai_on and why == "cloud":
            note = ("Auf diesem Rechner abgeglichen. Deine KI läuft in der Cloud – Unterlagen bleiben hier "
                    "(ändern: Einstellungen → Transkription).")
        elif ai_on:
            note = "Auf diesem Rechner abgeglichen – mit einer lokalen KI (Ollama) findet REKORD noch mehr."
    off = {(f["from"], f["to"]) for f in rec.get("context_fixes") or [] if f.get("off")}
    fixes = [{**f, "off": (f["from"], f["to"]) in off} for f in found]
    changed = _apply(rid, base, fixes)
    _set_state(rid, ran_at=time.time(), note=note)
    n = sum(1 for f in fixes if not f["off"] and f.get("count"))
    log.info("context %s: %d fixes, %d lines changed", rid, n, changed)
    return {"fixes": n, "changed": changed, "note": note}


def _apply(rid: str, base: list[tuple[int, str]], fixes: list[dict]) -> int:
    counts: dict = {}
    updates = []
    for sid, text in base:
        new = apply_fixes(text, fixes, counts)
        updates.append((sid, new, text if new != text else None))
    for f in fixes:
        f["count"] = counts.get((f["from"], f["to"]), 0)
    fixes = [f for f in fixes if f["count"] or f.get("off")]
    db.set_segment_texts(updates)
    db.update_recording(rid, context_fixes=fixes)
    return sum(1 for _, _, orig in updates if orig is not None)


def toggle(rid: str, src: str, dst: str, on: bool) -> int:
    """Switch one correction off (back to what the recognizer wrote) or on again. Returns the lines changed."""
    rec = db.get_recording(rid) or {}
    fixes = [dict(f) for f in rec.get("context_fixes") or []]
    for f in fixes:
        if f["from"] == src and f["to"] == dst:
            f["off"] = not on
    segs = db.list_segments(rid)
    base = [(seg["id"], seg["orig"] if seg.get("orig") is not None else seg["text"]) for seg in segs]
    # off fixes are kept (so a re-run leaves them off); a switched-on one is counted again from the original text
    counts: dict = {}
    updates = []
    for sid, text in base:
        new = apply_fixes(text, fixes, counts)
        updates.append((sid, new, text if new != text else None))
    for f in fixes:
        f["count"] = counts.get((f["from"], f["to"]), 0) if not f.get("off") else f.get("count", 0)
    db.set_segment_texts(updates)
    db.update_recording(rid, context_fixes=fixes)
    return sum(1 for _, _, orig in updates if orig is not None)


def undo_all(rid: str) -> int:
    """Every correction off: the transcript as the recognizer wrote it (your own edits stay)."""
    rec = db.get_recording(rid) or {}
    fixes = [dict(f, off=True) for f in rec.get("context_fixes") or []]
    segs = db.list_segments(rid)
    base = [(seg["id"], seg["orig"] if seg.get("orig") is not None else seg["text"]) for seg in segs]
    db.set_segment_texts([(sid, text, None) for sid, text in base])
    db.update_recording(rid, context_fixes=fixes)
    return sum(1 for seg in segs if seg.get("orig") is not None)


# ------------------------------------------------------------------ live

class LiveFixer:
    """Corrections while recording: the documents' terms, re-read when a document is added during the recording."""

    def __init__(self, rid: str, settings: dict):
        self.rid, self.s = rid, settings
        self._sig: tuple = ()
        self._terms: list[str] = []
        self._vocab: set[str] = set()
        self._checked = 0.0

    def _refresh(self) -> None:
        now = time.monotonic()
        if now - self._checked < 5:
            return
        self._checked = now
        docs = items(self.rid)
        sig = tuple((d["name"], d["chars"]) for d in docs)
        if sig != self._sig:
            self._sig = sig
            text = all_text(self.rid)
            self._terms = terms(text, TERMS) if text else []
            self._vocab = doc_words(text) if text else set()

    def __call__(self, text: str) -> str:
        try:
            self._refresh()
            if not self._terms or not text:
                return text
            fixes = find_local([text], self._terms, self._vocab)
            return apply_fixes(text, fixes) if fixes else text
        except Exception as e:  # noqa: BLE001 - never break the live transcript
            log.debug("live fix: %s", e)
            return text
