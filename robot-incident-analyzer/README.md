# Robot Incident Analyzer v0.5.0 — State/Sensor Correlation Workbench

**Offline ROS2 incident triage, synchronized evidence charts, source-scoped odometry position markers, and optional local PDF export.**

This is an experimental diagnostic *aid*, not a validated root-cause detector. Time-aligned telemetry and nearby ROS logs are **not proof of causation**. It never uploads your recording to a server.

## v0.5.0 — Sensor readings before and after observed state changes

The **Incident workbench** now contrasts median numeric sensor values (velocity, battery, IMU, etc.) immediately before and after **explicitly logged** robot state changes. It uses two disjoint 2-second recording-time windows, requires at least two finite distinct samples per side and rejects stale windows. Findings show literal measurement summaries and separate state-vs-finding markers on the existing plots. Details are exported in `report.json` as `state_sensor_comparisons` and in the optional PDF dossier.

See [English investigation guide](docs/STATE_SENSOR_V050_EN.md), [Korean notes](docs/STATE_SENSOR_V050_KR.md), and [release notes](RELEASE_NOTES_V050.md). Observed shifts are descriptive **not causal fault diagnosis**; logs can misstate a robot's actual operating state.


## What's new

- **Incident Workbench:** Choose a finding or click an “Investigate” button from a finding or the event table; select ±5, ±10 or ±30 seconds of context.
- Automatically ranks relevant numeric signals (up to four visible plots) using the finding code and names of *decoded* numeric fields. It never infers that a nearby reading caused the incident.
- Groups nearby observations by the **recording source** and avoids blending clearly different `/robotX`, `/agvX`, and `/amrX` namespaces when the robot ID is known.
- Displays the **estimated event position** on an odometry XY path only if a sampled position is within two seconds of the event. This is not global/map ground truth.
- **PDF export:** the report contains a browser “Print / Save as PDF” action. CLI `analyze ... --pdf` creates `report.pdf` with a cover, evidence, charts and a path for each finding. The CLI PDF option requires the optional `reportlab` package.
- JSON + HTML remain available without third-party Python dependencies. All plots work offline without CDN or JavaScript libraries.

## Reproducible demo

```bash
python3 -m robot_incident_analyzer demo-studio --output studio_data
python3 -m robot_incident_analyzer analyze studio_data/fictional_signal_studio.mcap --output output
# output/report.html + output/report.json
xdg-open output/report.html
```

For a locally generated **PDF**:

```bash
python3 -m pip install '.[pdf]'    # or: python3 -m pip install reportlab
python3 -m robot_incident_analyzer analyze \
    studio_data/fictional_signal_studio.mcap --output output --pdf
# output/report.pdf
```

`--pdf` does not invoke a cloud service. If ReportLab is not installed, the HTML report's print control works with any browser offering “Save as PDF.”

## Known limits

- Standard XCDR1 and configured custom `.msg` types only; arbitrary vendor types and XCDR2 are not necessarily decoded.
- Signal previews are downsampled; nearest recorded samples are labeled and never interpolated as truth.
- Multi-robot source identification may be ambiguous if upstream logs omit robot identifiers and namespaces.
- Real physical robot incident precision and recall are **not measured**; synthetic tests are not a diagnostic accuracy benchmark.
- Up to 24 evidence-linked workbench cases (full results preserved in `report.json`); default bag read limit 200,000 messages.
- PDF export includes the first 20 cases and up to two signal charts per case; HTML offers richer interaction.

See [Incident Workbench guide](docs/INCIDENT_WORKBENCH_V048_EN.md).

---

# Robot Incident Analyzer v0.4.7 — Signal Studio

**ROS2 offline incident investigation and synchronized graphs (experimental alpha).**

## New in v0.4.7

- Choose from numeric scalar fields in supported CDR messages: Twist, Odometry, BatteryState, IMU and LaserScan.
- Plot explicitly provided custom `.msg` schema scalar fields, even without semantic command/odometry roles.
- Synchronized recording-time cursor shared across scalar, XY Odometry trajectory and existing velocity comparison charts.
- Click the timeline, path, speed plot or evidence link to focus on an observed time.
- Deterministically downsampled graph previews, with explicit limits and uncertainty labels.

**Fast offline demo (fictional MCAP):**

```bash
python3 -m robot_incident_analyzer demo-studio --output studio_data
python3 -m robot_incident_analyzer analyze studio_data/fictional_signal_studio.mcap --output studio_report
xdg-open studio_report/report.html
```

See [Signal Studio user guide](docs/SIGNAL_STUDIO_V047_EN.md) and [v0.4.7 release notes](RELEASE_NOTES_V047.md).

> **Limit:** No real physical robot ground-truth benchmark yet; recorded time alignment does not prove causality. This is not safety-critical diagnostic software.

---

# Robot Incident Analyzer — v0.4.5

**Offline ROS2 incident triage · MCAP/DB3 · standard and explicitly configured custom `.msg` schemas.**

Experimental MIT-licensed, Python 3.10+ tool for robotics engineers. It produces evidence-first HTML/JSON incident reports with topic discovery, velocity comparison, and timestamp-aligned anomaly markers. No cloud upload or AI API is required.

> **Research prototype / not safety-critical.** Automated test fixtures are synthetic. A public third-party MCAP sample has passed format-compatibility analysis, but it is NOT a confirmed physical robot field recording. The tool has NOT been validated on real robot fleet recordings or benchmarked for diagnosis precision. Rule-based alerts are observations and hypotheses, not confirmed root causes. Analyze only authorized data and authorized message schemas; respect employer/customer intellectual property and privacy restrictions.

## Quick start: built-in standard ROS2 messages

```bash
python3 -m robot_incident_analyzer demo --output demo_data
python3 -m robot_incident_analyzer analyze demo_data --output output
python3 -m unittest discover -s tests -v
```

Open `output/report.html` in a browser. Supported inputs: `.csv`, `.db3`, `.sqlite3` and `.mcap`, with the limitations listed below.

## New in v0.4.5: LaserScan quality observations

- `sensor_msgs/msg/LaserScan` XCDR1 decoding with bounded range/intensity counts.
- Report inconsistent metadata and 3+ consecutive all-NaN scans as **data-quality observations**, not confirmed sensor failures.
- ROS LaserScan `+inf` means no-return and is **not** automatically classified as an error.
- Synthetic scale measurements and limitations: [docs/V045_VALIDATION_KR.md](docs/V045_VALIDATION_KR.md).
- External alpha tester guide: [docs/ALPHA_PILOT_EN.md](docs/ALPHA_PILOT_EN.md).

## New in v0.4: custom ROS2 message analysis

If the bag uses vendor-specific `.msg` message types, you need authorized local **ROS2 `.msg` definitions** and a JSON field mapping. Do not assume the software can infer the operational meaning of a field from its name.

Example schema layout:

```text
examples/
  config_custom.json
  schemas/
    acme_robot_msgs/
      msg/
        DriveCommand.msg
        DriveFeedback.msg
        VelocityTarget.msg
```

`examples/config_custom.json`:

```json
{
  "schema_dirs": ["schemas"],
  "custom_messages": {
    "acme_robot_msgs/msg/DriveCommand": {
      "role": "command",
      "linear_x": "target.linear_x",
      "angular_z": "target.angular_z"
    },
    "acme_robot_msgs/msg/DriveFeedback": {
      "role": "odometry",
      "linear_x": "velocity_x",
      "position_x": "pos_x",
      "position_y": "pos_y"
    }
  },
  "topics": {
    "command": "/robot1/drive/input",
    "odometry": "/robot1/drive/feedback"
  }
}
```

Paths in `schema_dirs` are resolved relative to the JSON configuration file, *not* the current working directory. Topic overrides under `topics` are optional; omit them to use conservative type-and-name discovery. The values under `custom_messages` are required for custom type semantics.

Generate and analyze the synthetic custom-message demo:

```bash
python3 -m robot_incident_analyzer demo-custom --output demo_custom
python3 -m robot_incident_analyzer analyze \
  demo_custom/fictional_custom_telemetry.mcap \
  --config examples/config_custom.json \
  --output output_custom
```

Open `output_custom/report.html` and expand an anomaly-centered window to examine the velocity/feedback signals around an incident.

### Custom schema subset

Supported: ROS2 `.msg` field declarations with numeric/bool primitives, `string`, fixed arrays, bounded/unbounded sequences, and recursively nested `.msg` dependencies (such as `std_msgs/Header`), subject to resource limits. Canonical ROS type aliases `package/msg/Type` and `package/Type` are accepted. Basic `std_msgs/Header`, `builtin_interfaces/Time` and `builtin_interfaces/Duration` definitions are provided.

Unsupported: `.idl` files, arbitrary dynamic ROSIDL type discovery, DDS XCDR2, unions, action/service IDL, `wstring`, some advanced/bounded ROSIDL constructs, custom application framing, embedded MCAP schema auto-import, or arbitrary vendor wire encodings. The decoder currently supports the commonly used **XCDR1 CDR** encapsulation; this is NOT a general ROS2 serializer.

For custom odometry-like messages, `linear_x` is required while positions are optional. Without the position paths, no position jump check is performed (missing position is not silently treated as zero). All custom fields are explicitly mapped to known roles; no semantic inference from a message name. If decoding fails, the message is skipped, its count is shown in warnings, and statistics based on recording timestamps remain available.

## Browser interface

```bash
python3 -m robot_incident_analyzer gui --port 8765 --output output_gui
# For custom .msg files:
python3 -m robot_incident_analyzer gui --config examples/config_custom.json --port 8765
```

Open http://127.0.0.1:8765 and drag a file onto the upload area. Results and candidate topic mappings appear in the interface. The GUI binds **only to localhost** and supports one input at a time, with a default 50 MiB upload cap (configurable `--max-upload-mb`, max 200). This development server is NOT hardened for malicious or externally supplied bag files and MUST NOT be exposed to the internet.

## Visual incident review

The HTML report includes:

- Topic role auto-discovery with type compatibility checks and manual-mapping prompts.
- A command vs. feedback velocity plot, recording-time ticks, and WARN/ERROR timestamp markers with tooltips.
- Up to six expandable, anomaly-centered ±2.5-second charts; other events remain in the timeline and JSON.
- Evidence-linked incident findings, an event search filter and topic timing statistics.

**Important:** proximity of a marker to a speed anomaly is not a verified causal relationship. Sensor header stamps and clock offsets are not automatically reconciled. Velocity direction, frame choice, safety overrides and commanded vs executed control stream must be confirmed by the engineer.

## Compatibility and limits

- ROS2 standard supported CDR types include Twist, TwistStamped, Odometry, TFMessage, DiagnosticArray, BatteryState, Imu, LaserScan, and rcl_interfaces/Log.
- `.mcap` is readable natively for common `cdr` messages and uncompressed chunks. zstd chunks can use an installed `zstandard` package or compatible system `libzstd`; lz4 chunks require an optional `lz4` package or compatible `rosbags` integration. ROS1 bags and encrypted DB3 are not supported.
- Tests generate **fictional**, valid example DB3/MCAP message records. Recorded robot logs from real hardware are not used or included.
- `rosbags`, `zstandard`, and `lz4` are optional, not bundled. Install separately when needed. This environment has not verified an installed `rosbags` custom-schema reader.
- Resource caps: message count, schema size, array/sequence size and GUI upload size; nonetheless do not process untrusted logs without isolation.
- On multi-robot recordings, namespace inference and explicit mapping help prevent accidental cross-robot correlation; ambiguous candidates cause comparison to be skipped.

## Repository structure

- `robot_incident_analyzer/custom_messages.py` — `.msg` parser, bounded CDR decoder and explicit field mapping
- `robot_incident_analyzer/discovery.py` — topic role candidate matching
- `robot_incident_analyzer/telemetry.py` — standard/custom CDR decoding and detectors
- `robot_incident_analyzer/bag_reader.py` — DB3/MCAP raw readers
- `robot_incident_analyzer/report.py` — standalone offline HTML/JSON generation
- `robot_incident_analyzer/gui.py` — localhost-only web UI
- `robot_incident_analyzer/fixture_custom.py` — synthetic custom-message sample generator
- `examples/config_custom.json` and `examples/schemas/` — public fictional schema and configuration
- `tests/` — unit/integration tests

## Next engineering steps

1. Validate on licensed, independently recorded real-world ROS2 bags; measure false-positive rate and CPU/memory cost.
2. Consider ROSIDL `.idl` and MCAP embedded schema support through well-maintained libraries instead of expanding a full CDR parser indefinitely.
3. Gather early feedback from ROS2 engineers and verify which incident categories save them significant debugging time.

## v0.4.1 — pre-pilot engineering check (2026-10-11)

- 35 automated tests passed (28 baseline + 7 defensive/coverage tests).
- Linux Python 3.13 install and local GUI HTTP smoke tests passed.
- Synthetic 40k-message/15.68 MiB DB3 processed in about 0.45 seconds in one local run (not a field benchmark).
- Added NaN/Infinity time rejection, explicit per-robot namespace preservation in telemetry events, and coverage warnings for unsupported payload types.
- **No real externally recorded robot bag, overseas engineering participant, or paying customer has been validated.**
- See `docs/VALIDATION_REPORT_KR.md`, `docs/PILOT_GUIDE_EN.md`, and `docs/OUTREACH_EN.md` for next-stage evaluation.

## v0.4.2 — external field-validation runner (2026-10-11)

```bash
python3 -m robot_incident_analyzer field-validate \
  /path/to/your/recording.mcap \
  --origin unknown --output field_results

# Optional pre-annotated expected incidents for a specific recording:
python3 -m robot_incident_analyzer field-validate \
  /path/to/your/recording.mcap \
  --origin physical --labels /path/to/your/labels.csv \
  --output annotated_results
```

`FIELD_RESULTS.md` provides topic/payload coverage warnings and per-file results; `field_results.json` includes file SHA-256 digests, selected mappings, event counts and human-label matching results. Each recording gets its own `case_XX/report.html`. Exit code 3 means review required, not an installation failure. **A generated report does NOT establish ground-truth failure diagnosis**. The physical/simulation/unknown origin flag is self-declared; no field recording has been analyzed or independently checked as part of this release.

Details: [Overseas engineer field-pilot guide](docs/FIELD_PILOT_EN.md) and [한국어 검증 보고](docs/FIELD_VALIDATION_KR.md). Never publish unredacted customer or employer logs.


## v0.4.3 — external data readiness (2026-10-11)

- Includes system `libzstd` fallback for native zstd-compressed MCAP chunks when Python `zstandard` is not installed (requires OS shared library; Windows/macOS users may still need the Python package).
- Rejects corrupted MCAP chunk CRC and truncated/missing file trailer instead of silently reporting success.
- Added 5 independent synthetic MCAP structural/codec tests (51/51 passed in the v0.4.3 Linux environment).
- Provides `scripts/validate_local_real_bag.sh`, independent data acceptance checklists and reproducible execution guidance.
- **Actual externally recorded physical robot bag tested: 0; overseas engineers who ran the tool: 0.** A source URL is not a successful dataset download. Do not claim field accuracy based on this release.
- See `docs/EXTERNAL_RECORDING_ACCEPTANCE_KR.md` and `docs/EXTERNAL_RECORDING_ACCEPTANCE_EN.md`.


## v0.4.5 — standard battery and IMU inspection

- Bounded CDR decoding for `sensor_msgs/msg/BatteryState` and `sensor_msgs/msg/Imu`.
- Explicit BMS health errors trigger `BATTERY_HEALTH_ABNORMAL`; low charge alone never triggers a fault.
- The ROS2 `orientation_covariance[0] == -1` sentinel is honored; unavailable orientation is not flagged.
- 61 automated tests pass locally, including seven new CDR, DB3/MCAP and defensive regression tests.
- These heuristics still require review of the bag's provenance, message types and publisher behavior.

## Independent GitHub repository setup

See [docs/STANDALONE_GITHUB_SETUP.md](docs/STANDALONE_GITHUB_SETUP.md). The owner must create and authorize the independent repository before migration.

## v0.4.6 Visual incident dashboard

Generated `report.html` now includes an offline evidence-centric dashboard with:
stacked event histogram (click to filter the event table), severity/search filters, linked findings, preserved velocity traces, ROS2 topic count and recording gap visualizations. The design is responsive, and **no bag data is sent to the cloud**. See [competitor / feature analysis](docs/COMPETITOR_GAP_V046.md) and [release notes](RELEASE_NOTES_V046.md).


## v0.4.9 — Explicit robot state timeline

Inspect timestamped transitions extracted only from explicitly assigned keys such as `mode=AUTONOMOUS`, `docking_state=ALIGN` and `charging_state=FAILED`. The Incident Workbench summarizes source- and namespace-scoped state evidence from the previous 30 seconds. Raw transitions, with event IDs, appear in `report.json` and PDF.

```bash
python3 -m robot_incident_analyzer demo-states --output state_demo
python3 -m robot_incident_analyzer analyze state_demo/fictional_state_transitions.mcap --output state_report --pdf
```

Pass `--config examples/state_config.json` for custom explicit state keys, e.g. `lift_state`. This is a **log-text state observation**, not verification of controller state. See `docs/STATE_TIMELINE_V049_EN.md` and `RELEASE_NOTES_V049.md`.

## v0.5.1: compare independent ROS2 bag recordings

Use recorded reference/candidate topic rates to investigate changes in ROS2 message cadence without declaring a cause:

```bash
python3 -m robot_incident_analyzer compare-bags normal.db3 suspected.db3 \
  --output comparison_output --ratio-threshold 3
xdg-open comparison_output/comparison.html
```

The reference is **user-supplied, not independently certified healthy**. No universal rate alarm is emitted without a reference. Differences in task duration or configuration can explain rate changes. [Full guide](docs/MULTI_BAG_V051_EN.md).
