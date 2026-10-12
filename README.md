# MoveInSync | Play Store review diagnosis & action plan

**Start with the brief, then the report.**

Open `MoveInSync_Decision_Brief.pdf` first for the recommendation and priorities, then read `MoveInSync_Play_Store_Ratings_Report.pdf` for the supporting evidence and limitations. The editable Word files are included if you need to inspect or adapt the documents.

A reproducible evidence-to-action project for the MoveInSync Forward Deployed Engineer candidate assignment.

## Submission note

I reviewed 24,315 public, English-language written reviews for the MoveInSync employee app on the India Google Play listing. The dataset is a saved snapshot dated through 11 October 2026, not a fresh live scrape. Using Python and pandas, I compared recent rating windows and monthly trends, looked at version and developer-reply patterns, grouped recurring complaints, and calculated a few hypothetical rating-impact scenarios.

A word-boundary regular-expression classifier assigns one primary theme to each low-rated review. A separate multi-label view records other issues mentioned in the same review, so overlapping themes are not treated as separate reviews. In a 100-review sample checked without showing the predictions during the check, the model-assisted review agreed with the primary labels 82% of the time. This is a directional quality check, not independent human validation. A separate 50-review blind worksheet and codebook are included for an independent reviewer, and that review is still pending.

I checked the public listing metadata on 13 October 2026: Google Play showed 4.3 stars and about 115,000 reviews; iOS showed 4.7/5 from about 60,000 ratings. A fresh structured review scrape could not run because the scraper dependency was unavailable and package-index network access failed. The first remote GitHub Actions run is also pending because the project has not been connected to an authenticated repository.

Tools used: Python, pandas, regular expressions, matplotlib, python-docx, the google-play-scraper package, a GitHub Actions workflow, and AI assistance. Public reviews help identify where to investigate, but they cannot establish root cause. The next step is to validate these signals against internal app, authentication, booking, and transport data.

## Recommendation in one sentence

Google Play shows **4.3/5** (1.15L displayed reviews) versus **4.7/5** on iOS (60k ratings), a useful but non-causal platform clue. **Reply to negative reviews today; investigate OTP/login first.** If all 123 low-rated OTP/login **primary-theme** reviews became 4 stars, the 365-day written mean would rise by **+0.116** (3.84 to 3.95). If those 123 reviews alone were lifted to 4 stars, a simple equal-weight calculation over ~115,000 displayed ratings gives about **+0.003 whole-listing points**; OTP plus booking together gives about **+0.006**. This is only an arithmetic bridge: the count is rounded and the public Play score is recency-weighted, so the true movement is not calculable from public text alone and the displayed rating would likely still read 4.3.

## Dated source snapshot — 13 October 2026

- Official India Google Play listing: **4.3 stars; 1.15L reviews** as displayed on 13 Oct 2026. The displayed count is rounded, and an exact count was not exposed in the live page. An AppBrain third-party tracker showed Android **12.20.0** (last updated 8 Oct); Apple’s iOS version history shows **10.50.0**. These are separate platform version sequences.
- Frozen review dataset: **24,315 public English-language written reviews**, 14 Mar 2014–11 Oct 2026, returned by `google-play-scraper` using `lang=en`, `country=in`.
- Written-review windows (not the same measure as the displayed store score): 30 days **n=243, mean 3.77, one-star 27.2%**; 90 days **n=721, mean 3.81, one-star 24.7%**; 365 days **n=2,848, mean 3.84, one-star 24.0%**.
- Current concern: the latest 30-day written mean sits below the 90- and 365-day means, monthly values are volatile, and only **1 of 73** recent 1–2-star reviews has a recorded developer reply in the snapshot. This is a problem signal, not proof of a single cause.
- The review dataset labels 105 reviews as Android version `12.19.0` (mean 3.62; 31.4% one-star). AppBrain showed Android `12.20.0` as current on 12 Oct, while `10.50.0` belongs to the iOS App Store sequence. This makes the cross-platform mismatch plausible; still confirm actual Play Console rollout/build IDs before attributing a spike to a release.

## Why the store score and written-review scores differ

They are different populations and measurements. Google states the user-facing Play rating is weighted toward more recent ratings. Most raters do not necessarily leave written text, the text sample is self-selected and limited here to English reviews returned for India, and the all-history text mean includes older reviews dating back to 2014. The all-time written-text mean is 3.61; reviews older than 365 days average 3.58, versus 3.84 in the recent 365-day window. The recent 30-day mean (3.77) is below the 90-day (3.81) and 365-day (3.84) means, although month-to-month values are volatile rather than a proven straight-line decline. The Android–iOS rating gap is a clue to investigate auth/install/launch friction on Android, not proof that platform differences caused the gap.

## Key findings and prioritisation

The 365-day theme set includes **843 reviews rated 1–3 stars**. Primary-theme labels are mutually exclusive; “all issue mentions” can overlap.

| Priority | Signal | What to do next |
|---|---|---|
| P0 | Public response coverage has fallen from 96.9% (2023) to 1.1% (2026 YTD) among 1–2-star reviews in this sample | Assign a daily review owner, a 48-hour reply target, real support routing and same-day safety escalation. |
| P0 | OTP/login/session is the largest actionable primary theme (123 reviews; 124 in the overlapping any-mention view) | Measure send/delivery/verification and session-expiry failure by provider, device and time before changing authentication behaviour. |
| P0 | Booking/schedule/roster is the next largest actionable primary theme (111 reviews) | Make Confirmed / Waitlisted / Cancelled state explicit; reconcile status, retry and push notifications. |
| P1 | ETA/tracking/location (86 primary-tag reviews) and transport operations/driver/route (71) | Compare predicted vs actual pickup; separately review route/vendor late-pickup clusters with transport desk. |
| P1 | App launch/crash and Play Store install-verification complaints spike in the monthly mention series | Reproduce update/launch paths and compare exact build, device and Android timelines against crash/ANR telemetry. |
| P1 | Forced rating prompts are lower-volume but cheap to address | Add Skip; never block booking or trip details behind a store-rating request. |

Full per-theme “if every review became 4 or 5 stars” calculations are in `output/theme_impact_scenarios.csv`. The equal-weight arithmetic bridge is exported in `output/store_score_bridge.csv`: OTP adds 331 missing star-points across 123 affected reviews, equal to about +0.003 across ~115,000 listing ratings; OTP plus booking adds 638 points across 234 reviews, about +0.006. This is a more transparent count-based illustration than scaling by all historical written rows. It still does not replicate Google’s recency-weighted score. These are deliberately extreme counterfactuals, not predictions of the rating shown in the store.

## Project contents

```text
MoveInSync_Masterpiece_Submission/
├── START_HERE.txt                       # opening instructions
├── RUN_STATUS.md                        # transparent live-check / workflow status
├── MoveInSync_Decision_Brief.pdf / .docx
├── MoveInSync_Play_Store_Ratings_Report.pdf / .docx
├── submission_note.md
├── reviews.csv                         # frozen, identifier-minimized text snapshot
├── snapshot_metadata.json              # dated public-source capture and scope
├── source_capture.md                   # live listing values, date and source links
├── moveinsync_ratings_monitor.py        # analysis, impact table, alerts, history
├── build_report.py                     # charts and Word reports from snapshot
├── test_classifier.py                  # classifier regression tests
├── test_snapshot.py                    # snapshot/metric/privacy/replay checks
├── test_monitor_alerts.py               # threshold behaviour tests
├── validate_classifier.py               # 100-review model-assisted quality check
├── human_validation_50_blind.csv         # blind worksheet for independent human labeling
├── human_validation_codebook.md          # instructions and exact category labels
├── evaluate_human_validation.py          # computes precision/recall/F1 after labels are returned
├── review_unmatched_semantically.py     # fixed semantic-triage audit for 55 longer residual comments
├── requirements.txt
├── data_dictionary.md
├── validation_summary.md
├── .github/workflows/weekly-play-store-monitor.yml
├── monitor_history/history.csv          # aggregate baseline only
└── output/                               # reproducible summaries, charts, audit labels and logs
```

## Reproduce the frozen analysis (no network required)

Python 3.10+ is recommended.

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python moveinsync_ratings_monitor.py --csv reviews.csv --output-dir output
python validate_classifier.py
python review_unmatched_semantically.py
python build_report.py
python -m unittest -v
```

The frozen report is rebuilt from `reviews.csv`; it does **not** refresh the public store listing metadata or update the longitudinal history. The submitted snapshot's tests should all pass locally. Current validation includes 32 classifier regression cases, eight snapshot/integrity/metric/privacy/replay/score-bridge checks, and three alert tests (43 in total). The snapshot-specific semantic triage can be recreated with `python review_unmatched_semantically.py`; it documents 55 longer comments in the initial residual set, eight explicit patterns added to the rules, and 47 comments kept unmatched because their wording was too vague.

## Run a fresh collection manually

A live run needs internet access and depends on the public listing/scraper being reachable:

```bash
python moveinsync_ratings_monitor.py --recent-days 400 --output-dir output
```

This fetches a recent slice sufficient for 365-day windows, writes current summaries and threshold alerts, and updates `output/history.csv`. Re-running live on the same local date replaces that date's aggregate history observation. Saved-CSV replay never appends a false new observation.

## Weekly monitor (GitHub Actions)

The repository includes `.github/workflows/weekly-play-store-monitor.yml`, scheduled for **Monday 08:00 India time** and manually runnable with `workflow_dispatch`. The workflow has not run on GitHub Actions yet. A local structured scrape was attempted on 13 Oct 2026 but could not run: `google-play-scraper` was missing and package-index access failed because of DNS/network restrictions. The live listing metadata was independently refreshed from the official public page; `reviews.csv` was not replaced. After pushing the project to your own GitHub repository:

1. Enable GitHub Actions and allow the workflow `contents: write` permission so it can commit the aggregate-only history and selected aggregate report files (never the fetched review text or manual queue).
2. Trigger the workflow once with **Run workflow** and check the run log/artifact; this remains pending because no GitHub repository/connection was available in this workspace.
3. Review the commit for `monitor_history/history.csv` and selected `output/` aggregates, and download the artifact for the text pulse, current windows, theme/impact summaries and alert file.

Configured triage triggers: a 30-day mean drop of at least 0.15 versus the prior recorded run when both windows have at least 100 reviews; a version mean below 3.5 with at least 30 reviews; and a theme-share doubling when both samples meet minimum-volume guards. Rolling windows overlap and small samples are noisy, so alerts ask for investigation and do not automatically roll back a release. The weekly trend is meaningful only after multiple fresh runs.

## Classification and impact interpretation

Each 1–3-star review in the latest 365 days gets one **primary theme** for exclusive shares. Separately, the script extracts every matched **issue mention**, so one text can contribute to several mention categories. Counts in the two views should not be mixed or compared without the label. False-positive regressions are tested (including `hang` inside `change`, `rating` inside `frustrating`, and `late` inside `completely`).

The fixed 100-review prediction-blind model-assisted adjudication check shows **82% exact primary-theme agreement** (Wilson 95% interval about 73%–88%; macro-F1 about 0.76). This is not human validation. A 50-review blind worksheet and codebook are now included so an independent person can label a random subset without seeing rule predictions; the human result remains pending until those labels are completed. The unmatched queue is retained for further inspection; no-match means the rules did not understand the phrasing, not that a complaint is unimportant. The semantic-triage audit is in `output/semantic_triage_unmatched.csv` with rationale and rule-capture status.

Each impact scenario replaces only the ratings of one exclusive primary-theme group with 4 or 5, leaves all other observed scores unchanged, and divides by the 2,848 reviews in the latest 365-day window. It estimates a change in the **mean of this written-review sample only**. It does not estimate causal impact or predict the public Play Store score.

## Scope and limitations

- The official India Google Play listing was checked on 13 Oct 2026: 4.3/5, 1.15L reviews (rounded), last updated 8 Oct. Apple’s iOS page showed 4.7/5 from 60k ratings the same day. AppBrain’s third-party tracker showed Android version 12.20.0 and 4.32/114,644 on 12 Oct. The Android–iOS rating gap is a directional clue, not a controlled platform experiment.
- The review dataset has Android `12.19.0`; AppBrain listed Android `12.20.0` as available on 12 Oct 2026; Apple’s iOS listing shows `10.50.0`. These belong to separate platform version sequences. Confirm precise Android release/build and rollout metadata in Play Console before tying a spike to a release.
- Only English-language reviews from the India listing are included. A Hindi/localized listing exists, but Hindi and other regional-language reviews were not separately scraped or counted.
- The India iOS App Store listing displayed 4.7/5 from 60k ratings on 13 Oct 2026. This is directional context only—not a controlled comparison with Google Play because platforms, populations, app versions and rating mechanics differ.
- Reviews are self-selected; they do not represent every employee, commute, device, company or region. Counts are not incident rates.
- Public text cannot establish root cause, and developer-reply presence is not the same as support response time or ticket resolution. Validate with crash/ANR, authentication, booking, actual pickup, route and vendor data.

## Sources

- India Google Play listing (captured 13 Oct 2026): https://play.google.com/store/apps/details?hl=en_IN&id=com.moveinsync.ets
- Google Play rating methodology (states public rating is weighted toward recent ratings): https://support.google.com/googleplay/android-developer/answer/138230?hl=en-IN
- India iOS App Store listing (captured 13 Oct 2026): https://apps.apple.com/in/app/moveinsync/id962949521
- AppBrain Android listing metadata (third-party, capture 12 Oct 2026): https://www.appbrain.com/app/moveinsync/com.moveinsync.ets
