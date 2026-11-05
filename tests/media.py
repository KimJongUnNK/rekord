"""Test media made on the fly: a 'presentation' video (three slides with a moving pointer) with sound."""
from pathlib import Path

import av
import numpy as np

FIX = Path(__file__).parent / "fixtures"
SLIDES = [(230, 60, 40), (40, 120, 230), (40, 200, 90)]  # red and blue are equally bright in grey on purpose


def slides_video(path, seconds_per_slide=5, fps=10, sound=True):
    from rekord import audio
    n = len(SLIDES) * seconds_per_slide * fps
    with av.open(str(path), "w", format="mp4") as out:
        vs = out.add_stream("mpeg4", rate=fps)
        vs.width, vs.height, vs.pix_fmt = 320, 180, "yuv420p"
        vs.options = {"g": str(fps)}  # a key frame every second
        if sound:
            a = out.add_stream("aac", rate=16000)
            a.layout = "mono"
        for i in range(n):
            img = np.zeros((180, 320, 3), np.uint8)
            img[:] = SLIDES[i // (seconds_per_slide * fps)]
            x = 40 + (i % (seconds_per_slide * fps)) * 2
            img[60:120, x:x + 40] = 255  # a pointer moving across – must not count as a new slide
            f = av.VideoFrame.from_ndarray(img, format="rgb24")
            f.pts = i
            for pk in vs.encode(f):
                out.mux(pk)
        for pk in vs.encode(None):
            out.mux(pk)
        if sound:
            x = audio.load(FIX / "meeting1.wav")[:16000 * len(SLIDES) * seconds_per_slide]
            fr = av.AudioFrame.from_ndarray((x * 32767).astype(np.int16).reshape(1, -1), format="s16", layout="mono")
            fr.sample_rate = 16000
            for pk in [*a.encode(fr), *a.encode(None)]:
                out.mux(pk)
    return Path(path)


# ------------------------------------------------------------------ documents for the Unterlagen (built by hand, no libraries)

def _zip(path, parts: dict):
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return Path(path)


def _x(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def docx(path, paragraphs):
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = "".join(f"<w:p><w:r><w:t>{_x(p)}</w:t></w:r></w:p>" for p in paragraphs)
    return _zip(path, {"word/document.xml": f'<?xml version="1.0"?><w:document {w}><w:body>{body}</w:body></w:document>'})


def pptx(path, slides, notes=None):
    a = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    parts = {}
    for i, lines in enumerate(slides, 1):
        paras = "".join(f"<a:p><a:r><a:t>{_x(t)}</a:t></a:r></a:p>" for t in lines)
        parts[f"ppt/slides/slide{i}.xml"] = f'<?xml version="1.0"?><p:sld {a}><p:cSld><p:spTree><p:sp><p:txBody>{paras}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
    for i, text in (notes or {}).items():
        parts[f"ppt/notesSlides/notesSlide{i}.xml"] = f'<?xml version="1.0"?><p:notes {a}><a:p><a:r><a:t>{_x(text)}</a:t></a:r></a:p></p:notes>'
    return _zip(path, parts)


def xlsx(path, strings):
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    si = "".join(f"<si><t>{_x(s)}</t></si>" for s in strings)
    return _zip(path, {"xl/sharedStrings.xml": f'<?xml version="1.0"?><sst {ns}>{si}</sst>'})


def odt(path, paragraphs):
    ns = 'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
    body = "".join(f"<text:p>{_x(p)}</text:p>" for p in paragraphs)
    return _zip(path, {"content.xml": f'<?xml version="1.0"?><office:document-content {ns}><office:body><office:text>{body}</office:text></office:body></office:document-content>'})


def _pdf(path, objects: list[bytes]):
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for o in offsets:
        out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(path).write_bytes(bytes(out))
    return Path(path)


def _stream(data: bytes, extra: str = "") -> bytes:
    return f"<< /Length {len(data)} {extra}>>\nstream\n".encode() + data + b"\nendstream"


def pdf_text(path, lines):
    """A one-page PDF with real text (Helvetica, umlauts as WinAnsi)."""
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")  # noqa: E731
    content = ("BT /F1 12 Tf 50 750 Td 16 TL " + " ".join(f"({esc(t)}) Tj T*" for t in lines) + " ET").encode("cp1252")
    return _pdf(path, [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        _stream(content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"])


def pdf_scan(path, jpeg: bytes, w: int, h: int):
    """A scanned page: no text, just one JPEG picture filling the page."""
    return _pdf(path, [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /XObject << /Im1 5 0 R >> >> >>",
        _stream(b"q 612 0 0 792 0 0 cm /Im1 Do Q"),
        _stream(jpeg, f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode ")])


def jpeg(w=320, h=180, value=200) -> bytes:
    from rekord import frames
    img = np.full((h, w, 3), value, np.uint8)
    img[20:60, 20:200] = 30
    return frames._jpeg(av.VideoFrame.from_ndarray(img, format="rgb24"), width=w)
