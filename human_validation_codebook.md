# Independent human validation: 50 blind low-rated reviews

## Purpose
Use this sheet to measure the rule classifier against an independent human reader. The spreadsheet deliberately does not show the classifier's predicted labels. Please ask a reviewer who has not seen the report or predictions to label each review independently.

## Instructions for the human reviewer
1. Read the review text and rating; do not use the app-version field (it is not included) or the report's predicted labels.
2. Assign exactly one **primary theme**: the single issue most central to the complaint. If multiple issues appear, choose the one that most directly explains the low rating or the most blocking problem.
3. Choose `No specific detail / other` only if the text does not support a specific category.
4. Do not guess a root cause; label what the reviewer reports, not why it happened.
5. Fill `human_primary_theme` with one exact category name from the list below. Add an optional short rationale in `human_note`.

## Primary-theme labels
- Safety / security
- Install verification / Play Store error
- OTP / login / session
- App launch / crash
- ETA / tracking / location
- Booking / schedule / roster
- Rating prompts / notifications
- Policy / permission prompts
- UI / release / usability
- Support / escalation
- General app reliability / performance
- Transport operations / driver / route
- No specific detail / other

## Evaluation
After all 50 rows are labeled, save the completed file as `human_validation_50_completed.csv` in the project folder and run:

```bash
python evaluate_human_validation.py --input human_validation_50_completed.csv
```

The script reports exact accuracy, per-theme precision/recall/F1, and a confusion matrix against the rule-based primary labels. Do not describe the result as a perfect measure of truth: one human coder is a reference label, and reasonable disagreement can occur when reviews mention multiple issues. The report should say who labeled the sample, that the labeling was blind to model output, and the resulting accuracy only after the completed worksheet is returned.
