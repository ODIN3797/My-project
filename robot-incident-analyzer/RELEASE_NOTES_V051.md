# v0.5.1 — Multi-bag baseline topic analysis

- New `compare-bags` command for comparing independent ROS2 DB3/MCAP recordings with an operator-selected reference.
- Rate normalization by per-topic recording times, adjustable thresholds and exclusion of missing or low-information topics.
- Standalone HTML/JSON/Markdown topic comparison, per-source SHA-256 hashes and topic-relative one-second rate sparklines.
- Streaming topic timestamp handling without loading message bodies and refusing silently truncated recordings.
- Independent evaluation with Zenodo normal and simulated attack recordings; University of Vigo multi-trial navigation bags collected separately by GitHub CI.
- Strong disclaimer: observations are not automatic diagnosis, publisher rates, actual equipment faults or calibrated precision/recall estimates.

### Independent dataset results verified on GitHub Actions

- **12/12** publicly published recordings summarized and analyzed (Zenodo 2, Vigo 9, BAGEL sample MCAP 1).
- Publisher-labeled simulated attack recording: observed downstream `/mobile_base_controller/cmd_vel` average reception frequency **19.85Hz → 165.19Hz (8.32×)** against the normal baseline; automatically flagged as reference-relative `RATE_INCREASE`.
- Vigo: 9 navigation recordings, 8 baseline-relative comparisons, **0 topic rates >3×** under selected settings. Across 9 rule-based field-analysis runs, **24 unverified event candidates** including 19 ROS log messages and 3 odometry jump candidates.
- Semantic discovery correction: `/rpsc4/global_position/raw/gps_vel` is a GPS measurement, **not an actuation command**; auto-mapping it was blocked and validated against all Vigo recordings.
- **134 Python unit tests passed**, GitHub Actions Python 3.10–3.13 and the independent bag evaluation succeeded.
- No ground-truth fault diagnosis, false-positive/false-negative rates, or paid customer study yet.
