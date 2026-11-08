"""Formulas in summaries, notes and answers: readable everywhere – window, copy, Word, search, Markdown export.

AIs (local ones above all) like to write LaTeX: $\\frac{G}{U} \\cdot 100$, x^{2}, \\Delta K. REKORD's text views (Qt rich
text), Word and a plain-text clipboard can't typeset that, so the reader saw backslashes and braces. This turns it into
formula text with real symbols – G / U · 100, x², ΔK – offline, without a browser engine. The AI is also told to write
formulas like that in the first place (summarize.FORMULA_RULE); this catches what slips through, also in old summaries.
"""
from __future__ import annotations

import re

SUP = dict(zip("0123456789+-=()niaeoxyklmnprstuvwhjgdbc", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵃᵉᵒˣʸᵏˡᵐⁿᵖʳˢᵗᵘᵛʷʰʲᵍᵈᵇᶜ"))
SUB = dict(zip("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"))
SUP["−"], SUB["−"] = "⁻", "₋"  # the minus sign the converter writes

SYMBOLS = {
    # operators and relations
    "cdot": "·", "times": "×", "div": "÷", "pm": "±", "mp": "∓", "ast": "∗", "circ": "∘",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠", "approx": "≈", "equiv": "≡",
    "sim": "∼", "propto": "∝", "ll": "≪", "gg": "≫", "infty": "∞", "partial": "∂", "nabla": "∇",
    "sum": "Σ", "prod": "Π", "int": "∫", "oint": "∮", "in": "∈", "notin": "∉", "subset": "⊂", "subseteq": "⊆",
    "cup": "∪", "cap": "∩", "emptyset": "∅", "forall": "∀", "exists": "∃", "neg": "¬", "land": "∧", "lor": "∨",
    "to": "→", "rightarrow": "→", "leftarrow": "←", "Rightarrow": "⇒", "Leftarrow": "⇐", "implies": "⇒",
    "leftrightarrow": "↔", "Leftrightarrow": "⇔", "iff": "⇔", "mapsto": "↦", "uparrow": "↑", "downarrow": "↓",
    "cdots": "⋯", "ldots": "…", "dots": "…", "vdots": "⋮", "degree": "°", "prime": "′", "angle": "∠",
    "perp": "⊥", "parallel": "∥", "therefore": "∴", "because": "∵", "euro": "€", "%": "%", "$": "$", "&": "&",
    "#": "#", "_": "_", "{": "{", "}": "}", "lbrace": "{", "rbrace": "}", "langle": "⟨", "rangle": "⟩",
    "lvert": "|", "rvert": "|", "vert": "|", "mid": "|", "|": "‖", "backslash": "\\",
    # spacing
    "quad": " ", "qquad": "  ", ",": " ", ";": " ", ":": " ", "!": "", " ": " ", "enspace": " ", "thinspace": " ",
    # functions: just the name
    "log": "log", "ln": "ln", "lg": "lg", "exp": "exp", "sin": "sin", "cos": "cos", "tan": "tan", "lim": "lim",
    "max": "max", "min": "min", "det": "det", "mod": "mod", "sup": "sup", "inf": "inf", "arg": "arg",
}
GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
    "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ", "phi": "φ", "varphi": "φ", "chi": "χ",
    "psi": "ψ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
TEXTLIKE = ("text", "textrm", "textit", "textbf", "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "operatorname",
            "boldsymbol", "mbox", "emph", "textnormal", "mathcal", "mathbb")
FRACS = ("frac", "dfrac", "tfrac", "cfrac")
DROP = ("left", "right", "big", "Big", "bigg", "Bigg", "displaystyle", "textstyle", "limits", "nolimits")

_ANY_TEX = re.compile(r"\\[A-Za-z]+|\$[^$\n]+\$|\\\(|\\\[|\w\^|\w_\{")
_POWER = re.compile(r"(?<=[\w)\]])(\^(?:\{[^{}\n]{1,20}\}|-?\w)|_\{[^{}\n]{1,20}\})")


def has_tex(s: str) -> bool:
    return bool(_ANY_TEX.search(s or ""))


def _group(s: str, i: int) -> tuple[str, int]:
    """The argument starting at s[i]: {…} (nested) or a single token. → (content, index after it)."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        depth, j = 0, i
        while j < len(s):
            if s[j] == "{" and (j == 0 or s[j - 1] != "\\"):
                depth += 1
            elif s[j] == "}" and s[j - 1] != "\\":
                depth -= 1
                if depth == 0:
                    return s[i + 1:j], j + 1
            j += 1
        return s[i + 1:], len(s)
    if s[i] == "\\":
        m = re.match(r"\\([A-Za-z]+|.)", s[i:])
        return s[i:i + m.end()], i + m.end()
    return s[i], i + 1


def _wrap(x: str) -> str:
    """Parentheses around a fraction part only where they're needed: a / b, (a + b) / c."""
    x = x.strip()
    outside = x
    while re.search(r"\([^()]*\)", outside):  # what's already in parentheses doesn't count
        outside = re.sub(r"\([^()]*\)", "", outside)
    return f"({x})" if re.search(r"[\s+\-−·×=/]", outside) else x


def _script(x: str, table: dict, mark: str) -> str:
    x = x.strip()
    if x and all(c in table for c in x):
        return "".join(table[c] for c in x)
    if mark == "^":
        return "^" + (x if len(x) == 1 else f"({x})")
    return "_" + x  # K_fix: readable, and no mark that Markdown would turn into italics on its own


def convert(tex: str) -> str:
    """One LaTeX formula (without the $) → formula text."""
    out, i, s = [], 0, tex
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[i:])
            name, i = m.group(1), i + m.end()
            if name.isalpha():  # LaTeX ignores spaces after a command word: \Delta K is ΔK
                while i < len(s) and s[i] == " ":
                    i += 1
            if name in FRACS:
                a, i = _group(s, i)
                b, i = _group(s, i)
                out.append(f"{_wrap(convert(a))} / {_wrap(convert(b))}")
            elif name == "sqrt":
                n = ""
                if i < len(s) and s[i] == "[":
                    j = s.find("]", i)
                    n, i = s[i + 1:j], j + 1
                a, i = _group(s, i)
                body = convert(a)
                root = {"3": "∛", "4": "∜"}.get(n.strip(), ("".join(SUP.get(ch, ch) for ch in n) if n else "") + "√")
                out.append(root + (body if len(body) <= 1 or re.fullmatch(r"\w+", body) else f"({body})"))
            elif name in TEXTLIKE:
                a, i = _group(s, i)
                out.append(convert(a))
            elif name in ("overline", "bar"):
                a, i = _group(s, i)
                out.append(convert(a) + "\u0305")
            elif name in ("hat", "widehat"):
                a, i = _group(s, i)
                out.append(convert(a) + "\u0302")
            elif name in ("ddot", "\""):  # K\ddot{a}ufe, M\"{u}ller
                a, i = _group(s, i)
                base = convert(a)
                out.append({"a": "ä", "o": "ö", "u": "ü", "A": "Ä", "O": "Ö", "U": "Ü"}.get(base, base + "\u0308"))
            elif name in ("vec",):
                a, i = _group(s, i)
                out.append(convert(a) + "\u20d7")
            elif name in DROP:
                continue
            elif name in GREEK:
                out.append(GREEK[name])
            elif name in SYMBOLS:
                sym = SYMBOLS[name]
                if name in ("cdot", "times", "div", "pm", "leq", "le", "geq", "ge", "neq", "ne", "approx", "equiv",
                            "to", "rightarrow", "Rightarrow", "leftarrow", "Leftrightarrow", "iff", "implies", "in"):
                    sym = f" {sym} "
                out.append(sym)
            else:
                out.append(name)  # unknown command: its name is more readable than a backslash
        elif c in "^_":
            neg = re.match(r"\s*-\s*(\w+)", s[i + 1:]) if s[i + 1:i + 3].strip().startswith("-") else None
            if neg:  # x^-1
                a, i = "-" + neg.group(1), i + 1 + neg.end()
            else:
                a, i = _group(s, i + 1)
            out.append(_script(convert(a), SUP if c == "^" else SUB, c))
        elif c in "{}":
            i += 1
        elif c == "&":
            out.append(" ")
            i += 1
        elif c == "~":
            out.append(" ")
            i += 1
        elif c == "-" and (not out or not out[-1].endswith("-")):
            out.append("−")
            i += 1
        elif c == "*":
            out.append(" · ")
            i += 1
        else:
            out.append(c)
            i += 1
    text = "".join(out)
    text = text.replace("\\\\", "; ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", text))
    return text.strip()


_DISPLAY = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]", re.S)
_INLINE = re.compile(r"\\\((.+?)\\\)|(?<![\\$\w])\$(?=\S)([^$\n]+?)(?<=\S)\$(?![\w$])")
_BARE = re.compile(r"\\(?:d?t?frac|sqrt|cdot|times|div|pm|leq?|geq?|neq?|approx|infty|sum|prod|int|Delta|alpha|beta|"
                   r"gamma|delta|lambda|mu|pi|sigma|varepsilon|epsilon|rho|theta|phi|omega|Sigma|Pi|text|mathrm|left|"
                   r"right|rightarrow|Rightarrow|to|partial|ln|log)(?![A-Za-z])")


def _looks_like_math(inner: str) -> bool:
    """$5 und $10 is money, not a formula."""
    return bool(re.search(r"[\\^_=+\-*/<>]|[A-Za-z]", inner)) and not re.fullmatch(r"\s*\d+([.,]\d+)?\s*", inner)


def to_text(src: str) -> str:
    """All formulas in a text (Markdown) → formula text. Code blocks stay as they are."""
    if not src or not has_tex(src):
        return src
    parts = re.split(r"(```.*?```|`[^`\n]+`)", src, flags=re.S)
    for k in range(0, len(parts), 2):
        p = parts[k]
        p = _DISPLAY.sub(lambda m: convert(m.group(1) or m.group(2)), p)
        p = _INLINE.sub(lambda m: convert(m.group(1) or m.group(2))
                        if (m.group(1) or _looks_like_math(m.group(2))) else m.group(0), p)
        if _BARE.search(p):  # LaTeX without $ (small models do that): line by line, only the formula part
            p = "\n".join(_bare_line(line) for line in p.split("\n"))
        p = _POWER.sub(lambda m: convert(m.group(1) if "{" in m.group(1) else m.group(1)[0] + "{" + m.group(1)[1:] + "}"), p)  # x^2, y^{10}, z_{1} outside $: x², y¹⁰, z₁
        parts[k] = p
    return "".join(parts)


def _bare_line(line: str) -> str:
    if not _BARE.search(line):
        return line
    # from the first command to the end of the formula-ish stretch – keeps "**Gewinn**: " in front untouched
    m = re.search(r"[A-Za-zÄÖÜäöüß0-9(\[]*\s*=?\s*\\", line)
    start = m.start() if m else line.find("\\")
    head = line[:start]
    lead = re.match(r"^(\s*(?:[-*]\s+|\d+\.\s+)?(?:\*\*[^*]+\*\*\s*:?\s*)?)", head)
    if lead and lead.end() < len(head):
        start = lead.end()
    return line[:start] + convert(line[start:])
