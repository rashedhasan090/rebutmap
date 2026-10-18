"""Match responses to comments and audit what each response claims about the revision."""

import re
from dataclasses import dataclass, field

from .structure import EXPLICIT_CORE, explicit_key, parse, resp_mark
from .text import Corpus, words

SEVERITY = {
    "unaddressed": "error",
    "empty-response": "error",
    "dangling-locator": "error",
    "phantom-quote": "error",
    "broken-crossref": "error",
    "mislabeled": "warning",
    "orphan-response": "warning",
    "untouched-section": "warning",
    "already-present": "warning",
    "unlocated-change": "warning",
    "hollow": "warning",
    "deferred": "info",
}
RANK = {"info": 0, "warning": 1, "error": 2}

_A = r"[A-H](?:\.\d+)*"
LOCATORS = [
    ("appendix", re.compile(r"(?i:\bappendix|\bappendices)\s*~?\s*(?P<v>" + _A + r")\b")),
    ("section", re.compile(r"(?:(?i:\b(?:sections?|secs?\.|subsections?))|\u00a7\u00a7?)\s*~?\s*(?P<v>\d+(?:\.\d+)*|" + _A + r")\b")),
    ("figure", re.compile(r"(?i:\b(?:figures?|figs?\.))\s*~?\s*(?P<v>\d+|[A-H]\.?\d+)\b")),
    ("table", re.compile(r"(?i:\b(?:tables?|tabs?\.))\s*~?\s*(?P<v>\d+|[A-H]\.?\d+)\b")),
    ("equation", re.compile(r"(?i:\b(?:equations?|eqs?\.))\s*~?\s*\(?(?P<v>\d+)\)?")),
    ("line", re.compile(r"(?i:\blines?|\bll?\.)\s*(?P<v>\d+)")),
    ("page", re.compile(r"(?i:\bpages?|\bpp?\.)\s*(?P<v>\d+)")),
    ("ref", re.compile(r"\\(?:ref|cref|Cref|autoref|eqref|nameref)\{(?P<v>[^}]+)\}")),
]
_VERBS = (r"added|revised|rewr(?:ote|itten)|clarified|expanded|extended|included|updated|moved|removed|"
          r"deleted|fixed|corrected|reorgani[sz]ed|rephrased|incorporated|introduced|modified|changed|"
          r"replaced|reworded|restructured|softened|toned\s+down")
CHANGE = re.compile(
    r"(?i)\b(?:(?:we|i)\s+(?:have\s+|now\s+|also\s+|further\s+|additionally\s+)*(?:" + _VERBS + r"|"
    r"now\s+(?:report|include|discuss|provide|describe|show|cite|explain)\w*)"
    r"|(?:has|have)\s+(?:now\s+)?been\s+(?:" + _VERBS + r")"
    r"|(?:is|are)\s+now\s+(?:included|discussed|reported|provided|described|shown|explained)"
    r"|now\s+reads|reads\s+as\s+follows)\b"
)
DEFER = re.compile(
    r"(?i)\b(?:we\s+will|we\s+plan\s+to|will\s+be\s+(?:added|addressed|included|discussed|fixed|clarified)"
    r"|(?:final|camera[- ]ready)\s+version|future\s+work|beyond\s+the\s+scope|out\s+of\s+(?:the\s+)?scope"
    r"|left\s+for\s+future)\b"
)
THANKS = re.compile(r"(?i)\b(?:thank|thanks|grateful|appreciate|gratitude)\b")
OLD_CTX = re.compile(
    r"(?i)\b(?:replaced|removed|deleted|instead\s+of|changed\s+from|previously|originally|old|"
    r"former(?:ly)?|original\s+(?:text|sentence|version|wording))\b"
)
CROSSREF = re.compile(
    r"(?i:\b(?:see|refer\s+to|as\s+(?:explained|discussed|described)\s+in)\s+(?:our\s+|the\s+)?"
    r"(?:(?:responses?|replies|reply|answers?)\s+to\s+(?:comment\s+)?)?)" + EXPLICIT_CORE, re.I
)
QUOTE_RE = re.compile(r'"([^"\n]+)"|\u201c([^\u201d]+)\u201d|``(.+?)\'\'|\u00ab([^\u00bb]+)\u00bb')


@dataclass
class Finding:
    code: str
    target: str
    line: int
    message: str
    source: str = "response"

    @property
    def severity(self):
        return SEVERITY[self.code]

    def as_dict(self):
        return {"code": self.code, "severity": self.severity, "target": self.target,
                "source": self.source, "line": self.line, "message": self.message}


@dataclass
class Response:
    item: object
    target: object = None
    how: str = ""
    quote: str = ""
    prose: str = ""
    locators: list = field(default_factory=list)
    quotes: list = field(default_factory=list)
    crossrefs: list = field(default_factory=list)
    change: bool = False


def split_block(lines):
    """Separate the quoted reviewer comment from the authors' answer."""
    idx = next((i for i, l in enumerate(lines) if resp_mark(l) is not None), None)
    if idx is not None:
        quote = [l.lstrip(">").strip() for l in lines[:idx]]
        resp = [resp_mark(lines[idx])] + lines[idx + 1:]
        return " ".join(q for q in quote if q), resp
    quote, i = [], 0
    while i < len(lines):
        l = lines[i].strip()
        if l.startswith(">"):
            quote.append(l.lstrip(">").strip())
        elif l:
            break
        i += 1
    return " ".join(quote), lines[i:]


def _extract_quotes(resp_lines, min_words):
    """Return (prose, [(quote_text, context_before)]) from the response part."""
    prose_lines, quotes, block, prev = [], [], [], ""
    for l in resp_lines + [""]:
        s = l.strip()
        if s.startswith(">"):
            block.append(s.lstrip(">").strip())
            continue
        if block:
            quotes.append((" ".join(block), prev[-80:]))
            block = []
        if s:
            prose_lines.append(s)
            prev = s
    prose = " ".join(prose_lines)
    last = 0
    for m in QUOTE_RE.finditer(prose):
        q = next(g for g in m.groups() if g is not None)
        quotes.append((q, prose[last:m.start()][-80:]))
        last = m.end()
    quotes = [(q, ctx) for q, ctx in quotes if len(words(q)) >= min_words]
    return prose, quotes


def analyze(reviews_text, response_text, paper=None, before=None, match_threshold=0.5,
            min_quote_words=5, hollow_words=8, quote_threshold=0.8):
    comments = parse(reviews_text, "review", default_reviewer="R1")
    blocks = parse(response_text, "response", default_reviewer=None)
    by_key = {}
    for c in comments:
        by_key.setdefault(c.key, c)
    comment_corpora = {c.id: Corpus(c.text) for c in comments}
    findings, responses = [], []

    for b in blocks:
        r = Response(item=b)
        r.quote, resp_lines = split_block(b.lines)
        r.prose, r.quotes = _extract_quotes(resp_lines, min_quote_words)
        explicit = by_key.get(b.key) if b.tagged else None
        fuzzy, score = None, 0.0
        qw = words(r.quote)
        if len(qw) >= 4:
            for c in comments:
                s = comment_corpora[c.id].coverage(qw, 3)
                if s > score:
                    fuzzy, score = c, s
            if score < match_threshold:
                fuzzy = None
        positional = by_key.get(b.key) if b.reviewer else None
        if b.tagged and fuzzy is not None and explicit is not fuzzy:
            findings.append(Finding("mislabeled", fuzzy.id, b.line,
                                    f"tagged {b.id} but the quoted comment matches {fuzzy.id} "
                                    f"({score:.0%} overlap); counting it for {fuzzy.id}"))
            r.target, r.how = fuzzy, "quote"
        elif explicit is not None:
            r.target, r.how = explicit, "tag"
        elif fuzzy is not None:
            r.target, r.how = fuzzy, "quote"
        elif positional is not None:
            r.target, r.how = positional, "position"
        else:
            findings.append(Finding("orphan-response", b.id, b.line,
                                    f"response {b.id} does not correspond to any reviewer comment"))
        for kind, rx in LOCATORS:
            for m in rx.finditer(r.prose):
                r.locators.append((kind, m.group("v")))
        r.crossrefs = [explicit_key(m) for m in CROSSREF.finditer(r.prose)]
        r.change = bool(CHANGE.search(r.prose))
        responses.append(r)

    answered = {}
    for r in responses:
        if r.target is not None:
            answered.setdefault(r.target.id, []).append(r)

    for r in responses:
        b, tid = r.item, (r.target.id if r.target is not None else r.item.id)
        prose_words = words(r.prose)
        if not prose_words and not r.quotes:
            findings.append(Finding("empty-response", tid, b.line,
                                    "block quotes the comment but contains no answer"))
            continue
        for key in r.crossrefs:
            tgt = by_key.get(key)
            if tgt is None:
                findings.append(Finding("broken-crossref", tid, b.line,
                                        f"points to {key[0]}.{key[1]}, which is not a reviewer comment"))
            elif not answered.get(tgt.id):
                findings.append(Finding("broken-crossref", tid, b.line,
                                        f"points to the response for {tgt.id}, but {tgt.id} has no response"))
        if paper is not None:
            for kind, v in r.locators:
                why = paper.check_locator(kind, v)
                if why:
                    findings.append(Finding("dangling-locator", tid, b.line, why))
        for q, ctx in r.quotes:
            qw = words(q)
            if r.target is not None and comment_corpora[r.target.id].coverage(qw) >= quote_threshold:
                continue
            if OLD_CTX.search(ctx):
                continue
            if paper is None:
                continue
            short = (q[:60] + "...") if len(q) > 60 else q
            if paper.corpus.coverage(qw) < quote_threshold:
                if before is not None and before.corpus.coverage(qw) >= quote_threshold:
                    msg = f'quoted text "{short}" is only in the previous version, not the revision'
                else:
                    msg = f'quoted text "{short}" does not appear in the revised paper'
                findings.append(Finding("phantom-quote", tid, b.line, msg))
            elif r.change and before is not None and before.corpus.coverage(qw) >= quote_threshold:
                findings.append(Finding("already-present", tid, b.line,
                                        f'claims a change, but "{short}" was already in the previous version'))
        if r.change and paper is not None and before is not None:
            for kind, v in r.locators:
                if kind not in ("section", "appendix"):
                    continue
                u = paper.unit_by_number(v)
                old = before.unit_by_title(u.title_key) if u else None
                if u and old and u.words == old.words:
                    findings.append(Finding("untouched-section", tid, b.line,
                                            f'claims a change in {kind} {v} ("{u.title.strip()}"), '
                                            f"but its text is identical to the previous version"))
        if r.change and not r.locators and not r.quotes:
            findings.append(Finding("unlocated-change", tid, b.line,
                                    "claims a change but gives no section, figure, table, line, or quoted text"))
        if not r.change and not r.locators and not r.quotes and not r.crossrefs:
            sentences = re.split(r"(?<=[.!?])\s+", r.prose)
            substance = words(" ".join(s for s in sentences if not THANKS.search(s)))
            if len(substance) < hollow_words:
                findings.append(Finding("hollow", tid, b.line,
                                        "only thanks or agreement; no change, location, or argument"))
        if DEFER.search(r.prose):
            findings.append(Finding("deferred", tid, b.line,
                                    "promises future or camera-ready work instead of a change in this revision"))

    status = {}
    for c in comments:
        rs = answered.get(c.id, [])
        if rs:
            status[c.id] = "answered"
            continue
        refs = [r for r in responses if any(by_key.get(k) is c for k in r.crossrefs)]
        if refs:
            status[c.id] = "crossref"
            continue
        status[c.id] = "missing"
        snippet = c.text[:70] + ("..." if len(c.text) > 70 else "")
        findings.append(Finding("unaddressed", c.id, c.line, f'no response found for "{snippet}"', "reviews"))

    findings.sort(key=lambda f: (-RANK[f.severity], f.source != "reviews", f.line, f.code))
    return {"comments": comments, "responses": responses, "status": status, "findings": findings}
