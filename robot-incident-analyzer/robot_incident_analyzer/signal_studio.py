"""Bounded numeric telemetry previews + local-only synchronized incident explorer.

Each numeric series is downsampled independently as it streams in. Never infer
failure from an arbitrary numeric trend. Timestamps are bag-recording times.
"""
from __future__ import annotations

import html
import json
import math
from collections import OrderedDict

MAX_SERIES = 72
MAX_SAMPLES = 650
MAX_PATHS = 8


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def numeric_leaves(value, *, prefix='', depth=0, limit=18):
    """Bounded dict traversal; deliberately don't interpret arrays/booleans as scalars."""
    found = {}
    if depth > 5 or not isinstance(value, dict):
        return found
    for key, item in value.items():
        if len(found) >= limit:
            break
        if not isinstance(key, str) or len(key) > 90:
            continue
        name = (prefix + '.' if prefix else '') + key
        if finite_number(item):
            found[name] = float(item)
        elif isinstance(item, dict):
            found.update(numeric_leaves(item, prefix=name, depth=depth + 1, limit=limit - len(found)))
    return found


class BoundedSamples:
    """Deterministic, streaming, equally-spaced-by-message-index samples."""
    def __init__(self):
        self.rows = []
        self.count = 0
        self.stride = 1

    def add(self, *values):
        idx = self.count
        self.count += 1
        if idx % self.stride:
            return
        if len(self.rows) >= MAX_SAMPLES:
            # Retain every second existing observation; increase sampling stride.
            self.rows = self.rows[::2]
            self.stride *= 2
            if idx % self.stride:
                return
        self.rows.append(tuple(round(float(v), 6) for v in values))


class SignalSampler:
    def __init__(self):
        self.series = OrderedDict()
        self.trajectories = OrderedDict()

    def add(self, topic, msgtype, ts, fields):
        if not math.isfinite(ts):
            return
        for name, value in fields.items():
            if not finite_number(value):
                continue
            key = (topic, msgtype, name)
            if key not in self.series:
                if len(self.series) >= MAX_SERIES:
                    break
                self.series[key] = {'topic': topic, 'type': msgtype, 'field': name,
                                    'sampler': BoundedSamples()}
            self.series[key]['sampler'].add(ts, value)

    def position(self, topic, frame, ts, position):
        if (not math.isfinite(ts) or not isinstance(position, (tuple,list)) or len(position) < 2
                or not all(finite_number(n) for n in position[:2])):
            return
        # Distinct odometry topics and coordinate frames are never joined.
        key = (topic, frame or 'unknown')
        if key not in self.trajectories:
            if len(self.trajectories) >= MAX_PATHS:
                return
            self.trajectories[key] = BoundedSamples()
        self.trajectories[key].add(ts, position[0], position[1])

    def result(self):
        return {
            'signals': [{'topic': x['topic'], 'type': x['type'], 'field': x['field'],
                         'samples': x['sampler'].rows, 'recorded_count': x['sampler'].count,
                         'sampled_stride': x['sampler'].stride}
                        for x in self.series.values() if x['sampler'].rows],
            'paths': [{'topic': topic, 'frame': frame, 'samples': s.rows,
                       'recorded_count': s.count, 'sampled_stride': s.stride}
                      for (topic, frame),s in self.trajectories.items() if s.rows]
        }


def standard_fields(canonical, decoded):
    """Numeric inspection only; no automatic diagnosis implied."""
    if canonical in ('geometry_msgs/Twist','geometry_msgs/TwistStamped'):
        return {'linear.x (m/s)': decoded['linear'][0], 'angular.z (rad/s)': decoded['angular'][2]}
    if canonical == 'nav_msgs/Odometry':
        fields={'linear.x (m/s)': decoded['linear'][0], 'angular.z (rad/s)': decoded['angular'][2]}
        if decoded.get('position') is not None:
            fields.update({'position.x (m)':decoded['position'][0], 'position.y (m)':decoded['position'][1]})
        return fields
    if canonical == 'sensor_msgs/Range':
        return {'range (m)': decoded['distance'], 'field_of_view (rad)':decoded['field_of_view']}
    if canonical == 'mavros_msgs/State':
        return {'connected (0/1)':int(decoded['connected']), 'armed (0/1)':int(decoded['armed']),
                'guided (0/1)':int(decoded['guided']), 'system_status':decoded['system_status']}
    if canonical == 'mavros_msgs/ExtendedState':
        return {'vtol_state': decoded['vtol_state'], 'landed_state': decoded['landed_state']}
    if canonical == 'mavros_msgs/StatusText':
        return {'severity': decoded['severity']}
    if canonical == 'sensor_msgs/BatteryState':
        return {'voltage (V)': decoded['voltage'], 'current (A)':decoded['current'],
                'percentage (%)':decoded['percentage'] * 100, 'temperature (°C)':decoded['temperature']}
    if canonical == 'sensor_msgs/Imu':
        out={}
        if decoded['angular_available']:
            out['angular_velocity.z (rad/s)'] = decoded['angular_velocity'][2]
        if decoded['accel_available']:
            out['linear_acceleration.x (m/s²)'] = decoded['linear_acceleration'][0]
        if decoded['orientation_available']:
            out['quaternion_norm'] = math.sqrt(sum(a*a for a in decoded['orientation']))
        return out
    if canonical == 'sensor_msgs/LaserScan':
        beams=decoded['beam_count']
        return {'valid_return_ratio (%)': 100*decoded['valid_returns']/beams if beams else 0,
                'NaN_ranges':decoded['nan_count']}
    return {}


def escape_json(value):
    """Valid JSON safe inside a script element, including hostile topic names."""
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').replace('\u2028','\\u2028').replace('\u2029','\\u2029')


STUDIO_CSS = r'''
.studio-controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.studio-controls label{font-size:11px;color:var(--muted);font-weight:700}
.studio-controls select{width:min(100%,470px);background:#0b1928;color:#dceaf9;padding:10px;border:1px solid #335064;border-radius:9px}
.studio-controls button{background:#163c43;border:1px solid #39796f;color:#a9f2e7;border-radius:9px;padding:9px 12px;cursor:pointer}
.studio-plot{width:100%;height:auto;display:block;border-radius:10px;background:#0b1829;touch-action:pan-y;cursor:crosshair}
.studio-plot text{fill:#9db0c8;font-size:12px;font-family:ui-monospace,monospace}
.studio-plot .gridline{stroke:#273d52;stroke-dasharray:3 5}
.studio-plot .cursor-line{stroke:#eacb80;stroke-width:1.8;stroke-dasharray:5 4}
.studio-toolbar{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:13px;align-items:center;padding:14px 16px;background:#122e3d;border:1px solid #285060;border-radius:12px;margin:15px 0}
.studio-toolbar input[type=range]{width:100%;accent-color:#53dec4}
.studio-cursor-time{font-variant-numeric:tabular-nums;white-space:nowrap;color:#b9e9dc;font-size:12px}
.studio-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.studio-note{font-size:11px;color:#b1c1d3;margin:9px 0}
.studio-empty{font-size:13px;color:#a8b9cf;padding:20px}
.studio-legend{display:flex;flex-wrap:wrap;gap:10px;font-size:11px;color:#c4d1de}
.studio-legend i{display:inline-block;width:11px;height:11px;border-radius:3px;background:#53dec4;margin-right:4px}
@media(max-width:900px){.studio-row{grid-template-columns:1fr}.studio-toolbar{grid-template-columns:1fr}.studio-cursor-time{white-space:normal}}
'''


def studio_markup(details, events):
    sigs,paths=[],[]
    for d in details:
        for s in d.get('signals',[]):
            sigs.append({**s, 'source':d.get('source','')})
        for p in d.get('paths',[]):
            paths.append({**p, 'source':d.get('source','')})
    event_stamps=[{'t':e.timestamp,'severity':e.severity,'code':e.code,'id':e.event_id} for e in events
                  if e.severity in ('WARN','ERROR','FATAL') and math.isfinite(e.timestamp)][:500]
    payload=escape_json({'signals':sigs, 'paths':paths, 'events':event_stamps})
    return f'''<div class="box-card" id="studio"><div class="card-heading"><h3>Signal Studio · synchronized evidence</h3><span class="pill-inline">Offline · recording timestamps</span></div>
    <p class="studio-note">Select a decoded scalar field; all visible plots share the same recorded-time cursor. A timestamp match does not prove causality.</p>
    <div class="studio-controls"><label for="studio-signal">Numeric signal</label><select id="studio-signal" aria-label="Choose telemetry signal"></select><button type="button" id="studio-nearest">Jump to nearest log event</button></div>
    <div class="studio-toolbar"><label for="studio-time">Recording cursor <input type="range" id="studio-time" min="0" max="1000" value="0" aria-label="Move synchronized recording time cursor"></label><output id="studio-time-label" class="studio-cursor-time" aria-live="polite">—</output></div>
    <div class="studio-row"><div><h3>Telemetry value over time</h3><svg id="studio-signal-chart" class="studio-plot" viewBox="0 0 700 270" role="img" aria-label="Selected numeric telemetry history and synchronized cursor"></svg><p id="studio-signal-readout" class="studio-note"></p></div>
    <div><div class="studio-controls"><label for="studio-path">Odometry XY trajectory</label><select id="studio-path" aria-label="Choose odometry path"></select></div><svg id="studio-path-chart" class="studio-plot" viewBox="0 0 700 270" role="img" aria-label="Odometry XY trajectory, with selected recorded time and nearby events"></svg><p id="studio-path-readout" class="studio-note"></p></div></div>
    <p class="studio-note">Path positions are local to each odometry frame, never GPS/map truth. Sensor values reflect recording timestamps. Plots are downsampled; use the original ROS bag for exact measurements. No arbitrary unsupported CDR type is guessed.</p>
    <script type="application/json" id="studio-data">{payload}</script></div>'''


def studio_script():
    return r'''<script>
(function(){
 const el=document.getElementById('studio-data');if(!el)return;
 let dataset;
 try{dataset=JSON.parse(el.textContent);}catch(_){return;}
 const sigs=dataset.signals||[],paths=dataset.paths||[], incidents=dataset.events||[];
 const signalSel=document.getElementById('studio-signal'),pathSel=document.getElementById('studio-path');
 const slider=document.getElementById('studio-time'),when=document.getElementById('studio-time-label');
 const sgraph=document.getElementById('studio-signal-chart'),pgraph=document.getElementById('studio-path-chart');
 const sread=document.getElementById('studio-signal-readout'),pread=document.getElementById('studio-path-readout');
 const ns='http://www.w3.org/2000/svg';const H=270,W=700,L=62,R=684,T=30,B=218;
 function node(parent,tag,attrs,text){const e=document.createElementNS(ns,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(text!==undefined)e.textContent=text;parent.appendChild(e);return e;}
 function clear(svg){while(svg.firstChild)svg.removeChild(svg.firstChild);}
 function text(svg,x,y,value){node(svg,'text',{x,y},value);}
 function range(values){let lo=Math.min(...values),hi=Math.max(...values);if(!(Number.isFinite(lo)&&Number.isFinite(hi)))return [0,1];if(hi-lo<1e-8){const pad=Math.max(1,Math.abs(hi)*.05);return [lo-pad,hi+pad];}return [lo-(hi-lo)*.07,hi+(hi-lo)*.07];}
 function bounds(s){return s?.samples?.length?[s.samples[0][0],s.samples[s.samples.length-1][0]]:[0,1];}
 const all=sigs.concat(paths).flatMap(x=>[bounds(x)[0],bounds(x)[1]]).filter(Number.isFinite);
 const tmin=all.length?Math.min(...all):0,tmax=all.length?Math.max(...all):1,span=Math.max(.000001,tmax-tmin);
 let t=tmin;function xT(val,t0,t1){return L+(val-t0)/Math.max(1e-9,t1-t0)*(R-L);}
 function nearest(points,time){let lo=0,hi=points.length;while(lo<hi){let mid=(lo+hi)>>1;if(points[mid][0]<time)lo=mid+1;else hi=mid;}if(!points.length)return null;let a=points[Math.max(0,lo-1)],b=points[Math.min(points.length-1,lo)];return Math.abs(a[0]-time)<=Math.abs(b[0]-time)?a:b;}
 function option(sel,value,label){let o=document.createElement('option');o.value=value;o.textContent=label;sel.appendChild(o);}
 sigs.forEach((s,i)=>option(signalSel,i,s.source+' · '+s.topic+' · '+s.field));
 paths.forEach((p,i)=>option(pathSel,i,p.source+' · '+p.topic+' ['+p.frame+']'));
 if(!sigs.length)option(signalSel,'','No decodable numeric telemetry fields');
 if(!paths.length)option(pathSel,'','No odometry XY messages decoded');
 function axes(svg,label,ylo,yhi){for(let i=0;i<=4;i++){let yy=B-(B-T)*i/4;node(svg,'line',{x1:L,y1:yy,x2:R,y2:yy,class:'gridline'});text(svg,5,yy+4,(ylo+(yhi-ylo)*i/4).toFixed(2));}text(svg,L,18,label);}
 function drawSignal(){clear(sgraph);let s=sigs[Number(signalSel.value)];if(!s?.samples?.length){text(sgraph,45,138,'No decoded scalar data in this recording.');sread.textContent='';return;}
 const points=s.samples,[start,end]=bounds(s);const [min,max]=range(points.map(p=>p[1]));axes(sgraph,s.field,min,max);
 const yy=v=>B-(v-min)/(max-min)*(B-T),xx=v=>xT(v,start,end);
 const segments=points.map(p=>xx(p[0]).toFixed(2)+','+yy(p[1]).toFixed(2)).join(' ');
 node(sgraph,'polyline',{points:segments,fill:'none',stroke:'#53dec4','stroke-width':2.5,'stroke-linecap':'round','stroke-linejoin':'round'});
 const lo=Math.max(start,tmin),hi=Math.min(end,tmax);
 incidents.filter(e=>e.t>=lo&&e.t<=hi).slice(0,80).forEach(e=>node(sgraph,'line',{x1:xx(e.t),x2:xx(e.t),y1:T,y2:B,stroke:e.severity==='WARN'?'#f5bb65':'#ff7889','stroke-dasharray':'3 5',opacity:.35}));
 if(t>=start&&t<=end){let p=nearest(points,t);node(sgraph,'line',{x1:xx(t),x2:xx(t),y1:T,y2:B,class:'cursor-line'});node(sgraph,'circle',{cx:xx(p[0]),cy:yy(p[1]),r:5,fill:'#53dec4',stroke:'#fff','stroke-width':1});sread.textContent='Nearest sampled value: '+p[1].toFixed(4)+' at '+new Date(p[0]*1000).toISOString()+' · '+s.recorded_count+' recorded, '+points.length+' plotted';}
 else sread.textContent='Cursor outside this signal’s recording window.';
 sgraph.onclick=e=>{const rect=sgraph.getBoundingClientRect(),px=(e.clientX-rect.left)/rect.width*W;move(start+(Math.max(L,Math.min(R,px))-L)/(R-L)*(end-start));};
 }
 function drawPath(){clear(pgraph);let p=paths[Number(pathSel.value)];if(!p?.samples?.length){text(pgraph,45,138,'No odometry XY trajectory available.');pread.textContent='';return;}
 let points=p.samples,[xmin,xmax]=range(points.map(a=>a[1])),[ymin,ymax]=range(points.map(a=>a[2]));
 // Equal meter-per-pixel scale prevents rectangular distortion of turns.
 const centerX=(xmin+xmax)/2,centerY=(ymin+ymax)/2,scale=Math.min((R-L)/(xmax-xmin),(B-T)/(ymax-ymin));
 const px=x=>(L+R)/2+(x-centerX)*scale,py=y=>(T+B)/2-(y-centerY)*scale;
 node(pgraph,'line',{x1:L,x2:R,y1:(T+B)/2,y2:(T+B)/2,class:'gridline'});
 node(pgraph,'line',{x1:(L+R)/2,x2:(L+R)/2,y1:T,y2:B,class:'gridline'});
 text(pgraph,L,17,p.frame+' · meters (equal X/Y scale)');
 node(pgraph,'polyline',{points:points.map(a=>px(a[1]).toFixed(1)+','+py(a[2]).toFixed(1)).join(' '),fill:'none',stroke:'#7eabf4','stroke-width':2.5,'stroke-linejoin':'round'});
 const first=points[0],last=points[points.length-1];
 node(pgraph,'circle',{cx:px(first[1]),cy:py(first[2]),r:4,fill:'#53dec4'});
 node(pgraph,'circle',{cx:px(last[1]),cy:py(last[2]),r:4,fill:'#ffbd71'});
 incidents.filter(e=>e.t>=first[0]&&e.t<=last[0]).slice(0,80).forEach(e=>{let n=nearest(points,e.t);if(Math.abs(n[0]-e.t)<1)node(pgraph,'circle',{cx:px(n[1]),cy:py(n[2]),r:3.5,fill:e.severity==='WARN'?'#f5bb65':'#ff7889',opacity:.8});});
 if(t>=first[0]&&t<=last[0]){let n=nearest(points,t);node(pgraph,'circle',{cx:px(n[1]),cy:py(n[2]),r:6,fill:'#eacb80',stroke:'#fff','stroke-width':1.6});pread.textContent='Cursor: X '+n[1].toFixed(3)+' m · Y '+n[2].toFixed(3)+' m · '+points.length+' plotted / '+p.recorded_count+' recorded';}
 else pread.textContent='Cursor outside this odometry trajectory.';
 pgraph.onclick=e=>{let r=pgraph.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*W,y=(e.clientY-r.top)/r.height*H;let n=points.reduce((best,a)=>!best||Math.hypot(px(a[1])-x,py(a[2])-y)<Math.hypot(px(best[1])-x,py(best[2])-y)?a:best,null);if(n)move(n[0]);};
 }
 function syncVelocity(){document.querySelectorAll('svg.chart[data-tmin][data-tmax]').forEach(svg=>{const a=Number(svg.dataset.tmin),b=Number(svg.dataset.tmax);svg.querySelectorAll('.shared-cursor').forEach(n=>n.remove());if(t<a||t>b)return;let xx=56+(t-a)/(b-a)*(768-56);node(svg,'line',{x1:xx,x2:xx,y1:23,y2:202,stroke:'#eacb80','stroke-width':2,'stroke-dasharray':'4 4',class:'shared-cursor'});});}
 function move(value){t=Math.max(tmin,Math.min(tmax,value));slider.value=Math.round((t-tmin)/span*1000);when.textContent=new Date(t*1000).toISOString()+' UTC';drawSignal();drawPath();syncVelocity();}
 slider.addEventListener('input',()=>move(tmin+Number(slider.value)/1000*span));
 signalSel.addEventListener('change',drawSignal);pathSel.addEventListener('change',drawPath);
 document.getElementById('studio-nearest')?.addEventListener('click',()=>{if(!incidents.length)return;let e=incidents.reduce((a,b)=>Math.abs(a.t-t)<Math.abs(b.t-t)?a:b);move(e.t);document.getElementById('event-'+e.id)?.scrollIntoView({behavior:'smooth',block:'center'});});
 document.querySelectorAll('svg.chart[data-tmin][data-tmax]').forEach(svg=>svg.addEventListener('click',e=>{const r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*790;move(Number(svg.dataset.tmin)+(Math.max(56,Math.min(768,x))-56)/712*(Number(svg.dataset.tmax)-Number(svg.dataset.tmin)));}));
 document.querySelectorAll('a.evidence-link[href^="#event-"]').forEach(a=>a.addEventListener('click',()=>{const row=document.querySelector(a.getAttribute('href'));if(row)move(Number(row.dataset.ts));}));
 window.__riaMoveCursor=move;
 // Focus the report on a visible evidence marker if one exists.
 move(incidents.length ? Math.max(tmin,Math.min(tmax,incidents[0].t)) : tmin);
})();
</script>'''
