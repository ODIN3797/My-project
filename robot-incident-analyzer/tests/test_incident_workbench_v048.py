"""Incident evidence views use synthetic cases; not ground-truth diagnosis."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from robot_incident_analyzer.models import Event, Finding
from robot_incident_analyzer.incident_workbench import (priority, cases_from_findings,
    same_robot_topic, workbench_markup, workbench_script)
from robot_incident_analyzer.__main__ import analyze_files, main
from robot_incident_analyzer.fixture_studio import make_studio_demo


class IncidentWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.anchor=Event(timestamp=100,severity='ERROR',category='sensor',code='BATTERY_HEALTH_ABNORMAL',
                          message='Battery health',robot_id='robot_a',source='one.mcap',topic='/robot_a/battery',event_id='E1')
        self.foreign=Event(timestamp=100,severity='WARN',category='sensor',code='LASER_SCAN_ALL_NAN',
                           message='Laser',robot_id='robot_b',source='two.mcap',topic='/robot_b/scan',event_id='E2')
        self.finding=Finding('BATTERY_HEALTH_ABNORMAL','Battery status','HIGH','Battery observation',['Check BMS'],['E1'])
        self.detail={'source':'one.mcap','signals':[
            {'topic':'/robot_a/battery','field':'voltage (V)','samples':[(95,24.2),(100,23.9),(105,23.7)]},
            {'topic':'/robot_b/battery','field':'voltage (V)','samples':[(95,20.),(100,16.)]},
            {'topic':'/robot_a/cmd_vel','field':'linear.x (m/s)','samples':[(95,1.1),(101,0.3)]}
        ],'paths':[{'topic':'/robot_a/odom','frame':'odom','samples':[(99,1.,2.),(101,3.,4.)]},
                     {'topic':'/robot_b/odom','frame':'odom','samples':[(99,20.,20.)]}]}

    def test_finding_source_and_robot_namespace_isolation(self):
        cases=cases_from_findings([self.finding],[self.anchor,self.foreign],[self.detail,{'source':'two.mcap','signals':[{'topic':'/robot_b/battery','field':'voltage','samples':[(100,50)]}]}])
        self.assertEqual(len(cases),1)
        c=cases[0]
        self.assertEqual([e['id'] for e in c['events']],['E1'])
        self.assertEqual(len(c['signals']),2)
        self.assertEqual(len(c['paths']),1)
        self.assertTrue(all(x['topic'].startswith('/robot_a/') for x in c['signals']+c['paths']))

    def test_nearby_same_source_and_time_only(self):
        ok=Event(109,'INFO','x','CHARGING','observed',source='one.mcap',event_id='E3')
        far=Event(111,'ERROR','x','MOTOR','far',source='one.mcap',event_id='E4')
        out=cases_from_findings([self.finding],[self.anchor,ok,far],[self.detail])
        self.assertEqual({e['id'] for e in out[0]['events']},{'E1','E3'})

    def test_relevance_prefers_battery_metrics(self):
        c=cases_from_findings([self.finding],[self.anchor],[self.detail])[0]
        self.assertEqual(c['signals'][0]['topic'],'/robot_a/battery')
        self.assertGreater(priority('BATTERY_HEALTH_ABNORMAL','voltage (V)','/robot_a/battery'),priority('BATTERY_HEALTH_ABNORMAL','linear.x','/robot_a/cmd_vel'))

    def test_missing_evidence_does_not_invent_timestamp(self):
        missing=Finding('MISSING','No evidence','HIGH','Unknown',[],['ZZZ'])
        self.assertFalse(cases_from_findings([missing], [self.anchor], [self.detail]))
        self.assertIn('No evidence-linked findings',workbench_markup([missing],[self.anchor],[self.detail]))

    def test_markup_escapes_untrusted_code_and_message(self):
        evil='</script><img src=x onerror=alert(1)>'
        self.anchor.message=evil
        self.finding.title=evil
        markup=workbench_markup([self.finding],[self.anchor],[self.detail])
        self.assertNotIn(evil,markup)
        self.assertIn('\\u003c/script\\u003e',markup)
        self.assertIn('case-print',markup)

    def test_only_closest_samples_in_dossier(self):
        self.detail['signals'][0]['samples']=[(40,99),(99,20),(160,4)]
        c=cases_from_findings([self.finding],[self.anchor],[self.detail])[0]
        self.assertEqual(c['signals'][0]['samples'],[(99,20)])

    def test_script_safe_DOM_and_cursor_callback(self):
        js=workbench_script()
        self.assertIn('textContent',js)
        self.assertIn('window.__riaMoveCursor',js)
        self.assertNotIn('innerHTML',js)
        self.assertIn('Cannot locate event',js)

    def test_wrong_robot_rejected(self):
        self.assertFalse(same_robot_topic('/robot_b/odom','robot_a'))
        self.assertFalse(same_robot_topic('/robot2/odom','robot1'))
        self.assertTrue(same_robot_topic('/robot_a/odom','robot_a'))
        self.assertTrue(same_robot_topic('/odom','robot_a'))

    def test_end_to_end_dossier_and_pdf(self):
        try:import reportlab  # noqa: F401
        except ImportError:self.skipTest('Optional PDF package not installed')
        with tempfile.TemporaryDirectory() as tmp:
            bag=make_studio_demo(Path(tmp))
            output=Path(tmp)/'out'
            self.assertEqual(main(['analyze',str(bag),'--output',str(output),'--pdf']),0)
            h=(output/'report.html').read_text()
            self.assertIn('id="incident-workbench"',h)
            self.assertIn('data-inspect-case=',h)
            self.assertIn('data-event-inspect=',h)
            self.assertIn('id="case-select"',h)
            self.assertIn('incident-workbench',h)
            self.assertTrue((output/'report.pdf').read_bytes().startswith(b'%PDF-'))
            self.assertGreater((output/'report.pdf').stat().st_size,5000)
            self.assertEqual(json.loads((output/'report.json').read_text())['version'],'0.4.9')

    def test_optional_pdf_dependency_is_explained(self):
        from robot_incident_analyzer.pdf_export import export_pdf
        # Import is done inside the function: no dependency for normal HTML mode.
        self.assertTrue(callable(export_pdf))
