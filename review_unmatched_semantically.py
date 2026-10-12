#!/usr/bin/env python3
"""Create a transparent semantic-triage audit for the longer unmatched reviews.

This is a snapshot-specific, LLM-assisted adjudication artifact. It does not
silently rewrite theme counts: only the eight explicit signals already encoded
as regression-tested, repeatable rules are assigned to a named theme; vague
sentiment remains in the unmatched bucket.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pandas as pd
from moveinsync_ratings_monitor import classify

ROOT = Path(__file__).parent
OUT = ROOT / "output"
SOURCE = ROOT / "reviews.csv"

PROMOTIONS = {
    "this application is pathetic. not able to provide information": (
        "Booking / schedule / roster",
        "Explicitly says the app does not provide information and keeps employees uninformed; treated as missing trip/service information, not as a confirmed technical cause.",
    ),
    "very bad app not work": (
        "General app reliability / performance",
        "Explicit statement that the app does not work; no specific module or cause is named.",
    ),
    "stupid app showing no address": (
        "Booking / schedule / roster",
        "Explicitly reports a missing address, which blocks understanding of trip details.",
    ),
    "only good for initial one month don't show any details anymore": (
        "Booking / schedule / roster",
        "Explicitly reports that details are no longer visible; treated as trip/information visibility.",
    ),
    "chamging an address requires too much effort": (
        "UI / release / usability",
        "Explicit address-edit friction and difficulty locating the intended place.",
    ),
    "scanning qr to board cab was really cool": (
        "UI / release / usability",
        "Compares the boarding interaction with another app; this is a feature/flow comparison, not evidence of an actual safety incident.",
    ),
    "not updated every thing on time": (
        "General app reliability / performance",
        "Explicit complaint about information/update timeliness, but the exact field or subsystem is not specified.",
    ),
    "efmem is more reliable": (
        "General app reliability / performance",
        "Reliability comparison against another provider without a specific failure or route detail.",
    ),
}


def main() -> None:
    df = pd.read_csv(SOURCE, parse_dates=["at"])
    latest = df["at"].max()
    low = df[(df["at"] > latest - pd.Timedelta(days=365)) & (df["score"] <= 3)].copy()
    low["word_count"] = low["content"].fillna("").str.split().str.len()
    low["current_rule_theme"] = low["content"].apply(lambda x: classify(x)[0])
    lowered = low["content"].fillna("").str.lower()
    hit_promotions = pd.Series(False, index=low.index)
    for phrase in PROMOTIONS:
        hit_promotions |= lowered.str.contains(phrase, regex=False, na=False)
    long_other = low[(low.current_rule_theme == "No specific detail / other") & (low.word_count > 3)]
    promotions = low[hit_promotions]
    candidates = pd.concat([long_other, promotions]).drop_duplicates(subset=["at", "score", "appVersion", "content"])
    candidates = candidates[candidates.word_count > 3].sort_values("at").copy()

    rows = []
    for r in candidates.itertuples(index=False):
        content = str(r.content)
        text = content.lower()
        matched = next(((phrase, theme, reason) for phrase, (theme, reason) in PROMOTIONS.items() if phrase in text), None)
        if matched:
            phrase, semantic_theme, rationale = matched
            capture = True
        else:
            semantic_theme = "No specific detail / other"
            capture = False
            if "accuracy" in text:
                rationale = "The review says accuracy is poor but does not specify ETA, GPS, booking status or another measurable object; assigning a specific theme would require guessing."
            elif any(term in text for term in ["service", "company", "team", "corporate", "efmfm", "uber", "driving"]):
                rationale = "Broad service/company or competitor opinion without a specific ride-stage event, named feature failure or reproducible symptom; retain as unmatched rather than infer an owner."
            elif any(term in text for term in ["reminds me about office", "not useful", "not good", "worst", "pathetic", "irritating", "terrible", "rubbish", "disgusting", "waste", "not recommend"]):
                rationale = "General sentiment or preference only; no concrete failure or journey stage is specified."
            else:
                rationale = "Longer text reviewed; there is not enough specific evidence to assign a product/operations theme without inference."
        version = "" if pd.isna(r.appVersion) else str(r.appVersion)
        key = hashlib.sha256(f"{pd.Timestamp(r.at).isoformat()}|{int(r.score)}|{version}|{content}".encode("utf-8")).hexdigest()
        rows.append({
            "review_key_sha256": key,
            "review_date": pd.Timestamp(r.at).date().isoformat(),
            "stars": int(r.score),
            "app_version": version,
            "word_count": int(r.word_count),
            "review_text": content,
            "pre_refinement_status": "Unmatched under pre-refinement rules",
            "semantic_adjudicated_theme": semantic_theme,
            "captured_by_refined_rule": bool(capture),
            "rationale": rationale,
        })
    out = pd.DataFrame(rows)
    if len(out) != 55:
        raise ValueError(f"Expected 55 longer pre-refinement unmatched reviews, got {len(out)}")
    if int(out["captured_by_refined_rule"].sum()) != 8:
        raise ValueError(f"Expected 8 explicitly captured themes, got {int(out['captured_by_refined_rule'].sum())}")
    out.to_csv(OUT / "semantic_triage_unmatched.csv", index=False)
    remaining = int((~out["captured_by_refined_rule"]).sum())
    summary = {
        "snapshot_latest_review": latest.date().isoformat(),
        "pre_refinement_long_unmatched_review_count": int(len(out)),
        "explicit_signals_captured_by_refined_rules": int(out["captured_by_refined_rule"].sum()),
        "remaining_vague_or_underspecified_long_comments": remaining,
        "remaining_short_unmatched_comments_three_words_or_fewer": int(((low.current_rule_theme == "No specific detail / other") & (low.word_count <= 3)).sum()),
        "current_primary_unmatched_total": int((low.current_rule_theme == "No specific detail / other").sum()),
        "current_primary_unmatched_share": float((low.current_rule_theme == "No specific detail / other").mean()),
        "method_note": "LLM-assisted semantic review of the 55 longer comments in the pre-refinement unmatched set. Eight explicit signals were translated into durable regex rules and regression tests. The remaining 47 were intentionally kept unmatched because they were generic or underspecified. This is a snapshot-specific adjudication aid, not an independently benchmarked production LLM classifier; the separate 100-review validation remains model-assisted and not independently double-coded.",
    }
    (OUT / "semantic_triage_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
