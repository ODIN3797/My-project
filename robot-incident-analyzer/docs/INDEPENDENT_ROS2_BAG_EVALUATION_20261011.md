# External ROS2 bag validation: normal vs simulated DoS (2026-10-11)

Dataset: https://zenodo.org/records/17649537 (Experiment_1.zip).
Reproducible run: https://github.com/ODIN3797/My-project/actions/runs/38118352498
Independent ROS2 recordings, but physical-robot fault ground truth NOT established. E1-1 is publisher-labeled normal; E1-2 is publisher-labeled simulated DoS (500Hz messages injected to /input_joy/cmd_vel).

| Metric | E1-1 normal | E1-2 simulated attack |
|---|---:|---:|
| ROS2 messages | 7,120 | 10,355 |
| Topics | 8 | 7 |
| /mobile_base_controller/cmd_vel messages | 1,501 | 6,630 |
| Command-topic span | 75.57s | 40.13s |
| Mean command-topic recorded rate | 19.85Hz | 165.19Hz |
| Analyzer events | 3 | 1 |
| Findings incl. context | 4 | 1 |
| Review flag | REVIEW_REQUIRED | REVIEW_REQUIRED |

Measured downstream command-topic mean rate increased 8.32x. This is NOT the upstream injection frequency of 500Hz.
Normal events: CMD_ODOM_MISMATCH x1, ODOM_POSITION_JUMP x2. Attack events: CMD_ODOM_MISMATCH x1.

## Main product gap
v0.5.0 missed the unusually large downstream command message rate as a specific diagnostic, while producing more warnings on the normal recording. Warning counts cannot be used to classify these cases. Human inspection is required to establish which normal-case warnings are false positives.

## Sensor and ground-truth limitations
Unsupported payload types include sensor_msgs/msg/Range (both recordings) and sensor_msgs/msg/Image (normal only). No independently timestamped attack-onset annotations, exhaustive negative labels, or physical fault labels were validated. Precision, recall, false alarms/hour and root-cause accuracy remain unknown.

## Acceptance criteria for next release
1. Compare any two valid ROS2 recordings by matched topic/type and mean + 1s-window rates; normalize for their different capture durations.
2. Flag a configurable command-topic rate increase relative to user-provided baseline; do not enforce universal robot frequency expectations without context.
3. Audit source time alignment and odometry jump handling in the normal recording with a human reviewer.
4. Support sensor_msgs/msg/Range payloads where available.
5. Collect time-aligned labels and separately report detection latency, event recall and false alarms/hour.

## Provenance and reproducibility
The CI script downloads the published dataset and produces per-case HTML/JSON and COMPARISON.json. Original bag bytes are NOT uploaded to GitHub.
JKK Research Dataset 02 could not be verified because both official download URLs returned HTTP 404 in CI; that dataset has NOT been analyzed.
