# v0.5.0 — Sensor evidence around robot state changes

**Experimental offline ROS2 incident investigation, not root-cause proof.**

## Added

- State-transition-centered telemetry comparison, based only on explicit recorded `key=value` state observations.
- For up to **three distinct logged transition timestamps** preceding each finding, compare the median of **up to four numeric series** in **two disjoint 2-second time windows** (before and after the transition).
- Output raw comparison metadata: input topic and scalar field, before/after median, median delta, sample counts, gaps to transition, explicit transition evidence ID, source, and robot.
- Skip comparisons with fewer than two **distinct, finite timestamps** on either side or with a gap of more than one second to the transition.
- Incident workbench shows a comparison table and concise literal-value summary. Graphs show **teal state-time markers** separately from the **orange finding-time marker**.
- `report.json` now includes `state_sensor_comparisons`; offline PDF includes the first two transitions and two series each, with notice about truncation.
- New regression tests for outliers, NaN/Inf, duplicates, sparse samples, source/namespace isolation, JSON/HTML/PDF output, script safety and transition graph markers.

## Technical verification

- 124 Python tests passed (112 existing + 12 new).
- All five executable inline JavaScript scripts passed Node.js syntax checks.
- Synthetic multistream MCAP generated, inspected and rendered as HTML, JSON and PDF.
- GitHub Actions results are reported separately from local tests; no unrun CI is claimed.

## Limitations

- Correlation is by **recording timestamp**, not verified sensor measurement time or causality.
- Before/after medians are descriptive, **not statistically significant effects** or learned anomaly scores.
- Values come from existing bounded/downsampled decoded telemetry, not an exhaustive raw-bag analysis.
- Missing, unsupported, sparse, stale and ambiguous channels yield "insufficient samples"; missing detections never prove health.
- Current ROS2 data parser and AI-free heuristics do **not** establish hardware/driver/software root cause.
- Public sample format compatibility is not verified physical robot fault diagnosis. Independent field labels and human usability evidence are still unavailable.
