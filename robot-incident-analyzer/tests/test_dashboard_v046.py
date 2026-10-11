"""Regression checks for the offline investigation dashboard."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from robot_incident_analyzer.dashboard import density_timeline, topic_timing_variation, top_sources
from robot_incident_analyzer.models import Event, Finding, TopicStats
from robot_incident_analyzer.report import render_report, save_report


def ev(t, severity='WARN', code='TEST', src='robotA.mcap', message='sample'):
    return Event(timestamp=t, severity=severity, category='test', code=code,
                 message=message, source=src, event_id=f'E{int(t):04d}')


class DashboardV046Tests(unittest.TestCase):
    def test_blank_csv_only_report_still_useful(self):
        html=render_report([],[],[],[],[Path('empty.csv')])
        self.assertIn('No WARN, ERROR or INFO events to plot.',html)
        self.assertIn('No unambiguous command / odometry pair recorded.',html)
        self.assertIn('No ROS2 topic statistics available',html)
        self.assertNotIn('https://cdn.',html)
        self.assertIn('Offline by design',html)

    def test_chart_counts_and_last_event_window_inclusive(self):
        h=density_timeline([ev(100,'INFO'),ev(110,'WARN'),ev(120,'ERROR')])
        self.assertEqual(h.count('data-bin='),40)
        self.assertIn('data-end="120.001000000"',h)
        self.assertIn('3', h)
        self.assertIn('role="button"',h)

    def test_single_second_event_is_visible_and_keyboard_accessible(self):
        h=density_timeline([ev(100,'WARN'),ev(100,'ERROR')])
        self.assertEqual(h.count('data-bin='),40)
        self.assertIn('tabindex="0"',h)

    def test_source_display_escapes_untrusted_names(self):
        source='evil<script>alert(1)</script>.mcap'
        h=top_sources([ev(100,src=source)])
        self.assertNotIn('<script>alert(1)</script>',h)
        self.assertIn('&lt;script&gt;',h)

    def test_csv_rows_are_grouped_as_one_input_file(self):
        h=top_sources([ev(100,src='session.csv:row2'),ev(101,src='session.csv:row3')])
        self.assertIn('session.csv',h)
        self.assertNotIn('session.csv:row2',h)
        self.assertIn('<b>2</b>',h)

    def test_topic_gap_chart_is_not_automatic_fault_scoring(self):
        stat=TopicStats(topic='/scan',message_type='sensor_msgs/msg/LaserScan',count=100,
                        duration_s=10,approx_hz=10,median_gap_ms=100,max_gap_ms=800)
        h=topic_timing_variation([stat])
        self.assertIn('8.0×',h)
        self.assertIn('no sensor fault is inferred',h)
        self.assertNotIn('health score',h.lower())

    def test_findings_link_to_evidence_and_no_unescaped_html(self):
        event=ev(100,'ERROR',message='<img src=x onerror=alert(1)>')
        finding=Finding(code='INV',title='Investigate this',severity='HIGH',explanation='test',
                        evidence_ids=[event.event_id],suggested_checks=['Inspect first'])
        document=render_report([event],[finding],[],[],[Path('sample.mcap')])
        self.assertIn('href="#event-E0100"',document)
        self.assertIn('id="event-E0100"',document)
        self.assertNotIn('<img src=x onerror=alert(1)>',document)
        self.assertIn('&lt;img',document)

    def test_beyond_table_limit_is_explicit(self):
        events=[ev(100+i,'INFO') for i in range(2010)]
        html=render_report(events,[],[],[],[Path('test.csv')])
        self.assertEqual(html.count('data-ts='),2000)
        self.assertIn('First 2,000 time-sorted events shown',html)

    def test_json_preserved_with_same_event_count(self):
        events=[ev(100),ev(101,'ERROR')]
        with tempfile.TemporaryDirectory() as temp:
            save_report(Path(temp),events,[],[],[],[Path('sample.csv')])
            payload=json.loads((Path(temp)/'report.json').read_text())
            self.assertEqual(len(payload['events']),2)
            self.assertEqual(payload['version'],'0.5.4')


if __name__=='__main__':
    unittest.main()
