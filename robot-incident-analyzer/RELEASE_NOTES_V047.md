# v0.4.7 — Synchronized Signal Studio

**Added**
- Interactive finite scalar plot selector for supported standard ROS2 CDR types and authorized custom `.msg` schemas, without guessing unsupported layouts.
- Shared recorded-time cursor across the selected numeric plot, odometry XY path and existing command/feedback speed comparison.
- Clickable trajectory and speed plot to position the cursor, and timeline-bin/finding-evidence integration.
- Bounded deterministic sampling, per-odometry-frame trajectory separation, safe embedded JSON escaping.
- New fictional multi-sensor MCAP (`demo-studio`) and 9 regression tests.

**Validated**
- 87 local unit/integration tests passed.
- Chromium headless on desktop (1440px) and mobile (390px): 15 numeric signal choices, rendered trajectory, linked marker, zero JS errors and no horizontal overflow, using synthetic MCAP.
- GitHub CI status is documented separately once the pushed changes complete.

**Not validated**
- Ground-truth fault detection precision/recall, real robot calibration, actual ROS2 driver data completeness or external engineer uptake. No superiority claim against Foxglove/Roboto/bagx.
