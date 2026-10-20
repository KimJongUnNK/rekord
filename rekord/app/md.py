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
    lines = str(src or "").replace("\r", "").split("\n")
    out: list[str] = []
    stack: list[str] = []
    i = 0

    def close(depth: int = 0) -> None:
        while len(stack) > depth:
            out.append(f"</{stack.pop()}>")

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
            depth = len(m[1].replace("\t", "  ")) // 2 + 1
            tag = "ol" if m[2][0].isdigit() else "ul"
            close(depth)
            if len(stack) == depth and stack[-1] != tag:  # "1." after "-" on the same level: a new list
                close(depth - 1)
            while len(stack) < depth:
                stack.append(tag)
                out.append(f"<{tag}>")
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
            close()
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


def outline(src: str) -> dict:
    """Nested list / headings → tree for the mind map. Lists belong under the heading above them."""
    root = {"text": "", "children": []}
    stack = [(-1, root)]
    base = 0  # list items sit one level below the last heading
    for raw in str(src).split("\n"):
        h = re.match(r"^(#{1,4})\s+(.*)$", raw)
        m = h or re.match(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$", raw)
        if not m:
            continue
        if h:
            depth = len(h[1]) - 1
            base = depth + 1
        else:
            depth = base + len(m[1].replace("\t", "  ")) // 2
        node = {"text": re.sub(r"\[[^\]]*\]", "", m[2].replace("**", "")).strip(), "children": []}
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1]["children"].append(node)
        stack.append((depth, node))
    return root["children"][0] if len(root["children"]) == 1 else {"text": "Gespräch", "children": root["children"]}


PALETTE = ["#FF5A1F", "#2D7FF9", "#16A34A", "#E11D74", "#A855F7", "#EAB308", "#0EA5E9", "#F97316"]
LH, COLW, PAD = 30, 250, 24


def mindmap(src: str) -> dict:
    """Layout of the mind map (horizontal tree): nodes with x/y/depth/color, curved edges, overall size."""
    tree = outline(src)
    y = [0]

    def measure(n, depth):
        n["depth"] = depth
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
    depth = [0]
    walk(tree, lambda n: depth.__setitem__(0, max(depth[0], n["depth"])))
    x = lambda d: PAD + d * COLW  # noqa: E731
    trunc = lambda s, n: s if len(s) <= n else s[: n - 1] + "…"  # noqa: E731
    nodes, edges = [], []

    def emit(n):
        tx, ty = x(n["depth"]), n["y"] + PAD
        nodes.append({"x": tx, "y": ty, "depth": n["depth"], "text": trunc(n["text"], 24 if n["depth"] == 0 else 30),
                      "color": n.get("color", "")})
        for c in n["children"]:
            x1 = x(0) + 204 if n["depth"] == 0 else tx + 14 + min(len(n["text"]), 30) * (8.2 if n["depth"] == 1 else 7.2)
            edges.append({"x1": x1, "y1": ty, "x2": x(c["depth"]) - 6, "y2": c["y"] + PAD, "color": c.get("color", ""),
                          "width": 2.5 if c["depth"] == 1 else 1.5})
    walk(tree, emit)
    return {"nodes": nodes, "edges": edges, "width": (depth[0] + 1) * COLW + PAD * 2, "height": max(y[0], LH) + PAD * 2}


def mindmap_svg(src: str, fg: str = "#111111", fg2: str = "#55534E", bg: str = "#FFFFFF") -> str:
    m = mindmap(src)
    out = [f'<rect width="{m["width"]}" height="{m["height"]}" fill="{bg}"/>']
    for e in m["edges"]:
        mx = (e["x1"] + e["x2"]) / 2
        out.append(f'<path d="M{e["x1"]},{e["y1"]} C{mx},{e["y1"]} {mx},{e["y2"]} {e["x2"]},{e["y2"]}" fill="none" '
                   f'stroke="{e["color"] or fg2}" stroke-width="{e["width"]}" opacity=".75"/>')
    for n in m["nodes"]:
        if n["depth"] == 0:
            out.append(f'<rect x="{n["x"] - 10}" y="{n["y"] - 20}" width="214" height="40" rx="20" fill="{fg}"/>'
                       f'<text x="{n["x"] + 97}" y="{n["y"] + 5}" text-anchor="middle" font-size="15" font-weight="800" fill="{bg}">{esc(n["text"])}</text>')
        else:
            big = n["depth"] == 1
            out.append(f'<circle cx="{n["x"] - 2}" cy="{n["y"]}" r="{5 if big else 3.5}" fill="{n["color"]}"/>'
                       f'<text x="{n["x"] + 8}" y="{n["y"] + 4.5}" font-size="{14 if big else 13}" font-weight="{800 if big else 500}" '
                       f'fill="{fg if big else fg2}">{esc(n["text"])}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{m["width"]}" height="{m["height"]}" viewBox="0 0 {m["width"]} {m["height"]}" '
            f'font-family="Inter, -apple-system, Segoe UI, sans-serif">{"".join(out)}</svg>')
