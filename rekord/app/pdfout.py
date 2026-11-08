"""Export → PDF: the recording (summaries, notes, transcript) as A4 pages that never cut anything off.

The old way (QTextDocument.print_ on a QPdfWriter) laid the text out with the SCREEN's font metrics and painted it at
the PDF's resolution – on a Mac the lines came out wider than the page and were clipped at the right edge; long links
without spaces ran over the margin too. Now the document is measured on the PDF itself, words that don't fit are
broken, margins are fixed, and every page gets a footer (title · page n of N)."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import (QAbstractTextDocumentLayout, QColor, QFont, QFontDatabase, QPageLayout, QPageSize, QPainter,
                           QPalette, QPdfWriter, QTextDocument, QTextOption)

DPI = 300
MARGINS_MM = QMarginsF(18, 16, 18, 14)
FOOTER_PT = 8
FAMILIES = ("Helvetica", "Arial", "Helvetica Neue", "Liberation Sans", "DejaVu Sans", "Noto Sans", "Segoe UI")
# fonts the system has but Qt may not list (e.g. Windows without its own font backend): registered on demand
_SYSTEM_FONTS = ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf", "segoeui.ttf", "segoeuib.ttf")


def family() -> str:
    """A real sans-serif family Qt can embed – never a name it silently replaces with nothing."""
    have = set(QFontDatabase.families())
    for name in FAMILIES:
        if name in have:
            return name
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for file in _SYSTEM_FONTS:
        if (fonts / file).is_file():
            QFontDatabase.addApplicationFont(str(fonts / file))
    have = set(QFontDatabase.families())
    for name in FAMILIES:
        if name in have:
            return name
    return QFontDatabase.systemFont(QFontDatabase.GeneralFont).family()

STYLE = """
body { font-size: 10pt; color: #1A1A1A; }
h1 { font-size: 18pt; margin-bottom: 4pt; }
h2 { font-size: 13.5pt; margin-top: 14pt; margin-bottom: 4pt; }
h3 { font-size: 11.5pt; margin-top: 10pt; }
li { margin-top: 0; margin-bottom: 2pt; }
table { border-collapse: collapse; margin: 4pt 0; }
td, th { border: 1px solid #999999; padding: 3px; }
a { color: #1A1A1A; text-decoration: none; }
"""


def write(dest: str, title: str, body_html: str) -> int:
    """Lay out and write the PDF; returns the number of pages."""
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    w = QPdfWriter(buf)  # into memory: the file is written in one go, complete and closed, below
    w.setResolution(DPI)
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, MARGINS_MM, QPageLayout.Millimeter))
    w.setTitle(title)
    w.setCreator("REKORD")

    doc = QTextDocument()
    doc.documentLayout().setPaintDevice(w)  # measure fonts on the PDF, not on the screen
    font = QFont(family())
    font.setStyleHint(QFont.SansSerif)
    font.setPointSizeF(10)
    doc.setDefaultFont(font)
    opt = QTextOption()
    opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)  # a long link breaks instead of running off the page
    doc.setDefaultTextOption(opt)
    doc.setDefaultStyleSheet(STYLE)
    doc.setDocumentMargin(0)
    # space between paragraphs (the default style sheet's margins are in pixels – nothing at 300 dpi)
    gap = int(DPI * 5 / 72)
    doc.setHtml(body_html.replace("<p>", f'<p style="margin-top:0px; margin-bottom:{gap}px">'))

    page = w.pageLayout().paintRectPixels(DPI)
    footer_h = int(FOOTER_PT / 72 * DPI * 2.2)
    body_h = page.height() - footer_h
    doc.setPageSize(QSizeF(page.width(), body_h))  # the layout paginates: no line is split between two pages
    pages = doc.pageCount()

    paper = QPalette()  # black ink on white paper, whatever the screen's theme is
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        paper.setColor(role, QColor("#1A1A1A"))
    paper.setColor(QPalette.Base, QColor("white"))
    paper.setColor(QPalette.Link, QColor("#1A1A1A"))
    p = QPainter(w)
    try:
        foot = QFont(font)
        foot.setPointSizeF(FOOTER_PT)
        for n in range(pages):
            if n:
                w.newPage()
            p.save()
            p.setClipRect(QRectF(0, 0, page.width(), body_h))
            p.translate(0, -n * body_h)
            # not doc.drawContents: that takes the app's text colour – white in dark mode, invisible on paper
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.clip = QRectF(0, n * body_h, page.width(), body_h)
            ctx.palette = paper
            doc.documentLayout().draw(p, ctx)
            p.restore()
            p.setFont(foot)
            p.setPen(QColor("#777777"))
            line_y = body_h + footer_h * 0.25
            p.drawLine(0, int(line_y), page.width(), int(line_y))
            box = QRectF(0, line_y, page.width(), footer_h * 0.75)
            p.drawText(box, int(Qt.AlignLeft | Qt.AlignVCenter), title[:90])
            p.drawText(box, int(Qt.AlignRight | Qt.AlignVCenter), f"Seite {n + 1} von {pages}")
    finally:
        p.end()
    buf.close()
    Path(dest).write_bytes(bytes(data))
    return pages
