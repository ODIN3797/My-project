from __future__ import annotations
import unittest
from robot_incident_analyzer.analysis import build_findings
from robot_incident_analyzer.models import Event


def log_event(ts: float, message: str, severity: str = "WARN") -> Event:
    return Event(timestamp=ts, severity=severity, category="rosout", code="ROS_LOG",
                 message=message, source="public_sample.mcap", event_id=f"E{ts:g}")


class RosoutRecurrenceTests(unittest.TestCase):
    def test_unrelated_warnings_are_not_classified_as_repeated_alert(self):
        data = [log_event(1, "[perception] Person detected 3.1 m ahead, slowing down"),
                log_event(11, "[power] Battery at 20%, returning is now a priority"),
                log_event(21, "[docking] Dock beacon not visible, falling back to odometry")]
        findings = build_findings(data)
        self.assertNotIn("RECURRING_ALERT", [f.code for f in findings])

    def test_near_identical_rosout_warnings_are_classified_as_repeats(self):
        data = [log_event(1, "[perception] Person detected 3.1 m ahead, slowing down"),
                log_event(11, "[perception] Person detected 3.0 m ahead, slowing down"),
                log_event(21, "[perception] Person detected 2.8 m ahead, slowing down")]
        findings = build_findings(data)
        self.assertEqual(sum(f.code == "RECURRING_ALERT" for f in findings), 1)
        self.assertEqual(next(f for f in findings if f.code=="RECURRING_ALERT").evidence_ids, [e.event_id for e in data])

    def test_normalized_messages_remain_independent_of_other_error_codes(self):
        data = [Event(timestamp=i, severity="ERROR", category="robot", code="TIMEOUT",
                      message=f"Timeout on channel {i}", robot_id="robot1", source="a", event_id=f"E{i}")
                for i in (1, 4, 7)]
        findings = build_findings(data)
        self.assertIn("RECURRING_ALERT", [f.code for f in findings])


if __name__ == "__main__":
    unittest.main()
