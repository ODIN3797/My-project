# Public BAGEL MCAP compatibility assessment

**Status: format compatibility confirmed; diagnostic correctness NOT established.**

This is a third-party public MCAP sample, **not verified as a recording from a physical robot**. No independent fault ground truth or human validation is available for this sample.

## Provenance
- Upstream repository: https://github.com/Hussain004/BAGEL
- Pinned commit: `dc25e7ef395546bfbeea2ca07b71091fe70f5112`
- File: `public/sample-bags/tour.mcap`
- Input SHA-256: `1ee3a7b89700b35036f7eba33a5f7225d6a98ac313b4b9d5c106a9ffe337d1e1`

## Observed results (GitHub Actions, Python 3.12)

| Metric | Result |
|---|---:|
| Input size | 3,939,747 bytes |
| Topics | 18 |
| Messages | 3,057 |
| WARN/ERROR events from `/rosout` | 4 |
| Findings after recurrence fix | 1 (`OBSERVED_ERROR`) |
| Overall status | `REVIEW_REQUIRED` |

The remaining finding refers to a `/rosout` ERROR message concerning a docking beacon and odometry fallback. **A logged ERROR does not establish an actual equipment failure.**

The previous `RECURRING_ALERT` finding incorrectly grouped unrelated perception, battery and docking messages by the generic `ROS_LOG` code. We fixed this by grouping `ROS_LOG` messages using a normalized message signature, with numeric variation allowed, and added regression tests.

## Coverage limitations

- The recording has `/odom` but **no suitable command-velocity topic**, so the command-versus-odometry detector cannot be evaluated.
- **14 unsupported message types** had no payload inspection, including image, laser scan, battery, mapping and path messages.
- No ground-truth incident labels; precision, recall and false-positive rate **cannot be estimated**.
- The upstream sample's origin is not independently confirmed as physical recording.

## Reproduce
Run the pinned public-sample workflow at `.github/workflows/robot-incident-public-mcap.yml`. The uploaded Action artifact contains the HTML/JSON report and field validation summary.

## Follow-up
1. Obtain independently verified, authorized physical ROS2 recordings and known incident labels.
2. Compare detection findings with engineer-annotated event timelines.
3. Add selective sensor diagnostics after measuring demand and memory/cost constraints.
