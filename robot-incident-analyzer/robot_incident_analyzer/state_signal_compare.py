"""Bounded pre/post comparisons around *logged* robot state changes.

Measurements are recording-time samples, not confirmed physical robot states.
Medians are descriptive; the tool never infers fault cause or statistical significance.
"""
from __future__ import annotations

import math
from statistics import median


def _finite_samples(series, start: float, end: float):
    """Half-open window: adjacent before and after intervals do not overlap."""
    rows = []
    for sample in series.get('samples', []):
        if not isinstance(sample, (list, tuple)) or len(sample) < 2:
            continue
        try:
            t = float(sample[0]); value = float(sample[1])
        except (ValueError, TypeError, OverflowError):
            continue
        if math.isfinite(t) and math.isfinite(value) and start <= t < end:
            rows.append((t, value))
    # Same timestamp may occur twice after merging recorded topics. A pair of
    # repeated timestamps is not two independent measurements of change.
    return sorted({t: value for t, value in rows}.items())


def compare_transition(change: dict, signals: list[dict], *, seconds: float = 2.0,
                       min_samples: int = 2, limit: int = 4) -> dict:
    """Compute supported median shifts with explicit sample and gap coverage."""
    t = float(change['timestamp'])
    if not math.isfinite(t) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Transition time/window must be finite and positive')
    output = {k: change.get(k) for k in ('timestamp', 'field', 'from', 'to', 'event_id', 'source', 'robot_id')}
    output.update({'window_seconds': seconds, 'signals': [], 'status': 'insufficient_samples'})
    for s in signals[:32]:
        left = _finite_samples(s, t-seconds, t)
        right = _finite_samples(s, t, t+seconds)
        if len(left) < min_samples or len(right) < min_samples:
            continue
        # Ensure close evidence exists on both sides: sparse/holey telemetry
        # should not be represented as an immediate state-related difference.
        gap_before = t-left[-1][0]
        gap_after = right[0][0]-t
        if gap_before > seconds / 2 or gap_after > seconds / 2:
            continue
        b = median(v for _, v in left); a = median(v for _, v in right)
        delta = a-b
        output['signals'].append({'topic': s.get('topic',''), 'field': s.get('field',''),
            'before': round(b, 6), 'after': round(a, 6), 'delta': round(delta, 6),
            'before_n': len(left), 'after_n': len(right),
            'gap_before_s': round(gap_before, 3), 'gap_after_s': round(gap_after, 3)})
        if len(output['signals']) >= limit:
            break
    if output['signals']:
        output['status'] = 'descriptive_only'
    return output


def transition_comparisons(state_context: dict, signals: list[dict], *, seconds: float = 2.0,
                           max_transitions: int = 3, signals_per_transition: int = 4) -> list[dict]:
    """Compare the last distinct observed state timestamps, never future states."""
    changes = state_context.get('transitions', [])
    selected = []
    timestamps = set()
    for c in reversed(changes):
        # Several keys in a single ROS log share a timestamp. Avoid rendering
        # the same comparison repeatedly under different state keys.
        if c['timestamp'] in timestamps:
            continue
        timestamps.add(c['timestamp']); selected.append(c)
        if len(selected) >= max_transitions:
            break
    return [compare_transition(c, signals, seconds=seconds, limit=signals_per_transition)
            for c in selected]


def summary_for_case(comparisons: list[dict]) -> str:
    if not comparisons:
        return 'No explicit preceding transition to compare with telemetry.'
    found = [x for c in comparisons for x in c['signals']]
    if not found:
        return 'Logged transitions found, but not enough nearby numeric samples on both sides to compare.'
    first = next(c for c in comparisons if c['signals'])
    pre = '[first observed]' if first['from'] is None else str(first['from'])
    snapshots = []
    for signal in first['signals'][:2]:
        snapshots.append(f"{signal['topic']} {signal['field']}: {signal['before']:.3f} → {signal['after']:.3f} (Δ {signal['delta']:+.3f})")
    return (f"Logged {first['field']} {pre} → {first['to']}; " + '; '.join(snapshots)
            + f'. {len(found)} median comparisons total. Recorded timing only; no causal inference.')


COMPARE_CSS = '''
.transition-comparisons{display:grid;gap:10px;margin-top:10px}
.transition-compare{border:1px solid #36516a;border-radius:11px;background:#0c2235;padding:11px}
.transition-compare h5{margin:0 0 6px;font-size:13px;color:#a6e4ce}
.transition-compare p{margin:5px 0 8px;font-size:11px;color:#adc5d9}
.transition-compare table{width:100%;border-collapse:collapse;font-size:11px}
.transition-compare th,.transition-compare td{padding:6px;border-bottom:1px solid #345066;text-align:left;overflow-wrap:anywhere}
.transition-compare th{color:#a9c4dc}
@media(max-width:760px){.transition-compare{overflow-x:auto}.transition-compare table{min-width:570px}}
@media print{.transition-compare{background:white!important;color:#1b2636!important}.transition-compare th,.transition-compare td{color:#26364b!important}}
'''


def compare_script() -> str:
    """The caller owns DOM nodes; all untrusted strings use textContent."""
    return r'''<script>(function(){
window.__riaDrawComparisons=function(container,comparisons,summary){
 if(!container)return;
 container.replaceChildren();
 const make=(tag,txt,cls)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=String(txt);return e;};
 container.appendChild(make('h4','Telemetry before / after logged state transitions'));
 container.appendChild(make('p',summary,'case-caption'));
 container.appendChild(make('p','Two separate ±2 s recording-time windows. Median comparisons are descriptive, not fault attribution.','case-caption'));
 if(!comparisons?.length){container.appendChild(make('p','No state transition in context.','case-empty'));return;}
 for(const c of comparisons){
  const box=make('article',undefined,'transition-compare');
  box.appendChild(make('h5',c.field+': '+(c.from===null?'[first observed]':c.from)+' → '+c.to));
  box.appendChild(make('p','Recorded at '+new Date(c.timestamp*1000).toISOString()+' · '+c.event_id+' · ±'+c.window_seconds+' s median window'));
  if(!c.signals.length){box.appendChild(make('p','Insufficient samples or gaps around this transition; no delta reported.'));container.appendChild(box);continue;}
  const table=make('table');const thead=make('thead');const tr=make('tr');
  for(const label of ['Signal / topic','Before (median)','After (median)','Change','Samples before / after'])tr.appendChild(make('th',label));
  thead.appendChild(tr);table.appendChild(thead);const tbody=make('tbody');
  for(const s of c.signals){const row=make('tr');for(const cell of [s.field+' · '+s.topic,s.before.toFixed(3),s.after.toFixed(3),(s.delta>=0?'+':'')+s.delta.toFixed(3),s.before_n+' / '+s.after_n])row.appendChild(make('td',cell));tbody.appendChild(row);}
  table.appendChild(tbody);box.appendChild(table);container.appendChild(box);
 }
};
})();</script>'''
