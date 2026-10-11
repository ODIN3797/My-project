import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from robot_incident_analyzer.bag_comparison import summarize_bag, compare_summaries, compare_bags, render_comparison_html


def makebag(path, streams):
    con=sqlite3.connect(path)
    con.executescript('CREATE TABLE topics (id INTEGER PRIMARY KEY,name TEXT,type TEXT,serialization_format TEXT,offered_qos_profiles TEXT); CREATE TABLE messages (id INTEGER PRIMARY KEY, topic_id INTEGER, timestamp INTEGER, data BLOB);')
    idx=0
    for tid, (name,typ,timestamps) in enumerate(streams,start=1):
        con.execute('INSERT INTO topics VALUES(?,?,?,"cdr","")',(tid,name,typ))
        for t in timestamps:
            idx+=1
            con.execute('INSERT INTO messages VALUES(?,?,?,?)',(idx,tid,t,b'\x00\x01\x00\x00'))
    con.commit();con.close()


class MultiBagTests(unittest.TestCase):
    def test_rate_spike_detected_vs_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'normal.db3',Path(tmp)/'attack.db3'
            start=1_725_555_555_000_000_000
            makebag(a,[('/mobile_base_controller/cmd_vel','geometry_msgs/msg/Twist',[start+i*50_000_000 for i in range(1000)])])
            makebag(b,[('/mobile_base_controller/cmd_vel','geometry_msgs/msg/Twist',[start+i*6_000_000 for i in range(1600)])])
            report=compare_bags(a,[b],Path(tmp)/'output')
            row=report['candidate_cases'][0]['topic_comparisons'][0]
            self.assertEqual(row['status'],'RATE_INCREASE')
            self.assertGreater(row['rate_ratio'],8.2)
            self.assertLess(row['rate_ratio'],8.5)
            self.assertEqual(report['candidate_cases'][0]['rate_increases'],1)
            self.assertIn('mobile_base_controller/cmd_vel',(Path(tmp)/'output'/'comparison.html').read_text())
            self.assertTrue((Path(tmp)/'output'/'comparison.json').exists())
            self.assertTrue((Path(tmp)/'output'/'COMPARISON.md').exists())

    def test_no_universal_rate_alarm_without_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'only.db3'
            makebag(p,[('/rate','std_msgs/msg/String',[i*2_000_000 for i in range(7000)])])
            result=summarize_bag(p)
            self.assertGreater(result['topics'][0]['mean_hz'],400)
            self.assertEqual(result['topic_count'],1)

    def test_missing_or_different_type_cannot_be_compared(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a.db3',Path(tmp)/'b.db3'
            makebag(a,[('/foo','std_msgs/msg/String',[i*50_000_000 for i in range(100)])])
            makebag(b,[('/foo','std_msgs/msg/Int32',[i*4_000_000 for i in range(1000)])])
            report=compare_bags(a,[b],Path(tmp)/'out')
            self.assertEqual(report['candidate_cases'][0]['rate_increases'],0)
            self.assertTrue(all(x['status']=='NOT_COMPARABLE' for x in report['candidate_cases'][0]['topic_comparisons']))

    def test_short_or_sparse_time_series_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a.db3',Path(tmp)/'b.db3'
            makebag(a,[('/fast','t',[0,0,0,0])])
            makebag(b,[('/fast','t',[i*2_000_000 for i in range(15)])])
            report=compare_bags(a,[b],Path(tmp)/'out')
            self.assertEqual(report['candidate_cases'][0]['topic_comparisons'][0]['status'],'INSUFFICIENT_DATA')

    def test_html_escape_untrusted_topic_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a.db3',Path(tmp)/'b.db3'
            evil='/foo<img src=x onerror=alert(1)>'
            makebag(a,[(evil,'typ',[i*50_000_000 for i in range(100)])])
            makebag(b,[(evil,'typ',[i*5_000_000 for i in range(1000)])])
            html=render_comparison_html(compare_bags(a,[b],Path(tmp)/'out'))
            self.assertNotIn('<img src=x',html)
            self.assertIn('&lt;img',html)

    def test_no_partial_compared_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.db3'
            makebag(p,[('/foo','x',[i*1_000_000 for i in range(10)])])
            with self.assertRaisesRegex(ValueError,'exceeds'):
                summarize_bag(p,max_messages=5)

    def test_multiple_candidates_and_low_frequency(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[Path(tmp)/f'{n}.db3' for n in ['base','candidate1','candidate2']]
            for p,mult in zip(files,[0.2,0.02,0.005]):
                makebag(p,[('/rare','t',[int(i*mult*1e9) for i in range(1000)])])
            r=compare_bags(files[0],files[1:],Path(tmp)/'out',min_baseline_hz=2, min_candidate_hz=10)
            self.assertEqual(len(r['candidate_cases']),2)
            self.assertEqual(r['candidate_cases'][0]['rate_increases'],1)
            self.assertEqual(r['candidate_cases'][1]['rate_increases'],1)

    def test_threshold_input(self):
        with self.assertRaisesRegex(ValueError,'threshold'):
            compare_summaries({},[{'topics':[]}],ratio_threshold=1)

    def test_mcap_supported(self):
        from robot_incident_analyzer.fixture_studio import make_studio_demo
        with tempfile.TemporaryDirectory() as tmp:
            p=make_studio_demo(Path(tmp))
            r=summarize_bag(p)
            self.assertGreater(r['message_count'],2)
            self.assertGreater(r['topic_count'],1)


if __name__=='__main__': unittest.main()
