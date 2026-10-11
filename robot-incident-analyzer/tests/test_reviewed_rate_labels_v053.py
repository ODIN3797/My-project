"""All labels in this suite are fictional and do not claim any field accuracy."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from robot_incident_analyzer.label_evaluation import evaluate_labels, make_template, render_html, write_evaluation
from robot_incident_analyzer.rate_timeline import inspect_bag
from tests.test_rate_timeline_v052 import fixture, NS


class ReviewedRateLabelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rate = inspect_bag(fixture(self.root), self.root/'rate')
        self.topic = next(t for t in self.rate['topics'] if t['topic']=='/robot/cmd_vel')
        self.episode = self.topic['episodes'][0]
        self.origin = self.topic['window_origin_ns']
        self.start = self.origin + NS*2
        self.end = self.origin + NS*(len(self.topic['count_by_second'])-1)
        self.labels = make_template(self.rate, '/robot/cmd_vel')
        self.labels.update(reviewer='fictional-fixture-author',ground_truth_status='reviewed',
            positive_intervals=[{'start_ns': self.episode['start_ns'], 'end_ns': self.episode['end_ns']}],
            negative_intervals=[{'start_ns':self.start,'end_ns':self.episode['start_ns']}])

    def test_positive_detection_and_negative_coverage(self):
        got = evaluate_labels(self.rate, self.labels)
        self.assertEqual(got['positive_recall'],1)
        self.assertEqual(got['false_alarm_count'],0)
        self.assertEqual(got['false_alarms_per_hour'],0)
        self.assertEqual(got['detection_delay_median_seconds'],0)
        self.assertGreater(got['negative_reviewed_seconds'],0)

    def test_no_annotation_or_review_rejected(self):
        t = make_template(self.rate, '/robot/cmd_vel')
        self.assertEqual(t['ground_truth_status'],'unreviewed')
        with self.assertRaisesRegex(ValueError,'reviewed status'):
            evaluate_labels(self.rate,t)
        t['ground_truth_status']='reviewed';t['reviewer']='Test author'
        with self.assertRaisesRegex(ValueError,'No reviewed'):
            evaluate_labels(self.rate,t)

    def test_wrong_hash_and_topic_rejected(self):
        self.labels['recording_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            evaluate_labels(self.rate,self.labels)
        self.labels['recording_sha256']=self.rate['recording']['sha256']
        self.labels['topic']='/wrong'
        with self.assertRaisesRegex(ValueError,'topic/type'):
            evaluate_labels(self.rate,self.labels)

    def test_reviewed_negative_only_no_detection(self):
        self.labels['positive_intervals']=[]
        got=evaluate_labels(self.rate,self.labels)
        self.assertIsNone(got['positive_recall'])
        self.assertEqual(got['false_alarm_count'],0)
        self.assertEqual(got['false_alarms_per_hour'],0)

    def test_missed_label_and_unreviewed_detection(self):
        self.labels['positive_intervals']=[{'start_ns':self.start,'end_ns':self.start+NS}]
        self.labels['negative_intervals']=[]
        got=evaluate_labels(self.rate,self.labels)
        self.assertEqual(got['positive_recall'],0)
        self.assertEqual(got['missed_positives'],1)
        self.assertIsNone(got['false_alarms_per_hour'])
        self.assertEqual(got['unscored_prediction_count'],1)

    def test_unreviewed_prediction_is_not_false_alarm(self):
        self.labels['positive_intervals']=[]
        self.labels['negative_intervals']=[{'start_ns':self.start,'end_ns':self.start+NS}]
        got=evaluate_labels(self.rate,self.labels)
        self.assertEqual(got['false_alarm_count'],0)
        self.assertEqual(got['unscored_prediction_count'],1)

    def test_false_alarms_only_wholly_covered(self):
        self.labels['positive_intervals']=[]
        self.labels['negative_intervals']=[{'start_ns':self.episode['start_ns'],'end_ns':self.episode['end_ns']}]
        got=evaluate_labels(self.rate,self.labels)
        self.assertEqual(got['false_alarm_count'],1)
        self.assertGreater(got['false_alarms_per_hour'],0)

    def test_partial_overlap_pred_not_counted_false_alarm(self):
        self.labels['positive_intervals']=[]
        self.labels['negative_intervals']=[{'start_ns':self.episode['start_ns']+NS,'end_ns':self.episode['end_ns']}]
        got=evaluate_labels(self.rate,self.labels)
        self.assertEqual(got['false_alarm_count'],0)
        self.assertEqual(got['unscored_prediction_count'],1)

    def test_overlap_pos_and_negative_rejected(self):
        self.labels['negative_intervals']=[{'start_ns':self.episode['start_ns'],'end_ns':self.episode['end_ns']}]
        with self.assertRaisesRegex(ValueError,'must not overlap'):
            evaluate_labels(self.rate,self.labels)

    def test_outside_coverage_rejected(self):
        self.labels['positive_intervals']=[{'start_ns':self.episode['start_ns'],'end_ns':self.end+NS}]
        with self.assertRaisesRegex(ValueError,'outside complete'):
            evaluate_labels(self.rate,self.labels)

    def test_partial_histogram_rejected(self):
        self.topic['status']='PARTIAL_WINDOW_COVERAGE'
        with self.assertRaisesRegex(ValueError,'incomplete'):
            evaluate_labels(self.rate,self.labels)

    def test_bool_nan_numeric_rejected(self):
        self.labels['positive_intervals']=[{'start_ns':True,'end_ns':self.episode['end_ns']}]
        with self.assertRaisesRegex(ValueError,'integer Unix'):
            evaluate_labels(self.rate,self.labels)

    def test_duplicate_predictions_one_label(self):
        self.topic['episodes'].append(dict(self.episode))
        got=evaluate_labels(self.rate,self.labels)
        self.assertEqual(got['detected_positives'],1)
        self.assertEqual(got['unscored_prediction_count'],1)
        self.assertEqual(got['false_alarm_count'],0)

    def test_one_prediction_two_disjoint_positives(self):
        a=self.episode['start_ns'];b=self.episode['end_ns']
        self.labels['positive_intervals']=[{'start_ns':a,'end_ns':a+NS},{'start_ns':a+NS,'end_ns':b}]
        got=evaluate_labels(self.rate,self.labels)
        self.assertEqual(got['detected_positives'],1)
        self.assertEqual(got['missed_positives'],1)

    def test_html_escapes_reviewer(self):
        self.labels['reviewer']='<img src=x onerror=alert(1)>'
        html=render_html(evaluate_labels(self.rate,self.labels))
        self.assertNotIn('<img src=x',html)
        self.assertIn('&lt;img src',html)

    def test_output_file_roundtrip(self):
        labels_path=self.root/'labels.json';labels_path.write_text(json.dumps(self.labels))
        r=write_evaluation(self.root/'rate/rate_timeline.json',labels_path,self.root/'eval')
        self.assertEqual(r['positive_recall'],1)
        self.assertTrue((self.root/'eval/evaluation.html').is_file())

    def test_cli_e2e_and_unreviewed_exit(self):
        import subprocess,sys
        path=self.root/'labels.json'
        init=subprocess.run([sys.executable,'-m','robot_incident_analyzer','init-rate-labels',
            str(self.root/'rate/rate_timeline.json'),'--topic','/robot/cmd_vel','--output',str(path)],capture_output=True,text=True)
        self.assertEqual(init.returncode,0,init.stderr)
        fail=subprocess.run([sys.executable,'-m','robot_incident_analyzer','score-rate-labels',
            str(self.root/'rate/rate_timeline.json'),str(path),'--output',str(self.root/'fail')],capture_output=True,text=True)
        self.assertEqual(fail.returncode,2)
        self.assertFalse((self.root/'fail/evaluation.json').exists())
        path.write_text(json.dumps(self.labels))
        result=subprocess.run([sys.executable,'-m','robot_incident_analyzer','score-rate-labels',
            str(self.root/'rate/rate_timeline.json'),str(path),'--output',str(self.root/'scored')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.root/'scored/evaluation.json').exists())

if __name__=='__main__': unittest.main()

class AnnotationUITests(unittest.TestCase):
    def test_generated_html_uses_exact_int64_timestamps_and_no_remote_assets(self):
        from robot_incident_analyzer.review_ui import render_review_ui
        with tempfile.TemporaryDirectory() as tmp:
            r=inspect_bag(fixture(Path(tmp)),Path(tmp)/'rates')
            t=make_template(r,'/robot/cmd_vel')
            html=render_review_ui(r,t)
            self.assertIn('"origin": "174',html)
            self.assertIn('BigInt(data.origin)',html)
            self.assertIn('ground_truth_status:ready',html)
            self.assertIn('reviewed',html)
            self.assertNotIn('<script src=',html)
            self.assertIn('hidden by default',html)

    def test_untrusted_topic_name_is_escaped_in_inline_json(self):
        from robot_incident_analyzer.review_ui import render_review_ui
        with tempfile.TemporaryDirectory() as tmp:
            r=inspect_bag(fixture(Path(tmp)),Path(tmp)/'rates')
            evil='</script><img src=x onerror=alert(1)>'
            t=make_template(r,'/robot/cmd_vel')
            t['topic']=evil
            r['topics'][0]['topic']=evil
            html=render_review_ui(r,t)
            self.assertNotIn('</script><img',html)
            self.assertIn('\\u003c',html)
