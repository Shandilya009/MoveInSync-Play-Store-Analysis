#!/usr/bin/env python3
"""Score the fixed 100-review, prediction-blind manual adjudication sample."""
from __future__ import annotations
import json
from pathlib import Path
import math
import pandas as pd
from moveinsync_ratings_monitor import prepare, classify

ROOT = Path(__file__).parent
OUT = ROOT / "output"
labels = pd.read_csv(OUT / "manual_validation_labels.csv")
df = prepare(pd.read_csv(ROOT / "reviews.csv", parse_dates=["at"]))
as_of = df["at"].max()
low = df[(df["at"] > as_of - pd.Timedelta(days=365)) & (df["score"] <= 3)].copy().reset_index(drop=True)
if len(labels) != 100 or labels["sample_row_id"].nunique() != 100:
    raise ValueError("The audit must contain exactly 100 unique review indexes.")
if labels["sample_row_id"].max() >= len(low):
    raise ValueError("Audit sample references rows outside the current low-rated review subset.")
rows = []
for r in labels.itertuples(index=False):
    review = low.iloc[int(r.sample_row_id)]
    pred, _owner = classify(review["content"])
    rows.append({
        "sample_row_id": int(r.sample_row_id),
        "review_date": pd.Timestamp(review["at"]).date().isoformat(),
        "score": int(review["score"]),
        "app_version": "" if pd.isna(review["appVersion"]) else str(review["appVersion"]),
        "manual_primary_theme": r.manual_primary_theme,
        "regex_primary_theme": pred,
        "exact_match": pred == r.manual_primary_theme,
        "adjudication_note": r.adjudication_note,
    })
res = pd.DataFrame(rows)
res.to_csv(OUT / "classifier_validation_results.csv", index=False)
acc = float(res["exact_match"].mean())
# Wilson interval for the observed agreement proportion.
n = len(res); z = 1.96; phat = acc
centre = (phat + z*z/(2*n))/(1+z*z/n)
half = z*math.sqrt((phat*(1-phat)+z*z/(4*n))/n)/(1+z*z/n)
classes = sorted(set(res["manual_primary_theme"]) | set(res["regex_primary_theme"]))
per_class=[]
for c in classes:
    tp=int(((res.manual_primary_theme==c)&(res.regex_primary_theme==c)).sum())
    fp=int(((res.manual_primary_theme!=c)&(res.regex_primary_theme==c)).sum())
    fn=int(((res.manual_primary_theme==c)&(res.regex_primary_theme!=c)).sum())
    per_class.append({"theme":c,"manual_support":int((res.manual_primary_theme==c).sum()),
                      "predicted_support":int((res.regex_primary_theme==c).sum()),
                      "precision":tp/(tp+fp) if tp+fp else None,
                      "recall":tp/(tp+fn) if tp+fn else None,
                      "f1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None})
pd.DataFrame(per_class).to_csv(OUT / "classifier_validation_by_theme.csv", index=False)
macro_f1=sum(x["f1"] for x in per_class if x["f1"] is not None)/sum(x["f1"] is not None for x in per_class)
weighted_f1=sum((x["f1"] or 0)*x["manual_support"] for x in per_class)/n
summary={"n_reviewed":n,"exact_primary_theme_agreement":acc,"exact_matches":int(res.exact_match.sum()),
         "wilson_95pct_interval":[max(0,centre-half),min(1,centre+half)],
         "macro_f1":macro_f1,"weighted_f1":weighted_f1,
         "method_note":"A fixed 100-review simple random sample was manually adjudicated without displaying the predicted label during label assignment. Single-pass, model-assisted adjudication; not independently double-coded. Treat results as a directional quality check rather than a certified benchmark.",
         "snapshot_latest_review":"2026-10-11","low_rated_population_n":len(low)}
(OUT/"classifier_validation_metrics.json").write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
print(pd.DataFrame(per_class).sort_values('manual_support',ascending=False).head(15).to_string(index=False))
