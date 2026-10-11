# Robot Incident Analyzer — v0.4.4

**Offline ROS2 incident triage · MCAP/DB3 · standard and explicitly configured custom `.msg` schemas.**

Experimental MIT-licensed, Python 3.10+ tool for robotics engineers. It produces evidence-first HTML/JSON incident reports with topic discovery, velocity comparison, and timestamp-aligned anomaly markers. No cloud upload or AI API is required.

> **Research prototype / not safety-critical.** Tests use synthetic ROS2 CDR bags only. It has NOT been validated on real robot fleet recordings or benchmarked for diagnosis precision. Rule-based alerts are observations and hypotheses, not confirmed root causes. Analyze only authorized data and authorized message schemas; respect employer/customer intellectual property and privacy restrictions.

## Quick start: built-in standard ROS2 messages

```bash
python3 -m robot_incident_analyzer demo --output demo_data
python3 -m robot_incident_analyzer analyze demo_data --output output
python3 -m unittest discover -s tests -v
```

Open `output/report.html` in a browser. Supported inputs: `.csv`, `.db3`, `.sqlite3` and `.mcap`, with the limitations listed below.

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

- ROS2 standard supported CDR types include Twist, TwistStamped, Odometry, TFMessage, DiagnosticArray, and rcl_interfaces/Log.
- `.mcap` is readable natively for common `cdr` messages and uncompressed chunks. zstd/lz4 chunks require optional `zstandard`/`lz4` dependencies or compatible `rosbags` integration. ROS1 bags and encrypted DB3 are not supported.
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


## v0.4.4 — external data readiness (2026-10-11)

- Includes system `libzstd` fallback for native zstd-compressed MCAP chunks when Python `zstandard` is not installed (requires OS shared library; Windows/macOS users may still need the Python package).
- Rejects corrupted MCAP chunk CRC and truncated/missing file trailer instead of silently reporting success.
- Adds 5 independent synthetic MCAP structural/codec tests (51/51 tests pass in the recorded Linux environment).
- Provides `scripts/validate_local_real_bag.sh`, independent data acceptance checklists and reproducible execution guidance.
- **Actual externally recorded physical robot bag tested: 0; overseas engineers who ran the tool: 0.** A source URL is not a successful dataset download. Do not claim field accuracy based on this release.
- See `docs/EXTERNAL_RECORDING_ACCEPTANCE_KR.md` and `docs/EXTERNAL_RECORDING_ACCEPTANCE_EN.md`.


## v0.4.4 — standard battery and IMU inspection

- Bounded CDR decoding for `sensor_msgs/msg/BatteryState` and `sensor_msgs/msg/Imu`.
- Explicit BMS health errors trigger `BATTERY_HEALTH_ABNORMAL`; low charge alone never triggers a fault.
- The ROS2 `orientation_covariance[0] == -1` sentinel is honored; unavailable orientation is not flagged.
- These heuristics still require review of the bag's provenance, message types and publisher behavior.
