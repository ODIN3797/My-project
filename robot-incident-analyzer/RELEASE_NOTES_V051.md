# v0.5.1 — Multi-bag baseline topic analysis

- New `compare-bags` command for comparing independent ROS2 DB3/MCAP recordings with an operator-selected reference.
- Rate normalization by per-topic recording times, adjustable thresholds and exclusion of missing or low-information topics.
- Standalone HTML/JSON/Markdown topic comparison, per-source SHA-256 hashes and topic-relative one-second rate sparklines.
- Streaming topic timestamp handling without loading message bodies and refusing silently truncated recordings.
- Independent evaluation with Zenodo normal and simulated attack recordings; University of Vigo multi-trial navigation bags collected separately by GitHub CI.
- Strong disclaimer: observations are not automatic diagnosis, publisher rates, actual equipment faults or calibrated precision/recall estimates.
