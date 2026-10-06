# Precedent scorecard

_Synthetic corpus; ground truth hidden from the pipeline._  commit `ffe7db6`

| Metric | Target | Dev (`ffe7db6`) | Holdout (`0de46ce`) |
|---|---|---|---|
| Decision recall | >= 85% | 96% (25 GT) | 87% (15 GT) |
| Decision precision | >= 85% | 67% (36 predicted) | 46% (28 predicted) |
| Unmatched predictions judged genuine decisions (not in the 40 planted) | context | 10 of 12 | 12 of 15 |
| Near-decision false positives | <= 2 of 10 | 0 of 5 | 0 of 5 |
| Supersession-link accuracy | >= 80% | 80% (kind 80%) | 33% (kind 33%) |
| Status accuracy (matched) | - | 92% | 92% |
| Conflicts detected | >= 2 of 3 | 2 of 2 | 0 of 1 |
| Evidence support | >= 90% | 100% (strict 97%) | 100% (strict 100%) |
| Q&A accuracy | >= 85% | 68% of 19 | 68% of 11 |
| 'No decision' correct | 5/5 | 4/4 | 1/1 |
| Answer latency p50 | < 8 s | 8.9 s | 17.3 s |
| Triage recall | >= 98% | 100% | 100% |

Quote validity (all verified quotes are verbatim substrings): **100%** of 487 quotes. Pipeline wall-clock (Stages 1-5): **4.8 min**.

## Dev: decisions

| GT | Result | Status (GT -> predicted) | Predicted |
|---|---|---|---|
| D01 | hit | superseded -> superseded | Stay on PayForge until Q2 2026 and revisit the switch to Ledgerly after the v3 launch. |
| D02 | hit | amended -> active | Switch the payment processing from PayForge to Ledgerly, with a cutover date to be determi |
| D03 | miss | amended -> - |  |
| D04 | hit | active -> active | Cutover from PayForge to Ledgerly is set for Monday 6 July 2026, after the June 30 billing |
| D05 | hit | amended -> amended | Raise Starter plan from €49 to €59/month, effective 1 March 2026, with 4 weeks customer no |
| D06 | hit | active -> active | Existing Starter accounts remain at €49 for 12 months; new signups pay €59 from 1 March 20 |
| D07 | hit | superseded -> superseded | Approve a usage-based Scan Pack add-on at €0.08 per scan with a generous free allowance, p |
| D08 | hit | active -> active | Drop the Scan Pack add-on entirely and include 500 scans per month in the Pro plan, and ke |
| D09 | hit | amended -> amended | Migrate hosting from NimbusHost to Corvid Cloud, including app tier and managed Postgres,  |
| D10 | hit | active -> active | Approve Greg Ferrante for the Corvid migration with a firm budget cap of EUR 18,000 all-in |
| D11 | hit | active -> active | The app tier cutover to Corvid will take place on Saturday 18 – Sunday 19 April, with Ravi |
| D12 | hit | active -> active | Keep the production database on NimbusHost managed Postgres; only the app tier moves to Co |
| D13 | hit | superseded -> superseded | V3 will launch on Wednesday 15 April 2026, with Corvid hosting migration taking priority i |
| D14 | hit | amended -> active | The V3 launch is moved to the week of 11 May 2026, with RC freeze the week before. |
| D15 | hit | amended -> amended | Offline mode for the driver app is cut from v3 (mid-May launch) and deferred to v3.1; rout |
| D16 | hit | active -> active | Read-only offline mode (cached routes and manifests, no editing) is added back into v3 for |
| D17 | hit | active -> active | The driver app will be built with React Native, with a budget of ~15% platform-specific na |
| D18 | hit | active -> active | V3 rollout will be phased: 20% of accounts on Wednesday 13 May, reaching 100% by Wednesday |
| D19 | hit | active -> active | Approve one senior backend engineering hire with a budget ceiling of EUR 95,000 per annum  |
| D20 | hit | active -> active | Extend an offer to Elena Voss for the senior backend role at EUR 92,000 per annum and 0.15 |
| D21 | hit | amended -> amended | Implement a trial of meeting-free Wednesdays for internal meetings only, with existing rec |
| D22 | hit | active -> active | Pause Focus Wednesdays until 15 June 2026, then resume the previous meeting-free arrangeme |
| D23 | hit | active -> active | Engage Kofi Mensah as a QA contractor starting Monday 20 April, three days per week throug |
| D38 | hit | contested -> contested | The Pro plan first-response SLA was set at the March 25 leadership meeting, but the durati |
| D39 | hit | contested -> contested | The on-call rotation structure is contested between a two-person weekly alternation of Jon |

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
