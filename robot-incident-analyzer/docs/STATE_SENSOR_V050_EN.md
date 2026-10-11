# Investigating sensor readings around logged state changes

## Quick start

```bash
python3 -m robot_incident_analyzer demo-states --output demo_states
python3 -m robot_incident_analyzer analyze \
  demo_states/fictional_state_transitions.mcap \
  --output report_v050
xdg-open report_v050/report.html
```

Open **Incident workbench**, choose a finding, and look at the **Telemetry before / after logged state transitions** panel, above the familiar contextual signal plots.

When a state observation is present in the preceding 30 seconds, the tool compares nearby finite numeric observations from matching source-scoped ROS2 topics. It uses two nonoverlapping 2-second windows: `[transition−2s, transition)` and `[transition, transition+2s)`. Each side requires at least two distinct finite timestamps; the nearest point must not be farther than 1 second from the transition. Otherwise the result says data are insufficient. Do not interpret "insufficient" as "unchanged".

Recorded transitions are **not** a verified controller state machine. A log saying `docking_state=CONTACT` does not prove the robot physically contacted the dock. Timestamp alignment of voltage, speed, position and that log does **not** establish a root cause.

## Example comparison (fictional)

```text
mode: AUTONOMOUS → PAUSED
  /robot_a/cmd_vel linear.x (m/s): before median 0.480 / after median 0.480
  /robot_a/odom    linear.x (m/s): before median 0.480 / after median 0.000
```

The precise numbers depend on the sample time and the chosen state. These are intentionally invented ROS2 recordings, **not** findings on a physical robot. A difference in commanded and observed velocity may be legitimate, so review safety status, operator commands, timestamps and full raw samples.

## Export and API

- `report.html`: searchable incident review, state change markers (teal), findings (orange), and numeric comparisons.
- `report.json`: `state_sensor_comparisons`, each with case ID, source, robot ID, literal summary and individual transition comparisons (`status`, `signals`, `before`, `after`, `delta`, `before_n`, `after_n`, gap metadata).
- Optional `--pdf`: limited print-friendly comparison extracts. `pip install '.[pdf]'` first; the JSON retains the full bounded comparison data.

## Safety / privacy

Source and named robot namespaces must match. Missing topics, message types or sensor periods are surfaced as incomplete coverage, not as a clean run. Do not ingest employer or customer data without explicit authorization. Review all HTML/PDF/JSON for private metadata before sharing.

## Planned validation

Evaluate at least three consented, engineer-labeled physical robot cases, estimate false-positive/false-negative counts, and time skilled engineers with/without the tool. Without this evidence, do not claim causal inference or commercial diagnostic readiness.
