# rebutmap

**Check a response letter against the reviews and the revised paper before you hit submit.**

A revision cycle ends with three documents: the reviewer comments, your response letter, and the
revised paper. Each of them can be wrong in its own way. A comment never gets an answer. A response says
"see Table 5" when the revision only has three tables. The letter quotes a sentence that never made it
into the paper. It says "we revised Section 5" when Section 5 is word-for-word the same as before. A
copy-paste slip tags an answer as R2-W2 when it is really answering R2-W1, so W2 quietly goes unanswered.

`rebutmap` reads all three (plus, optionally, the previous version of the paper) and audits them
together. It is offline, uses only the Python standard library, and runs in milliseconds.

## What's novel

Spell checkers and LaTeX linters look at one file at a time. Diff tools show what changed, but they do not
know what you *claimed* changed. `rebutmap` is built around the claims a response letter makes and checks
each one against the documents it points to.

- **Comment-to-response mapping.** Every reviewer comment is matched to a response in one of three ways:
  an explicit tag (`R1.2`, `R2-W1`, `Reviewer 3, Comment 4`, `Comment 2.3`), overlap with the
  quoted comment text, or position under the same reviewer heading. When a tag disagrees with the quoted
  comment, `rebutmap` trusts the quote and reports the mislabel. That is how a quietly skipped comment
  gets caught.
- **Locator resolution against real LaTeX numbering.** "Section 3.2", "Appendix B", "Fig. 4",
  "Table 5", "Eq. (7)", and `\ref{...}` mentions are resolved against a model of the revised paper. The
  model numbers sections and subsections (letters after `\appendix`), captioned figures and tables
  (including `figure*`, with subfigure captions not double counted), and equations (`align` rows,
  with `\nonumber`/`\notag` respected). It follows `\input`/`\include` and ignores comments.
- **Quote verification.** Any text you quote as "now reads ..." is checked for presence in the revision
  using word 4-gram containment, so LaTeX markup, citations, and line wrapping don't matter. Quotes of the
  reviewer's own words, and old text you say you replaced, are recognised and skipped.
- **Change verification against the previous version.** With `--before`, a response that claims a
  change in Section *N* is checked against the matching section (by title) of the old paper. If its text
  is identical, you get a warning. The same goes for quoted "new" text that was already there.
- **Answer quality.** It flags responses that are only thanks or agreement, change claims with no
  location, promises of camera-ready or future work, cross-references ("see our response to R1.2")
  that point nowhere, and response blocks that quote a comment but never answer it.

## Install

```bash
pip install git+https://github.com/rashedhasan090/rebutmap
# or, from a checkout, with no install at all:
python -m rebutmap --help
```

Python 3.8 or newer. No dependencies.

## Run

```bash
rebutmap reviews.md response.md --paper revised/main.tex --before submitted/main.tex
```

| Option | Meaning |
|---|---|
| `--paper main.tex` | revised paper; enables locator and quote checks |
| `--before old.tex` | previous version; enables "did it actually change" checks |
| `--format text\|markdown\|json` | text (default), a Markdown checklist, or JSON for scripts |
| `--fail-on error\|warning\|info\|never` | exit 1 when a finding is at or above this level (default `error`) |
| `--min-severity` | hide lower-severity findings in the report |
| `--ignore CODE` | drop a finding code (repeatable) |
| `--match-threshold` | quoted-comment overlap needed to match by text (default 0.5) |
| `--min-quote-words` | ignore quoted snippets shorter than this (default 5) |

Reviews and responses can be Markdown, plain text, or LaTeX (`\section*{Reviewer 1}`, `quote`
environments, `\item[R1.2]`, and `\textbf{Response:}` are understood). Exit codes: 0 clean, 1
findings at or above `--fail-on`, 2 usage or file error.

### Input formats it understands

Reviewer headings include `# Reviewer 1`, `**Reviewer #2 (Remarks to the Author):**`, `Referee 3`,
`R4:`, `Meta-review`, `Associate Editor`, `Area Chair`, and the same with "Response to ..." in
front. Comments are taken from explicit tags (`R1.2`, `R1-C2`, `R2Q3`, `[R3.W1]`), labels
(`Comment 3:`, `W1:`, `Q2:`), numbered lists, bullets, or, failing all that, paragraphs. Inside a
response, the answer starts at `Response:` / `Reply:` / `Answer:` / `A:` or after the leading
`>` quote lines. Numbered lists inside an answer don't start a new item.

## Demo

The `examples/` folder has a small review set, a response letter with realistic mistakes, and two
versions of a paper.

```bash
python -m rebutmap examples/reviews.md examples/response.md \
  --paper examples/paper_v2.tex --before examples/paper_v1.tex
```

```text
rebutmap: 7 comments, 6 response blocks, 6 answered, 0 via cross-reference, 1 missing

  ok   R1.1     via quote          section 2
  ok   R1.2     via quote          table 5 [dangling-locator]
  ok   R1.3     via quote          section 5 [already-present, untouched-section]
  ok   R2.W1    via quote          table 3 [mislabeled, phantom-quote]
  MISS R2.W2    via -               [unaddressed]
  ok   R2.Q1    via tag             [hollow]
  ok   AE.1     via position        [deferred]

error   unaddressed       R2.W2    reviews:11  no response found for "The threshold of 0.7 seems arbitrary and is not justified anywhere."
error   dangling-locator  R1.2     response:8  table 5 does not exist (paper has 3 numbered tables)
error   phantom-quote     R2.W1    response:19  quoted text "removing retrieval lowers recall by twelve points on every d..." does not appear in the revised paper
warning already-present   R1.3     response:12  claims a change, but "Our benchmark tasks were sampled from public repositories." was already in the previous version
warning untouched-section R1.3     response:12  claims a change in section 5 ("Threats to Validity"), but its text is identical to the previous version
warning mislabeled        R2.W1    response:19  tagged R2.W2 but the quoted comment matches R2.W1 (100% overlap); counting it for R2.W1
warning hollow            R2.Q1    response:24  only thanks or agreement; no change, location, or argument
info    deferred          AE.1     response:30  promises future or camera-ready work instead of a change in this revision

3 error(s), 4 warning(s), 1 info
```

`--format markdown` turns the same audit into a checklist you can paste into a PR or a shared doc:

```text
| Done | Comment | Matched by | Points to | Issues |
|---|---|---|---|---|
| [x] | R1.1 | quote | section 2 |  |
| [ ] | R1.2 | quote | table 5 | dangling-locator |
| [x] | R1.3 | quote | section 5 | already-present, untouched-section |
| [ ] | R2.W1 | quote | table 3 | mislabeled, phantom-quote |
| [ ] | R2.W2 | none |  | unaddressed |
| [x] | R2.Q1 | tag |  | hollow |
| [x] | AE.1 | position |  | deferred |
```

## Finding codes

| Code | Severity | Meaning |
|---|---|---|
| `unaddressed` | error | a reviewer comment has no response |
| `empty-response` | error | a block quotes a comment but gives no answer |
| `dangling-locator` | error | a section, appendix, figure, table, equation, or `\ref` does not exist in the revision |
| `phantom-quote` | error | quoted "new" text is not in the revised paper |
| `broken-crossref` | error | "see our response to R*x.y*" points to a missing comment or an unanswered one |
| `mislabeled` | warning | the tag and the quoted comment disagree |
| `orphan-response` | warning | a response matches no reviewer comment |
| `untouched-section` | warning | a claimed change is in a section that is identical to the previous version |
| `already-present` | warning | quoted "new" text was already in the previous version |
| `unlocated-change` | warning | a change is claimed with no location or quote |
| `hollow` | warning | thanks or agreement only |
| `deferred` | info | promises future or camera-ready work |

## Use it in CI

If your paper lives in a repo, add a job that runs before each resubmission:

```yaml
- run: pip install git+https://github.com/rashedhasan090/rebutmap
- run: rebutmap reviews.md response.md --paper main.tex --before submitted/main.tex --fail-on error
```

## Limitations

- Numbering follows standard `article`-style counters. Per-section figure numbering (`3.1`),
  `subequations`, and custom counters aren't modelled, so appendix-style numbers like `A.1` are only
  checked for an `\appendix`.
- Line and page numbers are recognised as locations but not checked, since they depend on the PDF.
- Only the first number in a range ("Tables 2-3") is checked.
- Matching is heuristic. Use explicit tags (`R1.2`) in your letter if you want it exact.

## Tests

```bash
python -m unittest discover -s tests -v
```

## License

MIT
