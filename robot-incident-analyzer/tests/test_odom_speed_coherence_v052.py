import unittest
from robot_incident_analyzer.telemetry import TelemetryAnalyzer
from robot_incident_analyzer.fixture_v2 import odom_payload, BASE

class OdomSpeedConsistencyTests(unittest.TestCase):
    def _events(self, rows, thresholds=None):
        a=TelemetryAnalyzer('mock.db3',thresholds=thresholds)
        for t,pos,spd in rows:
            a.ingest('/robot/odom','nav_msgs/msg/Odometry',t,odom_payload(t,pos,spd))
        return [e for e in a.events if e.code=='ODOM_POSITION_JUMP']

    def test_legitimate_fast_translation_not_called_jump(self):
        self.assertEqual(self._events([(BASE,0,2.0),(BASE+.497,1.04,2.1)]),[])

    def test_implausible_translation_retains_candidate(self):
        es=self._events([(BASE,0,0.1),(BASE+.497,1.04,0.1)])
        self.assertEqual(len(es),1)
        self.assertIn('not corroborated',es[0].message)

    def test_missing_linear_feedback_does_not_suppress(self):
        # Nonfinite speed fields cannot support a claim of coherent displacement.
        es=self._events([(BASE,0,float('nan')),(BASE+.497,1.04,float('nan'))])
        self.assertEqual(len(es),1)

    def test_user_threshold_more_strict(self):
        es=self._events([(BASE,0,1.6),(BASE+.497,1.04,1.6)],
                        thresholds={'odom_speed_consistency_factor':1.05})
        self.assertEqual(len(es),1)

if __name__=='__main__':unittest.main()
