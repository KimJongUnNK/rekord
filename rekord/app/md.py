"""Markdown → Qt rich text for the window (summaries, answers, release notes). Same rules as the web renderer:
[mm:ss] become links that jump in the audio, [[id@mm:ss]] open another recording, "- [ ]" are to-dos you can tick.

Links: seek:<seconds>, rec:<id>:<seconds>, task:<line>, and normal http(s) links."""
from __future__ import annotations

import html
import re

_TS = r"(?:\d+:)?\d{1,2}:\d{2}"


def esc(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


def to_sec(ts: str) -> int:
    v = 0
    for part in ts.split(":"):
        v = v * 60 + int(part)
    return v


def _inline(s: str, links: bool, link_color: str = "") -> str:
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    if links:
        s = re.sub(rf"\[\[([a-f0-9]{{6,32}})@({_TS})\]\]", lambda m: f'<a href="rec:{m[1]}:{to_sec(m[2])}">{m[2]}</a>', s)
        s = re.sub(rf"\[({_TS})(?:\s*[–-]\s*{_TS})?\]", lambda m: f'<a href="seek:{to_sec(m[1])}">{m[0][1:-1]}</a>', s)
    else:
        s = re.sub(rf"\[\[([a-f0-9]{{6,32}})@({_TS})\]\]", r"\2", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(^|[^*\w])\*([^*\n]+)\*(?!\w)", r"\1<i>\2</i>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    if link_color:  # rich text ignores the window's colors: links in the accent color, without underline
        s = s.replace('<a href="', f'<a style="color:{link_color};text-decoration:none" href="')
    return s


def render(src: str, links: bool = True, link_color: str = "") -> str:
    from .. import formulas
    lines = formulas.to_text(str(src or "")).replace("\r", "").split("\n")  # old summaries with LaTeX, too
    out: list[str] = []
    stack: list[str] = []
    indents: list[int] = []  # the indentation each open list level started at
    i = 0

    def close(depth: int = 0) -> None:
        while len(stack) > depth:
            out.append(f"</{stack.pop()}>")
            indents.pop()

    def next_text(j: int) -> str:
        while j < len(lines) and not lines[j].strip():
            j += 1
        return lines[j] if j < len(lines) else ""

    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            close()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(esc(lines[i]))
                i += 1
            out.append("<pre>" + "\n".join(code) + "</pre>")
            i += 1
            continue
        if re.match(r"^\s*\|.*\|\s*$", line) and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            close()
            cells = lambda l: [_inline(c.strip(), links, link_color) for c in l.strip().strip("|").split("|")]  # noqa: E731
            out.append('<table border="1" cellspacing="0" cellpadding="5"><tr>' + "".join(f"<th>{c}</th>" for c in cells(line)) + "</tr>")
            i += 2
            while i < len(lines) and re.match(r"^\s*\|.*\|\s*$", lines[i]):
                out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells(lines[i])) + "</tr>")
                i += 1
            out.append("</table>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            close()
            n = min(len(m[1]) + 1, 4)  # # → h2: the page title is already the biggest text
            out.append(f"<h{n}>{_inline(m[2], links, link_color)}</h{n}>")
            i += 1
            continue
        if re.match(r"^\s*([-*_])\s*\1\s*\1[\s\-*_]*$", line):
            close()
            out.append("<hr>")
            i += 1
            continue
        m = re.match(r"^>\s?(.*)$", line)
        if m:
            close()
            out.append(f"<blockquote><i>{_inline(m[1], links, link_color)}</i></blockquote>")
            i += 1
            continue
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            # levels by indentation relative to the open lists – 2, 3 or 4 spaces all mean "one deeper"
            ind = len(m[1].replace("\t", "    "))
            tag = "ol" if m[2][0].isdigit() else "ul"
            while indents and indents[-1] > ind:
                close(len(stack) - 1)
            if indents and indents[-1] == ind and stack[-1] != tag:  # "1." after "-" on the same level: a new list
                close(len(stack) - 1)
            if not indents or indents[-1] < ind or stack[-1] != tag:
                start = int(re.match(r"\d+", m[2])[0]) if tag == "ol" else 1
                stack.append(tag)
                indents.append(ind)
                task_list = tag == "ul" and re.match(r"^\[( |x|X)\]\s", m[3])  # to-dos: the box is the marker, no dot as well
                out.append(f'<{tag} start="{start}">' if start > 1 else
                           '<ul style="list-style-type:none">' if task_list else f"<{tag}>")
            t = re.match(r"^\[( |x|X)\]\s+(.*)$", m[3])
            if t:
                done = t[1] != " "
                box = "☑" if done else "☐"
                tint = f";color:{link_color}" if link_color else ""
                box = f'<a href="task:{i}" style="text-decoration:none{tint}">{box}</a>' if links else box
                body = _inline(t[2], links, link_color)
                out.append(f"<li>{box}&nbsp; {'<s>' + body + '</s>' if done else body}</li>")
            else:
                out.append(f"<li>{_inline(m[3], links, link_color)}</li>")
            i += 1
            continue
        if not line.strip():
            nxt = next_text(i + 1)
            # a blank line between "1." and "2." (or before an indented answer) doesn't end the list – else every item says "1."
            if not (stack and (re.match(r"^\s*([-*+]|\d+[.)])\s", nxt) or (nxt[:1].isspace() and nxt.strip()))):
                close()
            i += 1
            continue
        if stack and line[:1].isspace() and out and out[-1].endswith("</li>"):  # an indented line under an item: part of it
            out[-1] = out[-1][:-5] + "<br>" + _inline(line.strip(), links, link_color) + "</li>"
            i += 1
            continue
        close()
        para = [_inline(line, links, link_color)]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|>|\s*([-*+]|\d+[.)])\s|```|\s*\|)", lines[i]):
            para.append(_inline(lines[i].rstrip(), links, link_color))
            i += 1
        out.append("<p>" + "<br>".join(para) + "</p>")
    close()
    return "".join(out)


def toggle_task(src: str, line_no: int) -> str:
    lines = str(src).split("\n")
    if 0 <= line_no < len(lines):
        ln = lines[line_no]
        lines[line_no] = ln.replace("[ ]", "[x]", 1) if "[ ]" in ln else re.sub(r"\[(x|X)\]", "[ ]", ln, count=1)
    return "\n".join(lines)


def _clean_list(src: str) -> list[str]:
    """What a model wraps around its list: <think>…</think>, ``` fences, "Hier ist die Mind Map:" – out."""
    t = re.sub(r"<think>.*?</think>", "", str(src or ""), flags=re.S)
    return [ln.replace("\u00a0", " ").rstrip() for ln in t.split("\n") if not ln.strip().startswith("```")]


def outline(src: str) -> dict:
    """Nested list / headings → tree for the mind map. Lists belong under the heading above them. Any indentation
    works (2 or 4 spaces, tabs) – the smallest step counts as one level."""
    lines = _clean_list(src)
    item = re.compile(r"^(\s*)(?:[-*+•–]|\d+[.)])\s+(.*)$")
    indents = sorted({len(m[1].replace("\t", "    ")) for ln in lines if (m := item.match(ln)) and m[1]})
    unit = indents[0] if indents else 2
    root = {"text": "", "children": []}
    stack = [(-1, root)]
    base = 0  # list items sit one level below the last heading
    for raw in lines:
        h = re.match(r"^(#{1,4})\s+(.*)$", raw.strip())
        m = h or item.match(raw)
        if not m:
            continue
        if h:
            depth = len(h[1]) - 1
            base = depth + 1
        else:
            depth = base + round(len(m[1].replace("\t", "    ")) / unit)
        text = re.sub(r"\[[^\]]*\]", "", m[2].replace("**", "").replace("__", "")).strip().strip("*").strip()
        if not text:
            continue
        node = {"text": text, "children": []}
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1]["children"].append(node)
        stack.append((depth, node))
    kids = root["children"]
    if len(kids) == 1:
        return kids[0]
    if kids and len(kids) > 2 and not kids[0]["children"] and all(not k["children"] for k in kids):
        return {"text": kids[0]["text"], "children": kids[1:]}  # all flat: the first line is the topic
    return {"text": "Gespräch", "children": kids}


def is_flat(src: str) -> bool:
    """A mind map without sub-points (or a dozen branches in a row) – a small model ignored the nesting."""
    tree = outline(src)
    return not any(c["children"] for c in tree["children"]) or len(tree["children"]) > 9


PALETTE = ["#FF5A1F", "#2D7FF9", "#16A34A", "#E11D74", "#A855F7", "#EAB308", "#0EA5E9", "#F97316"]
LH, PAD, GAP = 30, 24, 46
CHAR = {0: 8.6, 1: 8.4, 2: 7.3}  # px per character (bold 15 / bold 14 / 13)
MAXC = 52  # longer texts are shortened (with …) – a whole sentence isn't a branch


def _w(text: str, depth: int) -> float:
    return len(text) * CHAR.get(depth, 7.0)


def mindmap(src: str) -> dict:
    """Layout of the mind map (horizontal tree): nodes with x/y/depth/color/width, curved edges, overall size. Each
    column is as wide as its longest text – nothing cut off at a fixed length."""
    tree = outline(src)
    trunc = lambda s, n: s if len(s) <= n else s[: n - 1] + "…"  # noqa: E731
    y = [0]

    def measure(n, depth):
        n["depth"] = depth
        n["text"] = trunc(n["text"], 40 if depth == 0 else MAXC)
        if not n["children"]:
            n["y"] = y[0]
            y[0] += LH
            return
        for c in n["children"]:
            measure(c, depth + 1)
        n["y"] = (n["children"][0]["y"] + n["children"][-1]["y"]) / 2
    measure(tree, 0)

    def walk(n, f):
        f(n)
        for c in n["children"]:
            walk(c, f)
    for i, c in enumerate(tree["children"]):
        walk(c, lambda n, col=PALETTE[i % len(PALETTE)]: n.__setitem__("color", col))
    widest: dict[int, float] = {}
    walk(tree, lambda n: widest.__setitem__(n["depth"], max(widest.get(n["depth"], 0), _w(n["text"], n["depth"]))))
    center_w = max(140.0, widest.get(0, 0) + 34)
    col_x = {0: PAD}
    col_x[1] = PAD + center_w + GAP
    for d in range(2, max(widest) + 1):
        col_x[d] = col_x[d - 1] + 16 + widest[d - 1] + GAP
    nodes, edges = [], []

    def emit(n):
        tx, ty = col_x[n["depth"]], n["y"] + PAD
        nodes.append({"x": tx, "y": ty, "depth": n["depth"], "text": n["text"], "color": n.get("color", ""),
                      "w": center_w if n["depth"] == 0 else _w(n["text"], n["depth"])})
        for c in n["children"]:
            x1 = tx + center_w - 10 if n["depth"] == 0 else tx + 12 + _w(n["text"], n["depth"])
            edges.append({"x1": x1, "y1": ty, "x2": col_x[c["depth"]] - 7, "y2": c["y"] + PAD, "color": c.get("color", ""),
                          "width": 2.5 if c["depth"] == 1 else 1.5})
    walk(tree, emit)
    last = max(widest)
    width = col_x[last] + (16 + widest[last] if last else center_w) + PAD
    return {"nodes": nodes, "edges": edges, "width": round(width), "height": max(y[0], LH) + PAD * 2}


def mindmap_svg(src: str, fg: str = "#111111", fg2: str = "#55534E", bg: str = "#FFFFFF") -> str:
    m = mindmap(src)
    out = [f'<rect width="{m["width"]}" height="{m["height"]}" fill="{bg}"/>']
    for e in m["edges"]:
        mx = (e["x1"] + e["x2"]) / 2
        out.append(f'<path d="M{e["x1"]},{e["y1"]} C{mx},{e["y1"]} {mx},{e["y2"]} {e["x2"]},{e["y2"]}" fill="none" '
                   f'stroke="{e["color"] or fg2}" stroke-width="{e["width"]}" opacity=".75"/>')
    for n in m["nodes"]:
        if n["depth"] == 0:
            out.append(f'<rect x="{n["x"] - 10}" y="{n["y"] - 20}" width="{n["w"]}" height="40" rx="20" fill="{fg}"/>'
                       f'<text x="{n["x"] - 10 + n["w"] / 2}" y="{n["y"] + 5}" text-anchor="middle" font-size="15" font-weight="800" fill="{bg}">{esc(n["text"])}</text>')
        else:
            big = n["depth"] == 1
            out.append(f'<circle cx="{n["x"] - 2}" cy="{n["y"]}" r="{5 if big else 3.5}" fill="{n["color"]}"/>'
                       f'<text x="{n["x"] + 8}" y="{n["y"] + 4.5}" font-size="{14 if big else 13}" font-weight="{800 if big else 500}" '
                       f'fill="{fg if big else fg2}">{esc(n["text"])}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{m["width"]}" height="{m["height"]}" viewBox="0 0 {m["width"]} {m["height"]}" '
            f'font-family="Inter, -apple-system, Segoe UI, sans-serif">{"".join(out)}</svg>')
