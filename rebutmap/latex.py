"""A small LaTeX model: sectional numbering, float/equation counters, labels, section text."""

import os
import re
from dataclasses import dataclass

from .text import Corpus, strip_tex_comments, words

_INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
_FLOATS = ("figure", "table")
_EQ_ENVS = ("equation", "align", "gather", "eqnarray", "multline", "flalign", "alignat")
_LEVELS = {"section": 1, "subsection": 2, "subsubsection": 3}
_TOK = re.compile(
    r"\\(?P<sec>section|subsection|subsubsection)(?P<star>\*?)\s*(?:\[[^\]]*\])?\s*\{"
    r"|\\(?P<app>appendix)\b"
    r"|\\begin\{(?P<benv>[a-zA-Z]+)(?P<bstar>\*?)\}"
    r"|\\end\{(?P<eenv>[a-zA-Z]+)(?P<estar>\*?)\}"
    r"|\\label\{(?P<label>[^}]*)\}"
    r"|\\(?P<cap>caption)\b"
)


def flatten(path, root=None, _depth=0, _seen=None):
    """Read a .tex file, inlining \\input/\\include relative to the main file's folder."""
    _seen = set() if _seen is None else _seen
    root = root or os.path.dirname(os.path.abspath(path))
    real = os.path.realpath(path)
    if _depth > 20 or real in _seen:
        return ""
    _seen.add(real)
    with open(path, encoding="utf-8", errors="replace") as f:
        text = strip_tex_comments(f.read())
    here = os.path.dirname(os.path.abspath(path))

    def repl(m):
        name = m.group(1).strip()
        for base in (root, here):
            cand = os.path.join(base, name)
            for p in (cand, cand + ".tex"):
                if os.path.isfile(p):
                    return flatten(p, root, _depth + 1, _seen)
        return " "

    return _INPUT.sub(repl, text)


def _braced(text, i):
    depth, j = 1, i
    while j < len(text) and depth:
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        j += 1
    return text[i:j - 1], j


@dataclass
class Unit:
    number: object  # "3.2", "A", or None for starred headings
    level: int
    title: str
    start: int
    end: int = 0
    words: tuple = ()

    @property
    def title_key(self):
        return " ".join(words(self.title))


class Paper:
    def __init__(self, text, path=None):
        self.path = path
        text = strip_tex_comments(text)
        m = re.search(r"\\begin\{document\}(.*?)(?:\\end\{document\}|$)", text, re.S)
        if m:
            text = m.group(1)
        self.text = text
        self.units, self.labels = [], {}
        self.figures = self.tables = self.equations = 0
        self.appendix = False
        self._scan()
        self.corpus = Corpus(text)
        self.section_numbers = {u.number for u in self.units if u.number}

    @classmethod
    def from_file(cls, path):
        if path.lower().endswith(".tex"):
            return cls(flatten(path), path)
        with open(path, encoding="utf-8", errors="replace") as f:
            return cls(f.read(), path)

    def _scan(self):
        text = self.text
        counters, in_app, stack, cur = [0, 0, 0], False, [], "0"
        for m in _TOK.finditer(text):
            if m.group("sec"):
                title, _ = _braced(text, m.end())
                level = _LEVELS[m.group("sec")]
                if m.group("star"):
                    self.units.append(Unit(None, level, title, m.start()))
                    continue
                counters[level - 1] += 1
                for k in range(level, 3):
                    counters[k] = 0
                top = chr(64 + counters[0]) if in_app and counters[0] else str(counters[0])
                number = ".".join([top] + [str(c) for c in counters[1:level]])
                self.units.append(Unit(number, level, title, m.start()))
                cur = number
            elif m.group("app"):
                in_app, self.appendix, counters = True, True, [0, 0, 0]
            elif m.group("benv"):
                env = m.group("benv")
                if env in _FLOATS or env in _EQ_ENVS:
                    stack.append({"env": env, "star": bool(m.group("bstar")), "start": m.end(),
                                  "labels": [], "number": None})
            elif m.group("eenv"):
                env = m.group("eenv")
                if stack and stack[-1]["env"] == env:
                    fr = stack.pop()
                    if env in _EQ_ENVS:
                        self._number_equations(text, fr, m.start(), cur)
                    else:
                        for name, _ in fr["labels"]:
                            self.labels[name] = (env, fr["number"]) if fr["number"] else ("section", cur)
            elif m.group("label") is not None:
                if stack:
                    stack[-1]["labels"].append((m.group("label"), m.start()))
                else:
                    self.labels[m.group("label")] = ("section", cur)
            elif m.group("cap"):
                fr = next((f for f in reversed(stack) if f["env"] in _FLOATS), None)
                if fr and fr["number"] is None:
                    if fr["env"] == "figure":
                        self.figures += 1
                        fr["number"] = str(self.figures)
                    else:
                        self.tables += 1
                        fr["number"] = str(self.tables)
        for i, u in enumerate(self.units):
            u.end = next((v.start for v in self.units[i + 1:] if v.level <= u.level), len(text))
            u.words = tuple(words(text[u.start:u.end]))

    def _number_equations(self, text, fr, end, cur):
        if fr["star"]:
            for name, _ in fr["labels"]:
                self.labels[name] = ("section", cur)
            return
        content = text[fr["start"]:end]
        if fr["env"] in ("equation", "multline"):
            rows = [content]
        else:
            rows = re.split(r"\\\\", content)
            if len(rows) > 1 and not rows[-1].strip():
                rows.pop()
        spans, pos = [], fr["start"]
        for row in rows:
            num = None
            if not re.search(r"\\(?:nonumber|notag)\b", row):
                self.equations += 1
                num = str(self.equations)
            spans.append((pos, pos + len(row), num))
            pos += len(row) + 2
        for name, p in fr["labels"]:
            num = next((n for a, b, n in spans if a <= p <= b), None)
            self.labels[name] = ("equation", num or str(self.equations))

    def unit_by_number(self, number):
        return next((u for u in self.units if u.number == number), None)

    def unit_by_title(self, key):
        return next((u for u in self.units if u.title_key == key), None)

    def check_locator(self, kind, value):
        """Return None if the locator resolves in this paper, else a short reason."""
        if kind in ("line", "page"):
            return None
        if kind in ("section", "appendix"):
            if value in self.section_numbers:
                return None
            return f"{kind} {value} does not exist (paper has {self._section_summary()})"
        if kind in ("figure", "table", "equation"):
            count = {"figure": self.figures, "table": self.tables, "equation": self.equations}[kind]
            if value.isdigit():
                if 1 <= int(value) <= count:
                    return None
                return f"{kind} {value} does not exist (paper has {count} numbered {kind}s)"
            return None if self.appendix else f"{kind} {value} looks like an appendix number but the paper has no \\appendix"
        if kind == "ref":
            missing = [v.strip() for v in value.split(",") if v.strip() not in self.labels]
            return None if not missing else "no \\label for " + ", ".join(missing)
        return None

    def _section_summary(self):
        tops = [u.number for u in self.units if u.number and u.level == 1]
        return "sections " + ", ".join(tops) if tops else "no numbered sections"
