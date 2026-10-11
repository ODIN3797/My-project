import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from robot_incident_analyzer.bag_comparison import summarize_bag
from robot_incident_analyzer.rate_timeline import inspect_summary, inspect_bag, render_rate_html
from tests.test_multi_bag_v051 import makebag

NS=1_000_000_000

def msgs(start, width, hz):
    return [start*NS+int(i*NS/hz) for i in range(int(width*hz))]

def fixture(folder, *, baseline=False, constant_high=False):
    p=Path(folder)/('baseline.db3' if baseline else 'candidate.db3')
    cmd=msgs(1_740_000_010,18,20) if baseline else (
        msgs(1_740_000_010,18,165) if constant_high else
        msgs(1_740_000_010,11,20)+msgs(1_740_000_021,6,165)+msgs(1_740_000_027,3,20))
    scan=msgs(1_740_000_010,20,6)
    makebag(p,[('/robot/cmd_vel','geometry_msgs/msg/Twist',cmd),('/robot/scan','sensor_msgs/msg/LaserScan',scan)])
    return p

class RateTimelineTests(unittest.TestCase):
    def test_changepoint_without_reference_after_stable_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=fixture(tmp)
            report=inspect_bag(p,Path(tmp)/'out')
            self.assertEqual(report['episode_count'],1)
            ep=report['topics'][0]['episodes'][0]
            self.assertGreater(ep['peak_ratio'],7)
            self.assertGreaterEqual(ep['duration_s'],3)
            self.assertIn('rate_timeline.html',[p.name for p in (Path(tmp)/'out').iterdir()])
    def test_sustained_high_without_reference_is_not_claimed_bad(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=inspect_summary(summarize_bag(fixture(tmp,constant_high=True)))
            self.assertEqual(report['episode_count'],0)
    def test_reference_can_identify_sustained_high(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=fixture(tmp,baseline=True)
            other=fixture(tmp,constant_high=True)
            report=inspect_bag(other,Path(tmp)/'out',reference=base)
            self.assertEqual(report['episode_count'],1)
            self.assertGreater(report['topics'][0]['episodes'][0]['peak_ratio'],8)
    def test_expected_hz(self):
        with tempfile.TemporaryDirectory() as tmp:
            curr=fixture(tmp,constant_high=True)
            report=inspect_summary(summarize_bag(curr),expected_hz=20)
            self.assertEqual(report['episode_count'],1)
            self.assertEqual(report['topics'][0]['baseline_method'],'operator-expected Hz')
    def test_nonmatching_reference_never_falls_back_to_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'wrong.db3';makebag(base,[('/other','geometry_msgs/msg/Twist',msgs(1_740_000_010,18,20))])
            curr=fixture(tmp)
            report=inspect_summary(summarize_bag(curr),baseline=summarize_bag(base))
            self.assertEqual(report['episode_count'],0)
            self.assertEqual(report['topics'][0]['status'],'NO_COMPARABLE_REFERENCE')
    def test_partial_histogram_refuses_to_interpret(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'long.db3';makebag(p,[('/cmd_vel','geometry_msgs/msg/Twist', [1_740_000_000*NS+i*NS for i in range(1100)])])
            report=inspect_summary(summarize_bag(p),expected_hz=20)
            self.assertEqual(report['episode_count'],0)
            self.assertEqual(report['topics'][0]['status'],'PARTIAL_WINDOW_COVERAGE')
    def test_out_of_order_sqlite_timestamps_are_counted_accurately(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'ordered.db3';timestamps=msgs(1_740_000_010,10,20)
            makebag(p,[('/cmd_vel','geometry_msgs/msg/Twist',list(reversed(timestamps)))])
            result=summarize_bag(p)
            self.assertEqual(result['topics'][0]['peak_1s_count'],20)
            self.assertEqual(sum(result['topics'][0]['one_second_counts']),len(timestamps))
    def test_skips_first_and_last_partial_second(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'edges.db3';t=[1_740_000_010*NS+800_000_000+i*2_000_000 for i in range(100)]
            t+=msgs(1_740_000_011,6,20)
            makebag(p,[('/cmd_vel','geometry_msgs/msg/Twist',t)])
            result=inspect_summary(summarize_bag(p),expected_hz=20)
            self.assertEqual(result['episode_count'],0)
    def test_invalid_thresholds(self):
        with self.assertRaises(ValueError): inspect_summary({'topics':[]},ratio_threshold=1)
        with self.assertRaises(ValueError): inspect_summary({'topics':[]},expected_hz=float('nan'))
    def test_xss_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'inj.db3'
            evil='/x<script>alert(1)</script>/cmd_vel'
            makebag(p,[(evil,'geometry_msgs/msg/Twist',msgs(1_740_000_010,10,20))])
            report=inspect_summary(summarize_bag(p),topic=evil,expected_hz=20)
            html=render_rate_html(report)
            self.assertNotIn('<script>alert(1)',html)
            self.assertIn('&lt;script&gt;',html)
    def test_missing_exact_topic_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'not found'):
                inspect_summary(summarize_bag(fixture(tmp)),topic='/nonexistent')
    def test_one_second_counts_are_epoch_aligned(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'edges.db3'
            start=1_740_000_010*NS
            makebag(p,[('/cmd_vel','geometry_msgs/msg/Twist',[start+950_000_000,start+999_000_000,start+1_000_000_000])])
            row=summarize_bag(p)['topics'][0]
            self.assertEqual(row['one_second_counts'],[2,1])
            self.assertEqual(row['histogram_origin_ns'],start)

if __name__=='__main__':unittest.main()
