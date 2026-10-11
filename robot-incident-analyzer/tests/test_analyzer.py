from __future__ import annotations
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from robot_incident_analyzer.analysis import build_findings
from robot_incident_analyzer.demo import generate_demo, rosout_payload, BASE
from robot_incident_analyzer.inputs import collect_inputs, decode_rosout_log, read_csv_events
from robot_incident_analyzer.report import save_report
from robot_incident_analyzer.models import Event


class AnalyzerTests(unittest.TestCase):
    def test_rosout_cdr_decoder(self):
        value = decode_rosout_log(rosout_payload(40, 'controller', 'Timeout occurred', BASE))
        self.assertEqual(value, (40, 'controller', 'Timeout occurred'))

    def test_csv_incidents(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv, _ = generate_demo(Path(tmp))
            events = read_csv_events(csv)
            for i,event in enumerate(events,1):
                event.event_id = f'E{i:04d}'
            findings = build_findings(events)
            codes = [f.code for f in findings]
            self.assertIn('NAV_WITH_PRECEDING_SIGNAL', codes)
            self.assertIn('DOCK_OK_CHARGE_FAILED', codes)
            self.assertIn('RECURRING_ALERT', codes)

    def test_full_demo_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generate_demo(root/'demo')
            events, stats, warnings, files = collect_inputs([root/'demo'])
            self.assertGreater(len(events), 10)
            self.assertEqual(len(stats), 3)
            self.assertTrue(any(e.code == 'TOPIC_GAP' for e in events))
            self.assertTrue(any(e.topic == '/rosout' and e.severity == 'ERROR' for e in events))
            findings = build_findings(events)
            save_report(root/'results', events, findings, stats, warnings, files)
            document = (root/'results'/'report.html').read_text(encoding='utf-8')
            self.assertIn('Incident timeline', document)
            self.assertIn('rosout', document)
            report = json.loads((root/'results'/'report.json').read_text(encoding='utf-8'))
            self.assertEqual(len(report['events']), len(events))

    def test_html_escaping(self):
        from robot_incident_analyzer.report import render_report
        evt=Event(timestamp=BASE, severity='ERROR',category='demo',code='TEST',
                  message='<script>alert("x")</script>',event_id='E0001')
        document = render_report([evt], build_findings([evt]), [], [], [])
        self.assertNotIn('<script>alert("x")</script>', document)
        self.assertIn('&lt;script&gt;', document)

    def test_bad_csv_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'invalid.csv'
            file.write_text('a,b\n1,2\n')
            with self.assertRaises(ValueError):
                read_csv_events(file)

    def test_bag_truncation_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, bag=generate_demo(Path(tmp))
            events, stats, warnings, files = collect_inputs([bag], max_messages=20)
            self.assertTrue(warnings)
            self.assertTrue(stats)


if __name__=='__main__':
    unittest.main()
