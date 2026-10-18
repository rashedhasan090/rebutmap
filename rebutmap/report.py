"""Render analysis results as text, Markdown, or JSON."""

import json

from .checks import RANK


def _summary(result):
    sev = {"error": 0, "warning": 0, "info": 0}
    for f in result["findings"]:
        sev[f.severity] += 1
    st = list(result["status"].values())
    return {"comments": len(result["comments"]), "responses": len(result["responses"]),
            "answered": st.count("answered"), "crossref": st.count("crossref"),
            "missing": st.count("missing"), **sev}


def _per_comment(result):
    rows = []
    for c in result["comments"]:
        rs = [r for r in result["responses"] if r.target is c]
        locs = sorted({f"{k} {v}" for r in rs for k, v in r.locators})
        codes = sorted({f.code for f in result["findings"] if f.target == c.id})
        rows.append((c, result["status"][c.id], rs, locs, codes))
    return rows


def render_text(result, min_severity="info"):
    s = _summary(result)
    out = [f"rebutmap: {s['comments']} comments, {s['responses']} response blocks, "
           f"{s['answered']} answered, {s['crossref']} via cross-reference, {s['missing']} missing",
           ""]
    for c, st, rs, locs, codes in _per_comment(result):
        mark = {"answered": "ok  ", "crossref": "see ", "missing": "MISS"}[st]
        how = ",".join(sorted({r.how for r in rs})) or "-"
        extra = (" [" + ", ".join(codes) + "]") if codes else ""
        out.append(f"  {mark} {c.id:<8} via {how:<14} {'; '.join(locs) or ''}{extra}".rstrip())
    shown = [f for f in result["findings"] if RANK[f.severity] >= RANK[min_severity]]
    out.append("")
    if not shown:
        out.append("no findings")
    for f in shown:
        out.append(f"{f.severity:<7} {f.code:<17} {f.target:<8} {f.source}:{f.line}  {f.message}")
    out.append("")
    out.append(f"{s['error']} error(s), {s['warning']} warning(s), {s['info']} info")
    return "\n".join(out)


def render_markdown(result, min_severity="info"):
    s = _summary(result)
    out = ["# Response-letter audit", "",
           f"{s['comments']} reviewer comments, {s['answered']} answered, "
           f"{s['crossref']} answered by cross-reference, {s['missing']} missing.", "",
           "| Done | Comment | Matched by | Points to | Issues |", "|---|---|---|---|---|"]
    for c, st, rs, locs, codes in _per_comment(result):
        bad = st == "missing" or any(f.severity == "error" for f in result["findings"] if f.target == c.id)
        box = "[ ]" if bad else "[x]"
        how = ", ".join(sorted({r.how for r in rs})) or "none"
        out.append(f"| {box} | {c.id} | {how} | {', '.join(locs) or ''} | {', '.join(codes) or ''} |")
    out += ["", "## Findings", ""]
    shown = [f for f in result["findings"] if RANK[f.severity] >= RANK[min_severity]]
    if not shown:
        out.append("None.")
    for f in shown:
        out.append(f"- **{f.severity}** `{f.code}` {f.target} ({f.source} line {f.line}): {f.message}")
    return "\n".join(out) + "\n"


def render_json(result, min_severity="info"):
    data = {
        "summary": _summary(result),
        "comments": [{"id": c.id, "reviewer": c.reviewer, "number": c.number, "line": c.line,
                      "status": result["status"][c.id], "text": c.text} for c in result["comments"]],
        "responses": [{"id": r.item.id, "line": r.item.line,
                       "target": r.target.id if r.target is not None else None, "matched_by": r.how,
                       "locators": [{"kind": k, "value": v} for k, v in r.locators],
                       "quotes": [q for q, _ in r.quotes], "claims_change": r.change}
                      for r in result["responses"]],
        "findings": [f.as_dict() for f in result["findings"]
                     if RANK[f.severity] >= RANK[min_severity]],
    }
    return json.dumps(data, indent=2)
