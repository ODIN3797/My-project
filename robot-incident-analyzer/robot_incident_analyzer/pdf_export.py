"""Optional local, deterministic PDF dossier with vector telemetry charts.

Install `pip install reportlab` to use `analyze ... --pdf`. This export is
independent of browser print, requires no network, and intentionally avoids
asserting any diagnosis. Images/metadata from raw bag remain local.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import math
from pathlib import Path

from .incident_workbench import cases_from_findings
from .state_timeline import build_state_transitions


def export_pdf(path, events, findings, stats, warnings, input_files, details, *, state_keys=None):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
        from reportlab.graphics.shapes import Drawing, Line, PolyLine, Circle, String
    except ImportError as exc:
        raise ImportError('PDF output needs reportlab. Install it with: python -m pip install reportlab; or use HTML Print / Save as PDF.') from exc
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    font='Helvetica'
    for item in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'):
        if Path(item).is_file():
            try:
                pdfmetrics.registerFont(TTFont('RIA_PDF',item));font='RIA_PDF';break
            except Exception:pass
    ink=colors.HexColor('#17263a')
    muted=colors.HexColor('#52677c')
    bg=colors.HexColor('#edf3f8')
    aqua=colors.HexColor('#158a7b')
    amber=colors.HexColor('#dd7b27')
    violet=colors.HexColor('#4665a4')
    page_w,page_h=A4
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=43,leftMargin=43,
                          topMargin=45,bottomMargin=44,title='Robot Incident Analyzer | Evidence report',
                          author='Robot Incident Analyzer')
    normal=ParagraphStyle('normal',fontName=font,fontSize=8.5,leading=13,textColor=ink,spaceAfter=9)
    small=ParagraphStyle('small',parent=normal,fontSize=7.2,leading=10,textColor=muted)
    h1=ParagraphStyle('h1',parent=normal,fontSize=20,leading=25,textColor=ink,spaceAfter=15)
    h2=ParagraphStyle('h2',parent=normal,fontSize=12,leading=16,textColor=ink,spaceBefore=14,spaceAfter=9)
    h3=ParagraphStyle('h3',parent=normal,fontSize=10,leading=14,textColor=aqua,spaceAfter=8)
    items=[]
    def para(v,style=normal):return Paragraph(escape(str(v)).replace('\n','<br/>'),style)
    def footer(canv,document):
        canv.saveState();canv.setStrokeColor(colors.HexColor('#d9e3eb'));canv.line(43,34,page_w-43,34)
        canv.setFont(font,7);canv.setFillColor(muted)
        canv.drawString(43,22,'Offline evidence • Time correlation does not prove causation')
        canv.drawRightString(page_w-43,22,f'Page {document.page}');canv.restoreState()
    items.extend([para('ROBOT INCIDENT ANALYZER',h3),para('Incident evidence report',h1),
                  para('Research prototype: no root cause has been verified. Report timestamps reflect recording time.',normal)])
    items.append(para('Input files: '+', '.join(Path(x).name for x in input_files),small))
    kpis=[('Events',str(len(events))),('Findings',str(len(findings))),('Topics',str(len(stats))),('Warnings',str(len(warnings)))]
    kpi=Table([[para(k,small) for k,_ in kpis],[para(v, h2) for _,v in kpis]],colWidths=[(page_w-86)/4]*4)
    kpi.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),bg),('BOX',(0,0),(-1,-1),.5,colors.HexColor('#d5e0e8')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),12)]))
    items.extend([kpi,Spacer(1,15)])
    if warnings:
        items.append(para('Coverage notes',h2))
        for msg in warnings[:8]:items.append(para('• '+msg,small))
        if len(warnings)>8:items.append(para('... further warnings omitted; consult report.json.',small))
    state_transitions=build_state_transitions(events, state_keys)
    cases=cases_from_findings(findings,events,details,limit=20,state_transitions=state_transitions)
    if state_transitions:
        items.append(para('Observed robot state transitions',h2))
        items.append(para('Only explicit key=value log statements; not verified controller state.',small))
        for item in state_transitions[:20]:
            ts=datetime.fromtimestamp(item['timestamp'],tz=timezone.utc).strftime('%H:%M:%S.%f')[:-3]
            label=f"{ts} | {item['source']} / {item['robot_id']} | {item['field']}: {item['from'] or '[first]'} -> {item['to']} | {item['event_id']}"
            items.append(para(label,small))
        if len(state_transitions)>20:items.append(para('Additional state transitions in report.json.',small))
    else:
        items.append(para('No explicit robot state assignments observed (state unknown).',small))
    if not cases:items.append(para('No evidence-linked incident candidates. This is not proof of a healthy robot.',normal))

    def series_drawing(series, anchor, width=485, height=100):
        rows=[p for p in series.get('samples',[]) if len(p)>=2 and abs(p[0]-anchor)<=10 and all(math.isfinite(x) for x in p[:2])]
        if not rows:return None
        d=Drawing(width,height)
        x0,x1=anchor-10,anchor+10
        values=[x[1] for x in rows];vmin=min(values);vmax=max(values)
        pad=max(.001,(vmax-vmin)*.12,abs(vmax)*.001);vmin-=pad;vmax+=pad
        def xf(t):return 20+(t-x0)/(x1-x0)*(width-35)
        def yf(v):return 19+(v-vmin)/(vmax-vmin)*(height-33)
        for idx in range(4):
            y=19+(height-33)*idx/3
            d.add(Line(20,y,width-15,y,strokeColor=colors.HexColor('#dbe4ed'),strokeWidth=.4))
        coordinates=[]
        for t,value in rows:coordinates.extend([xf(t),yf(value)])
        if len(rows)>1:d.add(PolyLine(coordinates,strokeColor=aqua,strokeWidth=1.9))
        else:d.add(Circle(xf(rows[0][0]),yf(rows[0][1]),2.5,strokeColor=None,fillColor=aqua))
        d.add(Line(xf(anchor),15,xf(anchor),height-14,strokeColor=amber,strokeWidth=1.0,strokeDashArray=[3,3]))
        d.add(String(23,5,'t = -10 s',fontName=font,fontSize=7,fillColor=muted))
        d.add(String(width-73,5,'t = +10 s',fontName=font,fontSize=7,fillColor=muted))
        return d

    def path_drawing(path_samples,anchor,width=480,height=105):
        rows=path_samples
        if len(rows)<2:return None
        d=Drawing(width,height)
        xmin=min(p[1] for p in rows);xmax=max(p[1] for p in rows)
        ymin=min(p[2] for p in rows);ymax=max(p[2] for p in rows)
        scale=min((width-40)/max(xmax-xmin,.2),(height-32)/max(ymax-ymin,.2))
        cx=(xmin+xmax)/2;cy=(ymin+ymax)/2
        xf=lambda x:width/2+(x-cx)*scale
        yf=lambda y:height/2+(y-cy)*scale
        coords=[]
        for p in rows:coords.extend([xf(p[1]),yf(p[2])])
        d.add(PolyLine(coords,strokeColor=violet,strokeWidth=2))
        d.add(Circle(xf(rows[0][1]),yf(rows[0][2]),3,fillColor=aqua,strokeColor=None))
        nearest=min(rows,key=lambda p:abs(p[0]-anchor))
        if abs(nearest[0]-anchor)<=2:
            d.add(Circle(xf(nearest[1]),yf(nearest[2]),5,fillColor=colors.HexColor('#ed5669'),strokeColor=colors.white,strokeWidth=1))
        d.add(String(15,6,'XY meters in recorded odometry frame (not georeferenced)',fontName=font,fontSize=7,fillColor=muted))
        return d

    for i,c in enumerate(cases):
        items.append(PageBreak())
        items.extend([para(f'Investigation {i+1} · {c["severity"]}',h3),para(c['title'],h1),
                      para('Time: '+datetime.fromtimestamp(c['anchor'],tz=timezone.utc).isoformat(timespec='milliseconds')+' | Source: '+c['source'],small),
                      para(c['description'],normal),para('Evidence IDs: '+', '.join(c['evidence_ids'])+' | '+c['confidence'],small)])
        changes=c.get('state_context',{}).get('transitions',[])
        items.append(para(c.get('state_summary',''),small))
        if changes:
            items.append(para('Recorded state changes within 30 s before/at incident',h2))
            for transition in changes[-6:]:
                dt=transition['timestamp']-c['anchor']
                items.append(para(f"{dt:+.2f}s | {transition['field']}: {transition['from'] or '[first]'} -> {transition['to']} ({transition['event_id']})",small))
        else:items.append(para('No explicit state changes recorded in prior 30 s; do not infer state.',small))
        if c['checks']:
            items.append(para('Suggested checks',h2))
            for k in c['checks'][:4]:items.append(para('• '+k,small))
        items.append(para('Context signals, ±10 seconds',h2))
        shown=0
        for ser in c['signals']:
            figure=series_drawing(ser,c['anchor'])
            if figure is None:continue
            items.append(para(ser['topic']+' / '+ser['field'],small));items.append(figure)
            shown+=1
            if shown>=2:break
        if not shown:items.append(para('No numeric samples within this context window.',small))
        if c['paths']:
            items.append(para('Odometry path with approximate event position',h2))
            drawing=path_drawing(c['paths'][0]['samples'],c['anchor'])
            if drawing is not None:items.append(drawing)
        items.append(para('Nearby observations (same input source)',h2))
        for e in c['events'][:5]:
            if abs(e['t']-c['anchor'])<=10:
                items.append(para(f"{e['severity']}  {e['code']}: {e['message'][:185]}",small))
    doc.build(items,onFirstPage=footer,onLaterPages=footer)
    if path.stat().st_size < 1000: raise OSError('PDF output unexpectedly small')
    return path
