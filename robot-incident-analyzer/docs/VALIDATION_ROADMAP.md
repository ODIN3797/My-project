# Field validation roadmap

**Do not label v0.4.1 as field-validated or production-ready.**

1. Select 3 independently obtained, properly licensed/authorized bags: (A) healthy baseline, (B) known navigation failure, (C) known sensor/network issue. Preserve original checksums and ground-truth incident timestamps privately.
2. Record robot/model, ROS distribution, file format, compression, message types, clock source, and command pipeline without sharing secrets in public bug reports.
3. For each bag run `python3 -m robot_incident_analyzer analyze path/to/recording.mcap --output results/ID`.
4. Verify report's topic discovery before rating any `CMD_ODOM_MISMATCH`. Compare actual root cause and event timing manually with Foxglove, `ros2 bag info`, and ROS logs.
5. Label **TP / FP / FN / Not evaluable** separately for each incident rule and report false-positive rate and evidence completeness. Do not calculate accuracy when there is no independently labeled ground truth.
6. Time baseline debug (current workflow) and report-supported triage for five users; alternate task order to reduce learning bias.
7. Do not solicit or transfer confidential raw bags without express owner permission. Send only anonymized findings/timing/user opinions by default.

Potential independent-source starting points (NOT run in this environment):
- https://github.com/Hussain004/BAGEL/blob/main/public/sample-bags/tour.mcap (public independently created sample, not necessarily recorded hardware)
- https://jkk-research.github.io/dataset/jkk_dataset_02/ (public real-world robotics MCAP dataset; check license and size)
