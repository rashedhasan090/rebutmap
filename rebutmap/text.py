"""Text normalisation and n-gram containment helpers (stdlib only)."""

import re

_DROP_ARG = re.compile(
    r"\\(?:cite[a-zA-Z]*|ref|cref|Cref|autoref|eqref|pageref|nameref|label|url|href|"
    r"footnote|includegraphics)\*?(?:\[[^\]]*\])*\{[^}]*\}"
)
_CMD = re.compile(r"\\[a-zA-Z@]+\*?")
_WORD = re.compile(r"[a-z0-9]+")


def strip_tex_comments(text):
    """Remove unescaped % comments from LaTeX source, line by line."""
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def words(text):
    """Lower-cased word tokens with LaTeX commands, citations and refs removed."""
    t = _DROP_ARG.sub(" ", text)
    t = _CMD.sub(" ", t)
    t = t.lower().replace("\u2019", "'")
    return _WORD.findall(t)


def shingles(ws, n):
    if not ws:
        return set()
    if len(ws) < n:
        return {tuple(ws)}
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


class Corpus:
    """A bag of word n-grams that answers 'is this passage in here?'."""

    def __init__(self, text_or_words):
        if isinstance(text_or_words, str):
            self.words = words(text_or_words)
        else:
            self.words = list(text_or_words)
        self.joined = " " + " ".join(self.words) + " "
        self._cache = {}

    def _sh(self, n):
        if n not in self._cache:
            self._cache[n] = shingles(self.words, n)
        return self._cache[n]

    def coverage(self, qwords, n=4):
        """Fraction of the query's word n-grams that occur in this corpus."""
        if not qwords:
            return 0.0
        if len(qwords) < n:
            return 1.0 if (" " + " ".join(qwords) + " ") in self.joined else 0.0
        qs = shingles(qwords, n)
        return len(qs & self._sh(n)) / len(qs)
