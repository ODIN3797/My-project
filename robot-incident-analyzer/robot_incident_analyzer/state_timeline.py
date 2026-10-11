"""Conservative, evidence-linked robot state timeline from explicit key=value logs.

Not natural-language inference or root-cause diagnosis; no state assumed between
recorded transitions. State data remains scoped to its input file and robot.
"""
from __future__ import annotations

import re
from collections import defaultdict
from .models import Event
from .signal_studio import escape_json

DEFAULT_STATE_KEYS = ('mode', 'state', 'phase', 'docking_state', 'charging_state',
                      'navigation_state', 'mission_state', 'command_state', 'motion_state', 'controller_state', 'safety_state')
_STATE_WORD = re.compile(r'^[a-z][a-z0-9_]{0,39}$')
_VALUE = r'([\w.\-]{1,64})(?=$|[\s,;\]\)\}])'
_MAX_TRANSITIONS = 500


def validate_state_keys(value=None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_STATE_KEYS
    if not isinstance(value, list) or len(value) > 32 or any(
            not isinstance(s, str) or not _STATE_WORD.fullmatch(s) for s in value):
        raise ValueError('state_keys must be a list of up to 32 lowercase identifier keys')
    if len(value) != len(set(value)):
        raise ValueError('state_keys must not contain duplicates')
    return tuple(value)


def state_tokens(message: str, keys=None) -> list[tuple[str, str]]:
    """Only explicit assignment tokens; never infer phases from free text."""
    names = validate_state_keys(keys) if isinstance(keys, list) else (keys if keys is not None else DEFAULT_STATE_KEYS)
    if not names or not message:
        return []
    # Require start/space/punctuation before exact key: avoids desired_mode, /mode,
    # and avoids treating JSON escaped text as independent sensor observations.
    pattern = re.compile(r'(?<![\w/])(' + '|'.join(re.escape(k) for k in names) +
                         r')\s*[:=]\s*' + _VALUE, re.IGNORECASE | re.UNICODE)
    return [(m.group(1).lower(), m.group(2)) for m in list(pattern.finditer(message[:4000]))[:8]]


def _source(event: Event) -> str:
    return re.sub(r':row\d+$', '', event.source)


def _namespace(event: Event) -> str:
    if event.robot_id not in ('', 'unknown'):
        return event.robot_id
    m = re.match(r'^/((?:robot|agv|amr)[_-]?[a-z0-9]+)/', event.topic, re.I)
    return m.group(1) if m else 'unknown'


def build_state_transitions(events: list[Event], keys=None) -> list[dict]:
    names = validate_state_keys(keys) if isinstance(keys, list) else (keys if keys is not None else DEFAULT_STATE_KEYS)
    values = {}
    rows = []
    for event in sorted(events, key=lambda e:(e.timestamp,e.event_id)):
        if len(rows) >= _MAX_TRANSITIONS:
            break
        # Only log/CSV text may declare a state. Never turn an analyzer-generated
        # diagnostic description into a purported robot state.
        if event.category not in ('rosout', 'state', 'log', 'csv') and not re.search(r':row\d+$', event.source):
            continue
        source = _source(event)
        robot = _namespace(event)
        for field, value in state_tokens(event.message, names):
            key = (source, robot, field)
            previous = values.get(key)
            if previous == value:
                continue
            rows.append({'timestamp':event.timestamp,'source':source,'robot_id':robot,
                         'field':field,'from':previous,'to':value,'event_id':event.event_id,
                         'topic':event.topic})
            values[key] = value
            if len(rows) >= _MAX_TRANSITIONS:
                break
    return rows


def matching_transition(change: dict, anchor: Event) -> bool:
    if change['source'] != _source(anchor):
        return False
    incident_robot = _namespace(anchor)
    # Unknown identities may be correlated only if both sides are unknown,
    # or the source is a namespaceless stream. Never mix known robot A with B.
    return change['robot_id'] == incident_robot


def preceding_state_context(anchor: Event, transitions: list[dict], *, seconds=30., limit=10) -> dict:
    relevant = [c for c in transitions if matching_transition(c,anchor) and
                0 <= anchor.timestamp-c['timestamp'] <= seconds]
    # Only explicit changes. The most recent observed state for each key may
    # predate the window, but must not be represented as a recent transition.
    ordered = sorted(relevant, key=lambda c:(c['timestamp'],c['field']))[-limit:]
    latest={}
    for change in ordered:
        latest[change['field']] = change['to']
    return {'transitions':ordered,'last_observed':latest,'seconds':seconds}


def summarize_state_context(context: dict) -> str:
    """Report only literal change sequence; no causal or unobserved state inference."""
    rows = context.get('transitions', [])
    if not rows:
        return 'No explicit state changes logged within the 30 s context window.'
    pieces = []
    for c in rows[-6:]:
        before = c['from'] if c['from'] is not None else '[first observed]'
        pieces.append(f"{c['field']}: {before} -> {c['to']}")
    return 'Logged changes (not verified robot actions): ' + '; '.join(pieces) + '.'


STATE_CSS = '''
.state-timeline{display:grid;gap:10px;max-height:380px;overflow-y:auto}
.state-row{display:grid;grid-template-columns:minmax(115px,.7fr) minmax(105px,.8fr) minmax(180px,1.8fr);gap:12px;align-items:center;padding:10px 12px;border:1px solid #29445a;border-radius:10px;background:#0f2134;font-size:12px;color:#dcecf9}
.state-clock{font-family:ui-monospace,monospace;font-size:11px;color:#a4c7e0}
.state-field{color:#95c9ee;font-weight:700;overflow-wrap:anywhere}
.state-shift{color:#cfeadf;overflow-wrap:anywhere}
.state-row button{background:transparent;border:0;text-align:left;cursor:pointer;padding:0;color:inherit}
.state-row button:focus-visible{outline:2px solid #59d5bf}
.case-state-panel{border:1px solid #33576d;background:#112638;border-radius:10px;padding:12px;margin:10px 0}
.case-state-panel h4{margin:0 0 8px;font-size:13px}
.case-state-item{display:flex;gap:8px;flex-wrap:wrap;color:#d5e9f7;padding:6px 0;font-size:12px}
.case-state-item button{background:none;border:0;cursor:pointer;color:#a5e3cb;text-decoration:underline}
@media(max-width:700px){.state-row{grid-template-columns:1fr;gap:5px}}
@media print{.state-row{background:#fff!important;color:#243247!important;break-inside:avoid}.state-timeline{max-height:none}.case-state-panel{background:#fff!important;color:#243247!important}}
'''


def state_markup(transitions: list[dict]) -> str:
    if not transitions:
        return '<section id="state-timeline"><div class="section-head"><h2>Explicit state transitions</h2></div><div class="box-card"><p class="case-empty">No explicitly recorded state assignments found. Robot state is unknown; absence of transitions does not imply steady operation.</p></div></section>'
    payload = escape_json(transitions[:_MAX_TRANSITIONS])
    return '''<section id="state-timeline"><div class="section-head"><div><h2>Explicit state transitions</h2><p>Observed key=value state changes, grouped by source and robot namespace; click a row to align the investigation cursor.</p></div><span class="pill-inline">Observed · not inferred</span></div>
<div class="box-card"><div id="state-timeline-rows" class="state-timeline" aria-label="Observed robot state changes"></div>
<p class="case-caption">These are log statements, not verified robot actions. Recording time may differ from controller time.</p>
<script type="application/json" id="state-transitions-data">''' + payload + '''</script></div></section>'''


def state_script() -> str:
    return '''<script>(function(){
const data=document.getElementById('state-transitions-data'),holder=document.getElementById('state-timeline-rows');
if(!data||!holder)return;
let transitions;try{transitions=JSON.parse(data.textContent);}catch(_){return;}
const el=(t,v,cls)=>{const n=document.createElement(t);if(cls)n.className=cls;if(v!==undefined)n.textContent=String(v);return n;};
transitions.forEach(c=>{const b=el('button');b.type='button';b.className='state-row';
 b.appendChild(el('span',new Date(c.timestamp*1000).toISOString(),'state-clock'));
 b.appendChild(el('span',c.field+' · '+c.robot_id,'state-field'));
 b.appendChild(el('span',(c.from===null?'first observed':c.from)+' → '+c.to,'state-shift'));
 b.title='Jump to recorded state log '+c.event_id;
 b.addEventListener('click',()=>{window.__riaMoveCursor?.(c.timestamp);document.getElementById('event-'+c.event_id)?.scrollIntoView({behavior:'smooth',block:'center'});});
 holder.appendChild(b);
});
})();</script>'''
