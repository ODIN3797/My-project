# v0.5.4: MAVROS telemetry + blind dual-reviewer workflow

Four added standard ROS2 message types: `mavros_msgs/msg/State`, `mavros_msgs/msg/ExtendedState`, `mavros_msgs/msg/StatusText`, `sensor_msgs/msg/Range`. The last implements REP-117 sentinel semantics: finite distances become graph series, +/-Infinity remain intentional no-return indications, not hardware faults. All MAVROS state transitions and STATUSTEXT severities are publisher assertions, not root-cause proof. Custom MAVROS messages remain unsupported unless separately supplied through the generic custom-schema system.

## Dual reviewer operation

Two people independently mark positive incidents and explicitly reviewed normal intervals with the v0.5.3 editor. Share **only annotations** and an identical rate timeline; do not share proprietary raw logs without permission.

```bash
python3 -m robot_incident_analyzer compare-reviewers rates/rate_timeline.json reviewer_A.json reviewer_B.json --output review_comparison
```

Outputs: `reviewer_comparison.json`, `reviewer_comparison.html`. Exact recording SHA-256/topic/type, distinct reviewers and reviewed status are mandatory. Time-weighted agreement and Cohen kappa are calculated **only on the intersection of reviewed coverage**; kappa is undefined when no agreement statistics can be computed. Disagreements appear as nanosecond-exact intervals for human adjudication; the command never creates a consensus ground truth label.

`validation/v054_evidence` contains **fictional reviewer labels** used solely for implementation testing. No real incident recall/precision or field-engineer agreement results are available yet.
