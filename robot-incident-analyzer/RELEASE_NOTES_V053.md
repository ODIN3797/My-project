# v0.5.3 — Evidence Annotation and Evaluation (2026-10-11)

- Added `init-rate-labels`: produces an **unreviewed** annotation template and offline one-second time-bin labeling HTML.
- Added `score-rate-labels`: performs conservative one-to-one matching between reviewed positive intervals and recorded message-rate episodes; reports labeled recall, time-binned detection delay, and false alarms per **explicitly reviewed negative hour**.
- Scoring rejects missing manual-review status, mismatched bag SHA256, topic/type mismatch, overlapping positive/negative labels, out-of-coverage timestamps, missing review data and partial histograms.
- Human annotation UI keeps existing tool predictions hidden by default, exports exact 64-bit Unix nanoseconds and sends no data online.
- Synthetic end-to-end fixture added, plus an **UNREVIEWED** template for the independent Zenodo 17649537 rate-timeline result. No field diagnostic accuracy claim.
- Documentation: `docs/LABEL_EVALUATION_V053_KR.md`.

Important: these are single-topic rate **change** evaluations. A publisher-described simulated attack does not create validated onset timestamps, precision, or real-robot-fault ground truth. No calibration of physical-fault sensitivity or saved engineer time was performed.
