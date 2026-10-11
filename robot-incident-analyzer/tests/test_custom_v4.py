from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from robot_incident_analyzer.custom_messages import SchemaRegistry, parse_msg, validate_custom_roles
from robot_incident_analyzer.__main__ import analyze_files, load_config
from robot_incident_analyzer.fixture_custom import custom_records
from robot_incident_analyzer.fixture_v2 import make_db3, make_mcap
from robot_incident_analyzer.discovery import discover
from robot_incident_analyzer.report import velocity_plot
from robot_incident_analyzer.models import Event

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'examples' / 'config_custom.json'


class CustomMessageV4Tests(unittest.TestCase):
    def test_load_schema_nested_and_variable_array(self):
        cfg = load_config(CONFIG)
        registry = SchemaRegistry(cfg['schema_dirs'])
        record = next(rec for rec in custom_records() if 'DriveCommand' in rec[1])
        decoded = registry.decode(record[1],record[3])
        self.assertAlmostEqual(decoded['target']['linear_x'],.45)
        self.assertEqual(len(decoded['target']['wheel_rpm']),2)
        self.assertEqual(decoded['header']['frame_id'],'base_link')
        self.assertEqual(decoded['mode'],1)
        self.assertAlmostEqual(decoded['target']['wheel_rpm'][0],14.5)

    def test_explicit_role_maps_and_ambiguity(self):
        cfg=load_config(CONFIG)
        roles=validate_custom_roles(cfg['custom_messages'],SchemaRegistry(cfg['schema_dirs']))
        names={'/robot1/drive/input':'acme_robot_msgs/msg/DriveCommand',
               '/robot1/drive/input_backup':'acme_robot_msgs/msg/DriveCommand',
               '/robot1/drive/feedback':'acme_robot_msgs/msg/DriveFeedback'}
        d=discover(names, custom_roles=roles)
        self.assertNotIn('command',d.selected)
        d=discover(names,{'command':'/robot1/drive/input','odometry':'/robot1/drive/feedback'},roles)
        self.assertEqual(d.selected['command'],'/robot1/drive/input')

    def test_integration_custom_db3_mcap(self):
        cfg=load_config(CONFIG)
        for fmt,make in [('db3',make_db3),('mcap',make_mcap)]:
            with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/('custom.'+fmt)
                with patch('robot_incident_analyzer.fixture_v2.message_records',return_value=custom_records()):
                    make(path)
                ev,fi,stats,warns,files,details=analyze_files([path],Path(tmp)/'output',cfg)
                codes={e.code for e in ev}
                self.assertIn('CMD_ODOM_MISMATCH',codes)
                self.assertIn('ODOM_POSITION_JUMP',codes)
                self.assertEqual(details[0]['custom_decoded'],32)
                self.assertGreater(len(details[0]['velocity_trace']),8)
                html=(Path(tmp)/'output'/'report.html').read_text()
                self.assertIn('class="focus"',html)
                self.assertIn('WARN / ERROR marker',html)
                self.assertIn('Custom CDR messages decoded: 32',html)
                self.assertEqual(json.loads((Path(tmp)/'output'/'report.json').read_text())['version'],'0.5.1')

    def test_missing_schema_and_invalid_paths_are_rejected(self):
        registry=SchemaRegistry()
        with self.assertRaisesRegex(ValueError,'missing'):
            validate_custom_roles({'fake_pkg/msg/Drive':{'role':'command','linear_x':'speed'}},registry)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'does not exist'):
                SchemaRegistry([tmp+'/missing'])
        with self.assertRaisesRegex(ValueError,'required linear_x'):
            validate_custom_roles({'builtin_interfaces/msg/Time':{'role':'command'}},registry)
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            parse_msg('float64 weird_type[unsupported]', 'my_pkg')

    def test_bounded_sequence_denies_malformed_payload(self):
        cfg=load_config(CONFIG)
        registry=SchemaRegistry(cfg['schema_dirs'])
        raw=next(r[3] for r in custom_records() if 'DriveCommand' in r[1]);raw=bytearray(raw)
        # Nested sequence is two float32s, corrupt the count to a huge number
        needle=b'\x02\x00\x00\x00'
        pos=raw.find(needle,40)
        self.assertGreaterEqual(pos,0)
        raw[pos:pos+4]=(2**32-1).to_bytes(4,'little')
        with self.assertRaises(ValueError):
            registry.decode('acme_robot_msgs/msg/DriveCommand',bytes(raw))

    def test_html_marker_escapes_untrusted_values(self):
        trace=[{'time':10.,'command_mps':.5,'odometry_mps':0.},
               {'time':11.,'command_mps':.4,'odometry_mps':.1}]
        ev=Event(timestamp=10.5,severity='WARN',category='x',code='<script>',message='"onmouseover="')
        html=velocity_plot(trace,[ev])
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('recorded timestamps',html.lower())

if __name__ == '__main__':
    unittest.main()
