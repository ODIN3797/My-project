"""Additional independent engineering acceptance checks (synthetic inputs only)."""
from __future__ import annotations
from tempfile import TemporaryDirectory
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from robot_incident_analyzer.__main__ import analyze_files
from robot_incident_analyzer.inputs import parse_time, collect_inputs
from robot_incident_analyzer.models import Event
from robot_incident_analyzer.analysis import build_findings
from robot_incident_analyzer.fixture_v2 import make_mcap, message_records
from robot_incident_analyzer.telemetry import TelemetryAnalyzer


class ValidationReadinessTests(unittest.TestCase):
    def test_csv_nan_inf_overflow_rejected(self):
        for timestamp in ['NaN', 'inf', '-Infinity', '1e300']:
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(ValueError):
                    parse_time(timestamp)

    def test_csv_invalid_timestamp_no_report_written(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            p = root/'invalid.csv'
            p.write_text('timestamp,message,severity\nnan,an error,ERROR\n')
            with self.assertRaises(ValueError):
                analyze_files([p], root/'out')
            self.assertFalse((root/'out'/'report.json').exists())

    def test_robot_namespaces_propagate_to_events(self):
        a = TelemetryAnalyzer('shared_bag.mcap')
        a.emit(100.0, 'DIAGNOSTIC_ERROR', 'A broken', '/robot1/diagnostics')
        a.emit(101.0, 'DIAGNOSTIC_ERROR', 'B broken', '/robot2/diagnostics')
        self.assertEqual([x.robot_id for x in a.events], ['robot1', 'robot2'])
        f = build_findings(a.events)
        self.assertFalse(any(x.code == 'INCIDENT_CONTEXT' for x in f), 'must not correlate robot1 and robot2 only by file')

    def test_unsupported_payload_warnings_exposed(self):
        raw = message_records()
        unsupported = [('/robot1/laser/scan', 'sensor_msgs/msg/LaserScan', 1791633600000000000, b'not-a-cdr')]
        with TemporaryDirectory() as t:
            p = Path(t)/'mixed.mcap'
            with patch('robot_incident_analyzer.fixture_v2.message_records', return_value=raw+unsupported):
                make_mcap(p)
            events, stat, warnings, files, details = collect_inputs([p], with_details=True)
            self.assertTrue(any('NOT inspected' in w and 'LaserScan' in w for w in warnings))
            self.assertTrue(any(s.topic == '/robot1/laser/scan' for s in stat))

    def test_ambiguous_topic_selection_does_not_compare(self):
        raw = message_records()
        extra = [('/cmd_vel_safe',typ,ts,data) for topic,typ,ts,data in raw if topic == '/cmd_vel']
        with TemporaryDirectory() as t:
            p=Path(t)/'mixed.mcap'
            with patch('robot_incident_analyzer.fixture_v2.message_records',return_value=sorted(raw+extra, key=lambda x:x[2])):
                make_mcap(p)
            events,stats,warns,files,details=collect_inputs([p],with_details=True)
            self.assertTrue(any('ambiguous' in w for w in warns))
            self.assertFalse(any(e.code == 'CMD_ODOM_MISMATCH' for e in events))

    def test_report_has_local_only_and_warning(self):
        with TemporaryDirectory() as t:
            root=Path(t)
            p=make_mcap(root/'test.mcap')
            analyze_files([p],root/'report')
            html=(root/'report'/'report.html').read_text()
            self.assertIn('not verified root causes',html)
            self.assertIn('No files uploaded',html)
            obj=json.loads((root/'report'/'report.json').read_text())
            self.assertIn('events',obj)

    def test_errors_across_multiple_files_not_correlated(self):
        a=Event(timestamp=100,severity='WARN',category='log',code='COMMUNICATION',message='Network disconnected',source='robot_a.csv')
        b=Event(timestamp=110,severity='ERROR',category='log',code='NAVIGATION',message='Nav2 failed',source='robot_b.csv')
        findings=build_findings([a,b])
        self.assertNotIn('NAV_WITH_PRECEDING_SIGNAL',{x.code for x in findings})

if __name__=='__main__': unittest.main()
