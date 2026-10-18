"""Command-line entry point."""

import argparse
import sys

from . import __version__
from .checks import RANK, SEVERITY, analyze
from .latex import Paper
from .report import render_json, render_markdown, render_text
from .structure import tex_letter_to_text


def _read_letter(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if path.lower().endswith(".tex") or "\\begin{document}" in text:
        text = tex_letter_to_text(text)
    return text


def build_parser():
    p = argparse.ArgumentParser(
        prog="rebutmap",
        description="Map every reviewer comment to its response, and check that what the "
                    "response letter claims about the revision is actually true.")
    p.add_argument("reviews", help="reviewer comments (.md, .txt, or .tex)")
    p.add_argument("response", help="response / rebuttal letter (.md, .txt, or .tex)")
    p.add_argument("--paper", help="revised paper (.tex main file; \\input/\\include are followed)")
    p.add_argument("--before", help="previous version of the paper, enables change verification")
    p.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    p.add_argument("--min-severity", choices=("info", "warning", "error"), default="info",
                   help="hide findings below this severity in the report")
    p.add_argument("--fail-on", choices=("info", "warning", "error", "never"), default="error",
                   help="exit 1 when any finding is at or above this severity (default: error)")
    p.add_argument("--ignore", action="append", default=[], metavar="CODE",
                   help="drop a finding code entirely (repeatable), e.g. --ignore deferred")
    p.add_argument("--match-threshold", type=float, default=0.5,
                   help="minimum quoted-comment overlap to match a response by text (default 0.5)")
    p.add_argument("--min-quote-words", type=int, default=5,
                   help="ignore quoted snippets shorter than this many words (default 5)")
    p.add_argument("--version", action="version", version=f"rebutmap {__version__}")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    bad = [c for c in args.ignore if c not in SEVERITY]
    if bad:
        print(f"rebutmap: unknown finding code(s): {', '.join(bad)}", file=sys.stderr)
        return 2
    try:
        reviews = _read_letter(args.reviews)
        response = _read_letter(args.response)
        paper = Paper.from_file(args.paper) if args.paper else None
        before = Paper.from_file(args.before) if args.before else None
    except OSError as e:
        print(f"rebutmap: {e}", file=sys.stderr)
        return 2
    result = analyze(reviews, response, paper=paper, before=before,
                     match_threshold=args.match_threshold, min_quote_words=args.min_quote_words)
    result["findings"] = [f for f in result["findings"] if f.code not in args.ignore]
    render = {"text": render_text, "markdown": render_markdown, "json": render_json}[args.format]
    print(render(result, args.min_severity))
    if args.fail_on != "never" and any(RANK[f.severity] >= RANK[args.fail_on] for f in result["findings"]):
        return 1
    return 0
