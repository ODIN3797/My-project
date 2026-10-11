from __future__ import annotations
import html
import json
from collections import Counter
from pathlib import Path
import math
from .models import Event, Finding, TopicStats, utc_iso
from . import __version__

STYLE = '''
:root{color-scheme:dark;--bg:#0b1120;--panel:#111d30;--border:#25344b;--fg:#e7edf7;--muted:#9aaac0;--accent:#7fd1cf;--warn:#f5c46b;--error:#fa9097}
*{box-sizing:border-box}body{background:var(--bg);color:var(--fg);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif;line-height:1.55;margin:0}
main{max-width:1160px;padding:38px 24px 90px;margin:auto}h1{font-size:2rem;letter-spacing:-.04em;margin:8px 0}h2{font-size:1.25rem;margin:34px 0 14px}h3{font-size:1.03rem;margin:0}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}.muted,.small{color:var(--muted)}.small{font-size:.83rem}.eyebrow{text-transform:uppercase;letter-spacing:.14em;color:var(--accent);font-size:.74rem;font-weight:700}
.summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:30px}.metric,.panel,.finding{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px}.metric .num{font-weight:750;font-size:1.65rem;letter-spacing:-.04em}.metric .small{display:block}
.finding{margin-bottom:12px}.finding-head{display:flex;gap:10px;align-items:center;margin-bottom:8px}.pill{font-size:.72rem;border-radius:30px;padding:3px 9px;border:1px solid var(--border)}.pill.HIGH{color:var(--error)}.pill.MEDIUM{color:var(--warn)}.pill.INFO{color:var(--accent)}
.evidence{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.evidence a{font-size:.81rem;padding:3px 8px;border:1px solid var(--border);border-radius:6px}ul{padding-left:22px;margin:6px 0}table{width:100%;border-collapse:collapse;font-size:.88rem}th,td{text-align:left;border-bottom:1px solid var(--border);padding:12px;vertical-align:top}th{color:var(--muted);font-weight:600}code{color:#b1c5ef;overflow-wrap:anywhere}.sev-error{color:var(--error)}.sev-warn{color:var(--warn)}.tablewrap{overflow-x:auto}.notice{border-left:3px solid var(--warn);background:#242134;padding:14px 17px;border-radius:6px;margin-top:20px}.tag{font-size:.72rem;background:#1a3042;color:var(--accent);padding:4px 8px;border-radius:5px}
.chart-legend{display:flex;gap:20px;flex-wrap:wrap;font-size:.86rem;margin:12px 0}.chart-legend span::before{content:"";display:inline-block;width:14px;height:3px;margin-right:6px;vertical-align:middle;background:var(--accent)}.chart-legend .obs::before{background:var(--warn)}.chart-legend .fault::before{background:var(--error);border-top:2px dashed var(--error);height:0}.chart{width:100%;height:auto;max-height:310px}.focus{background:#122238;border:1px solid var(--border);border-radius:10px;margin:12px 0;padding:14px 18px}.focus summary{cursor:pointer;line-height:1.5}.focus summary:hover{color:var(--accent)}.topic-mapping{margin:12px 0 0}.toolbar{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.toolbar input,.toolbar select{background:var(--bg);color:var(--fg);border:1px solid var(--border);padding:10px;border-radius:8px}
@media(max-width:700px){.summary{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:24px 14px}.metric .num{font-size:1.3rem}}
'''


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def velocity_plot(points: list[dict], markers: list[Event] | None = None,
                  focus: float | None = None, seconds: float = 3.) -> str:
    """Offline SVG: aligned speed traces, axis ticks and incident marker overlays.

    Focus views take ±seconds around an event; never suggest timestamp
    proximity itself establishes causality. All data are recording times.
    """
    if focus is not None:
        points = [p for p in points if abs(p['time']-focus) <= seconds]
    valid = [p for p in points if all(math.isfinite(float(p[k])) for k in ('time', 'command_mps', 'odometry_mps'))]
    if len(valid) < 2:
        return '<p class="muted">Not enough synchronized telemetry samples in this interval.</p>'
    valid = sorted(valid, key=lambda p:p['time'])
    x0,x1 = valid[0]['time'],valid[-1]['time']
    if x1 - x0 < 1e-6:
        return '<p class="muted">Insufficient recording duration for a comparison.</p>'
    ylim = max(.25,1.15*max(abs(p[k]) for p in valid for k in ('command_mps','odometry_mps')))
    left,right,top,bottom=56,768,23,202
    xscale = lambda t: left+(right-left)*(t-x0)/(x1-x0)
    yscale = lambda v: (top+bottom)/2-(bottom-top)*v/(2*ylim)
    def poly(field):
        return ' '.join(f'{xscale(p["time"]):.1f},{yscale(p[field]):.1f}' for p in valid)
    grid = []
    for n in range(5):
        v = ylim * (1-n/2)
        y = yscale(v)
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#304058" stroke-dasharray="3 6"/>')
        grid.append(f'<text x="3" y="{y+4:.1f}" font-size="11" fill="#a4b4ce">{v:+.2f}</text>')
    for n in range(5):
        x=left+(right-left)*n/4
        grid.append(f'<text x="{x-10:.1f}" y="236" font-size="11" fill="#a4b4ce">+{(x1-x0)*n/4:.1f}s</text>')
    incident_markup=[]
    for e in (markers or []):
        if x0 <= e.timestamp <= x1 and e.severity in ('WARN','ERROR','FATAL'):
            px=xscale(e.timestamp)
            label=esc(e.code+' · '+e.message[:135])
            color='#fa9097' if e.severity in ('ERROR','FATAL') else '#f5c46b'
            incident_markup.append(f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{bottom}" stroke="{color}" stroke-width="1.5" stroke-dasharray="4 4" opacity=".65"><title>{label}</title></line>')
            incident_markup.append(f'<circle cx="{px:.1f}" cy="{top+2}" r="4" fill="{color}"><title>{label}</title></circle>')
    return ('<div class="chart-legend"><span>Command linear x</span><span class="obs">Odometry linear x</span>'
            '<span class="fault">WARN / ERROR marker</span></div>'
            '<svg class="chart" viewBox="0 0 790 246" role="img" '
            'aria-label="Command versus odometry velocity, with timestamp-aligned incident markers">'
            + ''.join(grid) + ''.join(incident_markup)
            + f'<polyline points="{poly("command_mps")}" fill="none" stroke="#7fd1cf" stroke-width="2.5" stroke-linejoin="round"/>'
            + f'<polyline points="{poly("odometry_mps")}" fill="none" stroke="#f5c46b" stroke-width="2.5" stroke-linejoin="round"/>'
            + f'<text x="{left}" y="14" font-size="10" fill="#a4b4ce">Start: {esc(utc_iso(x0))}</text></svg>'
            + '<p class="small">Recorded timestamps only. Dashed lines indicate log events, not confirmed causes.</p>')


def event_focus_charts(detail: dict, events: list[Event]) -> str:
    """Expose the strongest six anomaly windows for reproducible visual triage."""
    trace = detail.get('velocity_trace',[])
    if len(trace) < 2:
        return ''
    window_events = [e for e in events if e.source == detail.get('source') and
                     e.code in ('CMD_ODOM_MISMATCH','ODOM_POSITION_JUMP','TF_MAP_ODOM_JUMP',
                                'DIAGNOSTIC_ERROR','DIAGNOSTIC_STALE','TOPIC_GAP')]
    # Keep one focus card per unique (code, time bucket) so repeated alarms
    # do not generate hundreds of duplicated plots.
    used=set()
    chunks=[]
    for e in window_events:
        dedup=(e.code, round(e.timestamp))
        if dedup in used: continue
        used.add(dedup)
        chart = velocity_plot(trace, [e], focus=e.timestamp, seconds=2.5)
        if 'Not enough synchronized' in chart: continue
        chunks.append(f'<details class="focus"><summary><b>{esc(e.code)}</b> · {esc(utc_iso(e.timestamp))} — {esc(e.message[:125])}</summary>{chart}</details>')
        if len(chunks) >= 6: break
    return ''.join(chunks)


def render_discovery(details: list[dict]) -> str:
    if not details: return '<p class="muted">No bag topic mapping available.</p>'
    lines=[]
    for d in details:
        data=d.get('discovery',{})
        sel=data.get('selected',{})
        for role in ('command','odometry'):
            options=data.get('candidates',{}).get(role,[])
            chosen=sel.get(role)
            state=chosen if chosen else 'Ambiguous / missing — mapping required'
            allopts=', '.join(o['topic'] for o in options[:12]) or 'None'
            lines.append(f'<tr><td>{esc(d.get("source",""))}</td><td>{esc(role)}</td><td><code>{esc(state)}</code></td><td class="small">{esc(allopts)}</td></tr>')
    return '<div class="panel tablewrap"><table><thead><tr><th>Bag</th><th>Role</th><th>Selection</th><th>Type-compatible candidates</th></tr></thead><tbody>'+' '.join(lines)+'</tbody></table></div>'


def render_report(events: list[Event], findings: list[Finding], stats: list[TopicStats],
                  warnings: list[str], input_files: list[Path], details: list[dict] | None = None) -> str:
    details=details or []
    source_names = ', '.join(x.name for x in input_files)
    charts=''.join('<section class="panel"><h3>'+esc(d.get('source',''))+'</h3>'+
                   '<p class="small">Custom CDR messages decoded: '+str(d.get('custom_decoded',0))+'</p>'+
                   velocity_plot(d.get('velocity_trace',[]),[e for e in events if e.source==d.get('source')])+
                   event_focus_charts(d, events)+'</section>' for d in details if d.get('velocity_trace'))
    discovery_html=render_discovery(details)
    errors = sum(x.severity in ('ERROR','FATAL') for x in events)
    event_window = (f'{utc_iso(events[0].timestamp)} — {utc_iso(events[-1].timestamp)}' if events else 'No events')
    metrics = [(len(events), 'Log / incident events'), (errors, 'Error records'),
               (len([f for f in findings if f.severity == 'HIGH']), 'High-priority correlations'),
               (len(stats), 'ROS2 topics inspected')]
    metric_html = ''.join(f'<div class="metric"><div class="num">{val}</div><span class="small">{esc(label)}</span></div>' for val,label in metrics)
    finding_html = ''
    for finding in findings:
        evidence_html = ''.join(f'<a href="#event-{esc(eid)}">{esc(eid)}</a>' for eid in finding.evidence_ids)
        checks = ''.join(f'<li>{esc(s)}</li>' for s in finding.suggested_checks)
        finding_html += (f'<section class="finding"><div class="finding-head"><span class="pill {esc(finding.severity)}">{esc(finding.severity)}</span>'
                         f'<h3>{esc(finding.title)}</h3></div><p>{esc(finding.explanation)}</p>'
                         f'<p class="small">Evidence status: {esc(finding.confidence)}</p><ul>{checks}</ul>'
                         f'<div class="evidence">{evidence_html}</div></section>')
    event_html = ''.join(f'<tr id="event-{esc(e.event_id)}"><td><a href="#event-{esc(e.event_id)}">{esc(e.event_id)}</a></td>'
                         f'<td>{esc(utc_iso(e.timestamp))}</td><td class="sev-{esc(e.severity.lower())}">{esc(e.severity)}</td>'
                         f'<td><code>{esc(e.code)}</code></td><td>{esc(e.message)}</td><td class="small">{esc(e.source)}</td></tr>'
                         for e in events[:2000])
    topic_html = ''.join(f'<tr><td><code>{esc(st.topic)}</code></td><td>{st.count:,}</td><td>{st.approx_hz:.2f}</td>'
                         f'<td>{st.median_gap_ms:.1f}</td><td>{st.max_gap_ms:.1f}</td></tr>' for st in stats)
    warnings_html = ''.join(f'<li>{esc(x)}</li>' for x in warnings)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Robot Incident Analyzer — Report</title><style>{STYLE}</style></head><body><main>
<div class="eyebrow">Robot Incident Analyzer · offline MVP v{__version__}</div><h1>Robot incident report</h1>
<p class="muted">Evidence-first investigation of recorded robot events. No files uploaded or AI model called.</p>
<div class="small"><b>Input:</b> {esc(source_names)}<br><b>Recorded window (UTC):</b> {esc(event_window)}</div>
<div class="summary">{metric_html}</div><div class="notice"><b>Interpretation warning:</b> Correlated events are hypotheses, not verified root causes. Topic gaps use recording timestamps, not hardware sensor timestamps. No issues detected does not prove a healthy robot.</div>
<h2>Topic auto-discovery</h2>{discovery_html}
<h2>Velocity comparison · recording timestamps</h2>
<p class="muted">Aligned command/feedback curves, incident markers, and expandable anomaly-centered windows. Click a window for ±2.5 second inspection.</p>{charts or '<div class="panel muted">No unambiguous command / odometry pair.</div>'}
<h2>Investigation findings</h2>{finding_html}
<h2>Incident timeline</h2><div class="toolbar"><input id="event-filter" type="search" placeholder="Search events / codes" aria-label="Filter event table"><select id="severity-filter" aria-label="Filter severity"><option value="">All severities</option><option value="WARN">WARN</option><option value="ERROR">ERROR</option><option value="FATAL">FATAL</option><option value="INFO">INFO</option></select></div><div class="panel tablewrap"><table id="events-table"><thead><tr><th>ID</th><th>UTC time</th><th>Severity</th><th>Code</th><th>Message / observation</th><th>Source</th></tr></thead><tbody>{event_html}</tbody></table></div>
<h2>ROS2 topic timing</h2><div class="panel tablewrap"><table><thead><tr><th>Topic</th><th>Messages</th><th>Approx Hz</th><th>Median gap (ms)</th><th>Max gap (ms)</th></tr></thead><tbody>{topic_html or '<tr><td colspan="5" class="muted">No bag topics inspected</td></tr>'}</tbody></table></div>
<h2>Coverage and limitations</h2><div class="panel"><ul><li>CSV, ROS2 DB3 and MCAP supported; MCAP zstd/lz4 chunks require optional decompression packages.</li><li>Standard CDR types decoded, plus selected custom .msg types when authorized schema directories and explicit field maps are provided in configuration.</li><li>Custom .idl, arbitrary binary layouts, DDS XCDR2, and automatic field-semantic inference are not supported; missing/incompatible schema fields are excluded with warnings.</li><li>Experimental thresholds can be configured; velocity difference can reflect intentional stop, safety state or clock/frame mismatch.</li><li>Topic name/type matching is a candidate inference, not a guarantee of robot semantics; inspect mapping results before trusting any command/odom comparison.</li><li>Maximum 2,000 events displayed in HTML; full collection saved as report.json.</li>{warnings_html}</ul></div>
<p class="small" style="margin-top:35px">Generated locally · Synthetic examples only · Do not upload confidential customer or employer data</p>
<script>
(function(){{
const input=document.getElementById('event-filter'), severity=document.getElementById('severity-filter');
function apply(){{const q=input.value.toLowerCase(), s=severity.value;
document.querySelectorAll('#events-table tbody tr').forEach(row=>{{
row.style.display=(row.textContent.toLowerCase().includes(q)&&(!s||row.cells[2].textContent.trim()===s))?'':'none';
}});}}
if(input&&severity){{input.addEventListener('input',apply);severity.addEventListener('change',apply);}}
}})();
</script></main></body></html>'''


def save_report(output_dir: Path, events: list[Event], findings: list[Finding],
                stats: list[TopicStats], warnings: list[str], input_files: list[Path],
                details: list[dict] | None = None):
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {'tool': 'Robot Incident Analyzer', 'version': __version__,
               'scope': 'offline; recording timestamps; evidence is not root-cause proof',
               'inputs': [p.name for p in input_files], 'warnings': warnings,
               'events': [e.to_dict() for e in events], 'findings': [f.to_dict() for f in findings],
               'topic_stats': [s.to_dict() for s in stats], 'telemetry': details or []}
    (output_dir / 'report.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    (output_dir / 'report.html').write_text(render_report(events, findings, stats, warnings, input_files, details), encoding='utf-8')
