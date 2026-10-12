# Data dictionary

## Submitted review dataset: `reviews.csv`

One row per public written review in the frozen snapshot. The collection was returned by `google-play-scraper` using `lang=en` and `country=in`; review dates run from 14 March 2014 through 11 October 2026.

| Column | Type | Meaning |
|---|---|---|
| `content` | text | Public review text used for theme analysis. |
| `score` | integer, 1–5 | Star rating attached to the written review. |
| `at` | timestamp | Review timestamp returned by the collection tool. |
| `appVersion` | text / blank | App-version label in returned review metadata, where available. Some labels, including 12.19.0, do not reconcile with the live listing's visible 10.50.0 release-history entry and require internal build mapping. |
| `hasDeveloperReply` | boolean | Whether a non-empty developer reply existed in the source snapshot. Raw reply text and timestamp are not retained. |

Excluded fields: public display name, avatar URL, review ID, thumbs-up count, raw developer response and response timestamp. Review IDs were checked against the original supplied source before minimisation; no duplicate IDs were found in that original source. The current privacy-minimised export does not retain IDs, so a new dedupe check cannot be repeated from this file alone.

## Generated summaries

| File | Definition |
|---|---|
| `rating_windows.csv` | 30/90/365-day windows anchored to newest review timestamp; includes mean score, one-star share and reply rate among 1–2-star reviews. |
| `monthly_trend.csv` | Calendar month, written-review count, mean score and one-star share for the latest 12 months. October 2026 is partial through 11 Oct. |
| `developer_response_trend.csv` | Calendar-year count and reply rate among 1–2-star written reviews; the latest year is year-to-date. |
| `theme_summary.csv` | One **primary theme** per 1–3-star review in the latest 365 days. Shares are mutually exclusive and sum to 100% apart from rounding. |
| `theme_mentions.csv` | All issue mentions matched per low-rated review in the latest 365 days. A review can appear in multiple themes; percentages overlap. |
| `theme_impact_scenarios.csv` | Per-primary-theme arithmetic sensitivity for changing all scores in a group to 4 or 5, leaving other scores fixed. Not a forecast. |
| `monthly_theme_primary.csv` | Primary-theme share by month; exclusive categories. |
| `monthly_theme_mentions.csv` | All-issue mention share by month; overlapping categories. |
| `version_summary.csv` | Version-label statistics in the latest 365 days for labels with at least 10 written reviews. Labels require mapping to production build IDs before causal interpretation. |
| `version_theme_mentions.csv` | Overlapping issue mentions by version label. Do not sum themes within a version. |
| `journey_stage_summary.csv` | Exclusive mapping from primary theme to employee-journey stage; not a count of real trip incidents. |
| `journey_stage_mentions.csv` | Overlapping journey-stage indicators; do not sum counts across stages. |
| `classification_audit.csv` | Date, score, version, reply presence, primary theme, all matches and word count; no review text or reviewer identifiers. |
| `manual_review_queue.csv` | Current unmatched low-rated comment text for follow-up inspection; no reviewer identifiers. |
| `semantic_triage_unmatched.csv` | LLM-assisted audit of the 55 longer comments unmatched by the pre-refinement rules; eight specific issues are mapped to refined rules and 47 vague entries remain unmatched, with rationale. Snapshot-specific; do not treat as a live queue. |
| `semantic_triage_summary.json` | Count and method summary for the semantic triage. |
| `unanswered_reviews.csv` | Recent 1–2-star public review excerpts lacking a recorded developer response; minimise use and do not contact reviewers. |
| `data_quality.json` | Row count, date range, rating counts and data-minimisation notes. |
| `history.csv` | Aggregate monitoring observations appended only by live collection; replaying a saved CSV does not create a fresh observation. The GitHub workflow retains this aggregate history under `monitor_history/`. |
| `monitor_alerts.csv` | Live-run threshold flags; each flag is an investigation trigger, not an automatic decision. |

## Key denominators and labels

- Rating-window means and one-star shares use **all written reviews** in the rolling window.
- Theme analysis uses **1–3-star written reviews in the latest 365 days**.
- Developer-reply rates use **1–2-star written reviews**.
- **Primary-theme** share uses one exclusive label per low-rated review.
- **Any-mention** share uses all regex-matched issues; one review may contribute to multiple themes, so percentages can sum to more than 100%.
- Rating-lift scenarios describe only the mean of the frozen written-review sample, not the public Play Store score.
