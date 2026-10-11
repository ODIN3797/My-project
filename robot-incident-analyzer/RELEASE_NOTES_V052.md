# v0.5.2 — Time-localized ROS2 command message-rate investigation

This experimental release adds `inspect-rates` to locate **sustained increases in recorded message density** inside one `.db3` or `.mcap` recording. It also corrects epoch-second histogram accounting for out-of-order messages, avoids first/last partial-second interpretation and refuses >1,000-second incomplete histogram coverage instead of claiming a full-recording diagnosis.

## Examples

```bash
python3 -m robot_incident_analyzer inspect-rates attack.db3 \
  --reference reference.db3 --topic /mobile_base_controller/cmd_vel \
  --ratio-threshold 3 --min-consecutive 2 --output inspection
xdg-open inspection/rate_timeline.html
```

```bash
# Without a separate reference: detect only changes after an observed stable
# local history. This will not flag a recording that is high-rate throughout.
python3 -m robot_incident_analyzer inspect-rates mixed.db3 --output inspection

# Or use an explicitly operator-chosen expected receive rate.
python3 -m robot_incident_analyzer inspect-rates candidate.mcap \
  --expected-hz 20 --topic /robot/cmd_vel --output inspection
```

- Configurable thresholds: ratio (default 3), messages/second (10), consecutive full 1s windows (2).
- Normalization: absolute 1-second bag timestamp buckets; exclude partial start and end windows; calculate reference using matching **topic and message type**, not an unrelated stream.
- Conservative auto topic selection: only conventional `cmd_vel`-like names, unless explicit `--topic` requested.
- Data privacy: no network dependency. JSON/HTML outputs contain topic names and timestamp evidence but not ROS2 message body bytes.
- Independent real recorded E1-1/E1-2 Zenodo validation source: https://zenodo.org/records/17649537; published 500Hz attack input does NOT establish the actual downstream recorded rate.

**Not supported:** no automatic attribution to attack, motor fault, network fault or lost control. A recording with no accepted episode has not been certified healthy. Full physical field-fault precision and false-alerts/hour are still unmeasured. Odom 'jump' candidates may reflect legitimate motion above an absolute 1m/0.5s threshold; human review is required.

## v0.5.2 follow-up: Odometry plausibility

`ODOM_POSITION_JUMP` now checks displacement speed against the maximum magnitude of **consecutive** reported Odometry twist velocities (factor 1.5 plus margin 0.2m/s) before emitting this specific candidate. Purely fast robot motion should not automatically be called a position jump. If velocity is unavailable, invalid or inconsistent, the candidate remains. This heuristic can miss real localization errors if twist is simultaneously wrong; it is not a safety or cause determination algorithm. See `docs/RATE_EPISODES_V052_EN.md`.
