# Public MCAP sample — v0.4.4 compatibility assessment

**PASS: file parsing / report generation. NOT VERIFIED: physical robot provenance, incident correctness, or commercially useful diagnosis.**

## Reproducible input

- Upstream public repo: https://github.com/Hussain004/BAGEL
- Pinned revision: `dc25e7ef395546bfbeea2ca07b71091fe70f5112`
- File: `public/sample-bags/tour.mcap`
- Input SHA-256: `1ee3a7b89700b35036f7eba33a5f7225d6a98ac313b4b9d5c106a9ffe337d1e1`
- Source origin: **unknown** (physical-world provenance not independently confirmed)

## GitHub Actions observations

| Item | Result |
|---|---|
| File size | 3,939,747 bytes |
| Topic names | 18 |
| Recorded messages | 3,057 |
| `/rosout` WARN/ERROR observations | 4 |
| Findings | 1 × `OBSERVED_ERROR` (not a confirmed failure) |
| Status | `REVIEW_REQUIRED` |
| Unsupported payload message types | **12**, down from **14** in v0.4.3 |
| Diagnostics requiring a command velocity source | Not evaluated — no compatible command topic |
| Ground truth or human-annotated faults | None |

v0.4.4 added `sensor_msgs/msg/BatteryState` and `sensor_msgs/msg/Imu` decoders. This **reduces the number of uninspected types**, but it does *not* establish incident recall or a measured improvement in debugging time. There were no new abnormal battery health or IMU quaternion events in the sample under the configured checks.

In v0.4.3 we fixed a false repeated-alert issue by not grouping unrelated `/rosout` warning texts solely under generic `ROS_LOG`.

## Remaining limitations

- No truth labels: false-positive rate, precision and recall cannot be measured.
- `LaserScan`, `PointCloud2`, image and mapping/navigation payloads are not interpreted yet (some can have recording-time topic-gap checks).
- The observed log error is only proof a publisher logged an error, not that the hardware failed.
- This public sample must not be referred to as a verified physical or deployed robot field recording.
- 61 automated tests use **synthetic** data and validate software behavior rather than real-world diagnostic accuracy.

## Reproduction

In the standalone GitHub repository, the file `.github/workflows/public-mcap.yml` downloads this pinned MCAP and generates an artifact with `field_results.json` and the HTML report.
