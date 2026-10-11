"""Field-pilot regression tests; all fixtures are independently generated synthetic data."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from robot_incident_analyzer.field_validation import analyze_field_cases, load_labels, match_labels
from robot_incident_analyzer.fixture_v2 import make_mcap, message_records
from robot_incident_analyzer.models import Event


class FieldValidationTests(unittest.TestCase):
    def test_demo_bag_has_report_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bag=make_mcap(root/'generated.mcap')
            result=analyze_field_cases([bag], root/'result', origin='synthetic')
            case=result['cases'][0]
            self.assertEqual(result['recording_count'],1)
            self.assertEqual(case['provenance'],'synthetic')
            self.assertEqual(len(case['sha256']),64)
            self.assertGreater(case['topic_count'],0)
            self.assertTrue((root/'result/case_01/report.html').is_file())
            self.assertTrue((root/'result/FIELD_RESULTS.md').is_file())
            self.assertFalse(result['actual_engineer_review_completed'])
            self.assertFalse(result['ground_truth_validated'])

    def test_unreadable_non_bag_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            p=root/'test.txt'; p.write_text('not a bag')
            with self.assertRaisesRegex(ValueError,'accepts only'):
                analyze_field_cases([p],root/'out')

    def test_bad_origin_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                analyze_field_cases([Path(d)/'foo.mcap'], Path(d)/'out',origin='real')

    def test_empty_labels_do_not_claim_precision(self):
        result=match_labels([],[])
        self.assertIsNone(result['labelled_recall'])
        self.assertIsNone(result['precision'])
        self.assertIsNone(result['false_positive_rate'])

    def test_labels_detect_exact_time_and_code(self):
        events=[Event(100.1,'WARN','telemetry','TOPIC_GAP','gap',event_id='E0001'),
                Event(101,'ERROR','telemetry','TF_MAP_ODOM_JUMP','jump',event_id='E0002')]
        labels=[dict(time_epoch=100,code='TOPIC_GAP',tolerance_s=.2),
                dict(time_epoch=102,code='TF_MAP_ODOM_JUMP',tolerance_s=.1)]
        result=match_labels(events,labels)
        self.assertEqual(result['labelled_recall'],.5)
        self.assertEqual(result['detected_labelled_events'],1)
        self.assertIsNone(result['precision'])

    def test_each_event_cannot_satisfy_multiple_labels(self):
        event=[Event(100,'WARN','telemetry','TOPIC_GAP','x',event_id='E0001')]
        labels=[dict(time_epoch=100,code='TOPIC_GAP',tolerance_s=1) for _ in range(2)]
        self.assertEqual(match_labels(event,labels)['detected_labelled_events'],1)

    def test_csv_rejects_negative_tolerance(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'labels.csv'
            p.write_text('case_id,code,time_epoch,tolerance_s\ncase_01,TOPIC_GAP,100,-2\n')
            with self.assertRaisesRegex(ValueError,'invalid'):
                load_labels(p)

    def test_partial_message_budget_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); bag=make_mcap(root/'generated.mcap')
            result=analyze_field_cases([bag],root/'result', origin='synthetic',max_messages=3)
            case=result['cases'][0]
            self.assertEqual(case['status'],'REVIEW_REQUIRED')
            self.assertIn('incomplete_or_ambiguous_analysis',case['review_flags'])

    def test_unsupported_payloads_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            raw = message_records() + [('/camera/raw','sensor_msgs/msg/Image',1791633600000000000,b'XXXX')]
            with patch('robot_incident_analyzer.fixture_v2.message_records',return_value=raw):
                bag=make_mcap(root/'mixed.mcap')
            result=analyze_field_cases([bag],root/'result',origin='synthetic')
            self.assertIn('incomplete_or_ambiguous_analysis',result['cases'][0]['review_flags'])

    def test_unreadable_compressed_chunk_is_review_required(self):
        from robot_incident_analyzer.fixture_v2 import mcap_record, field
        import struct
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            # MCAP header + deliberately unavailable/invalid zstd chunk.
            chunk=(struct.pack('<QQQI',0,0,8,0) + field('zstd') +
                   struct.pack('<Q',3) + b'bad')
            blob=(b'\x89MCAP0\r\n' +
                  mcap_record(0x01,field('ros2')+field('test')) +
                  mcap_record(0x06,chunk) +
                  mcap_record(0x02,struct.pack('<QQI',0,0,0)) + b'\x89MCAP0\r\n')
            bag=root/'compressed.mcap';bag.write_bytes(blob)
            # In an environment with zstandard installed invalid compressed data raises;
            # in an environment without it must flag partial coverage rather than claim success.
            try:
                result=analyze_field_cases([bag],root/'out')
            except Exception as exc:
                self.assertIn('zstd',str(exc).lower())
            else:
                case=result['cases'][0]
                self.assertEqual(case['status'],'REVIEW_REQUIRED')
                self.assertIn('no_topics_read',case['review_flags'])

    def test_cli_run_marks_synthetic(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); bag=make_mcap(root/'demo.mcap')
            run=subprocess.run([sys.executable,'-m','robot_incident_analyzer',
                                'field-validate',str(bag),'--output',str(root/'out'),
                                '--origin','synthetic'],capture_output=True,text=True)
            self.assertIn(run.returncode,(0,3),run.stderr)
            self.assertIn('recording(s)',run.stdout)
            self.assertEqual(json.loads((root/'out/field_results.json').read_text())['origin_declared_by_operator'],'synthetic')


if __name__=='__main__': unittest.main()
