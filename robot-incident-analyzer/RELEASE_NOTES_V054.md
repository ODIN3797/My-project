# v0.5.4 — MAVROS/sonar decode + independent reviewer disagreement

- Standard ROS2 CDR decoding for `mavros_msgs/msg/State`, `ExtendedState`, `StatusText` and `sensor_msgs/msg/Range`, using official ROS2 message definitions.
- Mode/armed/connection changes and FCU status text appear as **publisher-origin evidence**, never verified failure causes; numeric fields are selectable in offline Signal Studio.
- REP-117 Range +Infinity/-Infinity remain valid no-return/fixed-distance indications, not hardware failure alarms.
- `compare-reviewers` compares two separately named, explicitly reviewed JSON annotations, requires same bag SHA256/topic/type, and reports time-weighted agreement, Cohen kappa, disagreement intervals and single-reviewer coverage. No auto-consensus.
- Real Zenodo sonar bag compatibility probe downloads independent source bytes **only in GitHub Actions**; original ROS bag files never added to the repository.
- 189 automated tests pass locally including CDR, ROS2 DB3 and MCAP, reviewer validation and CLI outputs.
- No independent real-robot fault ground truth, reviewed field incidents or calibrated accuracy claimed.

- ROS2 `sensor_msgs/Range` has a **schema-version difference**: Foxy/Humble terminate after `range`, while Jazzy/Rolling add `variance`. v0.5.4 accepts exactly these two recognized CDR layouts without inventing a variance value.
