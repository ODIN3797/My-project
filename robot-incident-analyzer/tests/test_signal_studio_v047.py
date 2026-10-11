"""Signal Studio tests use synthetic ROS2 CDR data; not real-robot validation."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from robot_incident_analyzer.signal_studio import (SignalSampler, BoundedSamples,
    MAX_SAMPLES, escape_json, numeric_leaves, studio_markup, standard_fields)
from robot_incident_analyzer.fixture_studio import make_studio_demo
from robot_incident_analyzer.__main__ import analyze_files, load_config
from robot_incident_analyzer.fixture_custom import custom_records
from robot_incident_analyzer.fixture_v2 import make_mcap
from unittest.mock import patch


class SignalStudioV047Tests(unittest.TestCase):
    def test_downsampling_is_bounded_and_spans_recording(self):
        s=BoundedSamples()
        for i in range(20000):s.add(1700000000+i*.01,math.sin(i*.04))
        self.assertLessEqual(len(s.rows),MAX_SAMPLES)
        self.assertGreater(s.rows[-1][0]-s.rows[0][0],150)
        self.assertEqual(s.count,20000)
        self.assertGreater(s.stride,1)

    def test_non_finite_bool_and_arrays_excluded(self):
        v={'flag':True,'count':3,'nested':{'speed':.2,'bad':float('nan')},'arr':[2,3],'inf':float('inf')}
        self.assertEqual(numeric_leaves(v),{'count':3.0,'nested.speed':0.2})
        sampler=SignalSampler()
        sampler.add('/battery','x',1,{'bad':float('inf'),'valid':33.,'bo':False})
        self.assertEqual([a['field'] for a in sampler.result()['signals']],['valid'])

    def test_trajectories_separate_by_topic_and_frame(self):
        s=SignalSampler()
        s.position('/robot1/odom','odom',1,(1,2,0))
        s.position('/robot2/odom','odom',1,(1,9,0))
        s.position('/robot1/odom','map',1,(99,2,0))
        s.position('/robot1/odom','odom',2,(2,3,0))
        self.assertEqual(len(s.result()['paths']),3)
        self.assertEqual(s.result()['paths'][0]['recorded_count'],2)

    def test_xss_escape_in_json_script(self):
        evil='</script><img src=x onerror=alert(1)>&'
        blob=escape_json({'topic':evil})
        self.assertNotIn('</script>',blob)
        self.assertNotIn('<img',blob)
        self.assertEqual(json.loads(blob)['topic'],evil)
        h=studio_markup([{'source':evil,'signals':[{'topic':evil,'type':'x','field':'value','samples':[[1,3]]}], 'paths':[]}],[])
        self.assertNotIn(evil,h)
        self.assertIn('studio-signal-chart',h)

    def test_prepared_payload_does_not_copy_full_sensor_array(self):
        s=SignalSampler()
        s.add('/scan','sensor_msgs/msg/LaserScan',10,{'valid_return_ratio (%)':87.5,'NaN_ranges':0})
        payload=json.dumps(s.result())
        self.assertIn('valid_return_ratio',payload)
        self.assertNotIn('"ranges": [',payload)

    def test_empty_studio_is_safe(self):
        markup=studio_markup([],[])
        self.assertIn('studio-data',markup)
        self.assertIn('"signals":[]',markup)
        self.assertIn('"paths":[]',markup)

    def test_custom_role_free_schema_is_visualized_without_command_claim(self):
        root=Path(__file__).resolve().parents[1]
        cfg=load_config(root/'examples/config_custom.json')
        cfg.pop('custom_messages')
        cfg.pop('topics')
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'custom.mcap'
            with patch('robot_incident_analyzer.fixture_v2.message_records',return_value=custom_records()):
                make_mcap(f)
            ev,fi,stats,warn,files,details=analyze_files([f],Path(tmp)/'report',cfg)
            data=details[0]
            self.assertTrue(any(s['field']=='target.linear_x' for s in data['signals']))
            self.assertFalse(data['velocity_trace'])
            self.assertFalse(data['paths'])
            self.assertNotIn('command',data['discovery']['selected'])

    def test_wire_format_demo_end_to_end_html_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=make_studio_demo(Path(tmp))
            ev,fi,stats,warn,files,details=analyze_files([f],Path(tmp)/'output')
            self.assertEqual(len(stats),5)
            data=details[0]
            self.assertEqual(len(data['paths']),1)
            self.assertGreaterEqual(len(data['signals']),13)
            self.assertEqual(len(data['paths'][0]['samples']),75)
            self.assertEqual(data['discovery']['selected']['command'],'/robot_a/cmd_vel')
            self.assertIn('BATTERY_HEALTH_ABNORMAL', {e.code for e in ev})
            report=json.loads((Path(tmp)/'output/report.json').read_text())
            self.assertEqual(report['version'],'0.5.2')
            html=(Path(tmp)/'output/report.html').read_text()
            self.assertIn('id="studio-path-chart"',html)
            self.assertIn('id="studio-time"',html)
            self.assertIn('data-tmin=',html)
            self.assertIn('signal-studio',html.lower().replace('signal studio','signal-studio'))

    def test_cap_series_and_paths(self):
        s=SignalSampler()
        for i in range(200):
            s.add('/t'+str(i),'x',1,{'speed':i})
            s.position('/p'+str(i),'frame',1,(i,1))
        self.assertLessEqual(len(s.result()['signals']),72)
        self.assertLessEqual(len(s.result()['paths']),8)


if __name__ == '__main__': unittest.main()
