from __future__ import annotations
import html
import json
from collections import Counter
from pathlib import Path
import math
from .models import Event, Finding, TopicStats, utc_iso
from . import __version__
from .dashboard import DASHBOARD_CSS, density_timeline, top_sources, topic_volume, topic_timing_variation, dashboard_script
from .signal_studio import STUDIO_CSS, studio_markup, studio_script
from .incident_workbench import WORKBENCH_CSS, workbench_markup, workbench_script, cases_from_findings
from .state_timeline import STATE_CSS, build_state_transitions, state_markup, state_script

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
            f'<svg class="chart" viewBox="0 0 790 246" data-tmin="{x0:.6f}" data-tmax="{x1:.6f}" role="img" '
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
                  warnings: list[str], input_files: list[Path], details: list[dict] | None = None, state_keys=None) -> str:
    """Incident-first offline HTML dashboard; no internet access or JS dependencies."""
    details = details or []
    display_events = sorted(events, key=lambda e: (e.timestamp, e.event_id))[:2000]
    severity_errors = sum(e.severity in ('ERROR', 'FATAL') for e in events)
    severity_warns = sum(e.severity == 'WARN' for e in events)
    high = sum(f.severity == 'HIGH' for f in findings)
    metrics = [
        (f'{len(events):,}', 'Recorded observations'),
        (f'{severity_errors:,}', 'Error / fatal events'),
        (f'{len(findings):,}', 'Investigation findings'),
        (f'{len(stats):,}', 'ROS2 topics inspected'),
    ]
    metric_html = ''.join(
        f'<div class="kpi"><div class="kpi-val">{esc(value)}</div>'
        f'<span class="kpi-label">{esc(label)}</span></div>'
        for value, label in metrics)

    transitions = build_state_transitions(events, state_keys)
    cases = cases_from_findings(findings, events, details, state_transitions=transitions)
    case_lookup = {(case["code"], case["evidence_ids"][0]): idx for idx, case in enumerate(cases) if case["evidence_ids"]}
    # Navigable event evidence never silently vanishes due to filters.
    evidence_visible = {e.event_id for e in display_events}
    finding_cards = []
    for f in findings[:30]:
        tone = (f.severity or 'INFO').lower()
        if tone not in ('high', 'medium', 'info'): tone = 'info'
        checks = ''.join('<li>' + esc(q) + '</li>' for q in f.suggested_checks[:4])
        evidence = ''.join(
            (f'<a class="evidence-link" href="#event-{esc(eid)}" title="Jump to evidence">'
             f'↗ {esc(eid)}</a>' if eid in evidence_visible else
             f'<span class="evidence-link" title="Evidence in JSON export">{esc(eid)} · JSON</span>')
            for eid in f.evidence_ids[:6])
        inspect_index = case_lookup.get((f.code, f.evidence_ids[0]), None) if f.evidence_ids else None
        inspect_button = (f'<button type="button" class="case-event" data-inspect-case="{inspect_index}">Inspect synchronized evidence ↗</button>' if inspect_index is not None else '')
        finding_cards.append(
            f'<article class="investigation-card {tone}"><div class="finding-head">'
            f'<h3>{esc(f.title)}</h3><span class="severity-pill {tone}">{esc(f.severity)}</span>'
            f'</div><p>{esc(f.explanation)}</p><div class="aux-text">Evidence: {esc(f.confidence)}</div>'
            f'<ol>{checks}</ol><div>{evidence}</div>{inspect_button}</article>')
    if not finding_cards:
        finding_cards=['<p class="empty">No configured investigation rules matched. This is not proof of robot health.</p>']
    if len(findings) > 30:
        finding_cards.append(f'<p class="aux-text">Showing 30 of {len(findings):,} findings. Full list: report.json.</p>')

    # Event table filtering is client-side and never alters original report.json.
    event_case_lookup = {eid: idx for idx, c in enumerate(cases) for eid in c['evidence_ids']}
    def event_row(e):
        inspect = (f'<button type="button" class="filter-chip" '
                   f'data-event-inspect="{esc(e.event_id)}">Investigate ↗</button>'
                   if e.event_id in event_case_lookup else '—')
        return (
            f'<tr id="event-{esc(e.event_id)}" data-ts="{e.timestamp:.9f}" '
            f'data-severity="{esc(e.severity)}">'
            f'<td><a href="#event-{esc(e.event_id)}">{esc(e.event_id)}</a></td>'
            f'<td>{esc(utc_iso(e.timestamp))}</td>'
            f'<td class="status-{esc(e.severity.lower())}">{esc(e.severity)}</td>'
            f'<td><code>{esc(e.code)}</code></td><td>{esc(e.message)}</td>'
            f'<td>{esc(e.source)}</td><td>{inspect}</td></tr>'
        )
    event_html = ''.join(event_row(e) for e in display_events)
    table = ('<div class="table-scroll"><table id="events-table" class="report-table">'
             '<thead><tr><th>ID</th><th>UTC timestamp</th><th>Level</th><th>Code</th>'
             '<th>Evidence / observation</th><th>Input</th><th>Action</th></tr></thead><tbody>'
             + event_html + '</tbody></table></div>')
    topic_rows=''.join(
        f'<tr><td><code>{esc(st.topic)}</code><div class="aux-text">{esc(st.message_type)}</div></td>'
        f'<td>{st.count:,}</td><td>{st.approx_hz:.2f}</td>'
        f'<td>{st.median_gap_ms:.1f}</td><td>{st.max_gap_ms:.1f}</td></tr>'
        for st in sorted(stats, key=lambda x: -x.count))
    topic_table = ('<div class="table-scroll"><table class="report-table"><thead><tr>'
                   '<th>Topic / type</th><th>Messages</th><th>Approx Hz</th>'
                   '<th>Median gap ms</th><th>Max gap ms</th></tr></thead><tbody>'
                   + (topic_rows or '<tr><td colspan="5">No ROS2 topic statistics available</td></tr>')
                   + '</tbody></table></div>')

    plots = []
    for d in details:
        if not d.get('velocity_trace'): continue
        src = d.get('source', '')
        trace = d['velocity_trace']
        mark = [e for e in events if e.source == src]
        plots.append('<div class="box-card"><div class="card-heading"><h3>' + esc(src)
                     + '</h3><span class="pill-inline">Recorded signals</span></div>'
                     + f'<p class="aux-text">{len(trace):,} aligned samples ·'
                     f' · Custom CDR messages decoded: {d.get("custom_decoded", 0):,}</p>'
                     + velocity_plot(trace,mark) + event_focus_charts(d,events) + '</div>')
    warnings_html=''.join('<li>'+esc(x)+'</li>' for x in warnings)
    alert_note=(f'{len(warnings)} coverage warning(s) need review.' if warnings
                else 'No input warnings emitted. This does not confirm full diagnostic coverage.')
    event_window=(f'{utc_iso(min(e.timestamp for e in events))} — {utc_iso(max(e.timestamp for e in events))}'
                  if events else 'No events')
    file_names=', '.join(p.name for p in input_files)
    css = STYLE + '\n' + DASHBOARD_CSS + '\n' + STUDIO_CSS + '\n' + WORKBENCH_CSS + '\n' + STATE_CSS
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Robot Incident Analyzer | Incident Overview</title><style>{css}</style></head>
<body><div class="report-shell">
<aside class="rail" aria-label="Report navigation">
 <a class="brand" href="#overview"><span class="brand-mark" aria-hidden="true">⌁</span><span>R I A <span>Robot insights</span></span></a>
 <nav aria-label="Sections"><p class="nav-heading">INVESTIGATE</p>
  <a class="nav-link" href="#overview"><span class="nav-num">01</span> Overview</a>
  <a class="nav-link" href="#findings"><span class="nav-num">02</span> Findings</a>
  <a class="nav-link" href="#incident-workbench"><span class="nav-num">03</span> Workbench</a>
  <a class="nav-link" href="#state-timeline"><span class="nav-num">04</span> Robot states</a>
  <a class="nav-link" href="#signals"><span class="nav-num">05</span> Signals</a>
  <a class="nav-link" href="#timeline"><span class="nav-num">06</span> Event log</a>
  <a class="nav-link" href="#topics"><span class="nav-num">07</span> Topic coverage</a>
 </nav>
 <div class="rail-bottom"><strong>Offline by design</strong><br>No files uploaded to external servers. No AI API. Correlation ≠ causation.<br><br>Experimental diagnostics only.</div>
</aside>
<main class="report-main" id="overview">
<div class="eyebrow">Investigations / recorded data · v{esc(__version__)}</div>
<div class="hero-head"><div><h1>Incident overview</h1><p class="dek">From recorded signals to testable hypotheses. Inspect anomalies, linked evidence and affected telemetry without leaving this report.</p></div>
<span class="report-chip">● OFFLINE ANALYSIS</span></div>
<div class="file-meta"><b>Inputs</b> · {esc(file_names)}<br><b>Observed event window (UTC)</b> · {esc(event_window)}</div>
<div class="kpi-row">{metric_html}</div>
<div class="warning-block"><b>Evidence, not a diagnosis.</b> These counts reflect observed events and configured analysis rules; no fault cause is verified. {esc(alert_note)}</div>
<section aria-labelledby="activity-title">
<div class="section-head"><div><h2 id="activity-title">Event activity</h2><p>Look for bursts in recorded events; select a window to filter the table.</p></div><span class="pill-inline">{severity_warns:,} WARN · {severity_errors:,} ERROR/FATAL</span></div>
<div class="grid-two">
<div class="box-card"><div class="card-heading"><h3>Events over recording time</h3><span class="aux-text">Counts per bin</span></div>{density_timeline(events)}</div>
<div class="box-card"><div class="card-heading"><h3>Where events came from</h3><span class="aux-text">Source grouping</span></div>{top_sources(events)}
<div class="insight-note">Source volume is not a reliability rating; merged logs can span multiple robots.</div></div>
</div></section>
<section id="findings" aria-labelledby="findings-title"><div class="section-head"><div><h2 id="findings-title">Investigation queue</h2><p>Evidence-backed observations with concrete follow-up checks, not AI-generated certainty.</p></div><span class="pill-inline">{high} high priority</span></div>
<div class="findings-grid">{''.join(finding_cards)}</div></section>
{workbench_markup(findings, events, details, state_transitions=transitions)}
{state_markup(transitions)}
<section id="signals" aria-labelledby="signals-title"><div class="section-head"><div><h2 id="signals-title">Velocity comparison · Signal explorer</h2><p>Aligned command/odometry speeds and expandable anomaly windows where both streams exist.</p></div></div>
{studio_markup(details, events)}
{''.join(plots) if plots else '<div class="box-card empty">No unambiguous command / odometry pair recorded. Inspect topic mapping and coverage below.</div>'}
</section>
<section id="timeline" aria-labelledby="events-title"><div class="section-head"><div><h2 id="events-title">Incident timeline</h2><p>Search, filter severity, or jump here from a finding.</p></div><span id="filtered-count" class="pill-inline" aria-live="polite">{len(display_events):,} / {len(display_events):,} shown</span></div>
<div class="quick-filter" aria-label="Severity quick filters"><button class="filter-chip active" data-severity-chip="">All events</button><button class="filter-chip" data-severity-chip="ERROR">Errors</button><button class="filter-chip" data-severity-chip="WARN">Warnings</button><button class="filter-chip" data-severity-chip="INFO">Info</button><button class="filter-chip" data-severity-chip="FATAL">Fatal</button></div>
<div class="event-tools"><label class="visually-hidden" for="event-filter">Search events</label><input id="event-filter" class="input-search" type="search" placeholder="Search code, source, message…" aria-label="Search event log">
<label class="visually-hidden" for="severity-filter">Severity</label><select class="input-select" id="severity-filter"><option value="">All severities</option><option value="ERROR">ERROR</option><option value="WARN">WARN</option><option value="INFO">INFO</option><option value="FATAL">FATAL</option></select>
<button class="filter-chip" id="clear-window" type="button" hidden>Reset time window ↻</button><span class="aux-text" id="active-bin-label"></span></div>
{table}
{('<p class="topic-caption">First 2,000 time-sorted events shown; complete event set in report.json.</p>' if len(events)>2000 else '')}
</section>
<section id="topics" aria-labelledby="topics-title"><div class="section-head"><div><h2 id="topics-title">Topics & coverage</h2><p>Check which signals were recorded before interpreting an apparent incident.</p></div></div>
<div class="grid-two"><div class="box-card"><div class="card-heading"><h3>Most recorded topics</h3><span class="aux-text">By message count</span></div>{topic_volume(stats)}</div>
<div class="box-card"><div class="card-heading"><h3>Topic auto-discovery</h3><span class="aux-text">Roles must be reviewed</span></div>{render_discovery(details)}</div></div>
<div class="box-card" style="margin-top:14px"><div class="card-heading"><h3>Largest timing variations</h3><span class="aux-text">Recording gap ratio</span></div>{topic_timing_variation(stats)}</div>
<div class="box-card" style="margin-top:14px"><h3 style="margin-bottom:10px">Topic timing table</h3><p class="topic-caption">Approx Hz and gaps use recorded timestamps, not sensor hardware stamps; sorting based on recorded message volume.</p>{topic_table}</div>
<div class="box-card" style="margin-top:14px"><h3>Limitations & analyst notes</h3><ul class="warning-list"><li>Standard CDR types decoded, plus configured custom message schemas; XCDR2, arbitrary .idl and unsupported schemas may be excluded.</li>
<li>Timeline is event-derived; unrecorded time and missing topics are not shown as healthy periods.</li><li>Timestamp-aligned events are observations, not verified root causes. No finding does not mean a healthy robot.</li>
<li>Event table displays at most 2,000 records; full results are in report.json.</li>{warnings_html}</ul></div>
</section>
<footer class="topic-caption" style="margin-top:30px">Robot Incident Analyzer · Generated locally · Research prototype. Review data before sharing reports.</footer>
</main></div>{dashboard_script()}{studio_script()}{workbench_script()}{state_script()}</body></html>'''


def save_report(output_dir: Path, events: list[Event], findings: list[Finding],
                stats: list[TopicStats], warnings: list[str], input_files: list[Path],
                details: list[dict] | None = None, state_keys=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {'tool': 'Robot Incident Analyzer', 'version': __version__,
               'scope': 'offline; recording timestamps; evidence is not root-cause proof',
               'inputs': [p.name for p in input_files], 'warnings': warnings,
               'events': [e.to_dict() for e in events], 'findings': [f.to_dict() for f in findings],
               'topic_stats': [s.to_dict() for s in stats], 'telemetry': details or [],
               'state_transitions':build_state_transitions(events, state_keys),
               'state_config_keys':list(state_keys) if state_keys is not None else None}
    (output_dir / 'report.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    (output_dir / 'report.html').write_text(render_report(events, findings, stats, warnings, input_files, details, state_keys), encoding='utf-8')
