# v0.5.2: Topic-rate episodes and odometry speed-coherence review

## One recording, known reference

```bash
python3 -m robot_incident_analyzer inspect-rates attack.db3 \
  --reference normal.db3 --topic /mobile_base_controller/cmd_vel \
  --ratio-threshold 3 --min-consecutive 2 --output rate_report
```

Open `rate_report/rate_timeline.html` and inspect `rate_report/rate_timeline.json` for recorded evidence timestamps, counts and a source SHA-256. **Do not claim a cyberattack just because a rate rises.** A healthy reference should represent the same task, robot, ROS interface and recording pipeline.

If you have no healthy bag, you can use `--expected-hz 20` *only if that expected logged rate is known and justified*. Without either source the tool requires a stable earlier eight-second topic window and may return no result for uniformly high-rate recordings.

All rates are based on epoch-aligned 1-second bag message-arrival count bins, excluding partial edge windows. A minimum two consecutive seconds must exceed both the ratio threshold (3x by default) and minimum 10 messages/sec. At most 1,000 seconds of rate histogram may be complete; longer topic histories are explicitly declined for localized inference rather than partially presented as complete.

## Independent experimental regression

Dataset: https://zenodo.org/records/17649537, normal bag E1-1 versus publisher-described simulated high-rate command injection E1-2. Previous recorded downstream cmd_vel topic means: 19.85Hz and 165.19Hz (8.32x). This is separate from the publisher's **500Hz upstream injection**. New v0.5.2 acceptance suite verifies the time-localized recorded message density against E1-1, plus a negative-control run with E1-1 compared to itself.

This is not an independent physical robot failure test. The published scenario is a simulated attack; the original experiment does not provide calibrated physical-fault onset labels.

## Odometry position delta refinement

Previously an absolute 1m position delta in <=0.5s always emitted an `ODOM_POSITION_JUMP` candidate. This can happen during legitimate 2+ m/s motion. v0.5.2 also considers finite, consecutive Odometry twist-speed magnitudes; if the measured translation is compatible within an adjustable `odom_speed_consistency_factor` margin (default 1.5, plus 0.2m/s tolerance), it avoids issuing that specific warning. If either velocity is unavailable or inconsistent, the candidate remains.

**Conservative caveat:** A misreported high twist velocity can mask a real position jump, and odometry velocity may have different semantics or time offsets. This is a *triage filter*, never a safety mechanism or certified fault detector. Verify sensor frame and ground-truth trajectory with an engineer. Unit tests cover plausible fast translation, implausible translation, nonfinite velocities and stricter overrides.

Vigo evidence (2024-06-14 recording 13:24:49) previously emitted three jump candidates: 1.04m/0.497s, 1.06m/0.497s and 1.15m/0.499s. `linear.x` around these times rose to approximately 1.75–2.54m/s. Re-run against the exact original bag to see whether the new speed-coherence filter suppresses them. A suppressed candidate is not proof that the localization was correct.

## Known limitations

- Downstream bag receive density differs from upstream publisher attempted frequency.
- Event bins do not prove fault onset; messages can be dropped before recording.
- Idle/active phases may vary naturally; compare like-for-like workloads.
- Recorded clock jumps, non-monotonic channels or missing metadata may affect results; inspect the source data.
- There is no exhaustively labeled ground-truth error-rate study or independent user trial.
