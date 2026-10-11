"""Independent-reviewer comparison of explicitly checked ROS2 rate time ranges.

No consensus or reviewer agreement can independently establish physical fault
truth. Only durations both reviewers explicitly inspected are compared.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from .label_evaluation import _interval, evaluate_labels, NANO


def _ranges(labels: dict):
    entries = []
    for kind, key in (('positive','positive_intervals'), ('negative','negative_intervals')):
        for i, row in enumerate(labels.get(key, [])):
            start, end = _interval(row, f'{key}[{i}]')
            entries.append((start, end, kind))
    return sorted(entries)


def _state_at(rows, idx, start):
    while idx < len(rows) and rows[idx][1] <= start:
        idx += 1
    state = rows[idx][2] if idx < len(rows) and rows[idx][0] <= start < rows[idx][1] else 'unreviewed'
    return idx, state


def compare_reviewers(report: dict, left: dict, right: dict) -> dict:
    # The existing reviewed-label validator also checks SHA256, topic, type,
    # complete recording coverage and positive/negative label consistency.
    evaluate_labels(report, left)
    evaluate_labels(report, right)
    if left['recording_sha256'].lower() != right['recording_sha256'].lower() or left['topic'] != right['topic'] or left['message_type'] != right['message_type']:
        raise ValueError('Reviewers must annotate exactly the same recording SHA256, topic and message type')
    reviewer1, reviewer2 = left['reviewer'].strip(), right['reviewer'].strip()
    if reviewer1.casefold() == reviewer2.casefold():
        raise ValueError('Two distinct reviewer identifiers are required')
    a, b = _ranges(left), _ranges(right)
    boundaries = sorted(set(t for rows in (a,b) for x, y, k in rows for t in (x,y)))
    durations = {'positive_positive':0, 'negative_negative':0,
                 'positive_negative':0, 'negative_positive':0, 'only_left':0,
                 'only_right':0}
    disagreements=[]
    ai=bi=0
    for x,y in zip(boundaries,boundaries[1:]):
        if y<=x: continue
        ai,sa=_state_at(a,ai,x);bi,sb=_state_at(b,bi,x)
        if sa=='unreviewed' and sb=='unreviewed': continue
        if sa=='unreviewed': key='only_right'
        elif sb=='unreviewed': key='only_left'
        else: key=f'{sa}_{sb}'
        durations[key]+=y-x
        if key in ('positive_negative','negative_positive'):
            if disagreements and disagreements[-1]['end_ns']==x and disagreements[-1]['left']==sa and disagreements[-1]['right']==sb:
                disagreements[-1]['end_ns']=y
            else:
                disagreements.append({'start_ns':x,'end_ns':y,'left':sa,'right':sb})
    agree=durations['positive_positive']+durations['negative_negative']
    disagree=durations['positive_negative']+durations['negative_positive']
    joint=agree+disagree
    left_positive=durations['positive_positive']+durations['positive_negative']
    right_positive=durations['positive_positive']+durations['negative_positive']
    # Cohen's kappa over time-weighted *jointly reviewed* durations only.
    po=agree/joint if joint else None
    p_left=left_positive/joint if joint else None
    p_right=right_positive/joint if joint else None
    chance=(p_left*p_right + (1-p_left)*(1-p_right)) if joint else None
    kappa=(po-chance)/(1-chance) if joint and chance < 1 - 1e-12 else None
    return {
        'schema_version':'1.0', 'comparison_kind':'independent-operator-reviewer-agreement',
        'recording_sha256':left['recording_sha256'].lower(), 'topic':left['topic'],
        'message_type':left['message_type'], 'reviewers':[reviewer1,reviewer2],
        'jointly_reviewed_seconds':round(joint/NANO,6),
        'agreement_seconds':round(agree/NANO,6),
        'disagreement_seconds':round(disagree/NANO,6),
        'agreement_fraction':round(po,6) if po is not None else None,
        'cohens_kappa':round(kappa,6) if kappa is not None else None,
        'kappa_note':('undefined: no joint review or only one observed label category' if kappa is None else 'time-weighted over jointly reviewed intervals'),
        'both_positive_seconds':round(durations['positive_positive']/NANO,6),
        'both_negative_seconds':round(durations['negative_negative']/NANO,6),
        'single_reviewer_coverage_seconds':round((durations['only_left']+durations['only_right'])/NANO,6),
        'disagreement_interval_count':len(disagreements),
        'disagreement_intervals':disagreements[:500],
        'disagreement_intervals_truncated':len(disagreements)>500,
        'notes':[
            'Independent review is operator asserted, not independently audited.',
            'Agreement does not make either review a verified physical fault diagnosis.',
            'Disagreements require separate adjudication; no majority vote or truth merge is produced.',
            'Unreviewed time is never assumed negative.',
            'Kappa is undefined if there is no joint review or chance agreement is 100%.'
        ]
    }


def render_agreement_html(d: dict) -> str:
    fmt = lambda x: 'Not measurable' if x is None else str(x)
    rows=''.join(f'<tr><td>{x["start_ns"]}</td><td>{x["end_ns"]}</td><td>{escape(x["left"])}</td><td>{escape(x["right"])}</td></tr>' for x in d['disagreement_intervals'])
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Independent reviewer agreement</title><style>body{{margin:0;background:#0b1726;color:#e5eff7;font:15px system-ui}}main{{max-width:950px;margin:auto;padding:32px 22px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}}.stat,section{{background:#17283d;border:1px solid #304a65;border-radius:14px;padding:18px;margin:10px 0}}strong{{display:block;font-size:24px;color:#6edcca}}small{{color:#b4c6d7}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #384a5e;text-align:left}}.scroll{{overflow:auto}}</style><main><small>Robot Incident Analyzer v0.5.4 · human validation</small><h1>Independent reviewer agreement</h1><p>Topic: {escape(d['topic'])} · Reviewers: {escape(d['reviewers'][0])} and {escape(d['reviewers'][1])}</p><div class="grid"><div class="stat">Joint review<strong>{d['jointly_reviewed_seconds']} s</strong></div><div class="stat">Agreement<strong>{fmt(d['agreement_fraction'])}</strong></div><div class="stat">Cohen's κ<strong>{fmt(d['cohens_kappa'])}</strong></div><div class="stat">Disagreements<strong>{d['disagreement_interval_count']}</strong></div></div><section><h2>Disagreement intervals — manual adjudication required</h2><div class="scroll"><table><thead><tr><th>Start Unix ns</th><th>End Unix ns</th><th>Reviewer A</th><th>Reviewer B</th></tr></thead><tbody>{rows or '<tr><td colspan="4">No conflicting classifications within overlapping reviewed coverage</td></tr>'}</tbody></table></div></section><section><h2>Evidence boundaries</h2><p>Reviewed together: {d['jointly_reviewed_seconds']} s. Disagreement: {d['disagreement_seconds']} s. Single-reviewer coverage: {d['single_reviewer_coverage_seconds']} s. Unreviewed time is excluded from the denominator.</p><p><small>Agreement is not an independently confirmed robot failure label. No automatic consensus is exported. {escape(d['kappa_note'])}.</small></p></section></main></html>"""


def write_reviewer_comparison(rate_json: Path, a_json: Path, b_json: Path, output: Path) -> dict:
    rate = json.loads(Path(rate_json).read_text(encoding='utf-8'))
    a = json.loads(Path(a_json).read_text(encoding='utf-8'))
    b = json.loads(Path(b_json).read_text(encoding='utf-8'))
    result=compare_reviewers(rate,a,b)
    output=Path(output);output.mkdir(parents=True, exist_ok=True)
    (output/'reviewer_comparison.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    (output/'reviewer_comparison.html').write_text(render_agreement_html(result),encoding='utf-8')
    return result
