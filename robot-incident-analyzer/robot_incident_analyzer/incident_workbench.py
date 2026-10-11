"""Offline incident-centered multi-signal evidence views.

Visual correlations are descriptive, never proof of a root cause.
All displayed incident and signal timestamps use bag recording times.
"""
from __future__ import annotations

import math
import re
from .signal_studio import escape_json


def priority(code: str, field: str, topic: str) -> int:
    """Select useful signals by *context*, without claiming causation."""
    text = (field + ' ' + topic).lower()
    code = code.upper()
    score = 1
    families = {
        'BATTERY': ('percentage', 'voltage', 'current', 'temperature'),
        'CHARG': ('percentage', 'voltage', 'current', 'linear.x'),
        'DOCK': ('linear.x', 'percentage', 'voltage', 'angular.z'),
        'IMU': ('quaternion', 'angular_velocity', 'linear_acceleration'),
        'LASER': ('valid_return_ratio', 'nan_ranges'),
        'SCAN': ('valid_return_ratio', 'nan_ranges'),
        'CMD_': ('linear.x', 'angular.z', 'voltage'),
        'ODOM': ('linear.x', 'position.x', 'position.y'),
        'TF_': ('position.x', 'position.y', 'angular.z'),
        'MOTOR': ('linear.x', 'current'),
    }
    for key, terms in families.items():
        if key in code:
            for i, phrase in enumerate(terms):
                if phrase in text:
                    score += 100 - i * 10
    if 'linear.x' in text: score += 20
    if 'voltage' in text: score += 7
    return score


def same_robot_topic(topic: str, robot_id: str) -> bool:
    """Do not merge another robot's named topic into an incident dossier."""
    if not topic or not topic.startswith('/') or robot_id in ('', 'unknown', None):
        return True
    # Only enforce this when the topic uses a robot namespace. Unnamespaced
    # standard topics may be shared/global and cannot be assigned confidently.
    pieces = topic.strip('/').split('/')
    robot_ns = re.match(r'^(?:robot|agv|amr)[_-]?[a-z0-9]+$', pieces[0], re.IGNORECASE)
    return len(pieces) < 2 or not robot_ns or pieces[0] == robot_id


def cases_from_findings(findings, events, details, *, limit=24, before=10., after=10.):
    """Build source-scoped investigation views, bounded for standalone HTML.

    Cases with missing evidence are retained but never joined to unrelated
    sources or imagined timestamps.
    """
    by_id = {e.event_id: e for e in events}
    cases=[]
    for idx, finding in enumerate(findings[:limit]):
        evidence=[by_id[eid] for eid in finding.evidence_ids if eid in by_id]
        if not evidence:
            continue
        anchor=evidence[0]
        if not math.isfinite(anchor.timestamp):
            continue
        source=anchor.source
        t=anchor.timestamp
        relevant=[e for e in events if e.source==source and math.isfinite(e.timestamp)
                  and t-before <= e.timestamp <= t+after]
        # Prefer events directly cited by the finding, then nearby observations.
        related_ids=set(finding.evidence_ids)
        relevant.sort(key=lambda e:(e.event_id not in related_ids,abs(e.timestamp-t),e.event_id))
        signals=[]
        paths=[]
        for d in details:
            if d.get('source')!=source:
                continue
            for s in d.get('signals',[]):
                samples=s.get('samples',[])
                if not samples or not same_robot_topic(s.get('topic',''), anchor.robot_id): continue
                # Keep continuous context series so changing the focus window remains possible.
                filtered=[p for p in samples if len(p)>=2 and t-30 <= p[0] <= t+30]
                if filtered:
                    signals.append({**s,'samples':filtered})
            for path in d.get('paths',[]):
                if path.get('samples') and same_robot_topic(path.get('topic',''), anchor.robot_id):
                    paths.append(path)
        signals.sort(key=lambda s:(-priority(finding.code,s.get('field',''),s.get('topic','')),
                                   s.get('topic',''),s.get('field','')))
        cases.append({
            'id': f'C{idx+1:03d}', 'title': finding.title, 'code':finding.code,
            'severity':finding.severity, 'description':finding.explanation,
            'checks':finding.suggested_checks[:5], 'confidence':finding.confidence,
            'anchor':t, 'source':source, 'robot_id':anchor.robot_id, 'topic':anchor.topic,
            'evidence_ids':finding.evidence_ids[:12],
            'events':[{'id':e.event_id,'t':e.timestamp,'code':e.code,
                       'severity':e.severity,'message':e.message[:250]} for e in relevant[:25]],
            'signals':signals[:8], 'paths':paths[:2],
        })
    return cases


WORKBENCH_CSS=r'''
.case-head{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:13px}
.case-head select,.case-head button,.case-controls select{padding:10px 12px;background:#0c1d2f;border:1px solid #35536c;color:#e6f3ff;border-radius:9px;max-width:100%}
.case-picker{min-width:180px;max-width:100%;flex:1}
.case-heading{display:flex;gap:12px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
.case-heading h3{font-size:21px;line-height:1.4;margin:0}
.case-context{color:#b2c5d8;font-size:12px;line-height:1.8}
.case-controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0}
.case-controls label{font-size:12px;color:#b8cee0}
.case-chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:14px 0}
.case-chart-card{border:1px solid #304960;background:#101f32;border-radius:12px;padding:12px;min-width:0}
.case-chart-title{font-weight:700;font-size:12px;line-height:1.45;margin:0 0 5px;overflow-wrap:anywhere}
.case-chart{width:100%;height:auto;display:block;border-radius:6px;background:#0a1727}
.case-chart text{font-size:11px;fill:#aabed1}
.case-caption{font-size:11px;color:#a9bacf;margin:7px 0 0}
.case-events{display:grid;gap:7px}
.case-event{background:#15283c;border:1px solid #2b4358;color:#dce7f5;border-radius:9px;padding:10px;text-align:left;cursor:pointer;white-space:normal}
.case-event:hover,.case-event:focus-visible{border-color:#55cdb9;outline:1px solid #55cdb9}
.case-event b{margin-right:8px}
.case-event time{color:#b4c9d9;font-size:11px}
.case-badge{font-size:10px;padding:5px 9px;border:1px solid #677b97;border-radius:99px;color:#cfe2f6}
.case-empty{color:#b0c2d3;font-size:12px;padding:22px 7px}
.case-route{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px;font-size:11px;color:#b7cbdd}
.case-route .dot{height:9px;width:9px;border-radius:50%;display:inline-block;background:#f6a45b}
.case-route .dot.red{background:#ff8191}
.case-route .dot.green{background:#59d5bf}
.case-reports{display:flex;gap:12px;justify-content:flex-end;flex-wrap:wrap}
.case-reports button{padding:9px 15px;border:1px solid #4a927f;background:#143b3d;color:#b9f9eb;border-radius:9px;cursor:pointer}
@media(max-width:880px){.case-chart-grid{grid-template-columns:minmax(0,1fr)}}
@media print{.rail,.studio-toolbar,.event-tools,.quick-filter,.case-controls,.case-picker,.case-reports,.filter-chip{display:none!important}
 body,.report-shell,.report-main,.box-card,.case-chart-card{background:white!important;color:#1b2636!important;box-shadow:none!important}
 .report-shell{display:block!important}.report-main{padding:12px!important;max-width:100%!important}
 svg{max-width:100%!important} svg text{fill:#26364b!important}
 .case-chart-card,.investigation-card{break-inside:avoid} .case-event{color:#243247!important}
 .warning-block{border:1px solid #718096!important;color:#27354a!important}
 .case-chart-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
}
'''


def workbench_markup(findings, events, details):
    cases=cases_from_findings(findings,events,details)
    data=escape_json({'cases':cases})
    if not cases:
        intro='<div class="case-empty">No evidence-linked findings in this recording. Not a health clearance.</div>'
    else:
        intro='''<div class="case-head"><label for="case-select">Select incident</label>
 <select id="case-select" class="case-picker" aria-label="Choose a finding to investigate"></select>
 <span class="case-badge">±10 s evidence · configurable</span></div>
 <div id="case-header"></div>
 <div class="case-controls"><label for="case-window">Time window</label><select id="case-window" aria-label="Context window"><option value="5">±5 s</option><option value="10" selected>±10 s</option><option value="30">±30 s</option></select>
 <button type="button" id="case-sync" class="case-event">↗ Sync main time cursor</button></div>
 <div id="case-charts" class="case-chart-grid" aria-label="Contextual multi-sensor graphs"></div>
 <h4>Timestamp-adjacent observations</h4><div id="case-events" class="case-events"></div>'''
    return f'''<section id="incident-workbench" aria-labelledby="case-title"><div class="section-head"><div><h2 id="case-title">Incident workbench</h2>
    <p>Choose an observation to inspect aligned sensors, location on the recorded path and nearby logs.</p></div><span class="pill-inline">Not verified root cause</span></div>
    <div class="box-card">{intro}
    <div class="case-reports"><button id="case-print" type="button" onclick="window.print()">Print / Save as PDF</button></div>
    <p class="case-caption">Events are aligned by bag recording timestamp and source, not by confirmed robot state. Nearby sensor values are observations, not explanations. Print uses your browser's Save as PDF.</p>
    <script type="application/json" id="case-data">{data}</script></div></section>'''


def workbench_script():
    return r'''<script>
(function(){
 const element=document.getElementById('case-data');if(!element)return;
 let cases;try{cases=JSON.parse(element.textContent).cases||[];}catch(_){return;}
 const selector=document.getElementById('case-select');if(!selector||!cases.length)return;
 const section=document.getElementById('incident-workbench');
 const header=document.getElementById('case-header'),plots=document.getElementById('case-charts'),events=document.getElementById('case-events');
 const windowSel=document.getElementById('case-window');let active=0;
 const ns='http://www.w3.org/2000/svg';
 const dom=(tag,cls,content)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(content!==undefined)n.textContent=String(content);return n;};
 function svgNode(p,tag,attrs){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs||{}))n.setAttribute(k,v);p.appendChild(n);return n;}
 function nearest(a,t){if(!a?.length)return null;let left=0,right=a.length;while(left<right){let m=(left+right)>>1;if(a[m][0]<t)left=m+1;else right=m;}const b=a[Math.min(a.length-1,left)],c=a[Math.max(0,left-1)];return Math.abs(b[0]-t)<Math.abs(c[0]-t)?b:c;}
 function chartSvg(){const s=document.createElementNS(ns,'svg');s.setAttribute('viewBox','0 0 600 204');s.setAttribute('class','case-chart');s.setAttribute('role','img');return s;}
 const xx=(t,a,b)=>50+(t-a)/Math.max(1e-6,b-a)*530;
 function drawScalar(entry,c,half){let card=dom('div','case-chart-card');card.appendChild(dom('p','case-chart-title',entry.topic+' / '+entry.field));
 const svg=chartSvg();card.appendChild(svg);const a=c.anchor-half,b=c.anchor+half;let points=entry.samples.filter(p=>p[0]>=a&&p[0]<=b&&Number.isFinite(p[1]));
 if(!points.length){card.appendChild(dom('p','case-empty','No sampled values inside this ±'+half+' s interval.'));plots.appendChild(card);return;}
 let values=points.map(p=>p[1]);let min=Math.min(...values),max=Math.max(...values),pad=Math.max(1e-4,(max-min)*.13,Math.abs(min)*.001);min-=pad;max+=pad;
 const yy=v=>178-(v-min)/(max-min)*143;
 for(let i=0;i<4;i++){let y=178-i*43;svgNode(svg,'line',{x1:50,y1:y,x2:580,y2:y,stroke:'#2b4358','stroke-dasharray':'3 5'});}
 svgNode(svg,'polyline',{points:points.map(p=>xx(p[0],a,b).toFixed(1)+','+yy(p[1]).toFixed(1)).join(' '),stroke:'#57d5c1','stroke-width':'2.6',fill:'none'});
 let x=xx(c.anchor,a,b);svgNode(svg,'line',{x1:x,x2:x,y1:20,y2:178,stroke:'#ffb264','stroke-width':2,'stroke-dasharray':'5 4'});
 let p=nearest(points,c.anchor);let t=svgNode(svg,'text',{x:50,y:18});t.textContent='±'+half+' s · '+points.length+' sampled points';
 let last=svgNode(svg,'text',{x:50,y:197});last.textContent='Nearest sampled: '+p[1].toFixed(3)+' · Δt '+(p[0]-c.anchor).toFixed(2)+' s';
 let maxGap=Math.abs(p[0]-c.anchor);if(maxGap>2)card.appendChild(dom('p','case-caption','Warning: nearest sample is '+maxGap.toFixed(1)+' s away from event; no interpolation.'));
 plots.appendChild(card);
 }
 function drawPath(path,c){let card=dom('div','case-chart-card');card.appendChild(dom('p','case-chart-title','Odometry path · '+path.topic+' · frame '+path.frame));const svg=chartSvg();card.appendChild(svg);
 let samples=path.samples;if(!samples?.length){plots.appendChild(card);return;}
 let xs=samples.map(p=>p[1]),ys=samples.map(p=>p[2]);let x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
 const sx=Math.max(x1-x0,.1),sy=Math.max(y1-y0,.1),scale=Math.min(510/sx,145/sy);
 const px=x=>315+(x-(x0+x1)/2)*scale,py=y=>104-(y-(y0+y1)/2)*scale;
 svgNode(svg,'polyline',{points:samples.map(p=>px(p[1]).toFixed(1)+','+py(p[2]).toFixed(1)).join(' '),stroke:'#72a8f8','stroke-width':3,fill:'none'});
 let start=samples[0],end=samples[samples.length-1];svgNode(svg,'circle',{cx:px(start[1]),cy:py(start[2]),r:5,fill:'#59d5bf'});svgNode(svg,'circle',{cx:px(end[1]),cy:py(end[2]),r:5,fill:'#c1bcf9'});
 let nearestPoint=nearest(samples,c.anchor);let delta=Math.abs(nearestPoint[0]-c.anchor);
 if(delta<=2){svgNode(svg,'circle',{cx:px(nearestPoint[1]),cy:py(nearestPoint[2]),r:9,stroke:'#fff','stroke-width':2,fill:'#ff8191'});card.appendChild(dom('p','case-caption','Approx. event position: X '+nearestPoint[1].toFixed(2)+' m / Y '+nearestPoint[2].toFixed(2)+' m (sample Δt '+delta.toFixed(2)+' s).'));}
 else card.appendChild(dom('p','case-caption','Cannot locate event: nearest odometry sample is '+delta.toFixed(2)+' s away.'));
 const text=svgNode(svg,'text',{x:50,y:18});text.textContent='XY meters · equal scale · not georeferenced';
 plots.appendChild(card);
 }
 function render(index){active=Math.max(0,Math.min(cases.length-1,Number(index)||0));const c=cases[active];selector.value=String(active);header.replaceChildren();plots.replaceChildren();events.replaceChildren();
 const main=dom('div','case-heading');const h=dom('h3','',c.title);main.appendChild(h);main.appendChild(dom('span','case-badge',c.severity));header.appendChild(main);
 header.appendChild(dom('p','case-context',c.source+' · '+new Date(c.anchor*1000).toISOString()+' · '+c.code));
 header.appendChild(dom('p','case-context',c.description));header.appendChild(dom('p','case-context','Evidence: '+(c.evidence_ids.join(', ')||'None')+' · '+c.confidence));
 const half=Number(windowSel.value)||10;let signals=c.signals.filter(s=>s.samples.some(p=>Math.abs(p[0]-c.anchor)<=half));
 signals.slice(0,4).forEach(s=>drawScalar(s,c,half));
 if(c.paths.length)drawPath(c.paths[0],c);
 if(!plots.children.length)plots.appendChild(dom('p','case-empty','No numeric signals or odometry path available for this source and time interval.'));
 let near=c.events.filter(e=>Math.abs(e.t-c.anchor)<=half);
 near.forEach(e=>{const b=dom('button','case-event');b.type='button';b.appendChild(dom('b','',e.severity+' · '+e.code));b.appendChild(dom('time','',new Date(e.t*1000).toISOString()));b.appendChild(dom('div','',e.message));b.addEventListener('click',()=>{window.__riaMoveCursor?.(e.t);document.getElementById('event-'+e.id)?.scrollIntoView({behavior:'smooth',block:'center'});});events.appendChild(b);});
 if(!near.length)events.appendChild(dom('p','case-empty','No related logged events in ±'+half+' seconds.'));
 }
 cases.forEach((c,i)=>{const opt=dom('option','',c.id+' · '+c.title);opt.value=i;selector.appendChild(opt);});
 selector.addEventListener('change',()=>render(selector.value));windowSel.addEventListener('change',()=>render(active));
 document.getElementById('case-sync')?.addEventListener('click',()=>window.__riaMoveCursor?.(cases[active].anchor));
 window.__riaSelectCaseByEventId=id=>{const idx=cases.findIndex(c=>c.evidence_ids.includes(id));if(idx>=0){render(idx);section.scrollIntoView({behavior:'smooth',block:'start'});window.__riaMoveCursor?.(cases[idx].anchor);}};
 document.querySelectorAll('[data-event-inspect]').forEach(btn=>btn.addEventListener('click',()=>window.__riaSelectCaseByEventId(btn.dataset.eventInspect)));
 document.querySelectorAll('[data-inspect-case]').forEach(btn=>btn.addEventListener('click',()=>{render(Number(btn.dataset.inspectCase));section.scrollIntoView({behavior:'smooth',block:'start'});window.__riaMoveCursor?.(cases[active].anchor);}));
 render(0);
})();
</script>'''
