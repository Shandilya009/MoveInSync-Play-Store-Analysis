#!/usr/bin/env python3
"""Evaluate blind human labels against the rule classifier's primary labels.

Run only after filling human_primary_theme in the 50-row template and saving it
as a completed CSV. The classifier labels are computed here, not shown in the
blind worksheet.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from moveinsync_ratings_monitor import classify


def metrics_for(true: pd.Series, pred: pd.Series, labels: list[str]) -> dict:
    rows=[]
    support_total=len(true)
    for label in labels:
        tp=int(((true==label)&(pred==label)).sum())
        fp=int(((true!=label)&(pred==label)).sum())
        fn=int(((true==label)&(pred!=label)).sum())
        support=int((true==label).sum())
        precision=tp/(tp+fp) if tp+fp else 0.0
        recall=tp/(tp+fn) if tp+fn else 0.0
        f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
        rows.append({'theme':label,'precision':precision,'recall':recall,'f1':f1,'support':support})
    exact=float((true==pred).mean()) if support_total else float('nan')
    macro=float(sum(r['f1'] for r in rows)/len(rows)) if rows else float('nan')
    weighted=float(sum(r['f1']*r['support'] for r in rows)/support_total) if support_total else float('nan')
    return {'n_labeled':support_total,'exact_accuracy':exact,'macro_f1':macro,'weighted_f1':weighted,'per_theme':rows}


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',default='human_validation_50_completed.csv')
    ap.add_argument('--output-dir',default='output/human_validation')
    args=ap.parse_args()
    path=Path(args.input)
    if not path.exists():
        raise SystemExit(f'Completed file not found: {path}. Fill the blind worksheet and save it under this name.')
    df=pd.read_csv(path).fillna('')
    required={'sample_id','review_text','human_primary_theme'}
    missing=required-set(df.columns)
    if missing:
        raise SystemExit(f'Missing required columns: {sorted(missing)}')
    df['human_primary_theme']=df['human_primary_theme'].astype(str).str.strip()
    empty=df['human_primary_theme'].eq('')
    if empty.any():
        raise SystemExit(f'{int(empty.sum())} human labels are blank; label all rows before evaluation.')
    df['rule_primary_theme']=df['review_text'].apply(lambda t: classify(t)[0])
    labels=sorted(set(df['human_primary_theme']) | set(df['rule_primary_theme']))
    result=metrics_for(df['human_primary_theme'],df['rule_primary_theme'],labels)
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    row_results=df[['sample_id','human_primary_theme','rule_primary_theme']].copy()
    row_results['exact_match']=row_results['human_primary_theme'].eq(row_results['rule_primary_theme'])
    row_results.to_csv(out/'human_validation_row_results.csv',index=False)
    cm=pd.crosstab(df['human_primary_theme'],df['rule_primary_theme'],dropna=False).reindex(index=labels,columns=labels,fill_value=0)
    cm.to_csv(out/'human_validation_confusion_matrix.csv')
    result['warning']='Single-human reference labels are a comparison baseline, not error-free ground truth. Document independent blind labeling and adjudicate ambiguous cases.'
    (out/'human_validation_metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'per_theme'}},indent=2))
    print('Per-theme metrics:',out/'human_validation_metrics.json')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
