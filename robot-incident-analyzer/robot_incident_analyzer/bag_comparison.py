"""Evidence-only ROS2 bag-to-bag topic-rate comparison, no ROS installation.

The first recording is an operator-supplied reference, *not* certified healthy.
Rate heuristics are not safety alarms or proof of attack / root cause.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from statistics import median
from urllib.parse import quote
import hashlib
import json
import math
import sqlite3
import struct

from .bag_reader import read_bag

NS = 1_000_000_000
MAX_BINS = 1000


def _rate(count: int, first: int, last: int) -> float | None:
    if count < 2 or last <= first:
        return None
    return (count - 1) * NS / (last - first)


def _fmt(value, decimals=1):
    if value is None:
        return 'n/a'
    return f'{value:,.{decimals}f}'


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def summarize_bag(path: Path, max_messages: int = 2_000_000) -> dict:
    """Summarize topic reception times. No decoding of private message bodies."""
    path = Path(path)
    if not path.is_file() or path.suffix.lower() not in ('.db3', '.sqlite3', '.mcap'):
        raise ValueError('Expected a standalone existing .db3, .sqlite3 or .mcap file')
    if max_messages < 1:
        raise ValueError('max_messages must be positive')

    # DB3 SQL aggregates avoid decoding payload blobs. Respect read-only access.
    if path.suffix.lower() in ('.db3', '.sqlite3'):
        uri = 'file:' + quote(str(path.resolve()), safe='/') + '?mode=ro'
        try:
            con = sqlite3.connect(uri, uri=True)
            try:
                topics = {int(i): (name, typ) for i, name, typ in con.execute('SELECT id,name,type FROM topics')}
                row = con.execute('SELECT COUNT(*),MIN(timestamp),MAX(timestamp) FROM messages').fetchone()
                total_messages, file_min, file_max = row
                if total_messages > max_messages:
                    raise ValueError(f'{path.name}: {total_messages:,} messages exceeds --max-messages={max_messages:,}; use a higher limit (no partial comparison)')
                # Streaming read. Index-ordered reading gives memory O(topics*rate-bins).
                records = ((topics[int(tid)][0], topics[int(tid)][1], int(ts)) for tid, ts in con.execute('SELECT topic_id,timestamp FROM messages ORDER BY timestamp') if int(tid) in topics)
                result = _summarize_records(records, path, int(file_min or 0), int(file_max or 0), total_messages, max_messages)
            finally:
                con.close()
        except sqlite3.DatabaseError as exc:
            raise ValueError(f'Invalid ROS2 SQLite bag {path.name}: {exc}') from exc
    else:
        warnings=[]
        # MCAP reads have a streaming native reader. We must reject silent partial reads.
        def items():
            for name, typ, timestamp, _raw in read_bag(path, max_messages + 1, warnings):
                yield name, typ, timestamp
        result = _summarize_records(items(), path, None, None, None, max_messages)
        if any('skipped' in s.lower() or 'partial' in s.lower() or 'only first' in s.lower() for s in warnings):
            raise ValueError(f'MCAP could not be fully read: {warnings[:3]}')
        result['reader_warnings'] = warnings[:20]
    result['sha256'] = _sha256(path)
    result['size_bytes'] = path.stat().st_size
    return result


def _summarize_records(records, path, file_first, file_last, reported_total, max_messages):
    # Keep only timestamps (ints) and no sensor payload bytes.
    meta=defaultdict(lambda: {'count':0,'first_ns':None,'last_ns':None})
    # For true streaming MCAP without known recording start time, use each topic's start as x=0.
    histogram=defaultdict(dict)
    earliest=file_first
    latest=file_last
    count=0
    for topic, msgtype, timestamp in records:
        count+=1
        if count>max_messages:
            raise ValueError(f'{path.name}: exceeded maximum messages for a complete comparison; retry with larger --max-messages')
        t=int(timestamp)
        earliest=t if earliest is None else min(earliest,t)
        latest=t if latest is None else max(latest,t)
        key=(str(topic),str(msgtype))
        s=meta[key]
        s['count']+=1
        s['first_ns']=t if s['first_ns'] is None else min(t,s['first_ns'])
        s['last_ns']=t if s['last_ns'] is None else max(t,s['last_ns'])
        # For typical runs (<1000s) record 1s bins keyed by topic-local start.
        # Dynamic re-binning for long recordings would bias the comparison;
        # instead store only first 1000 seconds of histogram and mark coverage.
        bin_ix=(t - s['first_ns'])//NS
        if 0<=bin_ix<MAX_BINS:
            h=histogram[key]
            h[int(bin_ix)]=h.get(int(bin_ix),0)+1
    if reported_total is not None and count!=reported_total:
        raise ValueError(f'{path.name}: message count changed while recording was read')
    out=[]
    for (name, typ),s in sorted(meta.items()):
        c=s['count']; first=s['first_ns']; last=s['last_ns']
        span=(last-first)/NS if c>=2 else 0
        bins=histogram[(name,typ)]
        complete=(span <= MAX_BINS-1)
        if complete:
            seq=[bins.get(i,0) for i in range(max(1,int(math.ceil(span))+1))]
        else:
            seq=[bins.get(i,0) for i in range(MAX_BINS)]
        nz=[v for v in seq if v>0]
        out.append({'topic':name,'type':typ,'messages':c,'duration_s':round(span,4),
                    'mean_hz':round(_rate(c,first,last),4) if _rate(c,first,last) is not None else None,
                    'peak_1s_count':max(seq,default=0),
                    'median_active_1s_count':median(nz) if nz else 0,
                    'sampled_window_s':min(MAX_BINS,max(1,int(math.ceil(span)))),
                    'one_second_hist_complete':complete,
                    'one_second_counts':seq[:MAX_BINS]})
    return {'path':str(path),'filename':path.name,'format':path.suffix.lower().lstrip('.'),
            'message_count':count,'topic_count':len(out),'start_ns':earliest,
            'end_ns':latest, 'duration_s':round((latest-earliest)/NS,4) if earliest is not None and latest is not None else 0,
            'topics':out}


def compare_summaries(baseline: dict, candidates: list[dict], ratio_threshold=3., min_baseline_hz=2., min_candidate_hz=10., min_duration_s=3.) -> dict:
    if not candidates:
        raise ValueError('At least one candidate recording is required')
    if not (ratio_threshold>1 and min_baseline_hz>=0 and min_candidate_hz>=0 and min_duration_s>=0):
        raise ValueError('Invalid comparison thresholds')
    baseline_map={(x['topic'],x['type']):x for x in baseline['topics']}
    cases=[]
    for candidate in candidates:
        rows=[]
        candidate_map={(x['topic'],x['type']):x for x in candidate['topics']}
        for key in sorted(set(baseline_map)|set(candidate_map)):
            base=baseline_map.get(key)
            curr=candidate_map.get(key)
            if base is None or curr is None:
                status='NOT_COMPARABLE'
                ratio=None
                reason='Topic/type missing from one recording'
            else:
                b,c=base['mean_hz'],curr['mean_hz']
                ratio=(c/b if b and c is not None else None)
                if (b is None or c is None or base['duration_s']<min_duration_s or curr['duration_s']<min_duration_s or base['messages']<10 or curr['messages']<10):
                    status='INSUFFICIENT_DATA';reason='Too few messages or too short to compare rates'
                elif b >= min_baseline_hz and c>=min_candidate_hz and ratio is not None and ratio>=ratio_threshold:
                    status='RATE_INCREASE';reason='Observed recorded topic rate increase vs supplied baseline; not proof of failure or attack'
                elif b >= min_baseline_hz and ratio is not None and ratio<=1/ratio_threshold:
                    status='RATE_DECREASE';reason='Observed recorded topic rate decrease vs supplied baseline; check capture coverage'
                else:
                    status='NO_STRONG_RATE_CHANGE';reason='Did not cross the chosen reference-relative thresholds'
            rows.append({'topic':key[0],'type':key[1], 'baseline_messages':base['messages'] if base else None,
                         'candidate_messages':curr['messages'] if curr else None,
                         'baseline_mean_hz':base['mean_hz'] if base else None,
                         'candidate_mean_hz':curr['mean_hz'] if curr else None,
                         'baseline_peak_1s_count':base['peak_1s_count'] if base else None,
                         'candidate_peak_1s_count':curr['peak_1s_count'] if curr else None,
                         'rate_ratio':round(ratio,4) if ratio is not None else None,
                         'status':status,'reason':reason,
                         'baseline_histogram':(base['one_second_counts'][:240] if base else []),
                         'candidate_histogram':(curr['one_second_counts'][:240] if curr else []),
                         'histogram_scope':'first up to 240 topic-relative 1s bins, not wall-clock aligned across recordings'})
        cases.append({'candidate':candidate, 'topic_comparisons':rows,
                      'rate_increases':sum(x['status']=='RATE_INCREASE' for x in rows),
                      'rate_decreases':sum(x['status']=='RATE_DECREASE' for x in rows)})
    return {'version':'0.5.1', 'reference':baseline, 'candidate_cases':cases,
            'criteria':{'ratio_threshold':ratio_threshold,'min_baseline_hz':min_baseline_hz,
                        'min_candidate_hz':min_candidate_hz,'min_duration_s':min_duration_s},
            'caveats':['Supplied baseline is operator-declared, not automatically known healthy.',
                       'Rate changes are descriptive observations, not confirmed incident/attack labels.',
                       'Relative recording times need not represent the same task, lifecycle phase or load.',
                       'The topic name and message type must both match; file durations can differ.',
                       'Reported frequencies are recorded message reception rates, not original publisher rates.',
                       'No automatic root-cause claim and no detection precision/recall without human labels.']}


def _spark(values, color):
    if not values:
        return '<span class="muted">No values</span>'
    vals=values[:120]
    vmax=max(vals,default=0) or 1
    pts=' '.join(f'{(i / max(1,len(vals)-1))*320:.1f},{65-58*v/vmax:.1f}' for i,v in enumerate(vals))
    return f'<svg aria-label="Topic recorded message frequency over time" role="img" viewBox="0 0 320 70" preserveAspectRatio="none"><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/></svg>'


def render_comparison_html(data):
    bas=data['reference']
    cards=[]
    for ci,case in enumerate(data['candidate_cases']):
        cd=case['candidate']
        interesting=sorted(case['topic_comparisons'],key=lambda x:(x['status'] not in ('RATE_INCREASE','RATE_DECREASE'),-abs(math.log(x['rate_ratio'])) if x['rate_ratio'] and x['rate_ratio']>0 else 0))
        trs=[]
        for row in interesting:
            status=row['status']; badge='alert' if status=='RATE_INCREASE' else 'neutral'
            trs.append('<tr><td class="topic">'+escape(row['topic'])+'<small>'+escape(row['type'])+'</small></td><td>'+_fmt(row['baseline_mean_hz'])+'</td><td>'+_fmt(row['candidate_mean_hz'])+'</td><td>'+(_fmt(row['rate_ratio'],2)+'×' if row['rate_ratio'] is not None else 'n/a')+'</td><td><span class="pill '+badge+'">'+escape(status.replace('_',' '))+'</span></td></tr>')
        rate_rows=[x for x in interesting if x['status']=='RATE_INCREASE'][:4]
        examples=[]
        for row in rate_rows:
            examples.append('<section class="signals"><h4>'+escape(row['topic'])+' · '+_fmt(row['rate_ratio'],2)+'× recorded rate</h4><div class="legend"><span>● reference</span><span>● candidate</span></div><div class="sparks">'+_spark(row['baseline_histogram'],'#3cd6bd')+_spark(row['candidate_histogram'],'#ffba75')+'</div><p class="small">Each line starts at its own first message (1-second bins). Not timestamp aligned; displayed for relative rate shape only.</p></section>')
        cards.append('<article class="panel"><div class="head"><h2>'+escape(cd['filename'])+'</h2><span class="tag">'+str(case['rate_increases'])+' rate increases</span></div><p class="muted">'+f"{cd['message_count']:,} messages · {cd['topic_count']} topics · {cd['duration_s']:.1f}s"+'</p>'+''.join(examples)+ '<div class="table-wrap"><table><thead><tr><th>Matched topic</th><th>Reference Hz</th><th>Candidate Hz</th><th>Ratio</th><th>Evaluation</th></tr></thead><tbody>'+''.join(trs)+'</tbody></table></div></article>')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ROS2 Bag Baseline Comparison</title><style>
    :root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#e6edfa;background:#08101b}*{box-sizing:border-box}body{margin:0}main{max-width:1340px;padding:32px 26px;margin:auto}h1{font-size:clamp(26px,4vw,44px);letter-spacing:-.04em;margin:.4em 0}h2{font-size:22px;margin:0}.eyebrow{color:#48d9c7;font-weight:700;letter-spacing:.16em;font-size:11px;text-transform:uppercase}.muted{color:#94a4b9}.small{font-size:12px;color:#8291aa}.intro{max-width:850px;line-height:1.6}.metrics{display:flex;flex-wrap:wrap;gap:12px;margin:25px 0}.metric,.panel{background:#0e1b2b;border:1px solid #26374a;border-radius:17px;padding:20px}.metric{min-width:180px}.metric b{display:block;font-size:27px;margin-top:8px}.panel{margin:20px 0}.head{display:flex;align-items:center;justify-content:space-between;gap:20px}.tag,.pill{padding:7px 9px;border-radius:12px;background:#263c4a;font-size:11px;font-weight:700;white-space:nowrap}.pill.alert{color:#ffce8c;background:#533c2c}.pill.neutral{color:#b8cad9}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:14px 0}th{font-size:11px;letter-spacing:.07em;text-transform:uppercase;text-align:left;color:#8e9db1}td,th{padding:12px;border-bottom:1px solid #263447;font-size:13px}td{font-variant-numeric:tabular-nums}.topic{word-break:break-word;min-width:190px;max-width:370px}.topic small{display:block;font-size:10px;color:#7890a8;margin-top:4px}.signals{margin:12px 0;padding:15px;background:#0a1725;border:1px solid #284158;border-radius:14px}.signals h4{margin:0 0 12px}.sparks{display:grid;grid-template-columns:1fr 1fr;gap:12px}.sparks svg{height:75px;width:100%;background:#0e2435;border-radius:6px}.legend{display:flex;gap:24px;font-size:11px;color:#9fbed3;margin-bottom:7px}.legend span:first-child{color:#3cd6bd}.legend span:last-child{color:#ffba75}footer{color:#93a6ba;font-size:12px;line-height:1.7;margin-top:40px}a{color:#6bdae7}
    </style></head><body><main><span class="eyebrow">Robot Incident Analyzer / evidence first</span><h1>Cross-recording diagnostics</h1><p class="intro muted">A reference-relative comparison of recorded ROS2 topic rates. <strong>Rate increases do not establish failures or attacks.</strong> All rates are from bag timestamps; validate task and capture conditions independently.</p><div class="metrics"><div class="metric"><span class="muted">Reference</span><b>'''+escape(bas['filename'])+'''</b></div><div class="metric"><span class="muted">Reference messages</span><b>'''+f"{bas['message_count']:,}"+'''</b></div><div class="metric"><span class="muted">Candidates</span><b>'''+str(len(data['candidate_cases']))+'''</b></div><div class="metric"><span class="muted">Rate multiplier</span><b>'''+_fmt(data['criteria']['ratio_threshold'],1)+'''×</b></div></div>'''+''.join(cards)+'''<footer><strong>Important:</strong> The reference is only operator-selected, not verified healthy. Results are relative measurements, not a causal diagnosis. Relative bin plots do not share recording clock times. Topic names and message types must match; missing topics are NOT_COMPARABLE. Raw ROS2 messages remain local. This report is safe for investigation only, not autonomous safety decisions.</footer></main></body></html>'''


def save_comparison(output: Path, comparison: dict):
    output=Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output/'comparison.json').write_text(json.dumps(comparison,indent=2,ensure_ascii=False),encoding='utf-8')
    (output/'comparison.html').write_text(render_comparison_html(comparison),encoding='utf-8')
    lines=['# ROS2 bag comparison (reference-relative; not an incident verdict)','',
           f"Reference: {comparison['reference']['filename']} ({comparison['reference']['message_count']:,} messages)",'',
           f"Heuristic threshold: {comparison['criteria']['ratio_threshold']}x reference rate, minimum {comparison['criteria']['min_baseline_hz']}Hz reference and {comparison['criteria']['min_candidate_hz']}Hz candidate",'']
    for case in comparison['candidate_cases']:
        lines += [f"## Candidate {case['candidate']['filename']}", '', '| Topic | Baseline Hz | Candidate Hz | Ratio | Status |','|---|---:|---:|---:|---|']
        for x in case['topic_comparisons']:
            lines.append(f"| `{x['topic']}` | {_fmt(x['baseline_mean_hz'])} | {_fmt(x['candidate_mean_hz'])} | {_fmt(x['rate_ratio'],2)} | {x['status']} |")
        lines.append('')
    lines += ['## Cautions','']+['- '+s for s in comparison['caveats']]
    (output/'COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return output


def compare_bags(reference: Path, candidates: list[Path], output: Path, **kwargs):
    max_messages=kwargs.pop('max_messages',2_000_000)
    base=summarize_bag(reference,max_messages=max_messages)
    rest=[summarize_bag(p,max_messages=max_messages) for p in candidates]
    report=compare_summaries(base,rest,**kwargs)
    save_comparison(output,report)
    return report
