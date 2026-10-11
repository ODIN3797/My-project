from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from robot_incident_analyzer.discovery import discover
from robot_incident_analyzer.fixture_v2 import BASE, make_db3, make_mcap, message_records, twist_payload
from robot_incident_analyzer.__main__ import load_config, analyze_files
from robot_incident_analyzer.inputs import collect_inputs
from robot_incident_analyzer.telemetry import validate_thresholds


class DiscoveryV3Tests(unittest.TestCase):
    def test_vigo_gps_twist_not_inferred_as_motor_command(self):
        topics={'/rpsc4/global_position/raw/gps_vel':'geometry_msgs/msg/TwistStamped',
                '/rpsc4/global_position/local':'nav_msgs/msg/Odometry'}
        d=discover(topics)
        self.assertNotIn('command',d.selected)
        self.assertTrue(any('not automatically mapped' in w for w in d.warnings))
        d_manual=discover(topics,{'command':'/rpsc4/global_position/raw/gps_vel'})
        self.assertIn('command',d_manual.selected)
        self.assertTrue(any('verify it is an actuation command' in w for w in d_manual.warnings))

    def test_namespaced_alias_type_first(self):
        topics={'/robot1/navifra/control/velocity_cmd':'geometry_msgs/msg/Twist',
                '/robot1/wheel/odom':'nav_msgs/msg/Odometry',
                '/robot1/raw/speed':'std_msgs/msg/Float32'}
        d=discover(topics)
        self.assertEqual(d.selected['command'],'/robot1/navifra/control/velocity_cmd')
        self.assertEqual(d.selected['odometry'],'/robot1/wheel/odom')
        self.assertNotIn('/robot1/raw/speed',[x['topic'] for x in d.candidates['command']])

    def test_ambiguous_names_skip(self):
        d=discover({'/cmd_vel_raw':'geometry_msgs/msg/Twist','/cmd_vel_safe':'geometry_msgs/msg/Twist',
                    '/odom':'nav_msgs/msg/Odometry'})
        self.assertNotIn('command',d.selected)
        self.assertEqual(d.selected.get('odometry'),'/odom')
        self.assertTrue(any('ambiguous' in w for w in d.warnings))

    def test_manual_mapping_and_invalid_type(self):
        topics={'/cmd_vel_raw':'geometry_msgs/msg/Twist', '/cmd_vel_safe':'geometry_msgs/msg/Twist',
                '/odom':'nav_msgs/msg/Odometry', '/some_float':'std_msgs/msg/Float32'}
        d=discover(topics,{'command':'/cmd_vel_safe','odometry':'/odom'})
        self.assertEqual(d.selected['command'],'/cmd_vel_safe')
        d2=discover(topics,{'command':'/some_float'})
        self.assertNotIn('command',d2.selected)
        self.assertTrue(any('incompatible' in x for x in d2.warnings))

    def test_different_robot_namespaces_not_joined(self):
        d=discover({'/robot1/cmd_vel':'geometry_msgs/msg/Twist',
                    '/robot2/odom':'nav_msgs/msg/Odometry'})
        self.assertNotIn('command',d.selected)
        self.assertNotIn('odometry',d.selected)
        self.assertTrue(any('namespaces differ' in x for x in d.warnings))

    def test_invalid_threshold_rejected(self):
        with self.assertRaises(ValueError): validate_thresholds({'command_min_mps':-2})
        with self.assertRaises(ValueError): validate_thresholds({'other':1})
        with self.assertRaises(ValueError): validate_thresholds({'mismatch_min_samples':2.5})

    def test_end_to_end_alias_db3_and_mcap(self):
        sample=message_records()
        aliased=[(topic.replace('/cmd_vel','/robot1/navifra/control/velocity_cmd')
                    .replace('/odom','/robot1/wheel/odom'),ty,ts,data)
                 for topic,ty,ts,data in sample]
        for maker in [make_db3,make_mcap]:
            with self.subTest(format=maker.__name__),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/('rec.db3' if maker==make_db3 else 'rec.mcap')
                with patch('robot_incident_analyzer.fixture_v2.message_records',return_value=aliased):
                    maker(p)
                ev,_,_,_,details=collect_inputs([p],with_details=True)
                self.assertIn('CMD_ODOM_MISMATCH',{e.code for e in ev})
                self.assertIn('velocity_cmd',details[0]['discovery']['selected']['command'])
                self.assertGreater(len(details[0]['velocity_trace']),5)

    def test_ambiguity_disables_command_odom_comparison_until_override(self):
        sample=message_records()
        extra=[('/cmd_vel_safe',typ,ts,data) for topic,typ,ts,data in sample if topic=='/cmd_vel']
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'ambiguous.mcap'
            with patch('robot_incident_analyzer.fixture_v2.message_records',return_value=sorted(sample+extra,key=lambda r:r[2])):
                make_mcap(p)
            ev,_,warnings,_,details=collect_inputs([p],with_details=True)
            self.assertNotIn('CMD_ODOM_MISMATCH',{e.code for e in ev})
            self.assertTrue(any('ambiguous' in w for w in warnings))
            ev,_,warnings,_,details=collect_inputs([p],with_details=True,topic_map={'command':'/cmd_vel','odometry':'/odom'})
            self.assertIn('CMD_ODOM_MISMATCH',{e.code for e in ev})

    def test_config_and_html_report_contains_discovery_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=make_mcap(Path(tmp)/'demo.mcap')
            cfg=Path(tmp)/'config.json'
            cfg.write_text(json.dumps({'topics':{'command':'/cmd_vel','odometry':'/odom'},
                                       'thresholds':{'command_min_mps':0.3}}))
            events,findings,stats,warnings,paths,details=analyze_files([p],Path(tmp)/'out',load_config(cfg))
            self.assertIn('CMD_ODOM_MISMATCH',{e.code for e in events})
            html=(Path(tmp)/'out'/'report.html').read_text()
            self.assertIn('Velocity comparison',html)
            self.assertIn('<svg',html)
            self.assertIn('Topic auto-discovery',html)
            self.assertIn('INCIDENT_CONTEXT', json.dumps([f.to_dict() for f in findings]))
            payload=json.loads((Path(tmp)/'out'/'report.json').read_text())
            self.assertTrue(payload['telemetry'][0]['velocity_trace'])

if __name__=='__main__':unittest.main()
