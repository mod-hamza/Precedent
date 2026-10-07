#!/usr/bin/env python3
"""Build the single-file submission: SUBMISSION.md + screenshots -> submission/Precedent.html

python tools/build_submission.py

- Screenshots: every PNG/JPG in demo/screenshots/, in filename order (01_..., 02_..., ...), embedded as base64.
  Captions come from demo/screenshots/captions.json ({"01_ingest.png": "..."}) or, failing that, DEFAULT_CAPTIONS by
  number, or the filename.
- Video: if demo/video/*.mp4 exists and is <= 25 MB it is embedded; otherwise the URL in demo/video_url.txt is linked.
- The pipeline diagram is inline SVG. No external requests: the file opens offline.
- Prints every [TEAM] placeholder still left in the text.
"""
from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "SUBMISSION.md"
SHOTS = ROOT / "demo" / "screenshots"
VIDEO_DIR = ROOT / "demo" / "video"
VIDEO_URL = ROOT / "demo" / "video_url.txt"
OUT = ROOT / "submission" / "Precedent.html"
MAX_VIDEO = 25 * 1024 * 1024

DEFAULT_CAPTIONS = {  # PRD §12 storyline
    1: "Ingest: a mailbox goes in; the pipeline runs and the funnel fills (emails -> candidate threads -> decisions).",
    2: "Timeline: one swimlane per topic; arrows show supersedes / amends / refines.",
    3: "Decision drawer: the payment-provider decision with its history chain and quoted evidence from several emails.",
    4: "Ask: \"Why did we switch payment providers?\" A cited answer; every quote is verified against the email.",
    5: "Ask: \"Did we decide to open a Lisbon office?\" No decision found, with the closest discussions.",
    6: "Conflicts: the first-response SLA, two versions side by side. Precedent does not pick a side.",
    7: "Authority flag: the 15% renewal offer sent without sign-off, flagged neutrally.",
    8: "Scorecard: dev and holdout results against the targets, with the synthetic-data banner.",
}

PIPELINE_SVG = """<svg class="pipeline" viewBox="0 0 960 270" role="img" aria-label="Precedent pipeline">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="#6b5f50"/></marker></defs>
<g font-family="Inter, Segoe UI, sans-serif" font-size="12">
{boxes}
</g></svg>"""

STAGES = [  # (title, subtitle, kind) ; kind: code | model
    ("0 Parse & thread", "MIME, quotes, forwards, identities", "code"),
    ("1 Triage", "qwen3.8-flash", "model"),
    ("2 Extract", "qwen3.8-max", "model"),
    ("Quote verifier", "code: verbatim or dropped", "code"),
    ("3 Cluster", "deepseek-v4-pro", "model"),
    ("4 Reconcile", "deepseek-v4-pro: edges, conflicts", "model"),
    ("5 Index", "FTS5 + MiniLM", "code"),
    ("6 Ask", "qwen3.8-max + citation check", "model"),
]


def pipeline_svg() -> str:
    parts = []
    w, h, gap = 205, 64, 30
    pos = []
    for i, _ in enumerate(STAGES):
        row, col = divmod(i, 4)
        x = 20 + col * (w + gap) if row == 0 else 20 + (3 - col) * (w + gap)  # snake layout
        y = 30 + row * 130
        pos.append((x, y))
    for i, ((title, sub, kind), (x, y)) in enumerate(zip(STAGES, pos)):
        fill, stroke = ("#fbf6ec", "#b08a4e") if kind == "model" else ("#f1f3ef", "#7d8a74")
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        parts.append(f'<text x="{x + w / 2}" y="{y + 26}" text-anchor="middle" font-weight="600" fill="#2b2620">{html.escape(title)}</text>')
        parts.append(f'<text x="{x + w / 2}" y="{y + 46}" text-anchor="middle" fill="#6b5f50">{html.escape(sub)}</text>')
        if i + 1 < len(STAGES):
            nx, ny = pos[i + 1]
            if ny == y:
                x1, x2 = (x + w, nx) if nx > x else (x, nx + w)
                parts.append(f'<line x1="{x1 + 3}" y1="{y + h / 2}" x2="{x2 - 3}" y2="{y + h / 2}" stroke="#6b5f50" '
                             f'stroke-width="1.5" marker-end="url(#ar)"/>')
            else:
                parts.append(f'<line x1="{x + w / 2}" y1="{y + h + 3}" x2="{nx + w / 2}" y2="{ny - 3}" stroke="#6b5f50" '
                             f'stroke-width="1.5" marker-end="url(#ar)"/>')
    parts.append('<rect x="20" y="246" width="14" height="10" rx="2" fill="#fbf6ec" stroke="#b08a4e"/>'
                 '<text x="40" y="255" fill="#6b5f50">model call (JSON schema, validated, cached)</text>'
                 '<rect x="330" y="246" width="14" height="10" rx="2" fill="#f1f3ef" stroke="#7d8a74"/>'
                 '<text x="350" y="255" fill="#6b5f50">deterministic code</text>')
    return PIPELINE_SVG.format(boxes="\n".join(parts))


def _data_uri(p: Path) -> str:
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
            ".mp4": "video/mp4"}[p.suffix.lower()]
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def screenshots_html() -> str:
    files = sorted(p for p in SHOTS.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")) \
        if SHOTS.exists() else []
    if not files:
        return '<p class="todo">[TEAM] Screenshots go in demo/screenshots/ (01_ingest.png ... 08_scorecard.png).</p>'
    captions = {}
    cap_file = SHOTS / "captions.json"
    if cap_file.exists():
        captions = json.loads(cap_file.read_text(encoding="utf-8"))
    figs = []
    for i, p in enumerate(files, start=1):
        m = re.match(r"(\d+)", p.name)
        num = int(m.group(1)) if m else i
        cap = captions.get(p.name) or DEFAULT_CAPTIONS.get(num) or p.stem.replace("_", " ")
        figs.append(f'<figure><img src="{_data_uri(p)}" alt="{html.escape(cap)}" loading="lazy">'
                    f'<figcaption><span class="step">{num:02d}</span> {html.escape(cap)}</figcaption></figure>')
    return '<div class="shots">' + "\n".join(figs) + "</div>"


def video_html() -> str:
    vids = sorted(VIDEO_DIR.glob("*.mp4")) if VIDEO_DIR.exists() else []
    if vids and vids[0].stat().st_size <= MAX_VIDEO:
        return (f'<figure class="video"><video controls preload="metadata" src="{_data_uri(vids[0])}"></video>'
                f'<figcaption>Recording of the complete core flow, from input to result.</figcaption></figure>')
    if VIDEO_URL.exists() and VIDEO_URL.read_text(encoding="utf-8").strip():
        url = html.escape(VIDEO_URL.read_text(encoding="utf-8").strip())
        return (f'<p class="videolink"><a href="{url}">Watch the recording of the complete core flow</a> '
                f'(input to visible result).</p>')
    return '<p class="todo">[TEAM] Video: put a small mp4 in demo/video/ (embedded) or a link in demo/video_url.txt.</p>'


CSS = """
:root { --bg:#f7f3ec; --paper:#fffdf8; --ink:#2b2620; --muted:#6b5f50; --line:#e4dccd; --accent:#8a5a1f;
  --ok:#2f6b3f; --warn:#9a6a12; --bad:#a3352b; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.6 Inter, "Segoe UI", system-ui, sans-serif; }
main { max-width: 980px; margin: 0 auto; padding: 48px 20px 80px; background: var(--paper);
  box-shadow: 0 0 0 1px var(--line); }
h1 { font: 600 44px/1.1 Georgia, "Times New Roman", serif; margin: 0 0 8px; letter-spacing: -0.5px; }
h2 { font: 600 26px/1.25 Georgia, "Times New Roman", serif; margin: 48px 0 12px; padding-top: 16px;
  border-top: 1px solid var(--line); }
h3 { font-size: 18px; margin: 28px 0 8px; }
p, li { max-width: 78ch; }
a { color: var(--accent); }
code { background: #f1ebe0; padding: 1px 5px; border-radius: 4px; font-size: 0.92em; }
pre { background: #f1ebe0; padding: 14px; border-radius: 8px; overflow-x: auto; }
blockquote { margin: 16px 0; padding: 8px 16px; border-left: 3px solid var(--accent); background: #faf4e8; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14.5px; display: block; overflow-x: auto; }
th, td { border-bottom: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #f4eee3; font-weight: 600; }
.lede { font: 20px/1.5 Georgia, serif; border-left: 4px solid var(--accent); padding: 4px 0 4px 18px; }
.pipeline { width: 100%; height: auto; margin: 8px 0 16px; }
.shots { display: grid; grid-template-columns: 1fr; gap: 28px; margin: 20px 0; }
figure { margin: 0; }
figure img, figure video { width: 100%; border: 1px solid var(--line); border-radius: 10px; display: block; }
figcaption { color: var(--muted); font-size: 14.5px; margin-top: 8px; }
.step { display: inline-block; background: var(--ink); color: var(--paper); border-radius: 4px; padding: 0 6px;
  font-weight: 600; font-size: 12px; margin-right: 6px; }
.todo { background: #fdeceb; color: var(--bad); padding: 8px 12px; border-radius: 6px; font-weight: 600; }
.videolink { font-size: 18px; }
@media (max-width: 640px) { h1 { font-size: 32px; } main { padding: 28px 16px 60px; } }
"""


def build() -> Path:
    md = SRC.read_text(encoding="utf-8")
    md = md.replace(" -> ", " → ").replace("| >= ", "| ≥ ").replace("| <= ", "| ≤ ")
    md = re.sub(r"^> Sections marked \*\*\[TEAM\]\*\*.*\n", "", md, flags=re.M)  # drafting note
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
    body = body.replace("<!-- PIPELINE_DIAGRAM -->", pipeline_svg())
    body = body.replace("<!-- SCREENSHOTS -->", screenshots_html())
    body = body.replace("<!-- VIDEO -->", video_html())
    # the opening "We help ..." sentence is the required lede
    body = re.sub(r"<p>(We help .*?)</p>", r'<p class="lede">\1</p>', body, count=1, flags=re.S)
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>Precedent</title><style>{CSS}</style></head><body><main>{body}</main></body></html>")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    todos = sorted(set(re.findall(r"\[TEAM[^\]]*\]", page)))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    for t in todos:
        print("  still to fill:", t)
    return OUT


if __name__ == "__main__":
    build()
