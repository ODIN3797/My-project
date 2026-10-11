"""Localhost-only, stdlib browser UI. No cloud transmission.

Prototype security note: local use on trusted data only; not hardened for hostile bags.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import tempfile
from pathlib import Path
from urllib.parse import unquote

HTML = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot Incident Analyzer · Local UI</title><style>
:root{font-family:Inter,system-ui,-apple-system,Arial,sans-serif;color-scheme:dark;--fg:#e4e9f3;--muted:#a3b3c9;--line:#283c54;--panel:#132337}
*{box-sizing:border-box}body{background:#0a1322;color:var(--fg);margin:0}main{max-width:1150px;margin:auto;padding:40px 25px}h1{font-size:2rem;letter-spacing:-.04em;margin:6px 0}
header p,.muted{color:var(--muted)}.eyebrow{color:#7fd1cf;letter-spacing:.14em;font-size:.72rem;font-weight:700;text-transform:uppercase}
#drop{margin-top:30px;border:2px dashed #46647e;background:#112238;padding:35px;border-radius:16px;text-align:center;cursor:pointer}
#drop.over{background:#17374b;border-color:#7fd1cf}.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:20px 0}
button,.btn{background:#7fd1cf;color:#092029;border:0;border-radius:9px;padding:12px 20px;font-weight:700;cursor:pointer;text-decoration:none}
button:disabled{opacity:.55;cursor:default}select,input[type=file]{font:inherit}details{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:15px;margin:16px 0}
#result{border:1px solid var(--line);border-radius:14px;background:#111d30;min-height:550px;width:100%;display:none;margin-top:20px}
.notice{border-left:3px solid #f5c46b;padding:12px 15px;background:#272437;margin:20px 0;border-radius:5px}
pre{white-space:pre-wrap;overflow-wrap:anywhere}.small{font-size:.8rem}
</style></head><body><main><header><div class="eyebrow">Robot Incident Analyzer · Offline v0.4.1</div><h1>Investigate your ROS2 incidents.</h1>
<p>Upload an authorized .mcap, .db3, .sqlite3 or .csv file. Processing stays on this computer.</p></header>
<div class="notice">Experimental tool — findings are hypotheses. This prototype reads untrusted files; use only on trusted recordings. Do not upload employer/client data without authorization.</div>
<div id="drop" role="button" tabindex="0"><h2>Drop a recording here</h2><p>or click to select a local file</p><p class="muted small">One file at a time · maximum __LIMIT__ MB</p><input id="file" type="file" accept=".mcap,.db3,.sqlite3,.csv" hidden></div>
<div class="actions"><span id="filename" class="muted">No file selected</span><button id="go" disabled>Analyze locally</button><a class="btn" id="report-link" style="display:none" href="/report.html" target="_blank">Open report ↗</a><a class="btn" id="json-link" style="display:none" href="/report.json" target="_blank">JSON ↗</a></div>
<p id="status" class="muted" role="status"></p><div id="mapping" style="display:none;border:1px solid var(--line);border-radius:12px;padding:16px;margin:18px 0;background:var(--panel)"><h3>Topic mapping review</h3><p class="muted small">If two streams have the same ROS type, select the intended role and click Analyze locally again. Wrong topic selection can create false incidents.</p><div class="actions" id="mapping-selects"></div></div><details><summary>What gets detected?</summary><p>Typed topic discovery, velocity-vs-odometry matching, location/TF jumps, diagnostic statuses and nearby incident context. When several candidate topics are equally plausible, command–odometry correlation is skipped rather than guessed.</p><p>For custom ROS2 messages, provide a <code>--config examples/config_custom.json</code> at GUI startup with authorized local .msg schemas and field mappings.</p></details>
<iframe id="result" title="Local diagnostic report" sandbox="allow-scripts"></iframe><p class="muted small">Runs only on 127.0.0.1. No external scripts, CDNs or analytics.</p></main>
<script>
const token='__TOKEN__', maxBytes=__MAX__;let selected=null;
const drop=document.getElementById('drop'), file=document.getElementById('file'), go=document.getElementById('go'), label=document.getElementById('filename'), status=document.getElementById('status');
function choose(f){selected=f;go.disabled=!f;label.textContent=f?f.name+' · '+(f.size/1024/1024).toFixed(1)+' MB':'No file selected';}
drop.onclick=()=>file.click();drop.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();file.click();}};
file.onchange=()=>choose(file.files[0]);drop.ondragover=e=>{e.preventDefault();drop.classList.add('over');};
drop.ondragleave=()=>drop.classList.remove('over');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('over');choose(e.dataTransfer.files[0]);};
go.onclick=async()=>{if(!selected)return;if(selected.size>maxBytes){status.textContent='File exceeds configured upload limit.';return;}
go.disabled=true;status.textContent='Analyzing locally…';document.getElementById('result').style.display='none';
try{const r=await fetch('/analyze',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Filename':selected.name,'X-Local-Token':token,'X-Topic-Command':document.getElementById('choose-command')?.value||'','X-Topic-Odometry':document.getElementById('choose-odometry')?.value||''},body:selected});const data=await r.json();
if(!r.ok)throw new Error(data.error||('HTTP '+r.status));status.textContent='Done · '+data.events+' events · '+data.findings+' findings · '+data.warnings+' warnings';
const discovered=data.mapping?.[0], box=document.getElementById('mapping'), holder=document.getElementById('mapping-selects');
if(discovered){box.style.display='block';const prev={command:document.getElementById('choose-command')?.value,odometry:document.getElementById('choose-odometry')?.value};holder.replaceChildren();
for(const role of ['command','odometry']){const label=document.createElement('label');label.textContent=role+': ';const select=document.createElement('select');select.id='choose-'+role;
const empty=document.createElement('option');empty.value='';empty.textContent='Auto (or skip if ambiguous)';select.appendChild(empty);
for(const c of discovered.candidates?.[role]||[]){const opt=document.createElement('option');opt.value=c.topic;opt.textContent=c.topic+' ['+c.message_type+']';select.appendChild(opt);}
select.value=prev[role]||discovered.selected?.[role]||'';
label.appendChild(select);holder.appendChild(label);}}
document.getElementById('report-link').style.display='inline-block';document.getElementById('json-link').style.display='inline-block';
const frame=document.getElementById('result');frame.src='/report.html?v='+Date.now();frame.style.display='block';
}catch(err){status.textContent='Error: '+err.message;}finally{go.disabled=false;}};
</script></body></html>'''


def run_gui(port:int, output:Path, config:dict, max_upload_mb:int=50) -> int:
    from .__main__ import analyze_files
    limit=max_upload_mb*1024*1024
    token=secrets.token_urlsafe(32)
    output=output.resolve()

    class Handler(BaseHTTPRequestHandler):
        def valid_host(self):
            host=self.headers.get('Host','').split(':')[0].lower()
            return host in ('127.0.0.1','localhost')

        def send_bytes(self, status:int, body:bytes, content_type:str):
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self'; frame-src 'self'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def json(self, code, obj):
            self.send_bytes(code,json.dumps(obj).encode('utf-8'),'application/json; charset=utf-8')

        def do_GET(self):
            if not self.valid_host(): return self.json(403,{'error':'Invalid Host'})
            path=self.path.partition('?')[0]
            if path=='/':
                html=HTML.replace('__TOKEN__',token).replace('__LIMIT__',str(max_upload_mb)).replace('__MAX__',str(limit))
                return self.send_bytes(200,html.encode(),'text/html; charset=utf-8')
            if path in ('/report.html','/report.json'):
                target=output/path.lstrip('/')
                if not target.exists(): return self.json(404,{'error':'Analyze a file first'})
                return self.send_bytes(200,target.read_bytes(),'text/html; charset=utf-8' if path.endswith('.html') else 'application/json; charset=utf-8')
            self.json(404,{'error':'Not found'})

        def do_POST(self):
            if not self.valid_host(): return self.json(403,{'error':'Invalid Host'})
            origin=self.headers.get('Origin','')
            if origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
                return self.json(403,{'error':'Origin not allowed'})
            if self.path!='/analyze' or not secrets.compare_digest(self.headers.get('X-Local-Token',''),token):
                return self.json(403,{'error':'Invalid path or token'})
            suffix=Path(unquote(self.headers.get('X-Filename',''))).suffix.lower()
            if suffix not in ('.mcap','.db3','.sqlite3','.csv'):
                return self.json(400,{'error':'Only MCAP, DB3, SQLITE3 or CSV supported'})
            try: length=int(self.headers.get('Content-Length','0'))
            except ValueError: length=0
            if not 0 < length <= limit: return self.json(413,{'error':'File empty or larger than limit'})
            try:
                with tempfile.TemporaryDirectory(prefix='ria-ui-') as tmp:
                    path=Path(tmp)/('upload'+suffix)
                    with path.open('wb') as fp:
                        remaining=length
                        while remaining:
                            buf=self.rfile.read(min(1024*1024,remaining))
                            if not buf: raise ValueError('Upload truncated')
                            fp.write(buf);remaining-=len(buf)
                    override=dict(config)
                    mapped=dict(config.get('topics',{}))
                    for role,header in [('command','X-Topic-Command'),('odometry','X-Topic-Odometry')]:
                        value=self.headers.get(header,'').strip()
                        if value: mapped[role]=value
                    override['topics']=mapped
                    events,findings,stats,warnings,_,details=analyze_files([path],output,override)
                    self.json(200,{'events':len(events),'findings':len(findings),'topics':len(stats),
                                   'warnings':len(warnings),'mapping':[d['discovery'] for d in details]})
            except (ValueError,OSError,ImportError) as exc:
                self.json(400,{'error':str(exc)[:600]})

    with ThreadingHTTPServer(('127.0.0.1',port),Handler) as server:
        print(f'Local browser UI: http://127.0.0.1:{port}  (press Ctrl+C to stop)',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
    return 0
