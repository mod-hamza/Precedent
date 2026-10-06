#!/usr/bin/env python3
"""Deterministic filler schedule generator for the Parcelwise corpus.
Outputs: corpus/json/filler_schedule.json (list of rows) + per-chunk row files.
"""
import json, random, datetime as dt, os

random.seed(20260105)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "corpus", "json")
os.makedirs(OUT, exist_ok=True)

START = dt.date(2026, 1, 5)
END = dt.date(2026, 6, 30)
# Dutch holidays / closure days in window (avoid for business emails)
HOLIDAYS = {dt.date(2026, 4, 3), dt.date(2026, 4, 6), dt.date(2026, 4, 27),
            dt.date(2026, 5, 14), dt.date(2026, 5, 25)}

CATEGORIES = [
    ("scheduling", 60),
    ("invoices_finance_admin", 45),
    ("support_escalations", 50),
    ("sales_pipeline", 45),
    ("vendor_newsletters_spam", 35),
    ("out_of_office", 20),
    ("internal_banter", 30),
    ("hr_admin", 15),
    ("eng_status_incident_noise", 10),
]

INTERNAL = ["marta@parcelwise.example", "dev@parcelwise.example", "helen@parcelwise.example",
            "tomas@parcelwise.example", "priya@parcelwise.example", "jonas@parcelwise.example",
            "aisha@parcelwise.example", "lena@parcelwise.example", "samir@parcelwise.example",
            "chloe@parcelwise.example", "ravi@parcelwise.example", "ingrid@parcelwise.example"]

# business days list, weighted: Mon-Thu weight 1.2, Fri 0.6
days = []
d = START
while d <= END:
    if d.weekday() < 5 and d not in HOLIDAYS:
        days.append(d)
    d += dt.timedelta(days=1)

weights = [1.2 if x.weekday() < 4 else 0.6 for x in days]

TRIVIAL_TRAPS = [
    "trivial logistics decision: order lunch for the Thursday demo (wrap platter vs pizza) — sender settles it themselves",
    "trivial logistics decision: move Monday stand-up 15 minutes later; sender just informs the team",
    "trivial logistics decision: book the small meeting room for the Swiftbox call; no significance beyond the booking",
    "trivial logistics decision: choose the day for the office plant watering rota",
    "trivial logistics decision: pick which coffee machine vendor sample to keep",
    "trivial logistics decision: set the default time for the monthly all-hands to 16:00",
    "trivial logistics decision: choose the courier pickup time for a laptop repair (10:30 vs 14:00)",
    "trivial logistics decision: decide the office snack order for launch week",
    "trivial logistics decision: move the retro to Thursday because Wednesday is meeting-free",
    "trivial logistics decision: choose between two printer maintenance slots",
    "trivial logistics decision: pick the date of the team lunch for Elena's first week",
    "trivial logistics decision: settle who takes the demo iPad to the client meeting",
    "trivial logistics decision: choose the standing desk colour for the new hire",
    "trivial logistics decision: decide the parking spot swap between two staff",
    "trivial logistics decision: pick the wallpaper/design of the launch countdown channel",
]

SOFT_TRAPS = [
    "Include decision-sounding phrases like 'let's do it' or 👍 but ensure no actual commitment or authority is expressed; the topic stays open",
    "Include hypothetical language ('what if we...', 'we could...') without any commitment",
    "Include a question that sounds like a decision ('so we're going with X?') that receives no answer",
    "Include a retraction ('scratch that', 'ignore my last email') about something trivial",
    "Include a forward ('FYI see below') of a trivial earlier note",
    "Include an enthusiastic agreement to something the sender has no authority over, but nothing happens",
]

TOPIC_SEEDS = {
    "scheduling": [
        "find a slot for the v3 QA dry run", "reschedule the Redline check-in", "book the leadership weekly",
        "calendar conflict between Priya and Jonas", "set up the Kofi onboarding sessions", "Doodle-style poll for the all-hands",
        "book time with Bruno at Redline", "move the retro because of the rollout freeze", "schedule Elena's first-week 1:1s",
        "find a slot for the Blackthorn kickoff", "schedule the Beacon Desk demo", "book the Corvid Cloud technical review",
        "set the Swiftbox quarterly review call", "organize the June team planning", "schedule Harbor Express collections call",
        "book onboarding for a new customer", "move the 1:1 because of school pickup", "schedule the vendor demo for scanners",
        "find time for the pricing page review", "book the pentest debrief slot",
    ],
    "invoices_finance_admin": [
        "NimbusHost invoice query", "PayForge monthly statement reconciliation", "expense report question from Jonas",
        "VAT quarter preparation", "customer invoice for Swiftbox February usage", "Redline monthly invoice clarification",
        "petty cash for the office", "subscription renewal for design tooling", "Harbor Express dunning step reminder",
        "bank feed matching issue", "mileage claim from Samir", "conference expense from Paula Reyes' booking",
        "invoice number sequence question", "credit note for a double-charged customer", "Q2 prepaid revenue schedule check",
        "small usage overage dispute", "insurance renewal paperwork", "accountant request for migration cost breakdown",
        "invoice for scanner hardware resale", "approve a €400 software renewal",
    ],
    "support_escalations": [
        "customer reports slow route recalculation", "driver app crash on Android 14", "scanner pairing failing at Swiftbox",
        "duplicate tracking webhooks for a customer", "invoice PDF rendering wrong currency symbol", "customer asks about ETA accuracy",
        "export stuck for a large customer", "driver app offline sync complaint", "webhook retry storm from a small courier",
        "login loop after password reset", "map tile slowness complaints", "customer wants data deletion (small request)",
        "driver can't scan in rain mode", "report export CSV encoding complaints", "API rate limit hit by an integration",
        "billing portal session timeouts", "Push notification delays for Android", "customer confused by new plan page",
        "Harbor Express asks for an extension on usage report", "two customers report the same webhook gap",
    ],
    "sales_pipeline": [
        "new inbound lead from a Ghent courier", "demo request from a Rotterdam bike-courier startup", "churn risk signal on a mid account",
        "expansion chatter at Swiftbox (more seats)", "lead from the LogiConnect booth list", "competitor RouteBee spotted at a prospect",
        "pipeline hygiene nudge from Tomás", "pricing question from a prospect on the old plans", "Samir's weekly pipeline notes",
        "customer referral intro", "prospect asks about the driver app timeline", "renewal heads-up for a July customer",
        "prospect wants EU data residency confirmation", "trial account going quiet", "credit check question on a big prospect",
        "discount request within Tomás's 5% authority", "prospects asks for a security questionnaire (pre-Swiftbox style)", "win-back email to a churned account",
        "lead from a logistics LinkedIn post", "prospect asks about Scan Pack",
    ],
    "vendor_newsletters_spam": [
        "NimbusHost maintenance window notice", "PayForge product update newsletter", "Ledgerly onboarding drip email",
        "Corvid Cloud webinar invite", "LogiConnect speaker announcement", "generic SaaS cold pitch (recruiting tool)",
        "generic SaaS cold pitch (analytics)", "Helpdesk Co. release notes", "Beacon Desk trial nudge",
        "domain renewal notice from registrar", "Chamber of Commerce (KvK) newsletter", "office coffee supplier promo",
        "dev tools newsletter Jonas actually reads", "marketing webinar invite from a competitor of Chloe's tool", "spam: SEO audit offer",
        "NimbusHost upsell email", "bank newsletter about interest rates", "hardware vendor end-of-life notice for scanners",
        "newsletter: EU e-invoicing regulation explainer", "cold email: office plants subscription",
    ],
    "out_of_office": [
        "Ingrid OOO (works Mon-Wed)", "Helen OOO for a family matter", "Dev OOO after the migration weekend",
        "Lena OOO public holiday bridging", "Samir OOO at a customer visit", "Priya OOO after rollout night",
        "Greg auto-reply (contractor, slow replies)", "Marta OOO for a board trip to London", "Aisha OOO training day",
        "Jonas OOO (hiking, no phone)", "Chloe OOO at a conference", "Ravi OOO dentist",
        "Tomás OOO on holiday in Spain", "Elena OOO settling in logistics", "Kofi OOO (other client)",
        "generic internal 'I'm out this afternoon' note", "OOO with a wrong escalation contact, corrected in a follow-up", "OOO reply to an external customer",
        "short OOO from Owen Caldwell (investor, London)", "half-day OOO from Helen before a bank visit",
    ],
    "internal_banter": [
        "coffee machine debate", "launch countdown memes channel", "Jonas complains about meeting invites (again)",
        "photo of the office plant revived", "King's Day celebration plans", "Friday afternoon quiz teams",
        "someone's loud keyboard", "fantasy football league in the office", "Bike to work challenge",
        "Elena's desk setup welcome", "birthday cake logistics", "running club at lunch",
        "meme about p95 latency", "Tomás's 🚀 overuse teased gently", "new snack opinions",
        "Stroopwafel brand debate", "someone's terrible parking", "weather grumbling before the migration weekend",
        "RRR (random retro question) thread", "Dutch winter cycling tips for Elena",
    ],
    "hr_admin": [
        "holiday balance question", "update emergency contact details", "book a performance review cycle reminder",
        "onboarding checklist for Elena (paperwork)", "contract for Kofi's days logistics (admin side only)", "expired First Aid certificate",
        "office key handover for the sublet tenant (admin note)", "payslip question from Ravi", "remote work allowance form",
        "travel insurance for the London board trip", "wish to use study leave", "verification of employment letter request",
        "birthday/anniversary list for the intranet", "laptop ergonomics assessment request", "note about the appraisal template update",
    ],
    "eng_status_incident_noise": [
        "Friday deploy notes", "routine failover drill results", "noisy alert suppressed (disk on staging)",
        "flaky test quarantined", "weekend monitoring summary: all quiet", "backfill job finished late",
        "dashboard widget cache cleared", "minor DNS TTL change note", "log retention tweak", "dependency bump (patch versions)",
    ],
}

SENDERS = {
    "scheduling": INTERNAL + ["bruno@redlinecouriers.example", "carla@swiftbox.example"],
    "invoices_finance_admin": ["helen@parcelwise.example", "lena@parcelwise.example", "jonas@parcelwise.example",
                               "samir@parcelwise.example", "ravi@parcelwise.example", "tomas@parcelwise.example",
                               "aisha@parcelwise.example", "marta@parcelwise.example", "kofi@parcelwise.example",
                               "ingrid@parcelwise.example", "priya@parcelwise.example", "dev@parcelwise.example",
                               "elena@parcelwise.example"],
    "support_escalations": ["aisha@parcelwise.example", "bruno@redlinecouriers.example", "carla@swiftbox.example",
                            "walt@harborexpress.example", "ravi@parcelwise.example", "jonas@parcelwise.example",
                            "samir@parcelwise.example", "tomas@parcelwise.example", "kofi@parcelwise.example",
                            "support@parcelwise.example"],
    "sales_pipeline": ["tomas@parcelwise.example", "samir@parcelwise.example", "aisha@parcelwise.example",
                       "chloe@parcelwise.example", "marta@parcelwise.example", "helen@parcelwise.example"],
    "vendor_newsletters_spam": ["noreply@nimbushost.example", "news@payforge.example", "hello@ledgerly.example",
                                "events@corvidcloud.example", "info@logiconnect.example", "sales@coldtool.example",
                                "updates@helpdesk-co.example", "team@beacondesk.example", "billing@registrar.example",
                                "newsletter@kvk.example", "promo@koffie.example", "digest@devtools-weekly.example",
                                "info@seoboost.example", "noreply@bank.example", "products@scanhardware.example"],
    "out_of_office": INTERNAL + ["greg@ferrante-ops.example", "owen@northbridge.example"],
    "internal_banter": INTERNAL,
    "hr_admin": ["ingrid@parcelwise.example", "lena@parcelwise.example", "helen@parcelwise.example",
                 "ravi@parcelwise.example", "elena@parcelwise.example", "kofi@parcelwise.example",
                 "samir@parcelwise.example", "aisha@parcelwise.example"],
    "eng_status_incident_noise": ["jonas@parcelwise.example", "dev@parcelwise.example", "ravi@parcelwise.example",
                                  "greg@ferrante-ops.example", "elena@parcelwise.example", "kofi@parcelwise.example"],
}

rows = []
idx = 1
for cat, count in CATEGORIES:
    for _ in range(count):
        day = random.choices(days, weights=weights, k=1)[0]
        hour = random.randint(8, 19)
        minute = random.choice([0, 5, 9, 12, 17, 23, 31, 38, 42, 47, 53, 58])
        sender = random.choice(SENDERS[cat])
        # pick a plausible recipient
        if sender in INTERNAL:
            pool = [x for x in INTERNAL if x != sender]
            to = random.sample(pool, k=random.choices([1, 2, 3], weights=[6, 2.5, 1])[0])
        elif sender == "greg@ferrante-ops.example":
            to = [random.choice(["dev@parcelwise.example", "jonas@parcelwise.example", "helen@parcelwise.example"])]
        elif sender == "owen@northbridge.example":
            to = ["marta@parcelwise.example"]
        elif "@parcelwise.example" in sender:
            pool = [x for x in INTERNAL if x != sender]
            to = [random.choice(pool)]
        else:
            to = random.sample([x for x in INTERNAL if x not in ("marta@parcelwise.example",)], k=1)
        seed = random.choice(TOPIC_SEEDS[cat])
        # trap assignment
        trap = None
        if cat in ("internal_banter", "scheduling", "hr_admin") and random.random() < 0.5:
            trap = random.choice(TRIVIAL_TRAPS)
        elif random.random() < 0.45:
            trap = random.choice(SOFT_TRAPS)
        rows.append({
            "id": f"F{idx:03d}", "category": cat,
            "date": day.isoformat(), "time": f"{hour:02d}:{minute:02d}",
            "from": sender, "to": to, "topic_seed": seed,
            "trap": trap, "count": random.choices([1, 2, 3], weights=[4, 3, 1])[0],
        })
        idx += 1

random.shuffle(rows)
# split dev/holdout ~60/40, but keep trivial-logistics mostly dev
for i, r in enumerate(rows):
    if r["trap"] and r["trap"].startswith("trivial"):
        r["split"] = "dev"
    else:
        r["split"] = "dev" if random.random() < 0.6 else "holdout"

with open(os.path.join(OUT, "filler_schedule.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=1, ensure_ascii=False)

# chunk into 6 files of ~52 rows
chunks = [rows[i::6] for i in range(6)]
for ci, ch in enumerate(chunks):
    with open(os.path.join(OUT, f"filler_chunk_{ci+1}.json"), "w", encoding="utf-8") as f:
        json.dump(ch, f, indent=1, ensure_ascii=False)

from collections import Counter
print("total", len(rows))
print(Counter(r["category"] for r in rows))
print("dev", sum(1 for r in rows if r["split"] == "dev"), "holdout", sum(1 for r in rows if r["split"] == "holdout"))
print("chunks", [len(c) for c in chunks])
