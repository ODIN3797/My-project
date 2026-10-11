"""Synthetic ROS2 state history tests, not field-validated root cause."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from robot_incident_analyzer.models import Event,Finding
from robot_incident_analyzer.state_timeline import (
    state_tokens, validate_state_keys, build_state_transitions,
    preceding_state_context, matching_transition, summarize_state_context, state_markup, state_script)
from robot_incident_analyzer.__main__ import main,load_config
from robot_incident_analyzer.incident_workbench import cases_from_findings
from robot_incident_analyzer.fixture_states import make_state_demo


def ev(t,msg,*,robot='robot_a',source='record.mcap',topic='/robot_a/rosout',eid='E1',category='rosout'):
    return Event(t,'INFO',category,'ROS_LOG',msg,robot_id=robot,source=source,topic=topic,event_id=eid)

class StateTimelineTests(unittest.TestCase):
    def test_explicit_assignment_not_free_language(self):
        self.assertEqual(state_tokens('we are docking and charging'), [])
        self.assertEqual(state_tokens('desired_mode=AUTO threshold:3'), [])
        self.assertEqual(state_tokens('mode=AUTONOMOUS; docking_state=ALIGN'),[('mode','AUTONOMOUS'),('docking_state','ALIGN')])

    def test_configured_custom_state_key(self):
        self.assertEqual(state_tokens('lift_state=UP state=IDLE', ['lift_state']), [('lift_state','UP')])
        self.assertEqual(state_tokens('lift_state=UP'), [])
        self.assertRaises(ValueError,validate_state_keys, ['state','state'])
        self.assertRaises(ValueError,validate_state_keys, ['.*'])
        self.assertRaises(ValueError,validate_state_keys, ['A'*300])

    def test_state_transitions_only_on_change(self):
        es=[ev(1,'mode=AUTO',eid='E1'),ev(2,'mode=AUTO',eid='E2'),ev(3,'mode=PAUSED',eid='E3')]
        out=build_state_transitions(es)
        self.assertEqual([(x['from'],x['to'],x['event_id']) for x in out],[(None,'AUTO','E1'),('AUTO','PAUSED','E3')])

    def test_distinct_robots_on_same_recording(self):
        es=[ev(1,'mode=AUTO',eid='E1'),ev(1.3,'mode=MANUAL',robot='robot_b',topic='/robot_b/rosout',eid='E2'),ev(2,'mode=PAUSED',eid='E3')]
        out=build_state_transitions(es)
        self.assertEqual(out[-1]['from'],'AUTO')
        self.assertFalse(matching_transition(out[1],es[-1]))
        self.assertEqual(len(preceding_state_context(es[-1],out)['transitions']),2)

    def test_csv_rows_same_source_but_distinct_files(self):
        a=ev(1,'mode=AUTONOMOUS',robot='unknown',source='run.csv:row2',topic='',eid='E1',category='navigation')
        b=ev(2,'mode=STOPPED',robot='unknown',source='run.csv:row3',topic='',eid='E2',category='navigation')
        foreign=ev(1.5,'mode=MANUAL',robot='unknown',source='else.csv:row2',topic='',eid='E3',category='navigation')
        transitions=build_state_transitions([a,b,foreign])
        mine=[x for x in transitions if x['source']=='run.csv']
        self.assertEqual(len(mine),2)
        self.assertEqual(mine[-1]['from'],'AUTONOMOUS')
        self.assertEqual(len(preceding_state_context(b,transitions)['transitions']),2)

    def test_analyzer_generated_events_not_reinterpreted_as_state(self):
        bad=ev(1,'mode=PAUSED',category='telemetry')
        self.assertEqual(build_state_transitions([bad]),[])

    def test_same_source_but_stale_transition_not_claimed(self):
        before=ev(1,'mode=IDLE',eid='E1')
        incident=ev(40,'Error',eid='E2')
        changes=build_state_transitions([before,incident])
        self.assertEqual(preceding_state_context(incident,changes)['transitions'],[])

    def test_untrusted_content_escaped_inside_script(self):
        source='</script><svg onload=alert(1)>'
        item=ev(1,'mode=PAUSED',source=source)
        markup=state_markup(build_state_transitions([item]))
        self.assertNotIn(source,markup)
        self.assertIn('\\u003c/script\\u003e',markup)
        self.assertIn('textContent',state_script())
        self.assertNotIn('innerHTML',state_script())

    def test_workbench_has_relevant_state_changes_only(self):
        e1=ev(1,'mode=AUTO',eid='E1')
        e2=ev(2,'mode=STOPPED',eid='E2')
        other=ev(2.1,'mode=MANUAL',eid='E3',robot='robot_b',topic='/robot_b/rosout')
        fail=Event(3,'ERROR','rosout','CHARGING','charger handshake timed out','robot_a','record.mcap','/robot_a/rosout','E4')
        finding=Finding('CHARGING','Charge failed','HIGH','observed',[],['E4'])
        cases=cases_from_findings([finding],[e1,e2,other,fail],[],state_transitions=build_state_transitions([e1,e2,other,fail]))
        self.assertEqual([x['to'] for x in cases[0]['state_context']['transitions']],['AUTO','STOPPED'])
        self.assertEqual({e['id'] for e in cases[0]['events']},{'E1','E2','E4'})

    def test_synthetic_mcap_end_to_end_and_printable_state_context(self):
        with tempfile.TemporaryDirectory() as d:
            path=make_state_demo(Path(d))
            out=Path(d)/'out'
            self.assertEqual(main(['analyze',str(path),'--output',str(out)]),0)
            j=json.loads((out/'report.json').read_text())
            self.assertEqual(j['version'],'0.5.0')
            self.assertIn('charging_state', {c['field'] for c in j['state_transitions']})
            self.assertEqual(len([x for x in j['state_transitions'] if x['robot_id']=='robot_b']),2)
            html=(out/'report.html').read_text()
            self.assertIn('id="state-timeline"',html)
            self.assertIn('id="case-states"',html)
            self.assertIn('state-transitions-data',html)
            self.assertNotIn('<script src=',html)
            self.assertGreater(len(j['events']),3)

    def test_configuration_state_keys_and_invalid_config(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=Path(d)/'config.json';cfg.write_text('{"state_keys":["lift_state"]}')
            self.assertEqual(load_config(cfg)['state_keys'],['lift_state'])
            cfg.write_text('{"state_keys":["[evil]"]}')
            with self.assertRaises(ValueError):load_config(cfg)

    def test_summary_is_explicit_without_causal_claim(self):
        es=[ev(1,'docking_state=APPROACH',eid='E1'),ev(2,'docking_state=ALIGN',eid='E2')]
        summary=summarize_state_context(preceding_state_context(ev(3,'error',eid='E3'),build_state_transitions(es)))
        self.assertIn('APPROACH -> ALIGN',summary)
        self.assertNotIn('caused',summary.lower())
        self.assertIn('No explicit state changes',summarize_state_context({'transitions':[]}))

    def test_transition_limit_bounded_for_html(self):
        all_events=[ev(i,f'mode=MODE_{i}',eid=f'E{i}') for i in range(600)]
        self.assertLessEqual(len(build_state_transitions(all_events)),500)

    def test_unknown_state_key_is_not_autodiscovered(self):
        self.assertEqual(state_tokens('battery=0.4 speed=1.0 error=true'),[])

    def test_optional_pdf_includes_state_chronology(self):
        try:from reportlab.pdfgen import canvas
        except ImportError:self.skipTest('PDF optional dependency unavailable')
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as d:
            bag=make_state_demo(Path(d))
            out=Path(d)/'out'
            self.assertEqual(main(['analyze',str(bag),'--output',str(out),'--pdf']),0)
            content=' '.join(page.extract_text() or '' for page in PdfReader(out/'report.pdf').pages)
            self.assertIn('Observed robot state transitions',content)
            self.assertIn('docking_state',content)
            self.assertIn('HANDSHAKE',content)

if __name__=='__main__':unittest.main()
