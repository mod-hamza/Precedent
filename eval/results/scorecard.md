# Precedent scorecard

_Synthetic corpus; ground truth hidden from the pipeline._  commit `0de46ce`

| Metric | Target | Dev | Holdout |
|---|---|---|---|
| Decision recall | >= 85% | 98% (25 GT) | 87% (15 GT) |
| Decision precision | >= 85% | 74% (33 predicted) | 46% (28 predicted) |
| Unmatched predictions judged genuine decisions (not in the 40 planted) | context | 8 of 8 | 12 of 15 |
| Near-decision false positives | <= 2 of 10 | 0 of 5 | 0 of 5 |
| Supersession-link accuracy | >= 80% | 90% (kind 90%) | 33% (kind 33%) |
| Status accuracy (matched) | - | 88% | 92% |
| Conflicts detected | >= 2 of 3 | 2 of 2 | 0 of 1 |
| Evidence support | >= 90% | 100% (strict 100%) | 100% (strict 100%) |
| Q&A accuracy | >= 85% | 68% of 19 | 68% of 11 |
| 'No decision' correct | 5/5 | 4/4 | 1/1 |
| Answer latency p50 | < 8 s | 15.8 s | 17.3 s |
| Triage recall | >= 98% | 100% | 100% |

Quote validity (all verified quotes are verbatim substrings): **100%** of 478 quotes. Pipeline wall-clock (Stages 1-5): **9.8 min**.

## Dev: decisions

| GT | Result | Status (GT -> predicted) | Predicted |
|---|---|---|---|
| D01 | partial | superseded -> superseded | Stay on PayForge until Q2 and revisit the migration to Ledgerly after the v3 launch. |
| D02 | hit | amended -> active | Switch payment processing from PayForge to Ledgerly. |
| D03 | hit | amended -> active | The cutover from PayForge to Ledgerly is moved to after the June billing cycle, with Dev R |
| D04 | hit | active -> active | The Ledgerly cutover is fixed for Monday 6 July 2026, with PayForge termination notice sen |
| D05 | hit | amended -> amended | Raise Starter plan pricing from €49 to €59 per month, effective 1 March 2026, with 4 weeks |
| D06 | hit | active -> active | Existing Starter accounts are grandfathered at €49 for 12 months; new signups pay €59 from |
| D07 | hit | superseded -> superseded | Approve a usage-based 'Scan Pack' add-on at €0.08 per scan beyond a free allowance, with a |
| D08 | hit | active -> active | Drop Scan Pack and include 500 scans/month in the Pro plan; keep it out of the cutover. |
| D09 | hit | amended -> amended | Migrate hosting from NimbusHost to Corvid Cloud, with NimbusHost cancellation before 15 Ma |
| D10 | hit | active -> active | Approve Greg Ferrante (external contractor) for the Corvid migration with a firm budget ca |
| D11 | hit | active -> active | The app tier cutover will take place on Saturday 18 – Sunday 19 April, with Ravi shadowing |
| D12 | hit | active -> active | Keep the production database on NimbusHost managed Postgres and move only the app tier to  |
| D13 | hit | superseded -> superseded | Launch v3 on Wednesday 15 April. |
| D14 | hit | amended -> active | Move the v3 launch from 15 April to the week of 11 May, with RC freeze the week before. |
| D15 | hit | amended -> amended | Cut offline mode for the driver app from the mid‑May launch (v3) and defer it to v3.1; rou |
| D16 | hit | active -> active | Read-only offline mode (cached routes and manifests, no editing) is pulled back into v3 sc |
| D17 | hit | active -> active | The driver app will be built using React Native (single codebase), with an estimated ~15%  |
| D18 | hit | active -> active | Use a phased v3 rollout: 20% of accounts (including Swiftbox) on Wednesday 13 May, 100% by |
| D19 | hit | active -> active | Approve one senior backend engineering hire at a budget of up to EUR 95,000 per annum (exc |
| D20 | hit | active -> active | Offer Elena Voss the position of Senior Backend Engineer at EUR 92,000 salary plus 0.15% e |
| D21 | hit | amended -> amended | Implement a trial of meeting-free Wednesdays (internal meetings only, client-facing calls  |
| D22 | hit | active -> active | Pause Focus Wednesdays until June 15, 2026, to allow daily rollout syncs, after which the  |
| D23 | hit | active -> active | Engage Kofi Mensah as a QA contractor at three days per week from Monday 20 April through  |
| D38 | hit | contested -> contested | Pro customers get a first-response SLA of either 2 business hours (as per Lena Fischer's m |
| D39 | hit | contested -> contested | The on-call rotation starts next week with two people alternating weekly: Jonas Eklund one |

## Holdout: decisions

| GT | Result | Status (GT -> predicted) | Predicted |
|---|---|---|---|
| D24 | miss | superseded -> - |  |
| D25 | hit | active -> active | The discount offered to Redline Couriers for the 2-year renewal is capped at 10%, overridi |
| D26 | hit | active -> active | Parcelwise will not commit to 99.99% monthly uptime; the contractual SLA with Swiftbox wil |
| D27 | hit | active -> active | Suspend Harbor Express service at the 60-day overdue mark, terminate at 90 days if the €27 |
| D28 | hit | active -> active | Rotate all API keys and customer integration tokens (not just the exposed staging key) in  |
| D29 | hit | active -> active | Notify all 9 customers potentially affected by the leaked credentials by Friday 6 March, w |
| D30 | hit | active -> active | All staff accounts (email, Git host, cloud consoles, admin panels) must have 2FA enabled b |
| D31 | hit | active -> active | Parcelwise engages Blackthorn Audit for a third-party penetration test of the production e |
| D32 | miss | amended -> - |  |
| D33 | hit | active -> active | Sublet the first floor of the Keizersgracht office starting 1 June 2026, recovering approx |
| D34 | hit | superseded -> superseded | Commit to the Silver sponsorship tier at €6,000 for LogiConnect Europe 2026, including boo |
| D35 | hit | active -> active | Downgrade LogiConnect Europe 2026 sponsorship from Silver tier (€6,000) to booth-only (€2, |
| D36 | hit | active -> active | Keep the company name Parcelwise and do not proceed with the rebrand to Routewell; redirec |
| D37 | hit | active -> active | Switch from Helpdesk-Co to Beacon Desk effective July 1, 2026, accepting Beacon Desk's quo |
| D40 | hit | contested -> superseded | Marta Kowalczyk approved Chloe Winters' Q2 marketing budget request of €40,000. |
