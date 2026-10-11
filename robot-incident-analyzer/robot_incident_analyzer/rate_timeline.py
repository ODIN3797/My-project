"""Conservative, topic-scoped 1s rate episode inspection of ROS2 bag timestamps.

Observations are received messages, NOT the originating publisher rate, robot
health or evidence of attack. Baseline can be supplied or estimated only from
stable, fully observed earlier windows in the same recording.
"""
from __future__ import annotations

from html import escape
from math import ceil, isfinite
from pathlib import Path
from statistics import median
import json
import re

from .bag_comparison import summarize_bag, _fmt

_COMMAND = re.compile(r'(?:^|/)(?:cmd_vel|cmd_vel_unstamped|velocity_cmd|cmd_velocity|twist_cmd)(?:$|/)', re.I)


def _lower_baseline(values: list[int], required: int = 8) -> float | None:
    # Do not turn idle or missing windows into a falsely "healthy" 0 Hz baseline.
    if len(values) < required or any(v == 0 for v in values[-required:]):
        return None
    sample=values[-required:]
    center=float(median(sample))
    if center < 2 or max(sample)>2*center or min(sample)<.5*center:
        return None
    return center


def inspect_summary(summary: dict, *, baseline:dict|None=None, topic:str|None=None,
                    expected_hz:float|None=None, ratio_threshold:float=3.0,
                    min_count:int=10, min_consecutive:int=2, max_episodes:int=100) -> dict:
    """Return explicitly non-causal rate episodes with provenance and coverage flags."""
    if not isfinite(ratio_threshold) or ratio_threshold<=1 or not 1<=min_count<=10000 or not 1<=min_consecutive<=100 or not 1<=max_episodes<=1000:
        raise ValueError('Invalid rate detection thresholds')
    if expected_hz is not None and (not isfinite(expected_hz) or expected_hz<2):
        raise ValueError('--expected-hz must be finite and at least 2')
    if topic is not None and (not topic.strip() or len(topic)>400):
        raise ValueError('Invalid topic selection')
    if baseline is not None and expected_hz is not None:
        raise ValueError('Supply either --reference or --expected-hz, not both')
    base_map={(x['topic'],x['type']):x for x in baseline['topics']} if baseline else {}
    items=[]
    for signal in summary['topics']:
        name=signal['topic'];typ=signal['type']
        if topic is not None and name!=topic: continue
        if topic is None and not _COMMAND.search(name): continue
        seq=signal['one_second_counts']
        origin=signal.get('histogram_origin_ns', signal['first_ns'] if 'first_ns' in signal else None)
        # one_second_counts has one trailing partial window at end of a recording:
        # skip it rather than misreporting partial captures as rate changes.
        complete=bool(signal.get('one_second_hist_complete',False))
        span=signal.get('duration_s',0)
        if not complete:
            items.append({'topic':name,'type':typ,'status':'PARTIAL_WINDOW_COVERAGE','episodes':[],
                          'note':'Histogram truncated beyond 1000s; no local rate inference'})
            continue
        if origin is None or span<min_consecutive+2 or len(seq)<min_consecutive+2:
            items.append({'topic':name,'type':typ,'status':'INSUFFICIENT_DATA','episodes':[],
                          'note':'Need a span with at least two complete seconds'})
            continue
        # bins use epoch-second boundaries; first/last epoch seconds are partial.
        first_complete_index=1 if signal.get('epoch_aligned_bins',False) else 0
        last_complete_index=len(seq)-1
        indices=range(first_complete_index,last_complete_index)
        chosen=base_map.get((name,typ))
        fixed_hz=None
        method='local stable 8-second history'
        if expected_hz is not None:
            fixed_hz=float(expected_hz);method='operator-expected Hz'
        elif baseline is not None:
            b=chosen['mean_hz'] if chosen else None
            if b is not None and chosen['duration_s']>=5 and chosen['messages']>=50 and b>=2:
                fixed_hz=float(b);method='reference bag recorded Hz'
            else:
                items.append({'topic':name,'type':typ,'status':'NO_COMPARABLE_REFERENCE','episodes':[],
                    'note':'Reference requires same topic and type with >=50 messages and >=5s; no implicit local fallback'})
                continue
        out=[];run_start=None;run_end=None;run_peak=0;run_sum=0;run_base=None
        def finish():
            nonlocal run_start,run_end,run_peak,run_sum,run_base
            if run_start is not None and run_end-run_start+1>=min_consecutive and len(out)<max_episodes:
                start_ns=int(origin)+run_start*1_000_000_000
                end_ns=int(origin)+(run_end+1)*1_000_000_000
                out.append({'start_ns':start_ns,'end_ns':end_ns,'start_s_from_topic':run_start,
                    'duration_s':run_end-run_start+1,'messages_in_windows':run_sum,
                    'max_messages_per_s':run_peak,'baseline_hz':round(run_base,3),
                    'peak_ratio':round(run_peak/run_base,3),'baseline_method':method,
                    'evidence':'recorded message arrival times only; not fault or attack classification'})
            run_start=run_end=run_base=None;run_peak=run_sum=0
        for idx in indices:
            count=seq[idx]
            b=fixed_hz if fixed_hz is not None else (run_base if run_start is not None else _lower_baseline(seq[max(first_complete_index,idx-20):idx]))
            candidate=(b is not None and count>=min_count and count >=ceil(b*ratio_threshold))
            if candidate:
                if run_start is None:
                    run_start=idx;run_base=b
                run_end=idx;run_peak=max(run_peak,count);run_sum+=count
            else:
                finish()
        finish()
        items.append({'topic':name,'type':typ,'status':'RATE_EPISODES_FOUND' if out else 'NO_CONFIRMED_EPISODES',
            'reference_mean_hz':fixed_hz,'baseline_method':method,
            'messages':signal['messages'],'duration_s':span,'window_origin_ns':int(origin),
            'first_complete_bin_index':first_complete_index,
            'count_by_second':seq[:1000],'episodes':out,
            'note':'Non-detection does not mean normal. Full-recording sustained high rate cannot be detected without a reference or declared expectation.'})
    if topic is not None and not items:
        raise ValueError('Selected exact topic was not found')
    return {'version':'0.5.2','recording':{'filename':summary['filename'],'sha256':summary.get('sha256'),
        'messages':summary['message_count'],'duration_s':summary['duration_s']},
        'reference':{'filename':baseline['filename'],'sha256':baseline.get('sha256')} if baseline else None,
        'criteria':{'topic':topic,'expected_hz':expected_hz,'ratio_threshold':ratio_threshold,
                    'min_count':min_count,'min_consecutive':min_consecutive},
        'topics':items,'episode_count':sum(len(x['episodes']) for x in items),
        'caveats':['This detects increases in bag-recorded topic message density, NOT originating publish frequency, DoS or real robot faults.',
            'Unobserved/dropped messages may hide true publisher rates. Different workloads can naturally change topic rates.',
            'No rate determination is made on incomplete histogram coverage, partial edge-second bins or unmatched baselines.',
            'Short bursts that do not persist across the minimum consecutive full windows are not labeled.',
            'Without reference, a consistently high-frequency recording may have no local rate episode.']}


def _plot(topic:dict)->str:
    counts=topic.get('count_by_second',[])[:240]
    if not counts: return '<p>No full-rate histogram available.</p>'
    vmax=max(1,max(counts))
    width=850; height=120
    step=width/max(1,len(counts))
    hot=set()
    for e in topic.get('episodes',[]):hot.update(range(e['start_s_from_topic'], e['start_s_from_topic']+e['duration_s']))
    blocks=[]
    for i,count in enumerate(counts):
        h=95*count/vmax
        color='#ffb267' if i in hot else '#40cbbb'
        blocks.append(f'<rect x="{i*step:.1f}" y="{100-h:.1f}" width="{max(.8,step*.87):.2f}" height="{h:.1f}" fill="{color}"/>')
    return f'<svg role="img" aria-label="one-second recorded message count with orange high-rate windows" viewBox="0 0 {width} {height}" preserveAspectRatio="none" class="chart">'+''.join(blocks)+'</svg>'


def render_rate_html(report:dict)->str:
    cards=[]
    for item in report['topics']:
        ep=''.join('<tr><td>'+str(x['start_s_from_topic'])+' s</td><td>'+str(x['duration_s'])+' s</td><td>'+str(x['max_messages_per_s'])+'</td><td>'+_fmt(x['baseline_hz'])+'</td><td>'+_fmt(x['peak_ratio'],2)+'×</td><td>'+escape(x['baseline_method'])+'</td></tr>' for x in item['episodes'])
        cards.append('<section><h2>'+escape(item['topic'])+'</h2><p class="muted">'+escape(item['type'])+' · '+escape(item['status'])+'</p>'+_plot(item)+('<div class="scroll"><table><thead><tr><th>Offset</th><th>Duration</th><th>Max msg/s</th><th>Baseline Hz</th><th>Peak ratio</th><th>Reference</th></tr></thead><tbody>'+ep+'</tbody></table></div>' if ep else '<p class="muted">No sustained rate episode meets the configured baseline and thresholds.</p>')+'</section>')
    filename=escape(report['recording']['filename']); origin='Reference: '+escape(report['reference']['filename']) if report['reference'] else 'Reference: expected rate or conservative local baseline'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ROS2 Topic Rate Timeline</title><style>
    :root{{font-family:system-ui,sans-serif;color:#e9f0fb;background:#09111e}}body{{margin:0}}main{{max-width:1100px;margin:auto;padding:36px 22px}}.k{{color:#40cbbb;text-transform:uppercase;letter-spacing:.18em;font-size:12px;font-weight:700}}h1{{font-size:clamp(26px,4vw,42px);letter-spacing:-.035em}}h2{{font-size:19px;overflow-wrap:anywhere}}section{{background:#122034;border:1px solid #29445a;border-radius:15px;margin:19px 0;padding:22px}}.muted{{color:#a9b8c8;line-height:1.6}}.stats{{display:flex;gap:14px;flex-wrap:wrap}}.stat{{background:#162c3d;padding:16px 21px;border-radius:12px;min-width:180px}}.stat strong{{display:block;font-size:30px}}.chart{{width:100%;height:125px;background:#0b1c2a;border-radius:8px}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px;margin-top:16px}}td,th{{text-align:left;padding:11px;border-bottom:1px solid #314657;white-space:nowrap}}th{{color:#9fbed0;font-size:11px}}code{{overflow-wrap:anywhere;color:#c6efeb}}</style></head><body><main><p class="k">Robot Incident Analyzer · v0.5.2</p><h1>Topic message-rate investigation</h1><p class="muted">{filename} · {origin}. Detection is evidence of a change in recorded message density, not proof of cyberattack, damage or a failed robot.</p><div class="stats"><div class="stat">Episodes<strong>{report['episode_count']}</strong></div><div class="stat">Bag messages<strong>{report['recording']['messages']:,}</strong></div><div class="stat">Ratio criterion<strong>{report['criteria']['ratio_threshold']:.1f}×</strong></div></div>{''.join(cards)}<p class="muted">Only full one-second windows are considered; the first and last partial seconds are excluded where possible. Graphs are capped at 240 seconds for display and anchored at the topic's reported origin. Incomplete >1000-second histograms are explicitly skipped. No field-ground-truth detection accuracy is implied.</p></main></body></html>'''


def inspect_bag(path:Path, output:Path, *, reference:Path|None=None, max_messages:int=2_000_000, **kwargs)->dict:
    curr=summarize_bag(Path(path),max_messages=max_messages)
    ref=summarize_bag(Path(reference),max_messages=max_messages) if reference else None
    report=inspect_summary(curr,baseline=ref,**kwargs)
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    (output/'rate_timeline.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'rate_timeline.html').write_text(render_rate_html(report),encoding='utf-8')
    return report
