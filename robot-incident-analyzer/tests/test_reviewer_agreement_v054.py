"""No ground truth metrics from unreviewed intervals or same-reviewer inputs."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from robot_incident_analyzer.review_agreement import compare_reviewers, write_reviewer_comparison
from robot_incident_analyzer.label_evaluation import make_template

ORIGIN=1_740_000_000_000_000_000
N=1_000_000_000

def data():
    return {'recording':{'sha256':'a'*64},'topics':[{'topic':'/robot/cmd_vel',
            'type':'geometry_msgs/msg/Twist', 'status':'NO_CONFIRMED_EPISODES',
            'window_origin_ns':ORIGIN,'first_complete_bin_index':1,
            'count_by_second':[20]*12,'episodes':[]}]}

def interval(start,end):return {'start_ns':ORIGIN+start*N,'end_ns':ORIGIN+end*N}

def annotations(reviewer,positives=(),negatives=()):
    d=make_template(data(),'/robot/cmd_vel')
    d.update(reviewer=reviewer,ground_truth_status='reviewed',
             positive_intervals=[interval(*v) for v in positives],
             negative_intervals=[interval(*v) for v in negatives])
    return d

class ReviewAgreementTests(unittest.TestCase):
    def test_perfect_agreement_and_kappa(self):
        a=annotations('A',[(4,7)],[(1,4),(7,10)])
        d=compare_reviewers(data(),a,annotations('B',[(4,7)],[(1,4),(7,10)]))
        self.assertEqual(d['jointly_reviewed_seconds'],9)
        self.assertEqual(d['agreement_fraction'],1)
        self.assertEqual(d['cohens_kappa'],1)
        self.assertFalse(d['disagreement_intervals'])

    def test_disagreement_and_overlap_only(self):
        a=annotations('A',[(4,7)],[(1,4),(7,9)])
        b=annotations('B',[(5,8)],[(1,5),(8,11)])
        d=compare_reviewers(data(),a,b)
        self.assertEqual(d['jointly_reviewed_seconds'],8)
        self.assertEqual(d['disagreement_seconds'],2)
        self.assertEqual(d['agreement_fraction'],0.75)
        self.assertEqual(d['single_reviewer_coverage_seconds'],2)
        self.assertEqual(d['disagreement_interval_count'],2)
        self.assertEqual(d['disagreement_intervals'][0]['start_ns'],ORIGIN+4*N)

    def test_disjoint_review_is_not_100_percent(self):
        d=compare_reviewers(data(),annotations('A',[(1,3)]),annotations('B',[(5,7)]))
        self.assertEqual(d['jointly_reviewed_seconds'],0)
        self.assertIsNone(d['agreement_fraction'])
        self.assertIsNone(d['cohens_kappa'])

    def test_one_category_kappa_undefined(self):
        d=compare_reviewers(data(),annotations('A',negatives=[(1,5)]),annotations('B',negatives=[(1,5)]))
        self.assertEqual(d['agreement_fraction'],1)
        self.assertIsNone(d['cohens_kappa'])

    def test_same_reviewer_rejected(self):
        with self.assertRaisesRegex(ValueError,'distinct'):
            compare_reviewers(data(),annotations('Analyst X',[(2,4)]),annotations('analyst x',[(2,4)]))

    def test_unreviewed_rejected(self):
        a=annotations('A',[(2,4)])
        b=annotations('B',[(2,4)]);b['ground_truth_status']='unreviewed'
        with self.assertRaisesRegex(ValueError,'reviewed'):
            compare_reviewers(data(),a,b)

    def test_bad_hash_rejected(self):
        b=annotations('B',[(2,4)]);b['recording_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            compare_reviewers(data(),annotations('A',[(2,4)]),b)

    def test_overlapping_annotations_rejected(self):
        b=annotations('B',[(2,4)],[(3,5)])
        with self.assertRaisesRegex(ValueError,'overlap'):
            compare_reviewers(data(),annotations('A',[(2,4)]),b)

    def test_html_and_json_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name, payload in [('rate',data()),('a',annotations('A <b>',[(2,4)])),('b',annotations('B',negatives=[(2,4)]))]:
                (root/f'{name}.json').write_text(json.dumps(payload))
            result=write_reviewer_comparison(root/'rate.json',root/'a.json',root/'b.json',root/'out')
            self.assertEqual(result['disagreement_interval_count'],1)
            html=(root/'out/reviewer_comparison.html').read_text()
            self.assertIn('A &lt;b&gt;',html)
            self.assertNotIn('A <b>',html)
            self.assertEqual(json.loads((root/'out/reviewer_comparison.json').read_text())['disagreement_seconds'],2)

if __name__=='__main__':unittest.main()
