"""Reproducible third-party ROS2 bag benchmark. Never upload source recordings.

Use only public datasets. This is a format/rate comparison, not validation of
root-cause inference. Creates explicit success/failure evidence per source.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen, Request
import zipfile

from robot_incident_analyzer.bag_comparison import compare_bags, summarize_bag
from robot_incident_analyzer.rate_timeline import inspect_bag

ZENODO1='https://zenodo.org/records/17649537/files/Experiment_1.zip?download=1'
VIGO='https://zenodo.org/records/15433859/files/Navigation.zip?download=1'
BAGEL='https://raw.githubusercontent.com/Hussain004/BAGEL/dc25e7ef395546bfbeea2ca07b71091fe70f5112/public/sample-bags/tour.mcap'
SOURCES={'experiment1':(ZENODO1,30_000_000),'vigo_navigation':(VIGO,50_000_000),'bagel_example':(BAGEL,12_000_000)}


def stream_download(url, destination, limit):
    h=hashlib.sha256()
    size=0
    with urlopen(Request(url,headers={'User-Agent':'RobotIncidentAnalyzer-public-dataset-eval/0.5.1'}),timeout=30) as response, destination.open('wb') as fp:
        while True:
            data=response.read(1024*1024)
            if not data: break
            size+=len(data)
            if size>limit:
                raise ValueError(f'File larger than allowed {limit} bytes')
            fp.write(data)
            h.update(data)
    return {'bytes':size,'sha256':h.hexdigest()}


def extract_bags(zippath: Path, destination: Path, *, max_total=450_000_000):
    extracted=[]
    total=0
    with zipfile.ZipFile(zippath) as z:
        for entry in z.infolist():
            if entry.is_dir() or not entry.filename.lower().endswith(('.db3','.mcap')):
                continue
            # Only basename; avoid any symlink/zip-slip and duplicate filenames.
            relative=Path(entry.filename)
            if '..' in relative.parts or relative.is_absolute():
                raise ValueError('Unsafe ZIP entry path')
            total+=entry.file_size
            if total>max_total or entry.file_size>160_000_000:
                raise ValueError(f'Expanded ZIP exceeds safety limits ({total} bytes)')
            target=destination / entry.filename
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                raise ValueError('Duplicate ZIP entry')
            with z.open(entry) as src,target.open('wb') as dst:
                shutil.copyfileobj(src,dst)
            extracted.append(target)
    return sorted(extracted)


def sanitized_case(x):
    return {k:v for k,v in x.items() if k not in ('topics','one_second_histogram')}


def run(output: Path, *, download=True, input_dir:Path|None=None):
    output=Path(output).resolve()
    input_dir=Path(input_dir or (output.parent/'public_raw')).resolve()
    output.mkdir(parents=True,exist_ok=True)
    input_dir.mkdir(parents=True,exist_ok=True)
    ledger={'method':'External ROS2 bag file compatibility and topic rate evaluation (not fault classification)',
      'recording_sources':{},'status':'IN_PROGRESS',
      'reference_truth':'Publisher-described run labels only; no independent fault onset or true negative episode annotations.',
      'generated_reports_contain_no_raw_bag_bytes':True}
    def source(name,url,limit):
        suffix='.mcap' if name=='bagel_example' else '.zip'
        archive=input_dir/(name+suffix)
        rec={'url':url,'success':False,'files':[]}
        ledger['recording_sources'][name]=rec
        try:
            meta=stream_download(url,archive,limit) if download else ({'bytes':archive.stat().st_size} if archive.exists() else None)
            if not meta: raise ValueError('Missing local source '+str(archive))
            rec.update(meta)
            paths=[archive] if suffix=='.mcap' else extract_bags(archive,input_dir/name)
            if not paths: raise ValueError('Archive contained no ROS2 .db3 or MCAP')
            rec['success']=True
            rec['files']=[str(p.relative_to(input_dir)) for p in paths]
            rec['bag_count']=len(paths)
            print(name,':',len(paths),'bag(s)')
            return paths
        except Exception as exc:
            rec['error']=str(exc)[:350]
            print(name,': DOWNLOAD/EXTRACT ERROR:',rec['error'],file=sys.stderr)
            return []
    ex=source('experiment1',*SOURCES['experiment1'])
    vi=source('vigo_navigation',*SOURCES['vigo_navigation'])
    bg=source('bagel_example',*SOURCES['bagel_example'])
    for name, paths in [('experiment1',ex),('vigo_navigation',vi),('bagel_example',bg)]:
        rec=ledger['recording_sources'][name]
        if not paths: continue
        rec['bag_summaries']=[]
        for p in paths[:16]:
            try:
                case=summarize_bag(p,max_messages=2_000_000)
                rec['bag_summaries'].append({'name':p.name,'path':str(p.relative_to(input_dir)),
                    'messages':case['message_count'],'topics':case['topic_count'],'duration_s':case['duration_s'],
                    'sha256':case['sha256'],
                    'rate_preview':[{'topic':s['topic'],'hz':s['mean_hz']} for s in case['topics'] if ('cmd_vel' in s['topic'] or s['topic'].endswith('/odom'))][:8]})
            except Exception as exc:
                rec['bag_summaries'].append({'name':p.name,'error':str(exc)[:300]})
        if name=='bagel_example':
            try:
                p=paths[0]
                result=subprocess.run([sys.executable,'-m','robot_incident_analyzer','field-validate',str(p),'--origin','unknown', '--output',str(output/'bagel_single_report')],timeout=75,capture_output=True,text=True)
                rec['single_analysis_return_code']=result.returncode
                if result.returncode not in (0,3):rec['single_analysis_error']=result.stdout[-700:]+result.stderr[-700:]
            except Exception as exc:
                rec['single_analysis_error']=str(exc)[:350]
    # Deep run: compare not only topic headers but event-based rule analysis for
    # independent physical navigation recordings. Always label rule hits as
    # unadjudicated candidates, not confirmed hardware defects.
    for name, paths, origin in [('experiment1',ex,'unknown'),('vigo_navigation',vi,'physical')]:
        if not paths:
            continue
        rec=ledger['recording_sources'][name]
        try:
            result=subprocess.run([sys.executable,'-m','robot_incident_analyzer','field-validate',
                *[str(x) for x in paths[:12]], '--origin',origin,'--output',str(output/(name+'_field_reports')),
                '--max-messages','200000'], timeout=150,capture_output=True,text=True)
            rec['full_event_analysis_return_code']=result.returncode
            if result.returncode in (0,3):
                field=json.loads((output/(name+'_field_reports')/'field_results.json').read_text())
                rec['deep_analysis']=[{'name':x['input_name'],'messages':x['message_count'],
                    'topic_count':x['topic_count'],'event_count':x['event_count'],
                    'finding_count':x['finding_count'], 'event_codes':x['event_codes'],
                    'status':x['status'], 'review_flags':x['review_flags'],
                    'warning_count':len(x.get('warnings',[])),
                    'topic_mappings':x.get('topic_mappings',[])} for x in field['cases']]
                if name=='vigo_navigation':
                    wrong=[{'file':x['name'],'mapping':m.get('command')} for x in rec['deep_analysis']
                           for m in x.get('topic_mappings',[]) if 'gps_vel' in (m.get('command') or '')]
                    ledger['vigo_command_semantic_safety']={'passed':not wrong,
                        'improper_velocity_as_command_mappings':wrong,
                        'note':'GPS velocity measurement must not auto-map as actuation command'}
                print(name,': full event analysis',len(rec['deep_analysis']), 'bag(s)')
            else:
                rec['full_analysis_error']=(result.stderr[-1500:]+' '+result.stdout[-1500:])[:2600]
        except Exception as exc:
            rec['full_analysis_error']=str(exc)[:500]
    if len(ex)>=2:
        normal=next((p for p in ex if 'E1-1/' in p.as_posix()),None)
        attack=next((p for p in ex if 'E1-2/' in p.as_posix()),None)
        if normal and attack:
            try:
                cmp=compare_bags(normal,[attack],output/'experiment1_comparison')
                rows=cmp['candidate_cases'][0]['topic_comparisons']
                hit=next((r for r in rows if r['topic']=='/mobile_base_controller/cmd_vel'),None)
                ok=bool(hit and hit['status']=='RATE_INCREASE' and 5<hit['rate_ratio']<15)
                ledger['experiment1_rate_regression']={'verified':ok,'command_topic':hit,'note':'A simulated attack was publisher-described, but only downstream bag rates were measured.'}
                if not ok: ledger['experiment1_rate_regression']['error']='Rate increase was not identified as expected'
            except Exception as exc:
                ledger['experiment1_rate_regression']={'verified':False,'error':str(exc)[:350]}
    if len(ex)>=2:
        normal=next((p for p in ex if 'E1-1/' in p.as_posix()),None)
        attack=next((p for p in ex if 'E1-2/' in p.as_posix()),None)
        if normal and attack:
            try:
                case=inspect_bag(attack,output/'experiment1_rate_timeline',reference=normal,
                                 topic='/mobile_base_controller/cmd_vel',min_consecutive=2)
                control=inspect_bag(normal,output/'experiment1_control_rate_timeline',reference=normal,
                                    topic='/mobile_base_controller/cmd_vel',min_consecutive=2)
                ok=(case['episode_count']>=1 and control['episode_count']==0)
                ledger['experiment1_local_episode_regression']={
                    'verified':ok,'positive_episodes':case['episode_count'],
                    'negative_control_episodes':control['episode_count'],
                    'episodes':case['topics'][0]['episodes'][:10],
                    'note':'Observed recorded arrival-density windows; no external onset-time truth labels.'}
                print('experiment1: single-recording rate episodes',case['episode_count'],
                      'negative-control episodes',control['episode_count'])
            except Exception as exc:
                ledger['experiment1_local_episode_regression']={'verified':False,'error':str(exc)[:500]}
    if len(vi)>=2:
        try:
            cmp=compare_bags(vi[0],vi[1:13],output/'vigo_multi_comparison')
            ledger['vigo_reference_analysis']={'bag_count':len(vi),'compared':len(cmp['candidate_cases']),
                 'rate_increases':sum(c['rate_increases'] for c in cmp['candidate_cases']),
                 'note':'Different driving configurations; rate differences do not imply defects'}
        except Exception as exc:
            ledger['vigo_reference_analysis']={'error':str(exc)[:350]}
    # Independent navigation recordings are *not* confirmed healthy. This
    # rate-control pass measures only alerts against another recorded run;
    # each result must be reviewed before it can be called a false alarm.
    if len(vi)>1:
        cases=[]
        for p in vi[1:]:
            try:
                r=inspect_bag(p,output/'vigo_rate_episodes'/p.stem,
                    reference=vi[0],topic=None)
                cases.append({'name':p.name,'episode_count':r['episode_count'],
                    'selected_topics':len(r['topics']),
                    'status':'UNADJUDICATED'})
            except Exception as exc:
                cases.append({'name':p.name,'error':str(exc)[:300]})
        ledger['vigo_local_rate_review']={'cases':cases,
            'total_episodes':sum(c.get('episode_count',0) for c in cases),
            'note':'Not a labeled negative-control experiment; configuration differences may alter rates.'}
    ledger['total_bags_downloaded']=len(ex)+len(vi)+len(bg)
    ledger['successfully_summarized']=sum(sum('error' not in c for c in v.get('bag_summaries',[])) for v in ledger['recording_sources'].values())
    ledger['status']='COMPLETE_WITH_LIMITATIONS' if ledger['total_bags_downloaded'] else 'NO_BAGS_DOWNLOADED'
    (output/'DATASET_LEDGER.json').write_text(json.dumps(ledger,indent=2,ensure_ascii=False),encoding='utf-8')
    msg=['# External ROS2 bag evaluation — independent third-party recordings','',
      'This file distinguishes downloaded data and actual analysis from planned work. No data source has been judged to be free of fault.','',
      f"- Bags downloaded: **{ledger['total_bags_downloaded']}**",
      f"- Bags successfully summarized: **{ledger['successfully_summarized']}**",'']
    for name,rec in ledger['recording_sources'].items():
        msg += [f"## {name}",f"- Source: {rec['url']}",f"- Download: {'SUCCESS' if rec['success'] else 'FAILED'}"]
        if 'error' in rec:msg.append('- Error: '+rec['error'])
        msg.append(f"- Recordings: {len(rec['files'])}")
        for item in rec.get('bag_summaries',[]):
            msg.append(f"- {item['name']}: "+(f"{item['messages']:,} messages, {item['topics']} topics, {item['duration_s']} seconds" if 'error' not in item else 'ERROR: '+item['error']))
        msg.append('')
    msg+=['## Independent normal-vs-simulated-attack acceptance','',json.dumps(ledger.get('experiment1_rate_regression',{'status':'NOT_TESTED'}),ensure_ascii=False,indent=2),'',
          '## Vigo relative comparison','',json.dumps(ledger.get('vigo_reference_analysis',{'status':'NOT_TESTED'}),ensure_ascii=False,indent=2),
          '', '## Time-localized command-rate episode check','',json.dumps(ledger.get('experiment1_local_episode_regression',{'status':'NOT_TESTED'}),ensure_ascii=False,indent=2),
          '', '## Vigo rate-episode review','',json.dumps(ledger.get('vigo_local_rate_review',{'status':'NOT_TESTED'}),ensure_ascii=False,indent=2),
          '', '## Caveats', '', '- Recorded topic message rates are not publisher-set rates or verified robot control updates.',
          '- A normal publisher label does not make every individual observation normal; manually review normal-case warnings.',
          '- Different vehicle speeds, RTK configurations, and robots can legitimately have different sample rates.',
          '- This test does not establish fault detection precision/recall or a reduction in engineering investigation time.']
    (output/'DATASET_REPORT.md').write_text('\n'.join(msg)+'\n',encoding='utf-8')
    print('Data ledger:',output/'DATASET_LEDGER.json', 'summarized', ledger['successfully_summarized'])
    return ledger


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,default=Path('public_multibag_results'))
    ap.add_argument('--offline',action='store_true',help='Use existing archives in input directory; no download')
    ap.add_argument('--input-dir',type=Path)
    a=ap.parse_args()
    r=run(a.output,download=not a.offline,input_dir=a.input_dir)
    # Exit 0 only when the independent normal-vs-attack case is truly verified,
    # Vigo multi-run dataset downloaded, and BAGEL MCAP was interpreted.
    good=(r.get('experiment1_rate_regression',{}).get('verified') is True and
          r.get('experiment1_local_episode_regression',{}).get('verified') is True and
          r.get('vigo_reference_analysis',{}).get('compared',0)>=2 and
          r.get('vigo_command_semantic_safety',{}).get('passed') is True and
          r.get('recording_sources',{}).get('bagel_example',{}).get('single_analysis_return_code') in (0,3))
    raise SystemExit(0 if good else 1)
