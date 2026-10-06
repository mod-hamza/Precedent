#!/usr/bin/env python3
"""Deterministic assembly: JSON threads -> .eml corpus + manifest.csv + ground_truth.json.
Implements STORY_BIBLE §7.4 (headers, threading, quoted replies, signatures, threading breaks).
"""
import json, os, re, csv, hashlib, random, datetime as dt
from email.utils import format_datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THREADS_DIR = os.path.join(BASE, "corpus", "json", "threads")
FILLER_DIR = os.path.join(BASE, "corpus", "json", "filler")
SCHED = os.path.join(BASE, "corpus", "json", "filler_schedule.json")
EML_DIR = os.path.join(BASE, "corpus", "emails")
PRIV = os.path.join(BASE, "eval_private")
os.makedirs(EML_DIR, exist_ok=True)
os.makedirs(PRIV, exist_ok=True)

rng = random.Random(86014)

PERSONAS = {
    "marta@parcelwise.example": {"name": "Marta Kowalczyk", "sig": "M"},
    "dev@parcelwise.example": {"name": "Dev Raman", "sig": "Cheers, Dev\nDev Raman\nCTO & co-founder, Parcelwise B.V."},
    "helen@parcelwise.example": {"name": "Helen Oyelaran", "sig": "Kind regards,\nHelen Oyelaran\nChief Financial Officer\nParcelwise B.V. | Rotterdam"},
    "tomas@parcelwise.example": {"name": "Tomás Ibarra", "sig": "Saludos!\nTomás Ibarra\nHead of Sales, Parcelwise"},
    "priya@parcelwise.example": {"name": "Priya Natarajan", "sig": "Thanks!\nPriya Natarajan\nHead of Product, Parcelwise B.V."},
    "jonas@parcelwise.example": {"name": "Jonas Eklund", "sig": None},
    "aisha@parcelwise.example": {"name": "Aisha Bello", "sig": "Warmly,\nAisha Bello\nHead of Customer Success\nParcelwise B.V."},
    "greg@ferrante-ops.example": {"name": "Greg Ferrante", "sig": "Greg\nFerrante Ops BV\nsent from my phone, sorry for typos"},
    "lena@parcelwise.example": {"name": "Lena Fischer", "sig": "Danke!\nLena Fischer\nOps & Office Manager\nParcelwise B.V."},
    "samir@parcelwise.example": {"name": "Samir Haddad", "sig": "— Samir"},
    "chloe@parcelwise.example": {"name": "Chloe Winters", "sig": "Excited for what's next! 🚀\nChloe Winters\nMarketing Manager, Parcelwise"},
    "ravi@parcelwise.example": {"name": "Ravi Menon", "sig": "Thanks for your patience,\nRavi Menon\nJunior Engineer, Parcelwise"},
    "ingrid@parcelwise.example": {"name": "Ingrid Solberg", "sig": "Met vriendelijke groet,\nIngrid Solberg\nPeople & Culture, Parcelwise B.V."},
    "elena@parcelwise.example": {"name": "Elena Voss", "sig": "Best regards,\nElena Voss\nSenior Backend Engineer, Parcelwise B.V."},
    "kofi@parcelwise.example": {"name": "Kofi Mensah", "sig": "Regards,\nKofi Mensah\nQA Contractor"},
    "elena.voss@mailbox.example": {"name": "Elena Voss", "sig": "Best regards,\nElena Voss"},
    "bruno@redlinecouriers.example": {"name": "Bruno Alvarez", "sig": "Bruno Alvarez\nCOO, Redline Couriers"},
    "carla@swiftbox.example": {"name": "Carla Dunne", "sig": "Regards,\nCarla Dunne\nHead of Operations, Swiftbox"},
    "walt@harborexpress.example": {"name": "Walt Pruitt", "sig": "Walt Pruitt\nOwner, Harbor Express"},
    "nadia@okafor-lindqvist.example": {"name": "Nadia Petrova", "sig": "Sincerely,\nNadia Petrova\nOkafor Lindqvist Advocaten"},
    "owen@northbridge.example": {"name": "Owen Caldwell", "sig": "Owen"},
    "greg@": {"name": "Greg Ferrante", "sig": "Greg"},
    "kofi@parcelwise.example ": {"name": "Kofi", "sig": None},
    "ines@blackthorn-audit.example": {"name": "Ines Marquez", "sig": "Ines Marquez\nBlackthorn Audit BV"},
    "paula.reyes@logiconnect.example": {"name": "Paula Reyes", "sig": "Paula Reyes\nLogiConnect Europe"},
    "maya@ledgerly.example": {"name": "Maya Chen", "sig": "Maya Chen\nLedgerly"},
    "anders@corvidcloud.example": {"name": "Anders Holm", "sig": "Anders Holm\nCorvid Cloud"},
    "landlord@vdb-vastgoed.example": {"name": "VDB Vastgoed Beheer", "sig": "VDB Vastgoed Beheer"},
}
# generic fallbacks for vendor reps found in filler
def persona_for(addr):
    a = addr.strip().lower()
    if a in PERSONAS: return PERSONAS[a]
    dom = a.split("@")[-1]
    local = a.split("@")[0].replace(".", " ").title()
    if dom in ("nimbushost.example", "payforge.example", "ledgerly.example", "corvidcloud.example",
               "helpdesk-co.example", "beacondesk.example", "logiconnect.example", "blackthorn-audit.example"):
        return {"name": local or dom, "sig": f"{local}\n{dom.rsplit('.',1)[0].title()}"}
    return {"name": local or a, "sig": None}

DATE_FORMATS = [
    lambda d: d.strftime("%d %B %Y"),          # 06 May 2026
    lambda d: d.strftime("%B %d, %Y"),          # May 6, 2026
    lambda d: f"{d.day} {d.strftime('%b')} {d.year}",  # 6 May 2026
    lambda d: d.strftime("%Y-%m-%d"),
    lambda d: d.strftime("%d-%m-%Y"),
    lambda d: d.strftime("%A %d %B"),           # Wednesday 06 May
]

def fmt_hdr_date(iso):
    dtobj = dt.datetime.fromisoformat(iso)
    return format_datetime(dtobj)

def msg_id(tkey, idx):
    # opaque: the thread key (D13 / N04 / F176) must not leak into headers the pipeline reads
    h = hashlib.sha1(f"precedent-corpus-v2|{tkey}|{idx}".encode()).hexdigest()[:20]
    return f"<{h}@parcelwise.example>"

def slugify(s, maxlen=40):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:maxlen].strip("-") or "email"

def quote_outlook(parent):
    d = dt.datetime.fromisoformat(parent["sent_at"])
    return "\n".join(["", "-----Original Message-----",
                      f"From: {persona_for(parent['from'])['name']} <{parent['from']}>",
                      f"Sent: {format_datetime(d)}",
                      f"To: {', '.join(parent.get('to', []))}",
                      f"Subject: {parent['subject']}", "", parent["body"].strip()])

def quote_intro(parent):
    d = dt.datetime.fromisoformat(parent["sent_at"])
    return f"On {rng.choice(DATE_FORMATS)(d)}, {persona_for(parent['from'])['name']} wrote:"

# collect all threads
def load_threads(dirname, suffix=".json", exclude_schedule=False):
    items = []
    for fn in sorted(os.listdir(dirname)):
        if not fn.endswith(suffix) or (exclude_schedule and fn == "filler_schedule.json"):
            continue
        with open(os.path.join(dirname, fn), encoding="utf-8") as f:
            items.append(json.load(f))
    return items

thread_files = load_threads(THREADS_DIR)
filler_chunks = []
for i in range(1, 7):
    p = os.path.join(FILLER_DIR, f"filler_chunk_{i}_out.json")
    with open(p, encoding="utf-8") as f:
        filler_chunks.append(json.load(f))
with open(SCHED, encoding="utf-8") as f:
    sched_rows = {r["id"]: r for r in json.load(f)}

# decision id from thread key: D02_T1 -> D02, N03 -> N03
def dec_ids(tkey):
    m = re.match(r"([DN]\d+)", tkey)
    return [m.group(1)] if m else []

def thread_kind(tkey):
    if re.match(r"D\d", tkey): return "decision"
    if re.match(r"N\d", tkey): return "non_decision"
    return "filler"

threads = []
for t in thread_files:
    threads.append({"key": t["thread_id"], "messages": t["messages"], "kind": thread_kind(t["thread_id"]),
                    "split": "holdout" if t["thread_id"].startswith(("D24","D25","D26","D27","D28","D29","D30","D31","D32","D33","D34","D35","D36","D37","D40","N06","N07","N08","N09","N10")) else "dev",
                    "traps": []})
for chunk in filler_chunks:
    for t in chunk:
        row = sched_rows[t["thread_id"]]
        # volume plan: filler counts emails; keep only the initiating message of each filler thread
        t["messages"] = [m for m in t["messages"] if not m.get("in_reply_to_idx")]
        threads.append({"key": t["thread_id"], "messages": t["messages"], "kind": "filler",
                        "split": row["split"], "traps": [row["trap"]] if row.get("trap") else []})

# order emails globally by sent time
all_msgs = []
for t in threads:
    for m in t["messages"]:
        m["_thread"] = t
        all_msgs.append(m)
all_msgs.sort(key=lambda m: m["sent_at"])

manifest_rows = []
eml_count = 0
seen_subject_counts = {}

for m in all_msgs:
    t = m["_thread"]
    idx = m["idx"]
    mid = msg_id(t["key"], idx)
    frm = m["from"]
    to = ", ".join(m.get("to", []))
    cc = m.get("cc") or []
    subject = m["subject"]
    body = m["body"].strip()
    parent_idx = m.get("in_reply_to_idx")
    breaks_thread = False
    if parent_idx:
        parent = next(x for x in t["messages"] if x["idx"] == parent_idx)
        # 8% of replies break threading
        if rng.random() < 0.08:
            breaks_thread = True
            subject = rng.choice([subject, subject.replace("Re: ", "").strip() + " (fwd)", "Re: " + subject.split("Re: ")[-1]])
        else:
            if rng.random() < 0.5:
                body = body + "\n\n" + quote_intro(parent) + "\n" + \
                       "\n".join("> " + ln for ln in parent["body"].strip().splitlines())
            else:
                body = body + quote_outlook(parent)
    # signature
    p = persona_for(frm)
    if p["sig"] and rng.random() < 0.92:
        body = body + "\n\n-- \n" + p["sig"] if len(p["sig"]) > 40 else body + "\n\n" + p["sig"]
    if frm == "marta@parcelwise.example" and rng.random() < 0.35:
        body = body + "\n\nSent from my iPhone"

    dtobj = dt.datetime.fromisoformat(m["sent_at"])
    tzname = "+0100" if dtobj.utcoffset() == dt.timedelta(hours=1) else "+0200"
    hdr = []
    hdr.append(f"From: {p['name']} <{frm}>")
    hdr.append(f"To: {to}")
    if cc: hdr.append(f"Cc: {', '.join(cc)}")
    hdr.append(f"Subject: {subject}")
    hdr.append(f"Date: {format_datetime(dtobj)}")
    hdr.append(f"Message-ID: {mid}")
    if parent_idx and not breaks_thread:
        pmid = msg_id(t["key"], parent_idx)
        refs = [msg_id(t["key"], i) for i in range(1, parent_idx + 1)]
        hdr.append(f"In-Reply-To: {pmid}")
        hdr.append("References: " + " ".join(refs))
    hdr.append("MIME-Version: 1.0")
    hdr.append('Content-Type: text/plain; charset="UTF-8"')
    hdr.append('Content-Transfer-Encoding: 8bit')
    eml = "\n".join(hdr) + "\n\n" + body + "\n"

    fname = f"{eml_count+1:04d}_{slugify(subject)}.eml"
    with open(os.path.join(EML_DIR, fname), "w", encoding="utf-8", newline="\n") as f:
        f.write(eml)
    eml_count += 1

    manifest_rows.append({
        "message_id": mid, "file": fname, "split": t["split"], "bucket": t["kind"],
        "decision_ids": ";".join(dec_ids(t["key"])),
        "role": m.get("role", "discussion"),
        "traps": ";".join(t["traps"]),
    })

with open(os.path.join(PRIV, "manifest.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["message_id", "file", "split", "bucket", "decision_ids", "role", "traps"])
    w.writeheader(); w.writerows(manifest_rows)

# attach evidence_message_ids to ground truth decisions/non-decisions
gt_path = os.path.join(PRIV, "ground_truth.json")
with open(gt_path, encoding="utf-8") as f:
    gt = json.load(f)
ev = {}
for r in manifest_rows:
    for did in filter(None, r["decision_ids"].split(";")):
        ev.setdefault(did, []).append({"message_id": r["message_id"], "role": r["role"]})
for d in gt.get("decisions", []):
    d["evidence_message_ids"] = ev.get(d["id"], [])
for n in gt.get("non_decisions", []):
    n["evidence_message_ids"] = ev.get(n["id"], [])
with open(gt_path, "w", encoding="utf-8") as f:
    json.dump(gt, f, indent=1, ensure_ascii=False)

print(f"emails: {eml_count}")
from collections import Counter
print(Counter(r["bucket"] for r in manifest_rows))
print(Counter(r["split"] for r in manifest_rows))
