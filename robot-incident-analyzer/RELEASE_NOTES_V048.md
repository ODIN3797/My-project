# v0.4.8 Release notes

- Incident-centered, source-scoped multi-signal investigation, automatic signal relevance ranking and nearby event list.
- Selectable ±5/10/30 second windows; findings and event table link directly to incident workbench.
- Recorded odometry XY trajectory marks the selected event *only with a near-enough sample*.
- Optional vector PDF export with local ReportLab (`analyze --pdf`); browser Print / Save as PDF also provided.
- Independent ROS2 bag source separation and conservative robot namespace filters.
- Added 10 automated tests; 97 total passing on synthetic data; desktop/mobile headless Chromium interaction smoke checks.

**Not proven:** Actual robot root-cause diagnostic accuracy, long-term device reliability, external customer acceptance.
