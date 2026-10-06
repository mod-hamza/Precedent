"""Markdown scorecard for the submission (PRD §11 output)."""
from __future__ import annotations


def _pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def markdown(payload: dict) -> str:
    t = payload["targets"]
    g = payload["global"]
    lines = [f"# Precedent scorecard", "", f"_{payload['banner']}_  commit `{payload['git_commit']}`", "",
             "| Metric | Target | " + " | ".join(f"{s.title()} (`{r.get('git_commit', '?')}`)"
                                                  for s, r in payload["splits"].items()) + " |",
             "|---|---|" + "---|" * len(payload["splits"])]

    def row(name, target, fn):
        lines.append(f"| {name} | {target} | " + " | ".join(fn(r) for r in payload["splits"].values()) + " |")

    row("Decision recall", f">= {_pct(t['decision_recall'])}", lambda r: f"{_pct(r['decision_recall'])} ({r['n_gt']} GT)")
    row("Decision precision", f">= {_pct(t['decision_precision'])}", lambda r: f"{_pct(r['decision_precision'])} ({r['n_pred']} predicted)")
    row("Unmatched predictions judged genuine decisions (not in the 40 planted)", "context",
        lambda r: f"{r.get('unmatched_genuine', '-')} of {len(r['unmatched_predictions'])}")
    row("Near-decision false positives", f"<= {t['near_decision_fp_max']} of 10", lambda r: f"{r['near_decision_fp']} of {r['near_decision_n']}")
    row("Supersession-link accuracy", f">= {_pct(t['supersession_accuracy'])}", lambda r: f"{_pct(r['supersession_accuracy'])} (kind {_pct(r['supersession_kind_accuracy'])})")
    row("Status accuracy (matched)", "-", lambda r: _pct(r["status_accuracy"]))
    row("Conflicts detected", f">= {t['conflicts_min']} of 3", lambda r: f"{r['conflicts_detected']} of {len(r['conflicts'])}")
    row("Evidence support", f">= {_pct(t['evidence_support'])}", lambda r: f"{_pct(r['evidence_support'])} (strict {_pct(r['evidence_support_strict'])})")
    row("Q&A accuracy", f">= {_pct(t['qa_accuracy'])}", lambda r: f"{_pct(r.get('qa_accuracy'))} of {r.get('qa_n', 0)}" if "qa" in r else "not run")
    row("'No decision' correct", "5/5", lambda r: f"{r.get('no_decision_correct', '-')}/{r.get('no_decision_n', '-')}" if "qa" in r else "not run")
    row("Answer latency p50", "< 8 s", lambda r: f"{r['latency_p50_ms'] / 1000:.1f} s" if r.get("latency_p50_ms") else "not run")
    row("Triage recall", ">= 98%", lambda r: _pct(r["triage_recall"]))
    lines += ["", f"Quote validity (all verified quotes are verbatim substrings): **{_pct(g['quote_validity'])}** "
                  f"of {g['quotes_checked']} quotes. Pipeline wall-clock (Stages 1-5): **{g['pipeline_minutes']} min**.", ""]
    for name, r in payload["splits"].items():
        lines += [f"## {name.title()}: decisions", "", "| GT | Result | Status (GT -> predicted) | Predicted |", "|---|---|---|---|"]
        for d in r["decisions_table"]:
            lines.append(f"| {d['gt_id']} | {d['result']} | {d['gt_status']} -> {d['pred_status'] or '-'} | "
                         f"{(d['pred_text'] or '')[:90]} |")
        lines.append("")
    return "\n".join(lines)
