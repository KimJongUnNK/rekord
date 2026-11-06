"""Formatting like in Word for summaries: bold, italic, underline, strikethrough, sub/superscript, font, size, colour,
highlight, headings, lists – applied to the selection of the editor (a QML TextArea, through its QTextDocument).

Stored twice: as HTML (every format, for display, copying and the Word export) and as Markdown (what the AI, search
and the Markdown export read). Copying puts real formatting on the clipboard (HTML + plain text), so Word, Pages or
Google Docs paste bold as bold, lists as lists – not "**" and "- "."""
from __future__ import annotations

import re

from PySide6.QtCore import QMimeData, QObject, Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication, QStandardItem, QStandardItemModel, QTextBlockFormat, \
    QTextCharFormat, QTextCursor, QTextDocument, QTextListFormat

FONTS = ["Aptos", "Calibri", "Arial", "Helvetica", "Georgia", "Times New Roman", "Verdana", "Courier New"]
SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72]
HEADING_PT = {1: 22, 2: 17, 3: 14}
_TS = re.compile(r"\[((?:\d+:)?\d{1,2}:\d{2})\]")


def _doc(qdoc) -> QTextDocument | None:
    """QML passes TextArea.textDocument (a QQuickTextDocument) – or a QTextDocument in tests."""
    if qdoc is None:
        return None
    if isinstance(qdoc, QTextDocument):
        return qdoc
    return qdoc.textDocument() if hasattr(qdoc, "textDocument") else None


def markdown_to_html(src: str) -> str:
    """Markdown (what the AI writes) → HTML with real formatting (headings, bold, lists, tables)."""
    d = QTextDocument()
    d.setMarkdown(src or "")
    return d.toHtml()


def plain(src: str) -> str:
    """Markdown → readable text without marks (for apps that only take plain text)."""
    d = QTextDocument()
    d.setMarkdown(src or "")
    return d.toPlainText()


def display_html(html: str, link_color: str = "") -> str:
    """Stored rich text for showing in the window: timestamps [mm:ss] become links that jump in the audio."""
    def link(m):
        parts = [int(x) for x in m[1].split(":")]
        sec = parts[-1] + 60 * parts[-2] + (3600 * parts[0] if len(parts) == 3 else 0)
        style = f' style="color:{link_color}; text-decoration:none"' if link_color else ""
        return f'<a href="seek:{sec}"{style}>{m[1]}</a>'
    out, pos = [], 0
    for tag in re.finditer(r"<[^>]*>", html or ""):
        out.append(_TS.sub(link, html[pos:tag.start()]))
        out.append(tag.group(0))
        pos = tag.end()
    out.append(_TS.sub(link, (html or "")[pos:]))
    return "".join(out)


class Formatter(QObject):
    """The toolbar's actions for the rich editor (RichEditor.qml)."""

    # ---------------------------------------------------------------- load & save
    @Slot(QObject, str, str)
    def load(self, qdoc, markdown: str, html: str) -> None:
        d = _doc(qdoc)
        if d is None:
            return
        if html:
            d.setHtml(html)
        else:
            d.setMarkdown(markdown or "")

    @Slot(QObject, result=str)
    def html(self, qdoc) -> str:
        d = _doc(qdoc)
        return d.toHtml() if d else ""

    @Slot(QObject, result=str)
    def markdown(self, qdoc) -> str:
        """The text for the AI, search and Markdown export – Markdown knows no underline/colour/size, so those stay
        only in the HTML (underline would otherwise turn into stray "_")."""
        d = _doc(qdoc)
        if d is None:
            return ""
        copy = d.clone()
        c = QTextCursor(copy)
        c.select(QTextCursor.Document)
        f = QTextCharFormat()
        f.setFontUnderline(False)
        c.mergeCharFormat(f)
        return copy.toMarkdown().strip()

    # ---------------------------------------------------------------- the selection
    @staticmethod
    def _cursor(d: QTextDocument, start: int, end: int, word: bool = True) -> QTextCursor:
        c = QTextCursor(d)
        c.setPosition(max(0, start))
        c.setPosition(max(0, end), QTextCursor.KeepAnchor)
        if word and not c.hasSelection():  # nothing selected: the word at the cursor, like Word
            c.select(QTextCursor.WordUnderCursor)
        return c

    @staticmethod
    def _drop(d: QTextDocument, c: QTextCursor, prop) -> None:
        """Remove one format (colour, marker) from the selection – piece by piece, so bold here and italic there
        stay as they are (one setCharFormat over all would copy the first letter's format onto everything)."""
        a, b = c.selectionStart(), c.selectionEnd()
        blk = d.findBlock(a)
        while blk.isValid() and blk.position() <= b:
            it = blk.begin()
            while not it.atEnd():
                fr = it.fragment()
                lo, hi = max(a, fr.position()), min(b, fr.position() + fr.length())
                if lo < hi and fr.charFormat().hasProperty(prop):
                    f = fr.charFormat()
                    f.clearProperty(prop)
                    cc = QTextCursor(d)
                    cc.setPosition(lo)
                    cc.setPosition(hi, QTextCursor.KeepAnchor)
                    cc.setCharFormat(f)
                it += 1
            blk = blk.next()

    def _merge(self, qdoc, start: int, end: int, fmt: QTextCharFormat) -> None:
        d = _doc(qdoc)
        if d is None:
            return
        c = self._cursor(d, start, end)
        c.mergeCharFormat(fmt)

    @Slot(QObject, int, int, str)
    def toggle(self, qdoc, start: int, end: int, what: str) -> None:
        """bold | italic | underline | strike | sub | sup – on if the selection doesn't have it yet, else off."""
        d = _doc(qdoc)
        if d is None:
            return
        cur = self._cursor(d, start, end).charFormat()
        f = QTextCharFormat()
        if what == "bold":
            f.setFontWeight(QFont.Normal if cur.fontWeight() >= QFont.DemiBold else QFont.Bold)
        elif what == "italic":
            f.setFontItalic(not cur.fontItalic())
        elif what == "underline":
            f.setFontUnderline(not cur.fontUnderline())
        elif what == "strike":
            f.setFontStrikeOut(not cur.fontStrikeOut())
        elif what in ("sub", "sup"):
            want = QTextCharFormat.AlignSubScript if what == "sub" else QTextCharFormat.AlignSuperScript
            f.setVerticalAlignment(QTextCharFormat.AlignNormal if cur.verticalAlignment() == want else want)
        else:
            return
        self._merge(qdoc, start, end, f)

    @Slot(QObject, int, int, str)
    def setFont(self, qdoc, start: int, end: int, family: str) -> None:  # noqa: N802 - QML API
        f = QTextCharFormat()
        f.setFontFamilies([family])
        self._merge(qdoc, start, end, f)

    @Slot(QObject, int, int, float)
    def setSize(self, qdoc, start: int, end: int, pt: float) -> None:  # noqa: N802 - QML API
        f = QTextCharFormat()
        f.setFontPointSize(max(4.0, min(144.0, pt)))
        self._merge(qdoc, start, end, f)

    @Slot(QObject, int, int, int)
    def grow(self, qdoc, start: int, end: int, step: int) -> None:
        """A⁺ / A⁻: one step bigger or smaller on the size list."""
        d = _doc(qdoc)
        if d is None:
            return
        now = self._cursor(d, start, end).charFormat().fontPointSize() or 12
        bigger = [s for s in SIZES if s > now]
        smaller = [s for s in SIZES if s < now]
        new = (bigger[0] if bigger else SIZES[-1]) if step > 0 else (smaller[-1] if smaller else SIZES[0])
        self.setSize(qdoc, start, end, float(new))

    @Slot(QObject, int, int, str)
    def setColor(self, qdoc, start: int, end: int, color: str) -> None:  # noqa: N802 - QML API
        """Font colour; "" = automatic again (readable in light and dark, black in Word)."""
        d = _doc(qdoc)
        if d is None:
            return
        c = self._cursor(d, start, end)
        if color:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            c.mergeCharFormat(f)
        else:
            self._drop(d, c, QTextCharFormat.ForegroundBrush)

    @Slot(QObject, int, int, str)
    def setHighlight(self, qdoc, start: int, end: int, color: str) -> None:  # noqa: N802 - QML API
        """Text marker; "" removes it."""
        d = _doc(qdoc)
        if d is None:
            return
        c = self._cursor(d, start, end)
        if color:
            f = QTextCharFormat()
            f.setBackground(QColor(color))
            c.mergeCharFormat(f)
        else:
            self._drop(d, c, QTextCharFormat.BackgroundBrush)

    @Slot(QObject, int, int)
    def clear(self, qdoc, start: int, end: int) -> None:
        """Formatierung entfernen: plain text again (headings and lists stay)."""
        d = _doc(qdoc)
        if d is None:
            return
        self._cursor(d, start, end).setCharFormat(QTextCharFormat())

    # ---------------------------------------------------------------- paragraphs
    @Slot(QObject, int, int, int)
    def heading(self, qdoc, start: int, end: int, level: int) -> None:
        """0 = normal text, 1–3 = heading (bold, bigger) – Word sees it as a heading too."""
        d = _doc(qdoc)
        if d is None:
            return
        c = self._cursor(d, start, end, word=False)
        b = QTextBlockFormat()
        b.setHeadingLevel(level)
        c.mergeBlockFormat(b)
        c.select(QTextCursor.BlockUnderCursor) if not c.hasSelection() else None
        f = QTextCharFormat()
        if level:
            f.setFontWeight(QFont.Bold)
            f.setFontPointSize(HEADING_PT.get(level, 12))
        else:
            f.setFontWeight(QFont.Normal)
            f.setFontPointSize(12)
        c.mergeCharFormat(f)

    @Slot(QObject, int, int, str)
    def list(self, qdoc, start: int, end: int, kind: str) -> None:
        """bullet | number | none."""
        d = _doc(qdoc)
        if d is None:
            return
        c = self._cursor(d, start, end, word=False)
        blk = c.block()
        if kind == "none" or (blk.textList() and ((kind == "bullet") == (blk.textList().format().style()
                                                                         == QTextListFormat.ListDisc))):
            lst = blk.textList()
            if lst:
                for i in range(lst.count() - 1, -1, -1):
                    b = lst.item(i)
                    if c.selectionStart() <= b.position() + b.length() and b.position() <= c.selectionEnd():
                        lst.remove(b)
                        bf = b.blockFormat()
                        bf.setIndent(0)
                        QTextCursor(b).setBlockFormat(bf)
            return
        fmt = QTextListFormat()
        fmt.setStyle(QTextListFormat.ListDisc if kind == "bullet" else QTextListFormat.ListDecimal)
        c.createList(fmt)

    # ---------------------------------------------------------------- what the toolbar shows
    @Slot(QObject, int, int, result="QVariantMap")
    def state(self, qdoc, start: int, end: int) -> dict:
        d = _doc(qdoc)
        if d is None:
            return {}
        c = QTextCursor(d)
        c.setPosition(max(0, end if end > start else start))
        f = c.charFormat()
        fam = f.fontFamilies() or []
        lst = c.block().textList()
        return {"bold": f.fontWeight() >= QFont.DemiBold, "italic": f.fontItalic(), "underline": f.fontUnderline(),
                "strike": f.fontStrikeOut(), "sub": f.verticalAlignment() == QTextCharFormat.AlignSubScript,
                "sup": f.verticalAlignment() == QTextCharFormat.AlignSuperScript,
                "size": round(f.fontPointSize()) if f.fontPointSize() else 12,
                "font": fam[0] if fam else "", "heading": c.blockFormat().headingLevel(),
                "list": ("bullet" if lst.format().style() == QTextListFormat.ListDisc else "number") if lst else ""}

    @Slot(result="QVariantList")
    def fonts(self) -> list:
        return FONTS

    @Slot(result="QVariantList")
    def sizes(self) -> list:
        return SIZES


def for_word(html: str) -> str:
    """The editor's base font (REKORD's UI font) isn't part of the text: without it Word, Pages & co. use their own
    standard font – what you set yourself (size, font, colour) stays on the words."""
    return re.sub(r"<body[^>]*>", "<body>", html or "", count=1)


def _mime() -> QMimeData:
    """An empty QMimeData made by Qt itself. One made in Python (QMimeData()) is a PySide subclass: the clipboard
    still holds it when REKORD quits, deletes it after Python is gone – and the app crashes on quit (segfault)."""
    model = QStandardItemModel()
    model.appendRow(QStandardItem(""))
    m = model.mimeData([model.index(0, 0)])
    for f in m.formats():
        m.removeFormat(f)
    return m


def copy_rich(markdown: str, html: str = "") -> None:
    """On the clipboard as real formatting (HTML for Word & co.) plus clean text without Markdown marks."""
    m = _mime()
    if html:
        d = QTextDocument()
        d.setHtml(html)
        m.setHtml(for_word(html))
        m.setText(d.toPlainText())
    else:
        m.setHtml(for_word(markdown_to_html(markdown)))
        m.setText(plain(markdown))
    QGuiApplication.clipboard().setMimeData(m)
