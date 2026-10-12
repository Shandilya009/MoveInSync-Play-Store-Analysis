# Validation summary

**Project:** MoveInSync employee app — public Play Store review diagnosis and action plan  
**Snapshot date:** 13 October 2026  
**Latest review timestamp in dataset:** 11 October 2026  
**Live listing check (13 Oct 2026):** official India Play Store page displayed 4.3 stars and 1.15L reviews (rounded); listing last updated 8 Oct 2026. The iOS page displayed 4.7/5 from 60k ratings.

## Reproduction and checks

- Frozen input: 24,315 English-language written reviews returned for the India Google Play listing, 14 March 2014–11 October 2026.
- Current rolling written-review windows: 30 days (243 reviews; mean 3.77; one-star 27.2%), 90 days (721; mean 3.81; one-star 24.7%), and 365 days (2,848; mean 3.84; one-star 24.0%).
- Low-rated theme set: 843 written reviews rated 1–3 stars in the 365-day window.
- Primary-theme rule labels are exclusive. Multi-label mention counts overlap. Counterfactual uplift values in `output/theme_impact_scenarios.csv` are arithmetic sensitivity only, not a forecast.
- Classifier validation: fixed 100-review prediction-blind, single-pass model-assisted adjudication; 82/100 exact primary-theme matches (82%; Wilson 95% interval 73.3%–88.3%; macro-F1 0.763; weighted-F1 0.809). This is a directional check, not independently double-coded or a certified human benchmark.
- Automated tests: **43 passed** — 32 classifier regression tests, eight snapshot/integrity/metric/privacy/replay/score-bridge checks, and three alert tests.
- Render QA: the detailed report is expected to render to 11 pages (including the full-theme counterfactual appendix); the decision brief is one page. Both PDFs were rendered from the final Word documents and visually inspected for clipping and blank section pages.
- The public Google Play metadata was refreshed through the official listing page, and AppBrain was checked for Android version context. A fresh structured review scrape was attempted locally but not run: the `google-play-scraper` dependency was absent, and package-index access failed due to DNS/network restrictions, so the saved review snapshot remains unchanged. The GitHub Actions workflow has not been triggered remotely because no connected repository was available. Do not claim either was executed.

## Listing-score reconciliation

The previous 4.64/114,880 figure is not used. The official India Google Play page displayed 4.3 stars and 1.15L reviews (rounded) on 13 October 2026 and showed the app listing was updated 8 October 2026. The iOS App Store page displayed 4.7/5 from 60k ratings the same day. AppBrain's independent Android tracker showed 12.20.0 and 4.32/114,644 on 12 Oct. Google says the public Play rating is weighted toward recent ratings. All 24,315 collected written texts average 3.61; the 21,467 texts older than 365 days average 3.58, while the most recent 365-day window averages 3.84. The 30-day mean is lower at 3.77, though month-to-month values are volatile. Review metadata `12.19.0` is an Android label; AppBrain showed Android `12.20.0` as current and Apple’s iOS history showed `10.50.0`. This likely reflects separate platform release-numbering sequences. Confirm exact Play Console rollout/build mapping before causal attribution.

## Interpretation guardrails

- Written reviews are self-selected and do not represent every commute or employee.
- The dataset covers English-language reviews returned for India; Hindi and other regional-language review coverage was not measured.
- India iOS listing displayed 4.7/5 from 60k ratings on 13 October 2026, compared with Android at 4.3/5. This 0.4-star gap is a clue to investigate Android-specific auth/install/launch issues, not proof of platform causality.
- Theme counts are diagnostic signals, not incident rates. Public text does not establish root cause or causality.
- Validate suspected causes against internal app, authentication, booking and transport-operations telemetry.

## Reproduce locally

```bash
python -m pip install -r requirements.txt
python moveinsync_ratings_monitor.py --csv reviews.csv --output-dir output
python validate_classifier.py
python build_report.py
python -m unittest -v
```

## Store-score bridge (rough estimate only)

The package includes `output/store_score_bridge.csv`. It now sums the star-point deficits for the actually affected groups and divides by the approximate rounded whole-listing count: OTP/login adds 331 points across 123 reviews, or about +0.003 under an equal-weight 115,000-rating model; OTP/login plus booking adds 638 points across 234 reviews, or about +0.006. This is not a forecast: the public counter is rounded, the text dataset is self-selected, and Google weights recent ratings.

## Independent human-label check

`human_validation_50_blind.csv` and `human_validation_codebook.md` provide a prediction-blind sample for an independent human reader. This worksheet has not been returned with human labels, so no human accuracy claim is made yet. Once filled and saved as `human_validation_50_completed.csv`, run `python evaluate_human_validation.py --input human_validation_50_completed.csv`.
