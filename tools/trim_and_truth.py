#!/usr/bin/env python3
"""Trim thread JSONs to the §6 volume plan (decision 210, non-decision 40, filler 310 msgs)
and write eval_private/ground_truth.json (D01-D40 + non_decisions + Q&A)."""
import json, os, re, shutil, copy

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD = os.path.join(BASE, "corpus", "json", "threads")
FD = os.path.join(BASE, "corpus", "json", "filler")
PRIV = os.path.join(BASE, "eval_private")

def load(d, pred=lambda f: f.endswith(".json")):
    out = {}
    for fn in sorted(os.listdir(d)):
        if pred(fn):
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                out[fn] = json.load(f)
    return out

threads = load(TD)

# ---- trim decisions to 210 total ----
KEEP_ROLES = {"decisive", "recap", "confirmation", "reversal"}
def decision_key(fn):
    return re.match(r"(D\d+)", fn).group(1)

groups = {}
for fn, t in threads.items():
    if fn.startswith("D"):
        groups.setdefault(decision_key(fn), []).append(fn)

def count(group_fns): return sum(len(threads[f]["messages"]) for f in group_fns)

# removable candidates ranked: chatter first, then discussion, never idx 1, never keep-roles
def candidates(fn):
    t = threads[fn]
    msgs = t["messages"]
    min_keep = max(3, min(len(msgs), 3))
    cands = []
    for rank, role in enumerate(["chatter", "discussion", "proposal", "objection"]):
        for m in msgs:
            if m["idx"] == 1 or m.get("role") in KEEP_ROLES:
                continue
            if m.get("role") == role:
                cands.append((rank, m["idx"]))
    # dedupe keeping lowest rank
    seen, out = set(), []
    for r, i in sorted(cands):
        if i not in seen:
            seen.add(i); out.append(i)
    return out

total = sum(count(g) for g in groups.values())
TARGET_D = 210
remove_needed = total - TARGET_D
removed = 0
# remove from groups with the most excess over their minimum-size floor first
while removed < remove_needed:
    # group floors: keep >= 3 per file, and at least ceil(min_count*0.8)
    best = None
    for k, fns in groups.items():
        for fn in fns:
            msgs = threads[fn]["messages"]
            if len(msgs) <= 3:
                continue
            cands = candidates(fn)
            if not cands:
                continue
            # prefer removing from longer threads
            score = (len(msgs), -cands[0])
            if best is None or score > best[0]:
                best = (score, fn, cands)
    if best is None:
        break
    _, fn, cands = best
    drop_idx = cands[0]
    t = threads[fn]
    dropped = next(m for m in t["messages"] if m["idx"] == drop_idx)
    parent_of_dropped = dropped.get("in_reply_to_idx")
    t["messages"] = [m for m in t["messages"] if m["idx"] != drop_idx]
    for m in t["messages"]:
        if m.get("in_reply_to_idx") == drop_idx:
            m["in_reply_to_idx"] = parent_of_dropped
    removed += 1

# ---- trim non-decisions to 40 ----
n_total = sum(len(t["messages"]) for fn, t in threads.items() if fn.startswith("N"))
need_n = n_total - 40
nfiles = sorted(fn for fn in threads if fn.startswith("N"))
while need_n > 0:
    # remove chatter/discussion extras from the longest N threads, keep >= 3
    best = None
    for fn in nfiles:
        msgs = threads[fn]["messages"]
        if len(msgs) <= 3: continue
        for role in ["chatter", "discussion", "proposal", "objection"]:
            for m in msgs:
                if m["idx"] == 1 or m.get("role") in KEEP_ROLES or m.get("role") != role:
                    continue
                score = (len(msgs), -m["idx"])
                if best is None or score > best[0]:
                    best = (score, fn, m["idx"])
        if best: break  # one removal per pass per role scan
    if best is None: break
    _, fn, drop_idx = best
    t = threads[fn]
    dropped = next(m for m in t["messages"] if m["idx"] == drop_idx)
    parent_of_dropped = dropped.get("in_reply_to_idx")
    t["messages"] = [m for m in t["messages"] if m["idx"] != drop_idx]
    for m in t["messages"]:
        if m.get("in_reply_to_idx") == drop_idx:
            m["in_reply_to_idx"] = parent_of_dropped
    need_n -= 1

# save trimmed threads (backup originals)
bak = TD + "_orig"
if not os.path.isdir(bak):
    shutil.copytree(TD, bak)
for fn, t in threads.items():
    with open(os.path.join(TD, fn), "w", encoding="utf-8") as f:
        json.dump(t, f, indent=1, ensure_ascii=False)

d_msgs = sum(len(t["messages"]) for fn, t in threads.items() if fn.startswith("D"))
n_msgs = sum(len(t["messages"]) for fn, t in threads.items() if fn.startswith("N"))
print("decision msgs:", d_msgs, "non-decision msgs:", n_msgs, "(filler trimmed at assembly to first msg => 310)")
print("total:", d_msgs + n_msgs + 310)

# ---- ground truth ----
G = []
def D(i, date, text, decider, why, alts, typ, status, links, split="dev", authority=None):
    G.append({"id": f"D{i:02d}", "date": date, "canonical_text": text, "decider": decider,
              "rationale": why, "alternatives": alts, "type": typ, "status": status,
              "links": links, "split": split, **({"authority_flag": authority} if authority else {})})

D(1,"2026-01-20","Stay on PayForge for payments through the end of Q2","Marta","avoid migration risk before the v3 launch; fee gap tolerable","switch to Ledgerly now","explicit","SUPERSEDED",[],authority=None)
G[0]["links"]=[{"to":"D02","kind":"supersedes","full":True}]
D(2,"2026-03-11","Switch payments from PayForge to Ledgerly","Marta","fees 2.3% + EUR 0.25 vs 2.9% + EUR 0.30 (~EUR 1,860/month saved on ~EUR 310k processed); native local-currency invoicing; Redline asked for it","stay on PayForge; Bridgepay (dropped: no invoicing)","explicit","AMENDED",[{"to":"D01","kind":"supersedes","full":True},{"to":"D03","kind":"amends","full":"partial"}])
D(3,"2026-04-22","Delay the Ledgerly cutover (planned May 1) until after the June billing cycle","Dev (Marta concurs)","sandbox reconciliation failed on refunds and multi-currency; 3 mismatched settlement reports","cut over May 1 and fix forward","explicit","AMENDED",[{"to":"D02","kind":"amends","full":"partial"},{"to":"D04","kind":"refines","full":True}])
D(4,"2026-05-29","Ledgerly cutover fixed for Monday 2026-07-06","Marta (in meeting recap), confirmed by Dev","after June 30 billing close; reconciliation now passes","July 1","explicit","ACTIVE",[{"to":"D03","kind":"refines","full":True}])
D(5,"2026-01-28","Raise Starter plan from EUR 49 to EUR 59/month effective 2026-03-01","Marta","low churn elasticity; costs are up","EUR 55; no increase","explicit","AMENDED",[{"to":"D06","kind":"amends","full":"partial"}])
D(6,"2026-02-18","Grandfather existing Starter customers at EUR 49 for 12 months; EUR 59 applies to new signups from Mar 1","Marta","140 Starter accounts at risk, 3 loud complaints","full increase for everyone; EUR 54 compromise","explicit","ACTIVE",[{"to":"D05","kind":"amends","full":"partial"}])
D(7,"2026-05-06","Launch a usage-based Scan Pack add-on at EUR 0.08/scan","Priya (Marta approves)","scan-heavy customers cost more to serve","flat EUR 99 add-on","explicit","SUPERSEDED",[{"to":"D08","kind":"supersedes","full":True}])
D(8,"2026-06-10","Drop Scan Pack; include 500 scans/month in the Pro plan instead","Marta","customers found it confusing; sales cycles slowed; billing complexity during Ledgerly cutover","keep Scan Pack; flat add-on","explicit","ACTIVE",[{"to":"D07","kind":"supersedes","full":True}])
D(9,"2026-02-04","Migrate hosting from NimbusHost to Corvid Cloud","Dev","~30% cheaper compute; EU-region residency Swiftbox wants","stay; a third vendor","explicit","AMENDED",[{"to":"D12","kind":"amends","full":"partial"}])
D(10,"2026-02-26","Contract Greg Ferrante to run the migration with a budget cap of EUR 18,000","Helen","team lacks capacity before the launch","in-house; agency quote of EUR 34k","explicit","ACTIVE",[])
D(11,"2026-03-31","App-tier migration to Corvid scheduled for the weekend of Apr 18-19","Dev (casual confirmation)","proposed by Greg, confirmed casually","other weekend","implicit","ACTIVE",[])
D(12,"2026-04-09","Keep the production database on NimbusHost managed Postgres; only the app tier moves (hybrid)","Dev","cross-provider latency adds ~40 ms p95 which would break driver sync; DB migration risk","full move with replication","explicit","ACTIVE",[{"to":"D09","kind":"amends","full":"partial"}])
D(13,"2026-01-15","v3 launch date is April 15","Marta with Priya","Redline pilot starts Apr 20",[],"explicit","SUPERSEDED",[{"to":"D14","kind":"supersedes","full":True}])
D(14,"2026-03-24","v3 launch slips to mid-May (target week of May 11)","Priya/Marta (implicit)","41 open P1 bugs plus the migration collision",[],"implicit","AMENDED",[{"to":"D13","kind":"supersedes","full":True},{"to":"D18","kind":"refines","full":True}])
D(15,"2026-04-02","Cut offline mode from v3; ship it in v3.1","Priya (recorded in Lena's recap of the Apr 2 product meeting)","biggest schedule risk (~6 engineer-weeks)","cut route optimization instead","explicit","AMENDED",[{"to":"D16","kind":"amends","full":"partial"}])
D(16,"2026-04-30","Re-add a read-only offline mode (cached routes and manifests, no edits) to v3","Marta","Redline made it a renewal condition; read-only costs ~1.5 engineer-weeks","full offline; keep the cut","explicit","ACTIVE",[{"to":"D15","kind":"amends","full":"partial"}])
D(17,"2026-02-12","Build the driver app in React Native","Dev (Jonas agrees)","one codebase, team knows JS","native Swift/Kotlin; Flutter","explicit","ACTIVE",[])
D(18,"2026-05-04","Phased rollout: 20% of accounts on Wed May 13, 100% by May 27","Priya","limit blast radius after the migration","big-bang launch","explicit","ACTIVE",[{"to":"D14","kind":"refines","full":True}])
D(19,"2026-01-22","Open one senior backend engineer role, budget up to EUR 95k","Marta (Helen confirms)","backend capacity bottleneck","two juniors","explicit","ACTIVE",[])
D(20,"2026-03-05","Make an offer to Elena Voss at EUR 92k + 0.15% options","Marta","strongest interview loop (Jonas and Dev scores); runner-up Mark Teller weaker on systems design","Mark Teller","explicit","ACTIVE",[])
D(21,"2026-02-24","Try no-meeting Wednesdays company-wide","Marta (implicit: 'ok let's try it for a few weeks')","proposal by Ingrid",[],"implicit","AMENDED",[{"to":"D22","kind":"amends","full":"partial"}])
D(22,"2026-05-20","Suspend no-meeting Wednesdays until June 15 (launch rollout needs daily syncs)","Marta","launch rollout needs daily syncs","keep as is","explicit","ACTIVE",[{"to":"D21","kind":"amends","full":"partial"}])
D(23,"2026-04-14","Engage Kofi Mensah as a part-time QA contractor (3 days/week) instead of hiring a full-time QA","Helen/Priya (implicit)","cost; Kofi available from the 20th","full-time QA hire","implicit","ACTIVE",[])
D(24,"2026-02-09","Offer Redline Couriers a 15% discount for a 2-year renewal","Tomas (claims Marta approved; no supporting email)","win the renewal","no discount","explicit","SUPERSEDED",[{"to":"D25","kind":"supersedes","full":True}],"holdout","Tomas may only discount <= 5%; 15% exceeded his authority")
D(25,"2026-02-11","Cap the Redline renewal discount at 10% (2-year term)","Marta (after Helen escalated)","gross-margin floor of 68%","15% discount","explicit","ACTIVE",[{"to":"D24","kind":"supersedes","full":True}],"holdout")
D(26,"2026-03-17","Decline Swiftbox's request for a 99.99% uptime SLA; offer 99.9% with service credits","Dev (reviewed by Nadia)","cannot guarantee 99.99% on current architecture; credit exposure","accept at a premium price","explicit","ACTIVE",[],"holdout")
D(27,"2026-05-15","Harbor Express: suspend service at 60 days overdue, terminate at 90 days unless paid (EUR 27,400 overdue)","Helen (Marta and Nadia concur)","collection policy","write off; payment plan","explicit","ACTIVE",[],"holdout")
D(28,"2026-03-03","Rotate ALL API keys and customer integration tokens immediately","Dev","a key was found in a public fork of a repo","rotate only the exposed key","explicit","ACTIVE",[],"holdout")
D(29,"2026-03-04","Notify the 9 affected customers within 72 hours of discovery (by 2026-03-06)","Marta (on Nadia's advice)","data-protection notification duty",[],"explicit","ACTIVE",[],"holdout")
D(30,"2026-03-20","Require 2FA on all staff accounts by April 3","Dev (implicit; Marta thumbs-up)","security follow-up after key leak",[],"implicit","ACTIVE",[],"holdout")
D(31,"2026-04-28","Hire Blackthorn Audit for a pentest, EUR 12,000, scheduled for the week of June 1","Helen (approves), Dev","Swiftbox's security questionnaire requires a third-party pentest","Greyline (EUR 9k, not accepted by Swiftbox); skip","explicit","ACTIVE",[],"holdout")
D(32,"2026-01-30","Renew the Rotterdam office lease for 12 months at the current EUR 6,200/month","Helen and Lena (Marta ok)","stability","move to coworking","explicit","AMENDED",[],"holdout")
D(33,"2026-04-06","Sublet half the office from June 1","Marta","~40% of staff remote; recovers ~EUR 3,100/month","break the lease","explicit","ACTIVE",[{"to":"D32","kind":"amends","full":"partial"}],"holdout")
D(34,"2026-03-12","Sponsor LogiConnect Europe at the Silver tier (EUR 6,000)","Chloe (Marta approves)","lead generation","booth only","explicit","SUPERSEDED",[],"holdout")
D(35,"2026-03-27","Downgrade to booth-only (EUR 2,500); drop the sponsorship","Helen","cash priority after migration costs; Silver benefits limited","keep Silver","explicit","ACTIVE",[{"to":"D34","kind":"supersedes","full":True}],"holdout")
D(36,"2026-04-16","Keep the Parcelwise name; no rebrand","Marta","trademark/rebrand cost (>= EUR 8k) and customer recognition","rebrand to Routewell","explicit","ACTIVE",[],"holdout")
D(37,"2026-05-27","Replace the Helpdesk support tool with Beacon Desk effective July 1","Aisha (Marta approves, Helen on cost)","Helpdesk renewal +40%; Beacon integrates with our API","stay on Helpdesk","explicit","ACTIVE",[],"holdout")
D(38,"2026-03-25","First-response SLA for Pro customers","CONTESTED","Version A (Aisha; Lena's recap): 2 business hours. Version B (Tomas, Samir): 1 hour, promised to Carla at Swiftbox on 2026-04-03 in writing",[],"conflict","CONTESTED",[],"dev")
D(39,"2026-04-21","On-call rotation membership","CONTESTED","Version A (Dev, standup recap): weekly rotation of Jonas + Ravi. Version B (Priya): includes Greg and Elena once onboarded",[],"conflict","CONTESTED",[],"dev")
D(40,"2026-02-27","Q2 marketing budget","CONTESTED","Version A (Chloe): EUR 40,000 approved (cites Marta's 'go' reply). Version B (Helen): EUR 30,000 approved (cites the budget sheet shared Mar 2)",[],"conflict","CONTESTED",[],"holdout")

NON = [
 {"id":"N01","topic":"4-day work week","outcome":"Floated by Ingrid/Chloe; Marta: 'let's revisit after launch.' Never revisited.","trap_type":"Deferred","split":"dev"},
 {"id":"N02","topic":"Lisbon satellite office","outcome":"Tomas pushed for Portuguese customers; Marta: 'interesting. not now.'","trap_type":"Polite deferral","split":"dev"},
 {"id":"N03","topic":"Acquire RouteBee","outcome":"Owen proposed by phone; Marta asked Helen for numbers; Helen raised valuation questions; no conclusion.","trap_type":"Investigation != decision","split":"dev"},
 {"id":"N04","topic":"Rewrite backend in Kotlin","outcome":"Jonas ranted; Dev: 'we'll talk.'","trap_type":"One person's opinion","split":"dev"},
 {"id":"N05","topic":"Free tier","outcome":"Chloe's proposal; Helen skeptical; Priya neutral; thread trails off.","trap_type":"Proposal, no approval","split":"dev"},
 {"id":"N06","topic":"Dedicated DevRel hire","outcome":"Marta: 'maybe Q3 if the numbers allow.'","trap_type":"Conditional future","split":"holdout"},
 {"id":"N07","topic":"Rename plans (Starter/Pro/Enterprise)","outcome":"Chloe offered names; thread died.","trap_type":"Abandoned","split":"holdout"},
 {"id":"N08","topic":"Adopt OKRs","outcome":"Ingrid: 'I will draft a proposal.' Marta: 'send it.' No later message.","trap_type":"Task assignment, not decision","split":"holdout"},
 {"id":"N09","topic":"Change email/calendar provider","outcome":"Lena asked; forwarded a vendor quote; nobody with authority replied.","trap_type":"Unanswered question","split":"holdout"},
 {"id":"N10","topic":"Launch in the US in Q4","outcome":"Tomas: conditional on Redline signing the 2-year renewal; Redline hadn't signed by 06-30 (Bruno: 'signing in July').","trap_type":"Conditional, unmet","split":"holdout"},
]

QA = [
 ["Q01","Which payment provider will we use from July, and when is the cutover?","Ledgerly; Mon 2026-07-06","D04,D03,D02"],
 ["Q02","Why did we decide to switch payment providers?","lower fees (2.3% + EUR 0.25 vs 2.9% + EUR 0.30 ~ EUR 1,860/mo), local-currency invoicing, Redline's request","D02"],
 ["Q03","Why was the Ledgerly cutover delayed from May 1?","failed sandbox reconciliation (refunds, multi-currency, 3 mismatched reports)","D03"],
 ["Q04","What does the Starter plan cost, and does it apply to existing customers?","EUR 59 for new signups from Mar 1; existing grandfathered at EUR 49 for 12 months","D05,D06"],
 ["Q05","Are we still launching Scan Pack?","No; dropped 06-10; 500 scans/month included in Pro","D07,D08"],
 ["Q06","Where is the production database hosted?","NimbusHost managed Postgres; only the app tier moves to Corvid","D12,D09"],
 ["Q07","Who runs the hosting migration and with what budget?","Greg Ferrante, cap EUR 18,000","D10"],
 ["Q08","What is the v3 launch date and rollout plan?","Wed May 13 (slipped from Apr 15), phased 20% -> 100% by May 27","D13,D14,D18"],
 ["Q09","Why did the April 15 launch date change?","41 open P1 bugs + migration collision","D14"],
 ["Q10","Is offline mode in v3?","Read-only offline mode yes; full offline in v3.1","D15,D16"],
 ["Q11","Who decided to re-add offline mode and why?","Marta; Redline made it a renewal condition","D16"],
 ["Q12","What discount did we agree for Redline's renewal, and was the earlier 15% approved?","Capped at 10% (2-year); the 15% was offered by Tomas without authority","D24,D25"],
 ["Q13","What SLA are we offering Swiftbox?","99.9% with service credits; 99.99% declined","D26"],
 ["Q14","What happens to Harbor Express?","Suspend at 60 days overdue, terminate at 90 unless paid","D27"],
 ["Q15","What did we do after the leaked API key?","Rotated all keys, notified 9 customers within 72h, 2FA by Apr 3","D28,D29,D30"],
 ["Q16","Who is doing the pentest, when, and how much?","Blackthorn Audit, week of Jun 1, EUR 12,000","D31"],
 ["Q17","What is the status of the office?","Lease renewed 12 months at EUR 6,200/mo; half sublet from Jun 1","D32,D33"],
 ["Q18","Are we sponsoring LogiConnect?","No; booth-only EUR 2,500","D34,D35"],
 ["Q19","Are we rebranding?","No","D36"],
 ["Q20","Which support tool and when?","Beacon Desk from Jul 1","D37"],
 ["Q21","What is the first-response SLA for Pro customers?","CONTESTED: 2 business hours vs 1 hour","D38"],
 ["Q22","Who is on the on-call rotation?","CONTESTED: Jonas+Ravi vs including Greg and Elena","D39"],
 ["Q23","What is the Q2 marketing budget?","CONTESTED: EUR 40k vs EUR 30k","D40"],
 ["Q24","What was our payments plan as of Feb 1?","Stay on PayForge through Q2","D01"],
 ["Q25","Who was hired for the senior backend role, and on what terms?","Elena Voss, EUR 92k + 0.15% options","D20"],
 ["Q26","Did we decide to open a Lisbon office?","NO DECISION; closest: Tomas's pitch, Marta's 'not now'","N02"],
 ["Q27","Did we decide to acquire RouteBee?","NO DECISION","N03"],
 ["Q28","Did we decide to launch a free tier?","NO DECISION","N05"],
 ["Q29","Did we decide to rewrite the backend in Kotlin?","NO DECISION","N04"],
 ["Q30","Did we decide to launch in the US in Q4?","NO DECISION (conditional on Redline signing, which hasn't happened)","N10"],
]

gt = {"decisions": G, "non_decisions": NON,
      "qa": [{"id": q, "question": t, "expected": e, "evidence_decisions": ev.split(",")} for q, t, e, ev in QA]}
# evidence_message_ids get filled at assembly time; placeholder field
with open(os.path.join(PRIV, "ground_truth.json"), "w", encoding="utf-8") as f:
    json.dump(gt, f, indent=1, ensure_ascii=False)
print("ground_truth.json written:", len(G), "decisions,", len(NON), "non-decisions,", len(QA), "QA")
