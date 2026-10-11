# Product comparison: Robot Incident Analyzer v0.4.6

**As of October 11, 2026.** Public product descriptions, not hands-on comparative benchmarks or evidence of superiority.

| Product | Publicly described strengths | Gap relative to our prototype | What we implemented now |
|---|---|---|---|
| [Foxglove](https://docs.foxglove.dev/docs/visualization/panels/plot) | Time-synchronized flexible plots; multiple sensor/3D panels; workspace layouts; plot/transition linking | Our old SVG chart was static, standalone, and only velocity-focused | Incident count histogram with selectable time bins; linkable evidence and existing velocity traces preserved; no attempt to clone 3D or image playback |
| [Roboto](https://docs.roboto.ai/user-guides/visualize-ros.html) | Plot, log, raw, image, map panels; click a log to synchronize plots; multi-file visualization | Our finding list was disconnected from event inspection | Finding cards link directly to event records; search, severity and time-window filtering; timestamp-aligned incident markers retained |
| [bagx](https://github.com/rsasaki0109/bagx) | ROS bag readiness evaluations, timing, coverage, sensor sync and domain-specific checks, HTML report | Our topic timing table is hard to scan; no readiness benchmark | Visual topic-volume comparison and max/median recording-gap ratio; **not** a readiness score or sensor-fault verdict |
| [Insaion](https://www.insaion.com/platform/) | Robot fleet live dashboards, alarms, historical views, remote agent, event record buffers | We do not ship an always-on agent, live telemetry or fleet ops | Focus on offline per-incident evidence reports with no cloud upload; intentionally narrower scope |

## Usability changes shipped in v0.4.6

1. Left report navigation to Overview, Findings, Signals, Event log and Topic coverage.
2. Status overview with recorded events, error/fatal observations, generated findings and inspected ROS2 topic counts.
3. Keyboard-accessible stacked event density histogram (error/warn/info bins) that filters the log table when selected.
4. Investigation cards displaying explanation, caution about evidence status, checklists, and direct anchor links to underlying log events.
5. Incident table with severity quick filters, text search, selected time bin, and reset.
6. Source volume and topic volume horizontal visualizations; max-versus-median recording interval bars.
7. Retain command-velocity vs odometry plots and expandable anomaly windows when both signals are unambiguously available.
8. Self-contained offline HTML, mobile-responsive and printable, without remote stylesheets, fonts, or JS bundles.

## Explicitly not implemented / must not claim

- Interactive multi-signal synchronised playback/3D, arbitrary topic plotting, ROS transformations and camera image streams (Foxglove scope).
- AI/ML-based fault prediction or telemetry causal inference (Roboto/Insaion scope).
- Domain-certified ROS recording readiness score or accuracy benchmark against bagx.
- Actual overseas robotics engineer usability study, real incident ground-truth validation, commercial willingness-to-pay validation.

## Next experiments worth building **after** human testing

- Click an incident to show ±10 seconds of all supported traces sharing the same clock, with a draggable playhead.
- Topic sampling gap timeline (requires storing bounded timestamp segments, not just aggregate max gap).
- Pin/snapshot/share a redacted investigation case; require reviewing potentially sensitive logs before export.
- Evaluate first-run usability with 5 independent engineers, capture task completion time and click path, compare to their existing tool.

## Data interpretation safety

- Histogram x-axis spans **first to last recorded event**, not full input recording duration.
- Volume and gap-ratio bars are **counts/ratios**, not reliability scores. Burstiness or missing recordings can explain spikes.
- Position of events in time cannot establish causation; confirmed root cause requires independent diagnostics or ground truth.
- HTML table renders at most 2,000 events and findings render at most 30; full data remain in `report.json`.
