# STORY BIBLE v1.0: Parcelwise B.V. (fictional)

**Audience:** GLM 5.3 (email generation) and the eval harness.
**Hard rule:** `ground_truth` content below must NEVER be shown to the Precedent extraction pipeline. It is only used to (a) generate the corpus and (b) score the results.

---

## 1. The company

**Parcelwise B.V.** is a 22-person company in Rotterdam, Netherlands. It sells route-planning and delivery-tracking software (web dashboard + React Native driver app + a small handheld scanner integration) to small and mid-size courier companies. About 310 customer accounts. Revenue ~€310k/month processed through its billing (subscriptions + usage). All currency is EUR.

**Corpus window:** Monday 2026-01-05 to Tuesday 2026-06-30. Company timezone Europe/Amsterdam (CET; CEST from 2026-03-29). All weekday references in emails MUST match the real 2026 calendar.

**The six-month story in one paragraph:** Parcelwise is racing to ship v3 of its platform. While doing so it tries to cut payment fees, move hosting to a cheaper cloud, raise prices without losing customers, close a big renewal with its largest client, survive a leaked-API-key incident, and manage cash. Plans keep changing. Several decisions are reversed or amended, a few are made informally, three are remembered differently by different people, and many ideas are floated but never decided.

**Email domains (all reserved `.example`):** parcelwise.example, redlinecouriers.example, swiftbox.example, harborexpress.example, okafor-lindqvist.example (law firm), northbridge.example (investor), ferrante-ops.example (Greg), plus vendor domains `payforge.example`, `ledgerly.example`, `nimbushost.example`, `corvidcloud.example`, `helpdesk-co.example`, `beacondesk.example`, `blackthorn-audit.example`, `logiconnect.example`, `vdb-vastgoed.example` (landlord).

**Fictional vendors (never use real brand names):** PayForge (current payments), Ledgerly (new payments), NimbusHost (current hosting), Corvid Cloud (new hosting), Helpdesk Co. "Helpdesk" (old support tool), Beacon Desk (new support tool), Blackthorn Audit (pentest), LogiConnect Europe (conference).

### 1.1 Authority matrix (used by the "authority flag" feature)
| Role | Can decide alone |
|---|---|
| Marta (CEO) | Anything |
| Helen (CFO) | Spend ≤ €10,000; payment terms; collections |
| Dev (CTO) | Architecture, vendors for infra, security policy |
| Priya (Product) | Scope inside the roadmap; scope changes that move launch date need Marta |
| Tomás (Sales) | Discounts ≤ 5%. Anything above needs Marta. |
| Aisha (Support) | Support tooling ≤ €5,000/yr; support process |
| Chloe (Marketing) | Spend only inside an approved budget |
| Lena (Ops) | Office admin, logistics |

---

## 2. People (persona cards)

Each email MUST be written in its sender's voice. Signature blocks are fixed per person.

| # | Name / role / address | Voice and quirks |
|---|---|---|
| 1 | **Marta Kowalczyk**, CEO & co-founder, marta@parcelwise.example | Terse, no greeting, often lowercase, 1-3 lines, sign-off just "M". Occasional Polish ("dzięki", "ok super"). Decisive, often from phone: "Sent from my iPhone". Never explains much; rationale is usually in other people's emails. |
| 2 | **Dev Raman**, CTO & co-founder, dev@ | Structured bullets, dry humor, "my take:", precise numbers. Sign-off "Cheers, Dev". |
| 3 | **Helen Oyelaran**, CFO, helen@ | Very polite, formal, long sentences, "Dear all," / "Kind regards, Helen". Hedges ("I would gently suggest"). Cites figures. Full signature with title. |
| 4 | **Tomás Ibarra**, Head of Sales, tomas@ | Enthusiastic, exclamation marks, ✅ 🚀, occasional Spanish ("Hola equipo", "Saludos"). Over-promises. Sometimes acts before checking. |
| 5 | **Priya Natarajan**, Head of Product, priya@ | "Quick recap:" + numbered lists. Calendar-minded. "Thanks!" |
| 6 | **Jonas Eklund**, Senior Backend Eng, jonas@ | Lowercase, blunt, short, "fwiw", no signature, dislikes meetings, occasional code snippet. |
| 7 | **Aisha Bello**, Head of Customer Success, aisha@ | Warm, long paragraphs, names customers, "Hi team 😊". |
| 8 | **Greg Ferrante**, DevOps contractor, greg@ferrante-ops.example | Fragments, no greeting, typos ("teh", "migraton"), writes late at night, mobile-sent. |
| 9 | **Lena Fischer**, Ops & Office Manager, lena@ | Practical, bullet lists, German greetings ("Liebe Alle", "Danke"). Writes the **meeting recaps** ("Notes:" with Attendees / Actions). |
| 10 | **Samir Haddad**, Account Exec, samir@ | Casual "hey!", short, defers to Tomás. |
| 11 | **Chloe Winters**, Marketing Manager, chloe@ | Buzzwordy, "super excited", links to slide decks, exclamation marks. |
| 12 | **Ravi Menon**, Junior Engineer, ravi@ | Apologetic, hedging, "Sorry to bother", asks lots of questions. |
| 13 | **Ingrid Solberg**, People & Culture (part-time Mon-Wed), ingrid@ | Careful, warm-formal, policy-minded. |
| 14 | **Elena Voss**, candidate (Jan-Mar, personal address elena.voss@mailbox.example), then Senior Backend Eng from 2026-04-21 (elena@parcelwise.example) | Professional and thoughtful. After joining: asks sharp questions about decisions "I wasn't here for". |
| 15 | **Kofi Mensah**, QA contractor from 2026-04-20, kofi@ | Meticulous, bug IDs (PW-1234), numbered steps. |

**Externals:** Owen Caldwell (investor/board, Northbridge, very short phone emails, London time); Nadia Petrova (outside counsel, formal legalese); Bruno Alvarez (COO Redline Couriers, direct, impatient); Carla Dunne (Head of Ops Swiftbox, procedural, security-focused); Walt Pruitt (owner Harbor Express, folksy, apologetic about late payment); vendor reps: Maya Chen (Ledgerly), Anders Holm (Corvid Cloud), Ines Marquez (Blackthorn), Paula Reyes (LogiConnect), plus generic reps for PayForge, NimbusHost, Helpdesk Co., Beacon Desk, landlord.

Silent staff (appear only on "all@" distribution lists): 8 more employees.

**Other recurring entities:** Redline Couriers (largest client, ~18% of revenue, renewal due), Swiftbox (security-conscious mid client), Harbor Express (small client, €27,400 overdue), RouteBee (tiny competitor), Elena Voss's runner-up Mark Teller.

---

## 3. GROUND TRUTH: 40 planted decisions

Legend: **type** = explicit | implicit; **cross-thread** = decision assembled across ≥2 separate threads (or a meeting-recap email + a thread); **link** = relation to another decision. **Date** = date of the *decisive* message. **Thread** gives sender order and the minimum message count; GLM may add 1-3 messages of natural chatter.

> Each thread must also contain realistic *discussion* messages that are NOT decisive (questions, objections, data). The decisive message must exist and be identifiable; for implicit decisions it is a casual confirmation, never the words "decided"/"decision".

### Arc A: Payments (dev)
**D01** · 2026-01-20 · explicit · status: SUPERSEDED by D02
Decision: Stay on PayForge for payments through the end of Q2.
Decider: Marta (Helen consulted). Why: avoid migration risk before the v3 launch; the fee gap is tolerable for now. Alternatives: switch to Ledgerly now.
Thread (5 msgs): Helen (fee complaint, figures) → Dev (migration risk) → Tomás (customers asking for local-currency invoices) → Helen (summary question) → Marta (decisive: "stay on payforge till q2. revisit after v3.").

**D02** · 2026-03-11 · explicit · cross-thread · supersedes D01 · status: AMENDED by D03/D04
Decision: Switch payments from PayForge to Ledgerly.
Decider: Marta. Why: fees 2.3% + €0.25 vs 2.9% + €0.30 (≈ €1,860/month saved on ~€310k processed); native local-currency invoicing; Redline asked for it. Alternatives: stay on PayForge; "Bridgepay" (dropped: no invoicing).
Threads: (T1, 4 msgs) Helen's fee analysis with Dev's integration estimate; (T2, 3 msgs) Bruno at Redline asks Aisha/Tomás for local-currency invoices; (T3) Lena's recap email of the 2026-03-10 leadership meeting listing "payments: leaning Ledgerly"; then Marta's decisive email 3-11 to leadership ("ledgerly. dev pls plan cutover.").

**D03** · 2026-04-22 · explicit · amends D02 (timing) · status: AMENDED by D04
Decision: Delay the Ledgerly cutover (planned May 1) until after the June billing cycle.
Decider: Dev (Marta concurs). Why: sandbox reconciliation failed on refunds and multi-currency; 3 mismatched settlement reports. Alternatives: cut over May 1 and fix forward.
Thread (5 msgs): Jonas (mismatch findings) → Dev (analysis) → Helen (cash-flow worry) → Dev (decisive) → Marta ("fine").

**D04** · 2026-05-29 · explicit · cross-thread · refines D03 · status: ACTIVE (current)
Decision: Ledgerly cutover fixed for Monday 2026-07-06.
Decider: Marta (in meeting recap), confirmed by Dev. Why: after June 30 billing close; Dev confirms reconciliation now passes. Alternatives: July 1.
Threads: Lena's recap of the 05-28 leadership meeting; Dev's follow-up email to Helen/Jonas with the confirmed plan (3 msgs).

### Arc B: Pricing
**D05** · 2026-01-28 · explicit · status: AMENDED by D06
Decision: Raise Starter plan from €49 to €59/month effective 2026-03-01.
Decider: Marta. Why: Priya's analysis shows low churn elasticity; costs are up. Alternatives: €55; no increase.
Thread (6 msgs): Priya (analysis, attached table described in text) → Tomás (worried) → Helen (support) → Chloe (messaging) → Marta (decisive).

**D06** · 2026-02-18 · explicit · amends D05 · status: ACTIVE
Decision: Grandfather existing Starter customers at €49 for 12 months; €59 applies to new signups from Mar 1.
Decider: Marta. Why: Tomás: 140 Starter accounts at risk, 3 loud complaints (Aisha confirms). Alternatives: full increase for everyone; €54 compromise.
Thread (6 msgs): Aisha (complaints) → Tomás (push) → Helen (revenue impact) → Priya (data) → Marta (decisive).

**D07** · 2026-05-06 · explicit · status: SUPERSEDED by D08
Decision: Launch a usage-based "Scan Pack" add-on at €0.08/scan.
Decider: Priya, Marta approves. Why: scan-heavy customers cost more to serve. Alternatives: flat €99 add-on.
Thread (4 msgs).

**D08** · 2026-06-10 · explicit · supersedes D07 (full) · status: ACTIVE
Decision: Drop Scan Pack; include 500 scans/month in the Pro plan instead.
Decider: Marta. Why: customers found it confusing; sales cycles slowed; billing complexity during the Ledgerly cutover. Alternatives: keep Scan Pack; flat add-on.
Thread (6 msgs): Tomás (sales friction) → Aisha (confusion tickets) → Dev (billing complexity) → Priya (reluctant) → Marta (decisive).

### Arc C: Infrastructure
**D09** · 2026-02-04 · explicit · status: AMENDED by D12
Decision: Migrate hosting from NimbusHost to Corvid Cloud.
Decider: Dev. Why: ~30% cheaper compute; EU-region residency Swiftbox wants. Alternatives: stay; a third vendor.
Thread (5 msgs): Dev proposal → Helen (cost check) → Jonas (concerns, mild) → Marta ("ok") → Dev (confirms plan).

**D10** · 2026-02-26 · explicit · status: ACTIVE
Decision: Contract Greg Ferrante to run the migration with a budget cap of €18,000.
Decider: Helen. Why: team lacks capacity before the launch. Alternatives: in-house; agency quote of €34k.
Thread (4 msgs) incl. Greg's quote email (fragments, typos).

**D11** · 2026-03-31 · IMPLICIT · status: ACTIVE
Decision: App-tier migration to Corvid is scheduled for the weekend of Apr 18-19.
How it appears: Greg proposes two weekends; Dev replies "ok saturday then"; Marta 👍. The words "decide/decision" never appear.
Thread (4 msgs).

**D12** · 2026-04-09 · explicit · amends D09 (partial) · status: ACTIVE
Decision: Keep the production database on NimbusHost managed Postgres; only the app tier moves (hybrid).
Decider: Dev. Why: Jonas's benchmark: cross-provider latency adds ~40 ms p95 which would break driver sync; DB migration risk. Alternatives: full move with replication.
Thread (6 msgs): Jonas (benchmark) → Greg (alt plan) → Dev (decisive) → Helen (cost impact) → Priya (launch risk) → Dev.

### Arc D: Product and launch
**D13** · 2026-01-15 · explicit · status: SUPERSEDED by D14
Decision: v3 launch date is April 15.
Decider: Marta with Priya. Why: Redline pilot starts Apr 20. Alternatives: none seriously considered.
Thread (4 msgs).

**D14** · 2026-03-24 · IMPLICIT · supersedes D13 · status: AMENDED by D18
Decision: v3 launch slips to mid-May (target week of May 11).
How it appears: Priya sends bug triage (41 open P1 bugs, plus the migration collision); then Priya: "so mid-May realistically?" Marta: "yes. tell redline." Never a formal announcement.
Thread (6 msgs).

**D15** · 2026-04-02 · explicit · status: AMENDED by D16
Decision: Cut offline mode from v3; ship it in v3.1.
Decider: Priya (recorded in Lena's recap of the Apr 2 product meeting). Why: biggest schedule risk (≈6 engineer-weeks). Alternatives: cut route optimization instead.
Threads: Priya/Jonas/Dev thread (4 msgs) + Lena recap.

**D16** · 2026-04-30 · explicit · cross-thread · partially reverses D15 · status: ACTIVE
Decision: Re-add a read-only offline mode (cached routes and manifests, no edits) to v3.
Decider: Marta. Why: Redline made it a renewal condition; read-only costs ~1.5 engineer-weeks. Alternatives: full offline; keep the cut.
Threads: (T1) Bruno → Tomás email, firm tone; (T2) internal thread Tomás/Priya/Jonas/Dev sizing the work; (T3) Lena's recap of the 04-29 call with Redline; Marta's decisive message.

**D17** · 2026-02-12 · explicit · status: ACTIVE
Decision: Build the driver app in React Native.
Decider: Dev (Jonas agrees). Why: one codebase, team knows JS. Alternatives: native Swift/Kotlin; Flutter.
Thread (5 msgs) incl. Ravi asking naive questions.

**D18** · 2026-05-04 · explicit · refines D14 · status: ACTIVE
Decision: Phased rollout: 20% of accounts on Wed May 13, 100% by May 27.
Decider: Priya. Why: limit blast radius after the migration. Alternatives: big-bang launch.
Thread (5 msgs).

### Arc E: People
**D19** · 2026-01-22 · explicit · status: ACTIVE
Decision: Open one senior backend engineer role, budget up to €95k.
Decider: Marta (Helen confirms). Why: backend capacity bottleneck. Alternatives: two juniors.
Thread (4 msgs).

**D20** · 2026-03-05 · explicit · cross-thread · status: ACTIVE
Decision: Make an offer to Elena Voss at €92k + 0.15% options.
Decider: Marta. Why: strongest interview loop (Jonas and Dev scores); runner-up Mark Teller weaker on systems design. Alternatives: Mark Teller.
Threads: (T1) Jonas's and Dev's separate interview-feedback emails; (T2) Ingrid's comparison summary; (T3) Marta's decisive email; (T4) Ingrid → Elena offer email. Elena accepts 03-12, starts 04-21 (these are facts, not decisions).

**D21** · 2026-02-24 · IMPLICIT · status: AMENDED by D22
Decision: Try no-meeting Wednesdays company-wide.
How it appears: Ingrid proposes; Marta: "ok let's try it for a few weeks"; Lena: "I'll update the calendars".
Thread (5 msgs).

**D22** · 2026-05-20 · explicit · amends D21 · status: ACTIVE
Decision: Suspend no-meeting Wednesdays until June 15 (launch rollout needs daily syncs).
Decider: Marta. Alternatives: keep as is.
Thread (3 msgs). No later decision resumes it (leave the gap).

**D23** · 2026-04-14 · IMPLICIT · status: ACTIVE
Decision: Engage Kofi Mensah as a part-time QA contractor (3 days/week) instead of hiring a full-time QA.
How it appears: long thread Helen/Priya/Dev about cost; Priya: "Kofi's available from the 20th"; Helen: "Then I shall prepare his contract for three days a week." Nobody says "decided".
Thread (6 msgs).

### Arc F: Clients and contracts (HOLDOUT)
**D24** · 2026-02-09 · explicit · status: SUPERSEDED by D25 · **authority flag**
Decision: Offer Redline Couriers a 15% discount for a 2-year renewal.
Decider: Tomás (claims "Marta was fine with it" but no email from Marta supports it). Authority: Tomás may only discount ≤ 5%.
Thread (4 msgs): Tomás → Bruno (the offer, enthusiastic), Tomás → leadership (FYI, cc Helen).

**D25** · 2026-02-11 · explicit · supersedes D24 · status: ACTIVE
Decision: Cap the Redline renewal discount at 10% (2-year term).
Decider: Marta (after Helen escalated). Why: gross-margin floor of 68%. Tomás to walk back the 15% with Bruno.
Thread (6 msgs): Helen escalation → Marta → Tomás (defensive) → Marta → Tomás/Bruno (walk-back, Bruno annoyed).

**D26** · 2026-03-17 · explicit · status: ACTIVE
Decision: Decline Swiftbox's request for a 99.99% uptime SLA; offer 99.9% with service credits.
Decider: Dev, reviewed by Nadia. Why: cannot guarantee 99.99% on current architecture; credit exposure. Alternatives: accept at a premium price.
Thread (6 msgs) incl. Nadia's formal note and Carla's request.

**D27** · 2026-05-15 · explicit · status: ACTIVE
Decision: Harbor Express: suspend service at 60 days overdue, terminate at 90 days unless paid (€27,400 overdue).
Decider: Helen (Marta and Nadia concur). Alternatives: write off; payment plan.
Thread (6 msgs) incl. Walt's apologetic emails.

### Arc G: Security incident (HOLDOUT)
**D28** · 2026-03-03 · explicit · status: ACTIVE
Decision: Rotate ALL API keys and customer integration tokens immediately.
Decider: Dev. Why: a key was found in a public fork of a repo (commit by Ravi, panicked and apologetic). Alternatives: rotate only the exposed key.
Thread (7 msgs).

**D29** · 2026-03-04 · explicit · status: ACTIVE
Decision: Notify the 9 affected customers within 72 hours of discovery (by 03-06).
Decider: Marta, on Nadia's advice. Why: data-protection notification duty.
Thread (5 msgs).

**D30** · 2026-03-20 · IMPLICIT · status: ACTIVE
Decision: Require 2FA on all staff accounts by April 3.
How it appears: Dev: "proposal: 2FA mandatory, deadline Apr 3"; Marta 👍; Lena: "will send instructions Monday".
Thread (4 msgs).

**D31** · 2026-04-28 · explicit · cross-thread · status: ACTIVE
Decision: Hire Blackthorn Audit for a pentest, €12,000, scheduled for the week of June 1.
Decider: Helen (approves), Dev. Why: Swiftbox's security questionnaire requires a third-party pentest. Alternatives: Greyline (€9k, not accepted by Swiftbox), skip.
Threads: (T1) Carla's questionnaire email; (T2) Dev/Helen quote comparison; (T3) Helen → Ines (Blackthorn) engagement.

### Arc H: Office, marketing, tooling (HOLDOUT)
**D32** · 2026-01-30 · explicit · status: AMENDED by D33
Decision: Renew the Rotterdam office lease for 12 months at the current €6,200/month.
Decider: Helen and Lena (Marta ok). Alternatives: move to coworking.
Thread (4 msgs) incl. landlord's email.

**D33** · 2026-04-06 · explicit · amends D32 (partial) · status: ACTIVE
Decision: Sublet half the office from June 1.
Decider: Marta. Why: ~40% of staff remote; recovers ≈ €3,100/month. Alternatives: break the lease.
Thread (5 msgs).

**D34** · 2026-03-12 · explicit · status: SUPERSEDED by D35
Decision: Sponsor LogiConnect Europe at the Silver tier (€6,000).
Decider: Chloe, Marta approves. Why: lead generation. Alternatives: booth only.
Thread (4 msgs) incl. Paula's sales email.

**D35** · 2026-03-27 · explicit · supersedes D34 (full) · status: ACTIVE
Decision: Downgrade to booth-only (€2,500); drop the sponsorship.
Decider: Helen. Why: cash priority after migration costs; Silver benefits limited. Chloe disappointed.
Thread (5 msgs).

**D36** · 2026-04-16 · explicit · status: ACTIVE
Decision: Keep the Parcelwise name; no rebrand.
Decider: Marta. Why: trademark/rebrand cost (≥ €8k) and customer recognition. Alternatives: rebrand to "Routewell".
Thread (6 msgs).

**D37** · 2026-05-27 · explicit · status: ACTIVE
Decision: Replace the Helpdesk support tool with Beacon Desk effective July 1.
Decider: Aisha, Marta approves, Helen on cost. Why: Helpdesk renewal +40%; Beacon integrates with our API.
Thread (6 msgs).

### Conflicts (3): two or more people state *different versions* of the same decision
**D38** · 2026-03-25 (leadership meeting) · status: CONTESTED (dev split)
Topic: First-response SLA for Pro customers.
Version A (Aisha; Lena's recap): **2 business hours**. Version B (Tomás, Samir): **1 hour**, which Tomás promised to Carla at Swiftbox on 04-03 in writing.
Expected system behavior: show BOTH with evidence; do not pick one.
Thread (7 msgs across Lena's recap, Aisha's follow-up, Tomás → Carla, Samir, Aisha discovering the discrepancy, no resolution).

**D39** · 2026-04-21 · status: CONTESTED (dev split)
Topic: On-call rotation membership.
Version A (Dev, standup recap): weekly rotation of **Jonas + Ravi**. Version B (Priya): rotation **includes Greg and Elena** once onboarded. Greg writes: "nobody asked me about on call".
Thread (6 msgs, unresolved).

**D40** · 2026-02-27 · status: CONTESTED (holdout)
Topic: Q2 marketing budget.
Version A (Chloe): **€40,000** approved (cites Marta's "go" reply). Version B (Helen): **€30,000** approved (cites the budget sheet shared Mar 2).
Thread (6 msgs, unresolved).

### Relationship summary (11 supersession/amendment edges)
Full reversals (5): D01→D02, D07→D08, D13→D14, D24→D25, D34→D35.
Partial amendments/refinements (6): D02→D03, D05→D06, D09→D12, D15→D16, D21→D22, D32→D33. Refinements (no reversal): D03→D04, D14→D18.
Counts: implicit = 5 (D11, D14, D21, D23, D30); cross-thread = 5 (D02, D04, D16, D20, D31); conflicts = 3; authority flag = 1 (D24).

---

## 4. NON-DECISIONS: 10 "almost decisions" (must NOT be extracted as decisions)

| ID | Topic | What happens | Trap type |
|---|---|---|---|
| N01 | 4-day work week | Ingrid/Chloe float it. Marta: "let's revisit after launch." Never revisited. | Deferred |
| N02 | Lisbon satellite office | Tomás pushes for Portuguese customers. Marta: "interesting. not now." | Polite deferral |
| N03 | Acquire RouteBee | Owen proposes by phone. Marta asks Helen for numbers; Helen raises valuation questions; no conclusion. | Investigation ≠ decision |
| N04 | Rewrite backend in Kotlin | Jonas rants. Dev: "we'll talk." | One person's opinion |
| N05 | Free tier | Chloe's proposal; Helen skeptical; Priya neutral; thread trails off. | Proposal, no approval |
| N06 | Dedicated DevRel hire | Marta: "maybe Q3 if the numbers allow." | Conditional future |
| N07 | Rename plans (Starter/Pro/Enterprise) | Chloe offers names; thread dies. | Abandoned |
| N08 | Adopt OKRs | Ingrid: "I will draft a proposal." Marta: "send it." No later message. | Task assignment, not decision |
| N09 | Change email/calendar provider | Lena asks; forwards a vendor quote; nobody with authority replies. | Unanswered question |
| N10 | Launch in the US in Q4 | Tomás: "if Redline signs the 2-year renewal we go to the US in Q4." Redline hasn't signed by 06-30 (Bruno: "signing in July"). | Conditional, unmet |

Each N needs a thread of 3-5 messages. Include phrases like "sounds good", "let's do it", or a 👍 inside some of them, but never a real commitment.

---

## 5. TRAP CATALOG (sprinkle through the corpus, and label in the manifest)

1. **Quoted old decisions** in reply chains (script-inserted, see §7). Pipeline must not double-count them.
2. **Forwards** of earlier emails ("FYI see below") where the decision belongs to the forwarded author and date.
3. **Hypotheticals** ("we could switch to…", "what if we…").
4. **Retractions** ("scratch that", "ignore my last email").
5. **Wrong-authority statements** (D24).
6. **Questions that look like decisions** ("so we're going with Ledgerly?"), followed by no answer for several days.
7. **Trivial-logistics decisions** (lunch order, meeting room, moving stand-up 15 minutes): 15 of these in filler. They are *out of scope*: Precedent only extracts decisions that affect money, scope, people, customers, vendors, policy, or external commitments.
8. **Numbers that differ innocently** (net vs gross, EUR vs "k") that are NOT conflicts.

---

## 6. VOLUME PLAN (560 emails)

| Bucket | Count |
|---|---|
| Decision threads (D01-D40, avg ~5.2 msgs) | 210 |
| Non-decision threads (N01-N10, ~4 each) | 40 |
| **Filler** | **310** |

Filler breakdown: scheduling 60 · invoices/finance admin 45 · customer support escalations 50 · sales pipeline 45 · vendor newsletters/spam 35 · out-of-office/auto-replies 20 · internal banter/social 30 · HR admin 15 · engineering status/incident noise 10 (= 310).
Of those, 15 are the trivial-logistics decisions from trap #7, and ~25 contain decision-*sounding* language that is not a decision.

### 6.1 Dev / holdout split
- **DEV (tune prompts here):** D01-D23, D38, D39, N01-N05, plus ~60% of filler.
- **HOLDOUT (report headline numbers here; never look at failures until the final run):** D24-D37, D40, N06-N10, ~40% of filler, plus the **human-written slice**.
- **Human-written slice (30-40 emails):** the three team members hand-write a mini-arc (4 decisions H01-H04, 1 reversal, 1 almost-decision) in their own words, using the same fictional company. Add to the holdout. Record their ground truth in the same format.

---

## 7. GENERATION SPEC FOR GLM 5.3

### 7.1 Principles
- Generate **from the decision records above**, never "500 random emails".
- Keep a shared **facts ledger** (all numbers, names, dates in this document). Any number in an email must match the ledger except where a conflict (D38-D40) is intentionally planted.
- Never use the words "ground truth", "planted", "decision D12" etc. inside any email.
- The decisive message of a decision must not be the *longest* or *most formal* message in the thread. Real decisions are often a throwaway line.
- Make rationale come from several people, not the decider.
- People write in their own voice (§2). No two people sign off the same way.

### 7.2 Pipeline
1. **Pilot (hour ~1):** generate threads for D01, D02, D05, D11, N02, and 10 filler emails (≈ 35 emails). Send to the team for a voice check and to Opus for early parser testing. **Do not mass-generate until the pilot is approved.**
2. **Thread generation:** for each decision/non-decision, call the thread prompt (§7.3) with: persona cards for participants, the record, the thread seed, and `prior_context` (short summaries of earlier linked decisions, so later threads can say "as we agreed in Feb…").
3. **Filler generation:** for each filler category, generate in batches of 10 with a fresh random seed of (sender, recipient, date, topic) from a pre-built schedule table (a script builds the schedule so dates are spread realistically: more volume Mon-Thu, none on Dutch public holidays e.g. Apr 3 Good Friday, Apr 5-6 Easter, Apr 27 King's Day, May 14 Ascension, May 25 Whit Monday).
4. **Assembly script (deterministic, NOT an LLM):** converts message JSON → `.eml` with proper headers; builds `Message-ID`, `In-Reply-To`, `References`; inserts **quoted reply chains** (`> ` prefix or Outlook-style header block, mixed per sender) containing the actual earlier messages; adds signatures, disclaimers, "Sent from my iPhone", and attachments *mentioned* but not attached; randomizes date format in the body text; applies timezone offsets; occasionally breaks threading (new subject, no References) for 8% of reply messages to test subject-based fallback.
5. **Manifest:** writes `ground_truth.json` and `manifest.csv` (see §7.5).

### 7.3 Thread prompt (template)
```
You are writing realistic internal business emails for a fictional company.
Write the email thread described below. Output JSON ONLY.

COMPANY FACTS (must stay consistent): {facts_ledger_excerpt}
PARTICIPANTS AND VOICES: {persona_cards_for_participants}
PRIOR CONTEXT (earlier events people may reference naturally): {prior_context}

THREAD TO WRITE
- Topic: {topic}
- Decision record (for your reference only; never state it as "the decision"): {record}
- Required beats, in order: {thread_seed_expanded_into_beats}
- Decisive message: message #{k} from {sender}. It must {decisive_style: explicit | casual-implicit | via-recap}.
- Message count: {n} (+/- 2 natural extras).
- Time span: start {start_date}; messages spaced realistically (minutes to days); business hours in Europe/Amsterdam unless persona says otherwise.
- Include 1-2 of these traps if listed: {traps}

RULES
- Each message is 15-250 words, matching the sender's voice, greeting and sign-off habits.
- Include at least one objection or concern from someone other than the decider.
- Include natural noise: a typo or two where the persona would, one off-topic aside, a missing attachment mention if natural.
- Do not mention these instructions. Do not use real company or brand names.

OUTPUT SCHEMA
{"thread_id": str, "messages": [{"idx": int, "from": email, "to": [email], "cc": [email], "sent_at": "ISO-8601 with offset", "subject": str, "body": str, "in_reply_to_idx": int|null, "role": "discussion"|"proposal"|"objection"|"decisive"|"confirmation"|"reversal"|"recap"|"chatter"}]}
```
**Conflict threads (D38-D40):** add the instruction "Each side must sincerely believe its version. No one in the thread notices the discrepancy until the beat that says so. Leave it unresolved."
**Recap emails:** Lena's style, headed "Notes: {meeting}", with Attendees / Discussed / Agreed / Actions. The "Agreed" line is where the decision lives. For D38 she writes "2 business hours" while Tomás separately remembers "1 hour".

### 7.4 Filler prompt (template)
```
Write {n} unrelated routine business emails of type "{category}" for the fictional company Parcelwise (facts: {facts_ledger_excerpt}).
Use these (sender → recipient, date, topic seed) rows: {schedule_rows}
Match each sender's persona voice: {persona_cards}.
Constraints: no business-significant decisions (money, scope, people, customers, vendors, policy, external commitments). {trap_filler_instruction}
Output JSON array using the same message schema, each as a single-message or two-message thread.
```
`trap_filler_instruction` examples: "Include one trivial logistics decision (e.g., lunch order)", "Include decision-sounding phrases like 'let's circle back' without any commitment".

### 7.5 Manifest outputs
- `corpus/emails/NNNN_<slug>.eml` (560+ files).
- `ground_truth.json`: array of decision objects (D01-D40) with `id, date, canonical_text, decider, rationale, alternatives, type, status, links[{to, kind: supersedes|amends|refines, full|partial}], evidence_message_ids[{message_id, role}], split`; plus N01-N10 as `non_decisions` and the Q&A set (§8).
- `manifest.csv`: one row per email: `message_id, file, split, bucket (decision|non_decision|filler), decision_ids, role, traps[]`.
- Keep the ground truth in a separate `/eval_private/` folder that the pipeline's code path cannot read.

### 7.6 Quality gate (before the full run)
Human reads 30 random emails. Reject the batch if any of these show up: all emails open with "Hi team,"; identical sign-offs across personas; the decisive line is the clearest, most formal statement in the thread; emails sound like an AI summary ("I wanted to circle back and align on…") for people who are not Chloe; unrealistic perfect grammar everywhere; every thread has exactly the same length; dates fall on holidays or weekends for no reason.

---

## 8. Q&A SET (30 questions)

Expected answers key the decisions. A correct answer needs the right facts, the right status, and at least one gold evidence message.

| Q | Question | Expected |
|---|---|---|
| Q01 | Which payment provider will we use from July, and when is the cutover? | Ledgerly; Mon 2026-07-06 (D04, D03, D02) |
| Q02 | Why did we decide to switch payment providers? | D02: lower fees (2.3% + €0.25 vs 2.9% + €0.30 ≈ €1,860/mo), local-currency invoicing, Redline's request |
| Q03 | Why was the Ledgerly cutover delayed from May 1? | D03: failed sandbox reconciliation (refunds, multi-currency, 3 mismatched reports) |
| Q04 | What does the Starter plan cost, and does it apply to existing customers? | €59 for new signups from Mar 1; existing grandfathered at €49 for 12 months (D05, D06) |
| Q05 | Are we still launching Scan Pack? | No; dropped 06-10; 500 scans/month included in Pro (D07→D08) |
| Q06 | Where is the production database hosted? | NimbusHost managed Postgres; only the app tier moves to Corvid (D12, D09) |
| Q07 | Who runs the hosting migration and with what budget? | Greg Ferrante, cap €18,000 (D10) |
| Q08 | What is the v3 launch date and rollout plan? | Wed May 13 (slipped from Apr 15), phased 20% → 100% by May 27 (D13, D14, D18) |
| Q09 | Why did the April 15 launch date change? | 41 open P1 bugs + migration collision (D14) |
| Q10 | Is offline mode in v3? | Read-only offline mode yes; full offline in v3.1 (D15→D16) |
| Q11 | Who decided to re-add offline mode and why? | Marta; Redline made it a renewal condition (D16) |
| Q12 | What discount did we agree for Redline's renewal, and was the earlier 15% approved? | Capped at 10% (2-year); the 15% was offered by Tomás without authority (D24→D25) |
| Q13 | What SLA are we offering Swiftbox? | 99.9% with service credits; 99.99% declined (D26) |
| Q14 | What happens to Harbor Express? | Suspend at 60 days overdue, terminate at 90 unless paid (D27) |
| Q15 | What did we do after the leaked API key? | Rotated all keys (D28), notified 9 customers within 72h (D29), 2FA by Apr 3 (D30) |
| Q16 | Who is doing the pentest, when, and how much? | Blackthorn Audit, week of Jun 1, €12,000 (D31) |
| Q17 | What is the status of the office? | Lease renewed 12 months at €6,200/mo (D32); half sublet from Jun 1 (D33) |
| Q18 | Are we sponsoring LogiConnect? | No; booth-only €2,500 (D34→D35) |
| Q19 | Are we rebranding? | No (D36) |
| Q20 | Which support tool and when? | Beacon Desk from Jul 1 (D37) |
| Q21 | What is the first-response SLA for Pro customers? | CONTESTED: 2 business hours vs 1 hour (D38) |
| Q22 | Who is on the on-call rotation? | CONTESTED: Jonas+Ravi vs including Greg and Elena (D39) |
| Q23 | What is the Q2 marketing budget? | CONTESTED: €40k vs €30k (D40) |
| Q24 | What was our payments plan as of Feb 1? | Stay on PayForge through Q2 (D01) (as-of query) |
| Q25 | Who was hired for the senior backend role, and on what terms? | Elena Voss, €92k + 0.15% options (D20) |
| Q26 | Did we decide to open a Lisbon office? | **NO DECISION** (N02); closest: Tomás's pitch, Marta's "not now" |
| Q27 | Did we decide to acquire RouteBee? | **NO DECISION** (N03) |
| Q28 | Did we decide to launch a free tier? | **NO DECISION** (N05) |
| Q29 | Did we decide to rewrite the backend in Kotlin? | **NO DECISION** (N04) |
| Q30 | Did we decide to launch in the US in Q4? | **NO DECISION** (N10; conditional on Redline signing, which hasn't happened) |

---

## 9. Facts ledger (canonical numbers)
PayForge 2.9% + €0.30 · Ledgerly 2.3% + €0.25 · monthly processed ≈ €310k · saving ≈ €1,860/mo · Starter €49 → €59 · 140 Starter accounts · Scan Pack €0.08/scan · Pro includes 500 scans · Migration cap €18,000 (agency quote €34k) · p95 latency +40 ms · v3 dates: Apr 15 → May 13 · 41 P1 bugs · Redline ≈ 18% of revenue · discount 15% → 10% · gross-margin floor 68% · Swiftbox SLA 99.99% → 99.9% · Harbor Express overdue €27,400 · 9 affected customers · pentest €12,000 (alt €9k) · office €6,200/mo, sublet ≈ €3,100/mo · LogiConnect Silver €6,000 → booth €2,500 · rebrand cost ≥ €8k · senior backend budget €95k, offer €92k + 0.15% · Helpdesk renewal +40%.
