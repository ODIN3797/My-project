# v0.4.9 - Recorded robot state timeline

## New
- Parse **explicit** `mode=`, `docking_state=`, `charging_state=`, `safety_state=`, `phase=`, `navigation_state=` etc. from recorded ROS2 `/rosout` logs and CSV log messages. INFO log messages are only surfaced when they contain an explicit recognized assignment.
- Track changes with source and robot namespace isolation; do not merge two robots' states.
- Add a dedicated *Explicit state transitions* timeline and an evidence-linked contextual state-change summary for each incident within the preceding 30 seconds.
- Click a transition to synchronize the timeline cursor and scroll to its originating log event.
- Export raw transition evidence to `report.json`, and include state summaries in offline PDF investigations.
- Optional `state_keys` JSON configuration for vendor-specific labels such as `lift_state` (value matching is exact, not guessed).
- `demo-states` generates a **fully fictional** multi-sensor MCAP with explicit stage/mode logs, including a second robot to verify isolation.

## Verification
- 112 local unit tests passed with 15 new state tests, including fabricated MCAP data and offline PDF generation.
- HTML standalone JavaScript parsed without syntax errors; report includes 14 synthetic state observations; PDF generated locally.

## Limits
- Only explicit text assignments with known keys are interpreted; free-form messages or binary custom state messages are NOT inferred.
- Logged values are not verified robot actions. Recording-time order cannot prove causation. A state without a fresh observation must not be claimed to remain current.
- External real fault ground truth, precision/recall, and third-party engineer usability are not yet validated.
- This is a local offline research prototype, not safety-critical monitoring software.
