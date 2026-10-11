"""Regression tests for state-adjacent sensor comparisons (synthetic data)."""
from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from robot_incident_analyzer.models import Event, Finding
from robot_incident_analyzer.state_signal_compare import (compare_transition,
    transition_comparisons, summary_for_case, compare_script)
from robot_incident_analyzer.incident_workbench import cases_from_findings
from robot_incident_analyzer.state_timeline import build_state_transitions
from robot_incident_analyzer.fixture_states import make_state_demo
from robot_incident_analyzer.__main__ import main


def change(t=10):
    return dict(timestamp=t, field='docking_state', **{'from':'ALIGN', 'to':'CONTACT'},
                event_id='EV2', source='run.mcap', robot_id='robot_a')


def signal(rows, topic='/robot_a/odom'):
    return {'topic':topic,'field':'linear.x (m/s)','samples':rows}


class StateSignalCompareTests(unittest.TestCase):
    def test_pre_post_median_and_sample_counts(self):
        rows=[(8,0),(9,0),(10,0.5),(11,0.5)]
        r=compare_transition(change(),[signal(rows)],seconds=2)
        self.assertEqual(r['status'],'descriptive_only')
        self.assertEqual((r['signals'][0]['before'],r['signals'][0]['after'],r['signals'][0]['delta']), (0,0.5,0.5))
        self.assertEqual((r['signals'][0]['before_n'],r['signals'][0]['after_n']),(2,2))
        self.assertIn('CONTACT',summary_for_case([r]))
        self.assertIn('0.500',summary_for_case([r]))
        self.assertIn('no causal inference',summary_for_case([r]))

    def test_half_open_windows_no_shared_state_timestamp(self):
        rows=[(8,1),(9,3),(10,100),(11,0)]
        r=compare_transition(change(),[signal(rows)])['signals'][0]
        self.assertEqual(r['before'],2)
        self.assertEqual(r['after'],50)

    def test_sparse_telemetry_does_not_give_fake_delta(self):
        rows=[(8.01,1),(8.03,2),(10.01,4),(10.02,5)]
        r=compare_transition(change(),[signal(rows)])
        self.assertEqual(r['signals'],[])
        self.assertEqual(r['status'],'insufficient_samples')
        self.assertIn('not enough',summary_for_case([r]))

    def test_nan_inf_and_undecodable_values_excluded(self):
        rows=[(8,1),(9,float('nan')),(9.5,2),(10,float('inf')),(10.3,3),(11,4),(10.5,'not a number')]
        r=compare_transition(change(),[signal(rows)])
        self.assertEqual((r['signals'][0]['before_n'],r['signals'][0]['after_n']),(2,2))
        self.assertEqual(r['signals'][0]['delta'],2)

    def test_duplicate_timestamps_not_counted_as_independent_samples(self):
        rows=[(8.6,1),(8.6,2),(10.2,3),(10.2,4)]
        self.assertEqual(compare_transition(change(),[signal(rows)])['status'],'insufficient_samples')

    def test_multiple_transitions_at_same_time_only_one_comparison(self):
        a=change();b=dict(a,field='mode',to='PAUSED')
        c=dict(a,timestamp=11,field='command_state',to='STOPPED')
        out=transition_comparisons({'transitions':[a,b,c]},[signal([(8,1),(9,1),(10,2),(11,2),(12,3)])],max_transitions=3)
        self.assertEqual(len(out),2)
        self.assertEqual(out[0]['field'],'command_state')

    def test_limited_signals_and_transitions(self):
        rows=[(8,1),(9,1),(10,2),(11,2)]
        out=transition_comparisons({'transitions':[change()]},[signal(rows, f'/robot_a/{i}') for i in range(12)],signals_per_transition=3)
        self.assertEqual(len(out[0]['signals']),3)

    def test_no_transition_and_bad_window(self):
        self.assertIn('No explicit preceding',summary_for_case([]))
        with self.assertRaises(ValueError):compare_transition(change(),[],seconds=math.inf)

    def test_mismatch_isolation_by_robot_source(self):
        a=Event(5,'INFO','rosout','ROS_LOG','mode=AUTO','robot_a','first.mcap','/robot_a/rosout','E1')
        b=Event(6,'INFO','rosout','ROS_LOG','mode=STOPPED','robot_b','first.mcap','/robot_b/rosout','E2')
        err=Event(10,'ERROR','rosout','SYSTEM','something timed out','robot_a','first.mcap','/robot_a/rosout','E3')
        finding=Finding('SYSTEM','System log','HIGH','observed',[],['E3'])
        details=[{'source':'first.mcap','signals':[
          signal([(7,1),(8,1),(10,2),(11,2)],'/robot_a/odom'),
          signal([(7,50),(8,50),(10,80),(11,80)],'/robot_b/odom')]}]
        cases=cases_from_findings([finding],[a,b,err],details,state_transitions=build_state_transitions([a,b,err]))
        self.assertEqual(len(cases),1)
        self.assertEqual(cases[0]['sensor_comparisons'][0]['robot_id'],'robot_a')
        self.assertNotIn('/robot_b/odom', str(cases[0]['sensor_comparisons']))

    def test_standalone_html_and_json_and_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            bag=make_state_demo(Path(d))
            out=Path(d)/'output'
            self.assertEqual(main(['analyze',str(bag),'--output',str(out)]),0)
            j=json.loads((out/'report.json').read_text())
            self.assertEqual(j['version'],'0.5.2')
            comparisons=j['state_sensor_comparisons']
            self.assertTrue(comparisons)
            self.assertTrue(any(c['transitions'] and any(tr['signals'] for tr in c['transitions']) for c in comparisons))
            doc=(out/'report.html').read_text()
            self.assertIn('id="case-comparisons"',doc)
            self.assertIn('__riaDrawComparisons',doc)
            self.assertNotIn('<script src=',doc)
            self.assertIn('recording-time',doc)
            try:
                import reportlab  # noqa: F401
            except ImportError:
                return
            out2=Path(d)/'pdf'
            self.assertEqual(main(['analyze',str(bag),'--output',str(out2),'--pdf']),0)
            self.assertTrue((out2/'report.pdf').exists())
            try:
                from pypdf import PdfReader
            except ImportError:
                return
            pages=' '.join(p.extract_text() or '' for p in PdfReader(out2/'report.pdf').pages)
            self.assertIn('Observed sensor changes around logged states',pages)

    def test_chart_marks_logged_states_separately_from_finding(self):
        from robot_incident_analyzer.incident_workbench import workbench_script
        js=workbench_script()
        self.assertIn('Logged state: ',js)
        self.assertIn('Teal dashed: recorded state transition',js)
        self.assertIn("stroke:'#ffb264'",js)

    def test_html_uses_safe_dom_text(self):
        sc=compare_script()
        self.assertIn('textContent',sc)
        self.assertNotIn('innerHTML',sc)


if __name__ == '__main__':
    unittest.main()
