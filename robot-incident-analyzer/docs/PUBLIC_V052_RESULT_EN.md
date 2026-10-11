# v0.5.2 — 12 public ROS2 bag regression results (2026-10-11)

Reproducible CI: https://github.com/ODIN3797/My-project/actions/runs/38129129101
Original independent data: Zenodo 17649537 (2 ROS2 SQLite experiments), Zenodo 15433859 (9 Vigo navigation recordings), and BAGEL published example MCAP (1 sample; physical origin unconfirmed). No original bags distributed.

## E1-1 normal vs E1-2 publisher-described simulated attack

| Recorded metric | Result |
|---|---:|
| Normal downstream /mobile_base_controller/cmd_vel mean | 19.8495 Hz |
| Attack downstream same topic whole-bag mean | 165.1926 Hz |
| Whole-recording rate ratio | 8.3223x |
| v0.5.2 localized sustained rate episode count (attack, referenced to normal) | 1 |
| Episode length | 15 seconds |
| Messages in episode windows | 6,227 |
| Peak one-second receive count | 491 |
| Peak vs reference mean | 24.736x |
| Normal bag self-reference negative control episode count | 0 |

Detected episode recorded timestamp range: 1710160271000000000 ns to 1710160286000000000 ns.
Important: upstream *injection attempt* was described as 500Hz, whereas these are downstream **bag message recording** counts and times. Ground-truth attack onset timestamps were not available, so latency is **not measured**.

## Vigo 9 physical navigation bags

- Rule-derived event candidates dropped from 24 (v0.5.1) to 21 (v0.5.2) after an Odometry velocity-coherence check.
- Three former ODOM_POSITION_JUMP candidates at 1.04m/0.497s, 1.06m/0.497s, 1.15m/0.499s no longer appear, because fast translation was compatible with reported consecutive Odometry velocity magnitudes. This does NOT independently validate localization accuracy.
- No false automatic selection of GPS velocity as motor command (`/rpsc4/global_position/raw/gps_vel`).
- In the 8 reference comparisons there were **zero selected command-like topics**; therefore zero rate episodes is *not* a negative-control or zero-false-positive finding.

## Evidence and limitations

Independent public bags: 12/12 successfully downloaded and processed by the CLI workflow. 150 automated unit/integration cases and GitHub CI test matrix passed. Source bags remain absent from the repository and result archive. Root cause accuracy, fault precision/recall, time-to-detect and engineer time saving are NOT established. Time-coincident sensor changes do not prove causes. Do not use this experimental tool for safety-critical decisions.

Docs: `docs/RATE_EPISODES_V052_EN.md`; detailed workflow artifact: `independent-multi-ros2-bag-evidence` from the linked Actions run.