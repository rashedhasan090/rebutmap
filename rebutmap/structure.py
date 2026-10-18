"""Parse review files and response letters into reviewer-scoped items."""

import re
from dataclasses import dataclass, field

from .text import strip_tex_comments

_KC = r"[CP]|comment\s*#?\s*|point\s*#?\s*"
_KQ = r"[QW]|question\s*#?\s*|weakness\s*#?\s*"
EXPLICIT_CORE = (
    r"(?:Reviewer\s*#?\s*|Referee\s*#?\s*|Rev\.?\s*|R)(?P<rev>\d+)"
    r"(?:\s*[.\-:]\s*(?P<k1>" + _KC + "|" + _KQ + r")?|\s*,?\s*(?P<k2>" + _KC + "|" + _KQ + r"))"
    r"(?P<num>\d+)"
)
EXPLICIT = re.compile(r"\b" + EXPLICIT_CORE + r"\b", re.I)
_EXPLICIT_ITEM = re.compile(
    r"^\[?" + EXPLICIT_CORE + r"\]?(?:\s*[:.)\-\u2013]\s*|\s+|$)(?P<rest>.*)$", re.I
)
_ITEM_LABEL = re.compile(
    r"^(?P<lab>comment|point|issue|question|concern|weakness|[cwq])\s*#?\s*"
    r"(?P<num>\d+(?:\.\d+)?)(?:\s*[:.)\-\u2013]\s*|\s+|$)(?P<rest>.*)$",
    re.I,
)
_ITEM_NUM = re.compile(r"^\(?(?P<num>\d{1,2})[.)]\s+(?P<rest>.*)$")
_ITEM_BULLET = re.compile(r"^[-*\u2022+]\s+(?P<rest>.*)$")

_HEAD_PREFIX = (
    r"^(?:(?:our\s+|authors?['\u2019]?\s+)?(?:responses?|replies|reply|answers?|rebuttal)\s+to\s+(?:the\s+)?"
    r"|comments?\s+(?:from|by|of)\s+(?:the\s+)?)?"
)
_HEAD_REV = re.compile(_HEAD_PREFIX + r"(?:reviewer|referee|review)\s*#?\s*(\d+)\b", re.I)
_HEAD_BARE = re.compile(r"^r\s*#?\s*(\d+)\s*:?\s*$", re.I)
_HEAD_META = re.compile(
    _HEAD_PREFIX + r"(?:associate\s+editor|meta[- ]?review(?:er)?|senior\s+area\s+chair|area\s+chair|editor)\b",
    re.I,
)
_HEAD_META_BARE = re.compile(r"^(?:ae|ac|sac|meta)\s*:?\s*$", re.I)

RESP_MARK = re.compile(
    r"^(?:our\s+|authors?['\u2019]?\s+)?(?:response|reply|answer|rebuttal)\b\s*(?:to\s+[^:]{0,30})?"
    r"\s*[:.\-\u2013]\s*(?P<rest>.*)$|^a\s*:\s*(?P<rest2>.*)$",
    re.I,
)


@dataclass
class Item:
    reviewer: object  # "R1", "AE", or None when unknown
    number: str
    line: int
    tagged: bool = False  # header carried an explicit reviewer+comment tag
    lines: list = field(default_factory=list)
    in_response: bool = False
    uid: str = ""

    @property
    def key(self):
        return (self.reviewer, self.number)

    @property
    def id(self):
        return self.uid or f"{self.reviewer or '?'}.{self.number}"

    @property
    def text(self):
        return " ".join(l.lstrip(">").strip() for l in self.lines if l.strip())


def explicit_key(m):
    rev = f"R{int(m.group('rev'))}"
    kind = (m.group("k1") or m.group("k2") or "").strip().lower()
    prefix = "Q" if kind.startswith("q") else "W" if kind.startswith("w") else ""
    return rev, prefix + str(int(m.group("num")))


def clean_line(s):
    s = s.strip()
    s = re.sub(r"^#+\s*", "", s)
    s = re.sub(r"\*\*|__", "", s)
    return s.strip()


def resp_mark(line):
    m = RESP_MARK.match(clean_line(line.lstrip(">").strip()))
    if not m:
        return None
    return m.group("rest") if m.group("rest") is not None else (m.group("rest2") or "")


def heading_reviewer(raw):
    stripped = raw.strip()
    c = clean_line(stripped)
    if not c or len(c) > 80 or stripped.startswith(">"):
        return None
    if _EXPLICIT_ITEM.match(c):
        return None
    markup = stripped.startswith("#") or stripped.startswith("**") or stripped.startswith("__")
    m = _HEAD_REV.match(c) or _HEAD_BARE.match(c)
    rid = None
    if m:
        rid = f"R{int(m.group(1))}"
    elif _HEAD_META_BARE.match(c) or (_HEAD_META.match(c) and len(c) <= 60):
        m = _HEAD_META.match(c) or _HEAD_META_BARE.match(c)
        rid = "AE"
    if rid is None:
        return None
    rest = c[m.end():].strip(" :-\u2013\u2014.()#")
    if markup or c.endswith(":") or (len(rest.split()) <= 3 and not (rest and c.endswith("."))):
        return rid
    return None


def _classify(raw):
    s = raw.strip()
    quoted = s.startswith(">")
    body = s.lstrip(">").strip()
    c = clean_line(body)
    m = _EXPLICIT_ITEM.match(c)
    if m:
        return "strong", explicit_key(m), m.group("rest"), quoted
    m = _ITEM_LABEL.match(c)
    if m:
        lab = m.group("lab").lower()
        num = m.group("num")
        prefix = "Q" if lab.startswith("q") else "W" if lab.startswith("w") else ""
        if "." in num:
            a, b = num.split(".", 1)
            return "strong", (f"R{int(a)}", prefix + str(int(b))), m.group("rest"), quoted
        return "strong", (None, prefix + str(int(num))), m.group("rest"), quoted
    m = _ITEM_NUM.match(c)
    if m:
        return "num", (None, str(int(m.group("num")))), m.group("rest"), quoted
    m = _ITEM_BULLET.match(body)
    if m:
        return "bullet", None, m.group("rest"), quoted
    return None


def _split_items(rid, body, mode):
    cls = [(_classify(raw), ln, raw) for ln, raw in body]
    kinds = {c[0] for c, _, _ in cls if c}
    level = next((k for k in ("strong", "num", "bullet") if k in kinds), None)
    if level is None:
        return _paragraph_items(rid, body, mode)
    items, cur, seq = [], None, 0
    for c, ln, raw in cls:
        starts = c is not None and c[0] == level
        if (starts and mode == "response" and cur is not None and cur.in_response
                and level != "strong" and not c[3]):
            starts = False
        if starts:
            seq += 1
            if level == "bullet":
                rev, num = None, str(seq)
            else:
                rev, num = c[1]
            cur = Item(reviewer=rev or rid, number=num, line=ln,
                       tagged=level == "strong" and rev is not None,
                       lines=[(">" if c[3] else "") + c[2]])
            items.append(cur)
            if resp_mark(c[2]) is not None:
                cur.in_response = True
        elif cur is not None:
            cur.lines.append(raw.strip())
            if resp_mark(raw) is not None:
                cur.in_response = True
    return items


def _paragraph_items(rid, body, mode):
    paras, cur, start = [], [], None
    for ln, raw in body:
        if raw.strip():
            if not cur:
                start = ln
            cur.append(raw.strip())
        elif cur:
            paras.append((start, cur))
            cur = []
    if cur:
        paras.append((start, cur))
    if mode == "response":
        quoted_starts = any(p[1][0].startswith(">") for p in paras)
        merged = []
        for start, lines in paras:
            new = lines[0].startswith(">") if quoted_starts else resp_mark(lines[0]) is None
            if merged and not new:
                merged[-1][1].extend(lines)
            else:
                merged.append((start, list(lines)))
        paras = merged
    items = []
    for start, lines in paras:
        if mode == "review" and len(" ".join(lines).split()) < 4:
            continue
        items.append(Item(reviewer=rid, number=str(len(items) + 1), line=start, lines=lines))
    return items


def tex_letter_to_text(text):
    """Turn a LaTeX response/review letter into the Markdown-ish shape the parser reads."""
    t = strip_tex_comments(text)
    m = re.search(r"\\begin\{document\}(.*?)(?:\\end\{document\}|$)", t, re.S)
    if m:
        t = m.group(1)
    t = re.sub(r"\\begin\{(quote|quotation|reviewer|comment|point)\}(.*?)\\end\{\1\}",
               lambda mm: "\n" + "\n".join("> " + l.strip() for l in mm.group(2).strip().splitlines()) + "\n",
               t, flags=re.S)
    t = re.sub(r"\\(?:section|chapter)\*?\{([^}]*)\}", r"\n# \1\n", t)
    t = re.sub(r"\\(?:subsection|subsubsection|paragraph)\*?\{([^}]*)\}", r"\n## \1\n", t)
    t = re.sub(r"\\textbf\{([^}]*)\}", r"**\1**", t)
    t = re.sub(r"\\(?:emph|textit|textsc|underline)\{([^}]*)\}", r"\1", t)
    t = re.sub(r"\\item\s*(?:\[([^\]]*)\])?",
               lambda mm: "\n" + (mm.group(1) + " " if mm.group(1) else "- "), t)
    t = re.sub(r"\\(?:begin|end)\{[a-zA-Z*]+\}", "\n", t)
    t = t.replace("\\\\", "\n")
    return t


def parse(text, mode="review", default_reviewer=None):
    """Split a review file (mode='review') or response letter (mode='response') into Items."""
    sections, current, pre = [], None, []
    for i, raw in enumerate(text.splitlines(), 1):
        rid = heading_reviewer(raw)
        if rid:
            current = [rid, []]
            sections.append(current)
            continue
        if current is None:
            pre.append((i, raw))
        else:
            current[1].append((i, raw))
    if not sections:
        sections = [[default_reviewer, pre]]
    items = []
    for rid, body in sections:
        items.extend(_split_items(rid, body, mode))
    seen = {}
    for it in items:
        base = f"{it.reviewer or '?'}.{it.number}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        it.uid = base if n == 0 else f"{base}#{n + 1}"
    return items
