"""Self-contained investigation dashboard primitives.

No JavaScript framework, CDN, online fonts, or sensor-data uploads.
SVG binned plots are deliberately labelled as event *counts*, not root-cause probability.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import html
import math
import re

from .models import Event, Finding, TopicStats, utc_iso


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


DASHBOARD_CSS = r'''
:root{--bg:#08111f;--panel:#111d2d;--panel2:#132337;--border:#27364b;--ink:#f2f6fc;--muted:#9db0c8;--mint:#53dec4;--amber:#f5bb65;--red:#ff7889;--blue:#7eabf4;--radius:17px;color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--ink);margin:0;font:14px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif}
a{color:var(--mint);text-decoration:none}a:hover{text-decoration:underline}
.report-shell{display:grid;grid-template-columns:225px minmax(0,1fr);min-height:100vh}
.rail{padding:26px 18px;background:#0b1523;border-right:1px solid var(--border);position:sticky;top:0;height:100vh;align-self:start;display:flex;flex-direction:column;gap:22px}
.brand{display:flex;gap:11px;align-items:center;font-size:14px;font-weight:800;letter-spacing:-.025em;color:var(--ink)}
.brand-mark{display:grid;place-items:center;background:linear-gradient(145deg,#35d5b4,#5b9ae5);color:#071724;width:37px;height:37px;border-radius:12px;font-size:18px}
.brand span span{display:block;color:var(--muted);font-size:10px;font-weight:600;letter-spacing:.13em;text-transform:uppercase}
.nav-heading{font-size:10px;letter-spacing:.16em;color:#8195b1;font-weight:750;margin:0 13px 8px}
.rail a.nav-link{display:flex;align-items:center;color:#a9b9d0;border-radius:9px;padding:10px 12px;margin:2px 0;font-size:13px;font-weight:600;gap:10px}
.rail a.nav-link:hover,.rail a.nav-link:focus{background:#1b3044;color:var(--ink);text-decoration:none}
.nav-num{color:var(--mint);font-size:10px;font-weight:800}
.rail-bottom{margin-top:auto;border:1px solid #2a4054;border-radius:13px;padding:12px;background:#122334;color:#b7c7d8;font-size:11px;line-height:1.55}
.report-main{min-width:0;max-width:1450px;width:100%;margin:0 auto;padding:34px 44px 82px}
.eyebrow{color:var(--mint);text-transform:uppercase;letter-spacing:.16em;font-size:10px;font-weight:800}
.hero-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-top:10px}
h1{font-size:clamp(28px,3.1vw,43px);letter-spacing:-.052em;margin:0;line-height:1.2}
h2{font-size:21px;letter-spacing:-.035em;margin:0 0 6px}h3{margin:0;font-size:15px;letter-spacing:-.015em}
.dek{margin:12px 0 4px;font-size:14px;color:var(--muted);max-width:720px}
.report-chip{border:1px solid #2a5360;padding:6px 10px;border-radius:9px;color:#90e5d5;background:#133039;font-size:11px;font-weight:800;white-space:nowrap}
.file-meta{color:var(--muted);font-size:11px;margin-top:13px;overflow-wrap:anywhere}
.kpi-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:25px 0 26px}
.kpi{background:linear-gradient(145deg,#14283b,#101d2e);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;min-height:112px}
.kpi-val{font-size:30px;font-weight:800;line-height:1.23;letter-spacing:-.06em}.kpi-label{color:var(--muted);font-size:11px;font-weight:650;margin-top:9px;display:block}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:16px;margin:28px 0 13px}
.section-head p{margin:0;color:var(--muted);font-size:12px}
.grid-two{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(260px,1fr);gap:14px}
.box-card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:20px;min-width:0}
.card-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:13px}
.aux-text{color:var(--muted);font-size:11px}
.density-chart{width:100%;height:auto;display:block;overflow:visible}.density-chart .bar{transition:opacity .18s,filter .18s;cursor:pointer}
.density-chart .bar:hover,.density-chart .bar:focus{filter:brightness(1.65);outline:none}.density-chart .bar:focus{stroke:var(--mint);stroke-width:1.5}
.density-chart text{font-size:10px;fill:#91a6bf}.density-legend{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0 0;font-size:11px;color:var(--muted)}
.legend-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}
.legend-dot.error{background:var(--red)}.legend-dot.warn{background:var(--amber)}.legend-dot.info{background:var(--blue)}
.insight-note{background:#132535;border:1px solid #254253;border-radius:10px;color:#c4d8e6;font-size:11px;padding:10px 12px;margin-top:12px}
.signal-grid{display:grid;gap:10px}.signal-group{display:grid;grid-template-columns:132px 1fr 43px;gap:9px;align-items:center;font-size:11px;color:#d9e6f5}
.signal-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.signal-meter{height:7px;background:#1a3346;border-radius:99px;overflow:hidden}.signal-meter span{display:block;background:linear-gradient(90deg,#4a9ddd,#55d8bd);height:100%;border-radius:99px}
.pill-inline{display:inline-flex;gap:7px;align-items:center;background:#1c3043;color:#bfd1e5;border:1px solid #32465b;border-radius:30px;padding:4px 10px;font-size:10px;font-weight:750}
.findings-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.investigation-card{border-radius:14px;border:1px solid var(--border);background:#111f32;padding:18px;min-width:0}
.investigation-card.high{border-top:3px solid var(--red)}.investigation-card.medium{border-top:3px solid var(--amber)}.investigation-card.info{border-top:3px solid var(--mint)}
.finding-head{display:flex;gap:9px;justify-content:space-between;align-items:start;margin:0 0 8px}
.severity-pill{font-size:10px;font-weight:800;padding:4px 8px;border-radius:6px;white-space:nowrap}
.severity-pill.high{background:#3a2634;color:#ffa6b0}.severity-pill.medium{background:#383022;color:#ffd28f}.severity-pill.info{background:#173a3e;color:#8feadd}
.investigation-card p{color:#c1cee1;margin:6px 0 10px;font-size:12px}.investigation-card ol{padding-left:18px;margin:9px 0;color:#afc1d7;font-size:11px}
.evidence-link{font-size:11px;display:inline-block;margin:4px 5px 0 0;padding:5px 8px;background:#193548;border-radius:6px;color:#8eecdc;border:1px solid #2b5363}
.evidence-link:hover{background:#245065;text-decoration:none}
.quick-filter{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 14px}
.filter-chip{cursor:pointer;border:1px solid #33465b;background:#142536;color:#bdc9d9;padding:7px 11px;border-radius:8px;font-size:11px;font-weight:700}
.filter-chip.active{background:#1a4a4b;border-color:#3bc7b5;color:#a5f4e5}
.filter-chip:hover{border-color:#68bfb1}
.input-search,.input-select{background:#0c1928;border:1px solid #31445a;border-radius:9px;color:#e4ecf6;padding:10px 12px;font:inherit;font-size:12px;max-width:100%}
.event-tools{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0;align-items:center}
.table-scroll{max-width:100%;overflow-x:auto;border:1px solid #26394c;border-radius:11px}
.report-table{width:100%;border-collapse:collapse;font-size:11px}
.report-table th{background:#152638;color:#aec0d3;font-weight:800;text-transform:uppercase;letter-spacing:.05em;font-size:10px;padding:12px;text-align:left;white-space:nowrap}
.report-table td{border-top:1px solid #24354b;padding:11px 12px;vertical-align:top;color:#c8d7e7}
.report-table tr:hover td{background:#172b3f}.report-table tr:target td{background:#183f4d;outline:1px solid #52ddc4}
.report-table code{color:#b3d2eb;white-space:nowrap}.status-warn{color:#f6c278!important}.status-error,.status-fatal{color:#ff8e9a!important}.status-info{color:#9bdad5!important}
.report-table tbody tr{scroll-margin-top:70px}
.topic-caption{color:var(--muted);font-size:11px;margin:11px 0}.warning-list li{color:#b9c8d9;font-size:12px;margin:8px 0;overflow-wrap:anywhere}
.warning-block{border:1px solid #655038;border-left:3px solid var(--amber);background:#292636;color:#e9cfac;border-radius:10px;padding:14px 16px;margin:14px 0;font-size:12px}
.empty{padding:14px;color:var(--muted)}
.chart-legend{display:flex;gap:20px;flex-wrap:wrap;font-size:11px;margin:12px 0;color:#bbd0e6}.chart-legend span::before{content:'';display:inline-block;width:14px;height:3px;margin-right:6px;vertical-align:middle;background:var(--mint)}.chart-legend .obs::before{background:var(--amber)}.chart-legend .fault::before{background:var(--red);border-top:2px dashed var(--red);height:0}
.chart{width:100%;height:auto;max-height:315px}.focus{border-radius:10px;border:1px solid var(--border);padding:12px 14px;background:#152538;margin:9px 0}.focus summary{cursor:pointer;color:#dbecf8;font-size:12px}
.focus summary:hover{color:var(--mint)}.small,.muted{color:var(--muted)}.small{font-size:11px}.tablewrap{overflow-x:auto}
.topic-mapping{margin:12px 0}.topic-table td,.topic-table th{text-align:left;border-bottom:1px solid var(--border);padding:10px;font-size:12px}
.visually-hidden{position:absolute!important;height:1px;width:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
@media(max-width:1050px){.report-shell{grid-template-columns:180px minmax(0,1fr)}.report-main{padding:29px 22px}.grid-two{grid-template-columns:1fr}.findings-grid{grid-template-columns:1fr}}
@media(max-width:720px){.report-shell{display:block}.rail{position:relative;height:auto;display:flex;flex-direction:row;justify-content:space-between;align-items:center;padding:12px 18px}.rail nav,.rail-bottom{display:none}.report-main{padding:25px 14px 60px}.kpi-row{grid-template-columns:repeat(2,minmax(0,1fr))}.kpi{padding:14px}.kpi-val{font-size:25px}.hero-head{flex-direction:column}.signal-group{grid-template-columns:90px 1fr 34px}}
@media print{body{background:white;color:#1b2b3d}.rail,.event-tools,.quick-filter{display:none!important}.report-shell{display:block}.report-main{max-width:100%;padding:0}.box-card,.kpi,.investigation-card{break-inside:avoid;box-shadow:none;border-color:#9aa9b3;color:#1b2b3d;background:white}.report-table td,.report-table th{color:#1b2b3d}svg{max-width:100%}}
'''


def density_timeline(events: list[Event], bins: int = 40) -> str:
    """SVG event-count histogram; timestamps are recording times, not full bag coverage."""
    ordered = sorted((e for e in events if math.isfinite(e.timestamp)), key=lambda e:e.timestamp)
    if not ordered:
        return '<div class="empty">No WARN, ERROR or INFO events to plot.</div>'
    first, last = ordered[0].timestamp, ordered[-1].timestamp
    start = first
    end = last if last > first else first + 1.0
    counts = [{'ERROR': 0,'WARN':0,'INFO':0} for _ in range(bins)]
    for e in ordered:
        i = min(bins-1,max(0,int((e.timestamp-start)/(end-start)*bins)))
        level = 'ERROR' if e.severity in ('ERROR','FATAL') else ('WARN' if e.severity == 'WARN' else 'INFO')
        counts[i][level] += 1
    maxcount = max(1,max(sum(c.values()) for c in counts))
    rects=[]
    palette={'ERROR':'#ff7889','WARN':'#f5bb65','INFO':'#7eabf4'}
    plot_top=26
    height=132
    x0=26
    width=688
    stride=width/bins
    bw=max(2.0,stride-3.5)
    for idx,c in enumerate(counts):
        x=x0+stride*idx
        stack=plot_top+height
        lo=start+(end-start)*idx/bins
        hi=(start+(end-start)*(idx+1)/bins) if idx<bins-1 else end+0.001
        count=sum(c.values())
        bars=[]
        for sev in ('INFO','WARN','ERROR'):
            if c[sev] == 0: continue
            h=height*c[sev]/maxcount
            stack -= h
            bars.append(f'<rect x="{x:.2f}" y="{stack:.2f}" width="{bw:.2f}" height="{max(1,h):.2f}" fill="{palette[sev]}" rx="1"/>')
        if not bars: bars=[f'<rect x="{x:.2f}" y="{plot_top+height-2}" width="{bw:.2f}" height="2" fill="#294054"/>']
        desc=f'{count} event(s): {c["ERROR"]} errors, {c["WARN"]} warnings, {c["INFO"]} informational'
        rects.append(f'<g class="bar" tabindex="0" role="button" aria-label="Filter timeline bin {idx+1}: {escape(desc)}" data-bin="{idx}" data-start="{lo:.9f}" data-end="{hi:.9f}"><title>{escape(desc)}</title>'+''.join(bars)+'</g>')
    grids=''.join(f'<line x1="26" x2="714" y1="{plot_top+height-height*n/4:.1f}" y2="{plot_top+height-height*n/4:.1f}" stroke="#31435a" stroke-dasharray="3 5"/>' for n in range(5))
    labels=''.join(f'<text x="{26+688*n/4-4:.1f}" y="181" text-anchor="middle">{(end-start)*n/4:.1f}s</text>' for n in range(5))
    return (f'<svg viewBox="0 0 740 196" role="img" class="density-chart" aria-label="Stacked counts of recorded log events across the observed event window">'
            +grids+''.join(rects)+labels+f'<text x="26" y="13">{escape(utc_iso(start))} UTC</text></svg>'
            +'<div class="density-legend"><span><i class="legend-dot error"></i>ERROR / FATAL</span><span><i class="legend-dot warn"></i>WARN</span><span><i class="legend-dot info"></i>INFO</span></div>'
            +'<p class="aux-text">Click a bar to filter the event table below. Horizontal axis is seconds after first recorded event, not full bag duration.</p>')


def top_sources(events: list[Event]) -> str:
    counts=Counter(re.sub(r':row\d+$', '', e.source or 'Unknown') for e in events)
    if not counts:return '<p class="empty">No event sources observed.</p>'
    mx=max(counts.values())
    return '<div class="signal-grid">'+''.join(
        '<div class="signal-group"><span class="signal-name" title="'+escape(src)+'">'+escape(src)+'</span>'
        +f'<div class="signal-meter"><span style="width:{n/mx*100:.1f}%"></span></div><b>{n}</b></div>'
        for src,n in counts.most_common(7))+'</div><p class="aux-text">Recorded event volume by input source. A larger bar does not mean a less reliable robot.</p>'


def topic_volume(stats: list[TopicStats]) -> str:
    ordered=sorted(stats,key=lambda s:s.count,reverse=True)[:8]
    if not ordered: return '<p class="empty">No ROS2 topic statistics available for CSV-only inputs.</p>'
    mx=max(s.count for s in ordered) or 1
    return '<div class="signal-grid">'+''.join(
        '<div class="signal-group"><span class="signal-name" title="'+escape(s.topic)+'">'+escape(s.topic)+'</span>'
        +f'<div class="signal-meter"><span style="width:{s.count/mx*100:.1f}%"></span></div><b>{s.count:,}</b></div>'
        for s in ordered)+'</div><p class="aux-text">Message count, not stream health. Check the timing table and coverage notes for limitations.</p>'


def topic_timing_variation(stats: list[TopicStats]) -> str:
    """Compare max-to-median recording gaps (neither a fault nor a health score)."""
    ordered = sorted(
        (s for s in stats if s.count >= 3 and s.median_gap_ms > 0 and math.isfinite(s.max_gap_ms)),
        key=lambda s: s.max_gap_ms / s.median_gap_ms, reverse=True)[:8]
    if not ordered:
        return '<p class="empty">Not enough timestamp samples to compare inter-message gaps.</p>'
    items=[]
    for s in ordered:
        ratio=max(1., s.max_gap_ms/s.median_gap_ms)
        visual_ratio=min(ratio/12.0,1.0)*100
        items.append(
            '<div class="signal-group"><span class="signal-name" title="'+escape(s.topic)+'">'+escape(s.topic)+'</span>'
            f'<div class="signal-meter" title="Max gap {s.max_gap_ms:.1f} ms; median gap {s.median_gap_ms:.1f} ms"><span style="width:{visual_ratio:.1f}%;background:linear-gradient(90deg,#60b7df,#f4bb71)"></span></div>'
            f'<b>{ratio:.1f}×</b></div>')
    return ('<div class="signal-grid">'+''.join(items)+'</div>'
            '<p class="aux-text">Max / median interval from recording timestamps. Bars saturate at 12×. '
            'Bursty traffic or recorder behavior can explain gaps; no sensor fault is inferred.</p>')


def dashboard_script() -> str:
    """Interactive filters, keyboard-operable histogram, and export-free navigation.

    All user-provided strings are escaped server-side; no innerHTML for dataset content.
    """
    return r'''<script>
(function(){
 const rows=Array.from(document.querySelectorAll('#events-table tbody tr'));
 const search=document.getElementById('event-filter');
 const severity=document.getElementById('severity-filter');
 const count=document.getElementById('filtered-count');
 const clear=document.getElementById('clear-window');
 const binText=document.getElementById('active-bin-label');
 const chips=Array.from(document.querySelectorAll('[data-severity-chip]'));
 const bars=Array.from(document.querySelectorAll('.density-chart [data-bin]'));
 let windowRange=null;
 function apply(){
   const q=(search?.value||'').toLowerCase();
   const s=severity?.value||'';
   let visible=0;
   rows.forEach(row=>{
     const ts=Number(row.dataset.ts);
     const inWindow=!windowRange || (Number.isFinite(ts)&&ts>=windowRange[0]&&ts<windowRange[1]);
     const match=(!q||row.textContent.toLowerCase().includes(q))&&(!s||row.dataset.severity===s)&&inWindow;
     row.hidden=!match;
     if(match)visible++;
   });
   if(count)count.textContent=visible.toLocaleString()+' / '+rows.length.toLocaleString()+' shown';
   chips.forEach(chip=>chip.classList.toggle('active',chip.dataset.severityChip===s));
 }
 if(search) search.addEventListener('input',apply);
 if(severity)severity.addEventListener('change',apply);
 chips.forEach(chip=>chip.addEventListener('click',()=>{if(severity)severity.value=chip.dataset.severityChip;apply();}));
 function selectBar(bar){
   const lo=Number(bar.dataset.start),hi=Number(bar.dataset.end);
   if(!Number.isFinite(lo)||!Number.isFinite(hi))return;
   windowRange=[lo,hi];
   if(window.__riaMoveCursor)window.__riaMoveCursor((lo+hi)/2);
   bars.forEach(b=>b.setAttribute('aria-pressed',String(b===bar)));
   if(binText)binText.textContent='Time window selected · click Reset to show all';
   if(clear)clear.hidden=false;
   apply();
   document.getElementById('timeline')?.scrollIntoView({behavior:'smooth',block:'start'});
 }
 bars.forEach(bar=>{bar.addEventListener('click',()=>selectBar(bar));bar.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectBar(bar);}});});
 if(clear)clear.addEventListener('click',()=>{windowRange=null;bars.forEach(b=>b.setAttribute('aria-pressed','false'));clear.hidden=true;if(binText)binText.textContent='';apply();});
 document.querySelectorAll('a.evidence-link[href^="#event-"]').forEach(a=>a.addEventListener('click',()=>{
    windowRange=null;if(clear)clear.hidden=true;if(search)search.value='';if(severity)severity.value='';apply();
 }));
 apply();
})();
</script>'''
