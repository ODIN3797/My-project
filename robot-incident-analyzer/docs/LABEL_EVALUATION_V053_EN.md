# Evaluate robot incident rate episodes with independently reviewed intervals

Robot Incident Analyzer v0.5.3 includes a reproducible, **offline** labeling and scoring pipeline limited to recorded per-topic message-rate episodes. It does **not** assess all robot faults or prove why a rate increased.

## Three-step workflow

```bash
python3 -m robot_incident_analyzer inspect-rates candidate.db3 \
  --reference normal.db3 --topic /robot/cmd_vel --output rate_report
python3 -m robot_incident_analyzer init-rate-labels \
  rate_report/rate_timeline.json --topic /robot/cmd_vel --output labels.json
# Open labels.html, inspect the original recording independently and export labels JSON.
python3 -m robot_incident_analyzer score-rate-labels \
  rate_report/rate_timeline.json labels.json --output evaluation
```

`init-rate-labels` always generates `UNREVIEWED` output. The local HTML label editor hides the analyzer predictions by default to help reduce confirmation bias. Users select complete one-second bins and mark **verified positive** or **explicitly inspected negative** time spans. Enter a reviewer identifier and affirm the reviewed status to export the reviewed labels.

`score-rate-labels` rejects labels that are unreviewed, hash-mismatched, from a different topic/type, overlapping, outside the complete histogram coverage, or otherwise malformed. It writes `evaluation.html` and `evaluation.json`.

## Interpreting the metrics

- **Labeled recall**: fraction of reviewed positive intervals overlapping a distinct predicted episode. One prediction cannot match two incidents.
- **False alarms per reviewed hour**: unmatched predictions *fully contained* in separately reviewed normal intervals, divided by the duration of those intervals. Unreviewed intervals are never assumed normal.
- **Detection delay**: relative start-time difference for an overlapping episode; positive difference means detected after the reviewer-marked onset. If prediction started earlier and continued into the reviewed incident, delay is bounded at zero; a signed start difference is also included.
- **Missing labels/coverage**: shown as `null` / “Not measured”, not a misleading zero. This evaluation does not provide precision over unlabeled recording periods.
- **Reviewer provenance**: reviewer IDs and `reviewed` status are operator declarations, not proof of independent expert review.

The time resolution is one-second histogram bins; unrecorded data, message drops, bursty legitimate workloads, different DDS settings and controller changes may affect message rates. Never equate a rate increase to a cybersecurity attack or physical robot defect without independent supporting evidence.

## Public vs synthetic evidence

The project contains a fully fictional labeled test case used to exercise scoring; any 100% recall obtained from that fixture is **not** product accuracy. The real published [Zenodo 17649537](https://zenodo.org/records/17649537) E1-1/E1-2 bags supply source-described *scenario classes*, but not independently verified exact onset times and exhaustively reviewed negative windows. Their annotation example remains **UNREVIEWED** and cannot legitimately produce field accuracy metrics yet.

## Practical study design

Recruit at least two independent engineers to annotate timestamped evidence while blinded to the tool's predictions. Establish an adjudicated consensus and compare both the time-binned detection outcomes and elapsed human investigation times against a control workflow (e.g., manual ROS2/Foxglove analysis). Separate physical AMR fault studies, synthetic test fixtures and simulated cyberattack recordings. Do not upload employer/customer logs without authorization.
