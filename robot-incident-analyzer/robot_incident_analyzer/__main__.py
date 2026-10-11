from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from . import __version__
from .analysis import build_findings
from .demo import generate_demo
from .fixture_v2 import make_telemetry_demo
from .inputs import collect_inputs
from .report import save_report


def load_config(path: Path | None) -> dict:
    if path is None: return {}
    cfg=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(cfg,dict): raise ValueError('Configuration root must be an object')
    if set(cfg)-{'topics','thresholds','schema_dirs','custom_messages','state_keys'}: raise ValueError('Configuration has unknown top-level keys')
    if not isinstance(cfg.get('topics',{}),dict) or not isinstance(cfg.get('thresholds',{}),dict):
        raise ValueError('topics and thresholds must be JSON objects')
    if 'schema_dirs' in cfg:
        if not isinstance(cfg['schema_dirs'],list) or any(not isinstance(x,str) for x in cfg['schema_dirs']):
            raise ValueError('schema_dirs must be a JSON list of paths')
        cfg['schema_dirs'] = [str((path.parent / x).resolve()) for x in cfg['schema_dirs']]
    if 'custom_messages' in cfg and not isinstance(cfg['custom_messages'],dict):
        raise ValueError('custom_messages must be a JSON object')
    from .state_timeline import validate_state_keys
    validate_state_keys(cfg.get('state_keys'))
    return cfg


def analyze_files(paths:list[Path], output:Path, config=None, max_messages=200000):
    config=config or {}
    from .custom_messages import SchemaRegistry, validate_custom_roles
    registry = SchemaRegistry(config.get('schema_dirs', []))
    custom_roles = validate_custom_roles(config.get('custom_messages', {}), registry)
    events,stats,warnings,files,details=collect_inputs(paths,max_messages,with_details=True,
        topic_map=config.get('topics'),thresholds=config.get('thresholds'),
        schema_registry=registry,custom_roles=custom_roles,state_keys=config.get('state_keys'))
    findings=build_findings(events)
    save_report(output,events,findings,stats,warnings,files,details, state_keys=config.get('state_keys'))
    return events,findings,stats,warnings,files,details


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(prog='robot-incident-analyzer',
        description='Offline ROS2 MCAP/DB3/CSV incident report generator with topic auto-discovery')
    parser.add_argument('--version',action='version',version=f'%(prog)s {__version__}')
    sub=parser.add_subparsers(dest='command',required=True)
    demo=sub.add_parser('demo',help='generate fictional CSV + ROS2 MCAP examples')
    demo.add_argument('--output',default='demo_data',type=Path)
    studio_demo=sub.add_parser('demo-studio', help='generate fictional trajectories and multi-sensor MCAP')
    studio_demo.add_argument('--output', default='studio_data', type=Path)
    states_demo=sub.add_parser('demo-states',help='generate fictional docking/charging mode transitions with sensors')
    states_demo.add_argument('--output',default='state_demo',type=Path)
    custom_demo=sub.add_parser('demo-custom',help='generate fictional custom message MCAP example')
    custom_demo.add_argument('--output',default='demo_custom',type=Path)
    analyze=sub.add_parser('analyze',help='generate HTML/JSON report from inputs')
    analyze.add_argument('inputs',nargs='+',type=Path,help='CSV/DB3/MCAP file(s) or directory')
    analyze.add_argument('--output',default='output',type=Path)
    analyze.add_argument('--config',type=Path,help='optional JSON topic overrides and thresholds')
    analyze.add_argument('--max-messages',type=int,default=200000)
    analyze.add_argument('--pdf',action='store_true',help='create offline PDF report (optional reportlab package)')
    field=sub.add_parser('field-validate', help='offline compatibility and labelled-incident acceptance on external bags')
    field.add_argument('inputs', nargs='+', type=Path, help='local MCAP/DB3 recordings')
    field.add_argument('--output', default='field_results', type=Path)
    field.add_argument('--config', type=Path)
    field.add_argument('--labels', type=Path, help='optional human-authored CSV expected incidents')
    field.add_argument('--origin', choices=['unknown', 'physical', 'simulation', 'synthetic'], default='unknown')
    field.add_argument('--max-messages', type=int, default=200000)
    gui=sub.add_parser('gui',help='local-only browser UI with drag-and-drop upload')
    gui.add_argument('--port',type=int,default=8765)
    gui.add_argument('--output',type=Path,default=Path('output_gui'))
    gui.add_argument('--config',type=Path)
    gui.add_argument('--max-upload-mb',type=int,default=50)
    args=parser.parse_args(argv)
    try:
        if args.command=='demo':
            csv_path,db3_path=generate_demo(args.output)
            mcap_path=make_telemetry_demo(args.output)
            print(f'Fictional CSV: {csv_path}\nFictional DB3: {db3_path}\nFictional MCAP: {mcap_path}')
            print(f'Next: python -m robot_incident_analyzer analyze {args.output} --output output')
            return 0
        if args.command=='demo-studio':
            from .fixture_studio import make_studio_demo
            path = make_studio_demo(args.output)
            print(f'Fictional multi-sensor MCAP: {path}')
            print(f'Next: python -m robot_incident_analyzer analyze {path} --output studio_report')
            return 0
        if args.command=='demo-states':
            from .fixture_states import make_state_demo
            bag=make_state_demo(args.output)
            print(f'Fictional state-change recording: {bag}')
            print(f'Next: python -m robot_incident_analyzer analyze {bag} --output state_report')
            return 0
        if args.command=='demo-custom':
            from .fixture_custom import make_custom_demo
            mcap=make_custom_demo(args.output)
            print(f'Fictional custom MCAP: {mcap}')
            print(f'Next: python -m robot_incident_analyzer analyze {mcap} --config examples/config_custom.json --output output_custom')
            return 0
        if args.command=='field-validate':
            from .field_validation import analyze_field_cases
            result=analyze_field_cases(args.inputs, args.output, config_file=args.config,
                labels_file=args.labels, origin=args.origin, max_messages=args.max_messages)
            print(f'Processed {result["recording_count"]} recording(s). Results: {args.output / "FIELD_RESULTS.md"}')
            for item in result['cases']:
                print(f'{item["id"]}: {item["status"]}, {item["topic_count"]} topics, {item["event_count"]} events')
            return 3 if any(x['status']=='REVIEW_REQUIRED' for x in result['cases']) else 0
        if args.command=='gui':
            from .gui import run_gui
            if not (1<=args.port<=65535): raise ValueError('port must be between 1 and 65535')
            if not (1<=args.max_upload_mb<=200): raise ValueError('max-upload-mb must be within 1..200')
            return run_gui(args.port,args.output,load_config(args.config),args.max_upload_mb)
        if args.max_messages < 1: raise ValueError('--max-messages must be positive')
        events,findings,stats,warnings,paths,details=analyze_files(args.inputs,args.output,load_config(args.config),args.max_messages)
        print(f'Analyzed {len(events)} incident events and {len(stats)} ROS2 topics from {len(paths)} files.')
        print(f'Potential findings: {len(findings)} (not confirmed root causes)')
        for detail in details:
            print(f'Auto discovery ({detail["source"]}): {detail["discovery"]["selected"]}')
        if args.pdf:
            from .pdf_export import export_pdf
            export_pdf(args.output / "report.pdf",events,findings,stats,warnings,paths,details,state_keys=load_config(args.config).get("state_keys"))
            print(f'PDF: {args.output / "report.pdf"}')
        print(f'HTML: {args.output / "report.html"}\nJSON: {args.output / "report.json"}')
        if warnings:
            for warning in warnings: print(f'WARNING: {warning}',file=sys.stderr)
        return 0
    except (ValueError,OSError,ImportError,json.JSONDecodeError) as exc:
        print(f'Error: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
